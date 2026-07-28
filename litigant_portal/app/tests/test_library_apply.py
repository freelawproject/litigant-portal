"""Tests for library apply: field groups as docassemble-style pages.

The library YAMLs declare ``field_groups`` (one per interview page);
``_flow_replace_children`` reuses groups by position and upserts fields by
name across the whole flow, so re-applying a restructured config preserves
field ids — and with them litigants' stored answers.
"""

import pytest
from django.test import TestCase

from litigant_portal.app.models import (
    Topic,
    TopicFlowAnswer,
    TopicFlowField,
    UserIdentity,
)
from litigant_portal.app.selectors.library import topic_library_get
from litigant_portal.app.services.library import topic_library_apply


def _field(name, **overrides):
    row = {
        "name": name,
        "label": name.replace("_", " ").title(),
        "help_text": "",
        "required": False,
        "data_type": "text",
        "choices": [],
        "default": "",
    }
    row.update(overrides)
    return row


def _group(title, fields, description=""):
    return {"title": title, "description": description, "fields": fields}


def _config(field_groups, deadlines=None):
    return {
        "slug": "test-topic",
        "title": "Test Topic",
        "subtitle": "",
        "description": "",
        "icon": "",
        "meta_description": "",
        "prompts": [],
        "flows": [
            {
                "slug": "test-flow",
                "name": "Test Flow",
                "sections": [],
                "field_groups": field_groups,
                "links": [],
                "deadlines": deadlines or [],
                "forms": [],
            }
        ],
    }


@pytest.mark.postgres
class LibraryApplyGroupTests(TestCase):
    def _flow(self):
        return Topic.objects.get(slug="test-topic").flows.get(
            slug="test-flow"
        )

    def test_apply_creates_groups_and_fields_in_order(self):
        topic_library_apply(
            config=_config(
                [
                    _group("Page one", [_field("a"), _field("b")], "Intro"),
                    _group("Page two", [_field("c")]),
                ]
            )
        )
        groups = list(self._flow().field_groups.all())
        self.assertEqual(
            [(g.title, g.description, g.order) for g in groups],
            [("Page one", "Intro", 0), ("Page two", "", 1)],
        )
        self.assertEqual(
            [(f.name, f.order) for f in groups[0].fields.all()],
            [("a", 0), ("b", 1)],
        )
        self.assertEqual(
            [f.name for f in groups[1].fields.all()], ["c"]
        )

    def test_reapply_restructure_preserves_field_ids_and_answers(self):
        topic_library_apply(
            config=_config(
                [
                    _group("Page one", [_field("a"), _field("b")]),
                    _group("Page two", [_field("c")]),
                ]
            )
        )
        flow = self._flow()
        field_c = TopicFlowField.objects.get(group__flow=flow, name="c")
        identity = UserIdentity.objects.create(session_key="test-session")
        TopicFlowAnswer.objects.create(
            identity=identity, field=field_c, value="kept"
        )

        # Restructure: one page, field "b" gone, "c" moves into page one.
        topic_library_apply(
            config=_config([_group("Only page", [_field("a"), _field("c")])])
        )

        flow = self._flow()
        groups = list(flow.field_groups.all())
        self.assertEqual([g.title for g in groups], ["Only page"])
        self.assertEqual(
            [f.name for f in groups[0].fields.all()], ["a", "c"]
        )
        moved_c = TopicFlowField.objects.get(group__flow=flow, name="c")
        self.assertEqual(moved_c.id, field_c.id)
        self.assertEqual(
            TopicFlowAnswer.objects.get(identity=identity, field=moved_c).value,
            "kept",
        )
        self.assertFalse(
            TopicFlowField.objects.filter(group__flow=flow, name="b").exists()
        )

    def test_deadlines_resolve_against_fields_in_any_group(self):
        topic_library_apply(
            config=_config(
                [
                    _group("Page one", [_field("a")]),
                    _group(
                        "Page two", [_field("served", data_type="date")]
                    ),
                ],
                deadlines=[
                    {
                        "label": "Answer due",
                        "description": "",
                        "offset_days": 28,
                        "offset_from": "served",
                    }
                ],
            )
        )
        deadline = self._flow().deadlines.get()
        self.assertEqual(deadline.offset_from.name, "served")

    def test_real_library_standard_flow_mirrors_interview_pages(self):
        config = topic_library_get(
            court_slug="north-dakota", topic_slug="adult-name-change"
        )
        standard = next(
            f for f in config["flows"] if f["slug"] == "standard"
        )
        self.assertEqual(
            [g["title"] for g in standard["field_groups"]],
            [
                "Your current legal name",
                "The name you want",
                "Where you live",
                "A few details the Petition requires",
                "Publication of your notice",
                "A few more details for the rest of your packet",
            ],
        )
        # Every deadline still resolves against the grouped field namespace.
        field_names = {
            row["name"]
            for group in standard["field_groups"]
            for row in group["fields"]
        }
        for deadline in standard["deadlines"]:
            self.assertIn(deadline["offset_from"], field_names)
