"""Schema tests for the topic flow models.

These models carry no behavior yet — the editor and the public page arrive
in later stages. What is worth pinning now is the shape later stages will
build on: two app-wide pools (the variable glossary and the form library)
that flows only compose, the constraints that keep conditions coherent,
and the delete rules that decide what a flow can and cannot take with it.
"""

import pytest
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from litigant_portal.app.models import (
    Form,
    FormField,
    Topic,
    TopicFlow,
    TopicFlowDeadline,
    TopicFlowFormCondition,
    TopicFlowInterviewPage,
    TopicFlowInterviewVariable,
    TopicFlowLink,
    TopicFlowSection,
    UserIdentity,
    Variable,
    VariableAnswer,
)
from litigant_portal.app.models.choices import (
    TopicFlowFormConditionOperator,
    VariableDataType,
)


def build_flow(slug="tenant"):
    topic = Topic.objects.create(slug=f"{slug}-topic", title="Eviction")
    return TopicFlow.objects.create(topic=topic, slug=slug, name="Tenant")


def build_form(slug="answer"):
    return Form.objects.create(slug=slug, name="Answer", file="f.pdf")


@pytest.mark.postgres
class TopicFlowTests(TestCase):
    def test_slug_is_unique_per_topic_not_globally(self):
        first = build_flow()
        other_topic = Topic.objects.create(slug="other", title="Other")
        # Same slug under a different topic is fine.
        TopicFlow.objects.create(
            topic=other_topic, slug=first.slug, name="Tenant"
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            TopicFlow.objects.create(
                topic=first.topic, slug=first.slug, name="Clash"
            )

    def test_flows_are_disabled_until_switched_on(self):
        self.assertFalse(build_flow().enabled)

    def test_deleting_a_topic_takes_its_flows(self):
        flow = build_flow()
        flow.topic.delete()
        self.assertFalse(TopicFlow.objects.filter(pk=flow.pk).exists())


@pytest.mark.postgres
class GlossaryTests(TestCase):
    def test_name_is_unique_app_wide(self):
        # The inversion of the old per-flow field constraint: a variable is
        # named once for the whole app, so an answer given in one topic can
        # prefill every other topic that needs the same fact.
        Variable.objects.create(name="notice_date")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Variable.objects.create(name="notice_date")

    def test_variables_default_to_scoped_text(self):
        variable = Variable.objects.create(name="county")
        self.assertEqual(variable.data_type, VariableDataType.TEXT)
        self.assertFalse(variable.is_global)

    def test_a_gate_value_requires_a_gate(self):
        # asked_when_value is meaningless without asked_when; the check
        # constraint keeps a half-written gate from silently meaning
        # "always askable".
        with self.assertRaises(IntegrityError), transaction.atomic():
            Variable.objects.create(name="was_felony", asked_when_value=True)

    def test_gating_chains_are_expressible(self):
        gate = Variable.objects.create(
            name="has_conviction", data_type=VariableDataType.BOOLEAN
        )
        gated = Variable.objects.create(
            name="was_felony",
            data_type=VariableDataType.BOOLEAN,
            asked_when=gate,
            asked_when_value=True,
        )
        self.assertEqual(list(gate.gated_variables.all()), [gated])

    def test_deleting_a_gate_with_dependents_is_blocked(self):
        # PROTECT: removing has_conviction must not silently cascade away
        # was_felony; the author has to untangle the chain deliberately.
        gate = Variable.objects.create(name="has_conviction")
        Variable.objects.create(
            name="was_felony", asked_when=gate, asked_when_value=True
        )
        with self.assertRaises(ProtectedError):
            gate.delete()


@pytest.mark.postgres
class AnswerTests(TestCase):
    def setUp(self):
        self.variable = Variable.objects.create(name="county")
        self.identity = UserIdentity.objects.create(session_key="abc123")

    def test_one_answer_per_identity_per_variable(self):
        VariableAnswer.objects.create(
            identity=self.identity, variable=self.variable, value="Cass"
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            VariableAnswer.objects.create(
                identity=self.identity, variable=self.variable, value="Ward"
            )

    def test_two_identities_may_answer_the_same_variable(self):
        other = UserIdentity.objects.create(session_key="def456")
        VariableAnswer.objects.create(
            identity=self.identity, variable=self.variable, value="Cass"
        )
        VariableAnswer.objects.create(
            identity=other, variable=self.variable, value="Ward"
        )
        self.assertEqual(VariableAnswer.objects.count(), 2)

    def test_deleting_a_variable_discards_stored_answers(self):
        # Intentional, and the reason the library importer must match
        # variables by name on re-import rather than replacing them
        # wholesale. Only holds for a variable nothing else references:
        # conditions and deadlines PROTECT theirs.
        VariableAnswer.objects.create(
            identity=self.identity, variable=self.variable, value="Cass"
        )
        self.variable.delete()
        self.assertEqual(VariableAnswer.objects.count(), 0)

    def test_answers_start_unreviewed(self):
        answer = VariableAnswer.objects.create(
            identity=self.identity, variable=self.variable, value="Cass"
        )
        self.assertFalse(answer.reviewed)


@pytest.mark.postgres
class FormTests(TestCase):
    def test_slug_is_unique_app_wide(self):
        # The inversion of the old per-flow constraint: a form is a shared
        # asset, so one fee-waiver form can serve every flow that needs it
        # instead of each flow carrying a copy.
        build_form()
        with self.assertRaises(IntegrityError), transaction.atomic():
            build_form()

    def test_deleting_a_form_takes_its_fields(self):
        form = build_form()
        FormField.objects.create(form=form, pdf_field="Field1")

        form.delete()
        self.assertEqual(FormField.objects.count(), 0)

    def test_duplicate_orders_fall_back_to_creation_order(self):
        # order is a display hint, not an invariant: ties never raise, they
        # resolve by created_at, so a fill order written out of band stays
        # deterministic.
        form = build_form()
        FormField.objects.create(form=form, pdf_field="a", order=0)
        FormField.objects.create(form=form, pdf_field="b", order=0)
        self.assertEqual([f.pdf_field for f in form.fields.all()], ["a", "b"])


@pytest.mark.postgres
class FormConditionTests(TestCase):
    def setUp(self):
        self.flow = build_flow()
        self.form = build_form()

    def test_no_variable_means_always_in_the_packet(self):
        condition = TopicFlowFormCondition.objects.create(
            flow=self.flow, form=self.form
        )
        self.assertIsNone(condition.variable)
        self.assertEqual(
            condition.operator, TopicFlowFormConditionOperator.EQUALS
        )

    def test_a_value_requires_a_variable(self):
        # The check constraint keeps a condition from carrying a value with
        # nothing to compare it against, which would read as conditional
        # while behaving as unconditional.
        with self.assertRaises(IntegrityError), transaction.atomic():
            TopicFlowFormCondition.objects.create(
                flow=self.flow, form=self.form, value=True
            )

    def test_repeat_rows_for_the_same_pair_are_allowed(self):
        # Deliberate: one condition per row, and a form more than one
        # answer can pull in gets one row per answer, OR'd together. No
        # unique constraint on (flow, form).
        fee = Variable.objects.create(name="can_pay_filing_fee")
        served = Variable.objects.create(name="received_court_papers")
        TopicFlowFormCondition.objects.create(
            flow=self.flow, form=self.form, variable=fee, value=False
        )
        TopicFlowFormCondition.objects.create(
            flow=self.flow, form=self.form, variable=served, value=True
        )
        self.assertEqual(self.flow.form_conditions.count(), 2)

    def test_deleting_a_conditioning_variable_is_blocked(self):
        # PROTECT: deleting a variable that decides packet membership would
        # silently change what litigants are told to file.
        variable = Variable.objects.create(name="has_conviction")
        TopicFlowFormCondition.objects.create(
            flow=self.flow, form=self.form, variable=variable, value=True
        )
        with self.assertRaises(ProtectedError):
            variable.delete()

    def test_a_shared_form_survives_losing_one_flow(self):
        # The reuse story: two flows compose the same form through their
        # own condition rows, and deleting one flow takes only its row.
        other = build_flow("landlord")
        TopicFlowFormCondition.objects.create(flow=self.flow, form=self.form)
        keep = TopicFlowFormCondition.objects.create(
            flow=other, form=self.form
        )

        self.flow.delete()
        self.assertTrue(Form.objects.filter(pk=self.form.pk).exists())
        self.assertEqual(list(TopicFlowFormCondition.objects.all()), [keep])


@pytest.mark.postgres
class InterviewTests(TestCase):
    def setUp(self):
        self.flow = build_flow()

    def place(self, page, name, order=0):
        variable = Variable.objects.create(name=name)
        return TopicFlowInterviewVariable.objects.create(
            page=page, variable=variable, order=order
        )

    def test_page_and_placement_order_compose_into_interview_order(self):
        # Two Meta.ordering declarations compose into the order a litigant
        # is asked things in: pages by order, then placements by order
        # within each page. The docassemble exporter will lean on this.
        first = TopicFlowInterviewPage.objects.create(
            flow=self.flow, title="Your notice", order=0
        )
        second = TopicFlowInterviewPage.objects.create(
            flow=self.flow, title="Your case", order=1
        )
        self.place(second, "county", order=0)
        self.place(first, "landlord", order=1)
        self.place(first, "notice_date", order=0)

        ordered = [
            placement.variable.name
            for page in self.flow.interview_pages.all()
            for placement in page.variables.all()
        ]
        self.assertEqual(ordered, ["notice_date", "landlord", "county"])

    def test_a_variable_sits_on_a_page_at_most_once(self):
        page = TopicFlowInterviewPage.objects.create(flow=self.flow)
        placement = self.place(page, "county")
        with self.assertRaises(IntegrityError), transaction.atomic():
            TopicFlowInterviewVariable.objects.create(
                page=page, variable=placement.variable
            )

    def test_one_variable_may_appear_across_flows(self):
        # Nothing scopes a glossary variable to a flow, so each flow's
        # interview places the same variable on its own pages. Per-flow
        # single placement is an authoring concern, not a schema one.
        variable = Variable.objects.create(name="county")
        for flow in (self.flow, build_flow("landlord")):
            TopicFlowInterviewVariable.objects.create(
                page=TopicFlowInterviewPage.objects.create(flow=flow),
                variable=variable,
            )
        self.assertEqual(variable.interview_placements.count(), 2)

    def test_placements_are_cosmetic_and_die_with_the_variable(self):
        # Unlike conditions and deadlines, paging never PROTECTs: losing a
        # placement changes presentation, not what anyone is told to file.
        page = TopicFlowInterviewPage.objects.create(flow=self.flow)
        placement = self.place(page, "county")
        placement.variable.delete()
        self.assertEqual(TopicFlowInterviewVariable.objects.count(), 0)


@pytest.mark.postgres
class FlowContentTests(TestCase):
    """Sections and links hang off the flow in display order."""

    def setUp(self):
        self.flow = build_flow()

    def test_ordered_children_come_back_in_order(self):
        for model, kwargs in (
            (TopicFlowSection, {"heading": "h"}),
            (TopicFlowLink, {"name": "n", "url": "https://example.test"}),
        ):
            with self.subTest(model=model.__name__):
                model.objects.create(flow=self.flow, order=1, **kwargs)
                model.objects.create(flow=self.flow, order=0, **kwargs)
                orders = [
                    row.order for row in model.objects.filter(flow=self.flow)
                ]
                self.assertEqual(orders, [0, 1])

    def test_a_deadline_protects_its_variable(self):
        # The inversion of the old cascade: a deadline's anchor is a shared
        # glossary variable now, and deleting it would silently change the
        # dates litigants are shown. The deadline itself still dies with
        # its flow.
        variable = Variable.objects.create(
            name="notice_date", data_type=VariableDataType.DATE
        )
        TopicFlowDeadline.objects.create(
            flow=self.flow,
            label="Answer due",
            offset_days=7,
            offset_from=variable,
        )
        with self.assertRaises(ProtectedError):
            variable.delete()


@pytest.mark.postgres
class FlowDeletionTests(TestCase):
    def test_deleting_a_flow_takes_its_composition_and_spares_the_pools(self):
        # Deleting a flow is the destructive action the admin editor will
        # actually offer. It must reach everything the flow composed:
        # sections, links, deadlines, condition rows, and interview pages
        # with their placements. It must NOT reach the shared pools the
        # composition points at: the glossary, its answers, and the forms.
        # PROTECT on conditions and deadlines blocks deleting a variable,
        # never deleting the flow whose rows reference it.
        flow = build_flow()
        TopicFlowSection.objects.create(flow=flow, heading="h")
        TopicFlowLink.objects.create(
            flow=flow, name="n", url="https://example.test"
        )
        variable = Variable.objects.create(
            name="notice_date", data_type=VariableDataType.DATE
        )
        identity = UserIdentity.objects.create(session_key="abc123")
        VariableAnswer.objects.create(
            identity=identity, variable=variable, value="2026-08-01"
        )
        form = build_form()
        FormField.objects.create(form=form, pdf_field="Field1")
        TopicFlowFormCondition.objects.create(
            flow=flow, form=form, variable=variable, value=True
        )
        TopicFlowDeadline.objects.create(
            flow=flow, label="Answer due", offset_days=7, offset_from=variable
        )
        page = TopicFlowInterviewPage.objects.create(flow=flow)
        TopicFlowInterviewVariable.objects.create(page=page, variable=variable)

        flow.delete()

        for model in (
            TopicFlowSection,
            TopicFlowLink,
            TopicFlowDeadline,
            TopicFlowFormCondition,
            TopicFlowInterviewPage,
            TopicFlowInterviewVariable,
        ):
            with self.subTest(model=model.__name__):
                self.assertEqual(model.objects.count(), 0)
        for model in (Variable, VariableAnswer, Form, FormField):
            with self.subTest(model=model.__name__):
                self.assertEqual(model.objects.count(), 1)
        self.assertTrue(Topic.objects.exists())
        self.assertTrue(UserIdentity.objects.exists())
