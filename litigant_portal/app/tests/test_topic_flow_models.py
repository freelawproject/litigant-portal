"""Schema tests for the topic flow models.

These models carry no behavior yet — the editor and the public page arrive
in later stages. What is worth pinning now is the shape later stages will
build on: the constraints, the cascade rules, and the ordering that decides
what a litigant sees first.
"""

import pytest
from django.db import IntegrityError, connection, transaction
from django.test import TestCase

from litigant_portal.app.models import (
    Topic,
    TopicFlow,
    TopicFlowAnswer,
    TopicFlowDeadline,
    TopicFlowField,
    TopicFlowFieldGroup,
    TopicFlowForm,
    TopicFlowFormField,
    TopicFlowLink,
    TopicFlowSection,
    UserIdentity,
)


def build_flow(slug="tenant"):
    topic = Topic.objects.create(slug=f"{slug}-topic", title="Eviction")
    return TopicFlow.objects.create(topic=topic, slug=slug, name="Tenant")


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
class InterviewFieldTests(TestCase):
    def setUp(self):
        self.flow = build_flow()
        self.group = TopicFlowFieldGroup.objects.create(
            flow=self.flow, title="Your notice", order=0
        )

    def test_group_and_field_order_compose_into_interview_order(self):
        second = TopicFlowFieldGroup.objects.create(
            flow=self.flow, title="Your case", order=1
        )
        TopicFlowField.objects.create(group=second, name="county", order=0)
        TopicFlowField.objects.create(
            group=self.group, name="landlord", order=1
        )
        TopicFlowField.objects.create(
            group=self.group, name="notice_date", order=0
        )

        # Two Meta.ordering declarations compose into the order a litigant
        # is asked things in: groups by order, then fields by order within
        # each group. The selector that assembles an interview will lean on
        # this, so it is worth pinning before that selector exists.
        ordered = [
            field.name
            for group in self.flow.field_groups.all()
            for field in group.fields.all()
        ]
        self.assertEqual(ordered, ["notice_date", "landlord", "county"])

    def test_two_fields_cannot_share_an_order_within_a_group(self):
        TopicFlowField.objects.create(group=self.group, name="a", order=0)
        # The constraint is DEFERRED, so the database only checks it at
        # COMMIT — and TestCase wraps each test in a transaction that never
        # commits. check_constraints() forces the check that a real request's
        # autocommit would have triggered.
        with self.assertRaises(IntegrityError), transaction.atomic():
            TopicFlowField.objects.create(group=self.group, name="b", order=0)
            connection.check_constraints()

    def test_the_order_constraint_defers_so_a_swap_can_pass_through_a_clash(
        self,
    ):
        first = TopicFlowField.objects.create(
            group=self.group, name="a", order=0
        )
        second = TopicFlowField.objects.create(
            group=self.group, name="b", order=1
        )

        # Reordering renumbers rows one at a time, so the table is briefly
        # in a state the constraint forbids. DEFERRED is what lets that work
        # without a temporary sentinel value.
        with transaction.atomic():
            first.order, second.order = 1, 0
            first.save(update_fields=["order"])
            second.save(update_fields=["order"])

        self.assertEqual([f.name for f in self.group.fields.all()], ["b", "a"])

    def test_fields_default_to_text(self):
        field = TopicFlowField.objects.create(group=self.group, name="a")
        self.assertEqual(field.data_type, TopicFlowField.DataType.TEXT)


@pytest.mark.postgres
class FlowContentTests(TestCase):
    """Sections, links and deadlines all hang off the flow in display order."""

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

    def test_a_deadline_hangs_off_a_field_and_dies_with_it(self):
        group = TopicFlowFieldGroup.objects.create(flow=self.flow)
        field = TopicFlowField.objects.create(
            group=group, name="notice_date", data_type="date"
        )
        deadline = TopicFlowDeadline.objects.create(
            flow=self.flow,
            label="Answer due",
            offset_days=7,
            offset_from=field,
        )

        field.delete()
        self.assertFalse(
            TopicFlowDeadline.objects.filter(pk=deadline.pk).exists()
        )


@pytest.mark.postgres
class FormMappingTests(TestCase):
    def setUp(self):
        self.flow = build_flow()

    def test_form_slug_is_unique_per_flow(self):
        TopicFlowForm.objects.create(
            flow=self.flow, slug="answer", name="Answer", file="f.pdf"
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            TopicFlowForm.objects.create(
                flow=self.flow, slug="answer", name="Clash", file="g.pdf"
            )

    def test_deleting_a_form_takes_its_mappings(self):
        form = TopicFlowForm.objects.create(
            flow=self.flow, slug="answer", name="Answer", file="f.pdf"
        )
        TopicFlowFormField.objects.create(form=form, pdf_field="Field1")

        form.delete()
        self.assertEqual(TopicFlowFormField.objects.count(), 0)


@pytest.mark.postgres
class AnswerTests(TestCase):
    def setUp(self):
        self.flow = build_flow()
        group = TopicFlowFieldGroup.objects.create(flow=self.flow)
        self.field = TopicFlowField.objects.create(group=group, name="county")
        self.identity = UserIdentity.objects.create(session_key="abc123")

    def test_one_answer_per_identity_per_field(self):
        TopicFlowAnswer.objects.create(
            identity=self.identity, field=self.field, value="Cass"
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            TopicFlowAnswer.objects.create(
                identity=self.identity, field=self.field, value="Ward"
            )

    def test_two_identities_may_answer_the_same_field(self):
        other = UserIdentity.objects.create(session_key="def456")
        TopicFlowAnswer.objects.create(
            identity=self.identity, field=self.field, value="Cass"
        )
        TopicFlowAnswer.objects.create(
            identity=other, field=self.field, value="Ward"
        )
        self.assertEqual(TopicFlowAnswer.objects.count(), 2)

    def test_deleting_a_field_discards_stored_answers(self):
        # Intentional, and the reason the library importer matches fields by
        # name on re-import rather than replacing them wholesale.
        TopicFlowAnswer.objects.create(
            identity=self.identity, field=self.field, value="Cass"
        )
        self.field.delete()
        self.assertEqual(TopicFlowAnswer.objects.count(), 0)

    def test_answers_start_unreviewed(self):
        answer = TopicFlowAnswer.objects.create(
            identity=self.identity, field=self.field, value="Cass"
        )
        self.assertFalse(answer.reviewed)
