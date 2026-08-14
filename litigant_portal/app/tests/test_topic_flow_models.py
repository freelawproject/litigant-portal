"""Schema tests for the topic flow models.

These models carry no behavior yet — the editor and the public page arrive
in later stages. What is worth pinning now is the shape later stages will
build on: the constraints, the cascade rules, and the ordering that decides
what a litigant sees first.
"""

import pytest
from django.db import IntegrityError, transaction
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

    def field(self, name, **kwargs):
        kwargs.setdefault("group", self.group)
        return TopicFlowField.objects.create(
            flow=self.flow, name=name, **kwargs
        )

    def test_group_and_field_order_compose_into_interview_order(self):
        second = TopicFlowFieldGroup.objects.create(
            flow=self.flow, title="Your case", order=1
        )
        self.field("county", group=second, order=0)
        self.field("landlord", order=1)
        self.field("notice_date", order=0)

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

    def test_name_is_unique_per_flow_not_per_group(self):
        # Same name under a different flow is fine.
        other = build_flow("landlord")
        TopicFlowField.objects.create(
            flow=other,
            group=TopicFlowFieldGroup.objects.create(flow=other),
            name="notice_date",
        )
        self.field("notice_date")

        # The constraint reaches across groups: the same name on another
        # page of the same interview is still a clash. Answers and library
        # re-imports both identify a field by name within its flow.
        second = TopicFlowFieldGroup.objects.create(flow=self.flow, order=1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.field("notice_date", group=second)

    def test_duplicate_orders_fall_back_to_creation_order(self):
        # order is a display hint, not an invariant: ties never raise, they
        # resolve by created_at, and the move services renumber siblings
        # densely, so a list written out of band self-heals on first move.
        self.field("a", order=0)
        self.field("b", order=0)
        self.assertEqual([f.name for f in self.group.fields.all()], ["a", "b"])

    def test_fields_default_to_text(self):
        self.assertEqual(
            self.field("a").data_type, TopicFlowField.DataType.TEXT
        )


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
            flow=self.flow, group=group, name="notice_date", data_type="date"
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
class FlowDeletionTests(TestCase):
    def test_deleting_a_flow_takes_all_eight_collections(self):
        # Deleting a flow is the destructive action the admin editor will
        # actually offer, and it must reach every depth: five collections
        # hang off the flow directly, fields also arrive through their
        # group (a diamond the delete collector must resolve), answers
        # through fields, and mappings through forms.
        flow = build_flow()
        TopicFlowSection.objects.create(flow=flow, heading="h")
        TopicFlowLink.objects.create(
            flow=flow, name="n", url="https://example.test"
        )
        group = TopicFlowFieldGroup.objects.create(flow=flow)
        field = TopicFlowField.objects.create(
            flow=flow, group=group, name="notice_date"
        )
        TopicFlowDeadline.objects.create(
            flow=flow, label="Answer due", offset_days=7, offset_from=field
        )
        identity = UserIdentity.objects.create(session_key="abc123")
        TopicFlowAnswer.objects.create(
            identity=identity, field=field, value="x"
        )
        form = TopicFlowForm.objects.create(
            flow=flow, slug="answer", name="Answer", file="f.pdf"
        )
        TopicFlowFormField.objects.create(form=form, pdf_field="Field1")

        flow.delete()

        for model in (
            TopicFlowSection,
            TopicFlowLink,
            TopicFlowFieldGroup,
            TopicFlowField,
            TopicFlowDeadline,
            TopicFlowAnswer,
            TopicFlowForm,
            TopicFlowFormField,
        ):
            with self.subTest(model=model.__name__):
                self.assertEqual(model.objects.count(), 0)
        # Only flow content dies with the flow.
        self.assertTrue(Topic.objects.exists())
        self.assertTrue(UserIdentity.objects.exists())


@pytest.mark.postgres
class FormMappingTests(TestCase):
    def setUp(self):
        self.flow = build_flow()

    def test_form_slug_is_unique_per_flow_not_globally(self):
        # Same slug under a different flow is fine.
        TopicFlowForm.objects.create(
            flow=build_flow("landlord"), slug="answer", name="A", file="f.pdf"
        )
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
        self.field = TopicFlowField.objects.create(
            flow=self.flow, group=group, name="county"
        )
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
