"""
Tests for custom agent tool behavior.

Only tests our business logic — not the Agent base class, Pydantic field
declarations, or LiteLLM interactions.
"""

from unittest.mock import MagicMock

import pytest
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from litigant_portal.agents.litigant_assistant import (
    ActionItem,
    FactDate,
    Resource,
    SpottedIssue,
    UpdateActionPlan,
    UpdateCaseFacts,
)
from litigant_portal.app.models import (
    ActionItemModel,
    CaseInfo,
    ChatSession,
    Deadline,
    UserIdentity,
)

User = get_user_model()


def _mock_agent(session=None):
    """Return a minimal mock agent with an optional session."""
    agent = MagicMock()
    agent.session = session
    return agent


class UpdateCaseFactsPatchBuildingTests(SimpleTestCase):
    """UpdateCaseFacts builds the correct patch structure from its fields."""

    def _call_with(self, **kwargs):
        """Instantiate tool and call it with no session (patch-only path)."""
        tool = UpdateCaseFacts(**kwargs)
        result = tool(_mock_agent(session=None))
        assert result.data is not None
        return result.data["case_patch"]

    def test_case_type_maps_to_top_level_key(self):
        patch = self._call_with(case_type="Eviction")
        self.assertEqual(patch["case_type"], "Eviction")

    def test_opposing_party_maps_to_parties(self):
        patch = self._call_with(opposing_party="Acme Properties")
        self.assertEqual(patch["parties"]["opposing_party"], "Acme Properties")

    def test_opposing_address_maps_to_parties(self):
        patch = self._call_with(opposing_address="123 Main St")
        self.assertEqual(patch["parties"]["opposing_address"], "123 Main St")

    def test_court_name_maps_to_court_info(self):
        patch = self._call_with(court_name="DuPage County Circuit Court")
        self.assertEqual(
            patch["court_info"]["court_name"], "DuPage County Circuit Court"
        )

    def test_court_county_maps_to_county_key(self):
        patch = self._call_with(court_county="DuPage")
        self.assertEqual(patch["court_info"]["county"], "DuPage")

    def test_case_number_maps_to_court_info(self):
        patch = self._call_with(case_number="2026-EV-001234")
        self.assertEqual(patch["court_info"]["case_number"], "2026-EV-001234")

    def test_new_dates_map_to_key_dates(self):
        dates = [
            FactDate(label="Hearing", date="2026-04-01", is_deadline=True)
        ]
        patch = self._call_with(new_dates=dates)
        self.assertEqual(len(patch["key_dates"]), 1)
        self.assertEqual(patch["key_dates"][0]["label"], "Hearing")
        self.assertEqual(patch["key_dates"][0]["date"], "2026-04-01")
        self.assertTrue(patch["key_dates"][0]["is_deadline"])

    def test_none_fields_excluded_from_patch(self):
        """Fields left as None should not appear in the patch at all."""
        patch = self._call_with(case_type="Eviction")
        self.assertNotIn("parties", patch)
        self.assertNotIn("court_info", patch)
        self.assertNotIn("key_dates", patch)

    def test_summary_maps_to_top_level_key(self):
        patch = self._call_with(
            summary="Tenant facing eviction for nonpayment"
        )
        self.assertEqual(
            patch["summary"], "Tenant facing eviction for nonpayment"
        )

    def test_court_address_maps_to_court_info(self):
        patch = self._call_with(court_address="505 N County Farm Rd, Wheaton")
        self.assertEqual(
            patch["court_info"]["address"], "505 N County Farm Rd, Wheaton"
        )

    def test_court_phone_maps_to_court_info(self):
        patch = self._call_with(court_phone="630-407-8700")
        self.assertEqual(patch["court_info"]["phone"], "630-407-8700")

    def test_court_email_maps_to_court_info(self):
        patch = self._call_with(court_email="clerk@example.com")
        self.assertEqual(patch["court_info"]["email"], "clerk@example.com")

    def test_user_name_maps_to_parties(self):
        patch = self._call_with(user_name="Jane Doe")
        self.assertEqual(patch["parties"]["user_name"], "Jane Doe")

    def test_user_address_maps_to_parties(self):
        patch = self._call_with(user_address="456 Elm St")
        self.assertEqual(patch["parties"]["user_address"], "456 Elm St")

    def test_opposing_contact_info_maps_to_parties(self):
        patch = self._call_with(
            opposing_phone="555-1234",
            opposing_email="landlord@example.com",
            opposing_website="https://acme.com",
        )
        self.assertEqual(patch["parties"]["opposing_phone"], "555-1234")
        self.assertEqual(
            patch["parties"]["opposing_email"], "landlord@example.com"
        )
        self.assertEqual(
            patch["parties"]["opposing_website"], "https://acme.com"
        )

    def test_attorney_info_maps_to_parties(self):
        patch = self._call_with(
            attorney_name="Bob Smith",
            attorney_phone="555-5678",
            attorney_email="bob@lawfirm.com",
        )
        self.assertEqual(patch["parties"]["attorney_name"], "Bob Smith")
        self.assertEqual(patch["parties"]["attorney_phone"], "555-5678")
        self.assertEqual(patch["parties"]["attorney_email"], "bob@lawfirm.com")

    def test_empty_parties_excluded_when_all_none(self):
        """parties key omitted when all party fields are None."""
        patch = self._call_with(case_type="Eviction")
        self.assertNotIn("parties", patch)

    def test_returns_tool_output_with_case_patch_key(self):
        from litigant_portal.agents.base import ToolOutput

        tool = UpdateCaseFacts(case_type="Small Claims")
        result = tool(_mock_agent(session=None))
        self.assertIsInstance(result, ToolOutput)
        self.assertIn("case_patch", result.data)


@pytest.mark.postgres
class UpdateCaseFactsDbPersistenceTests(TestCase):
    """UpdateCaseFacts creates and updates CaseInfo in the database."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="jane", password="testpass"
        )
        self.user_identity = UserIdentity.objects.create(user=self.user)
        self.anon_identity = UserIdentity.objects.create(
            session_key="anon-key-abc"
        )
        self.user_session = ChatSession.objects.create(
            identity=self.user_identity
        )
        self.anon_session = ChatSession.objects.create(
            identity=self.anon_identity
        )

    def _call(self, tool, session):
        return tool(_mock_agent(session=session))

    def test_creates_case_info_for_authenticated_user(self):
        """First call creates a CaseInfo owned by the user."""
        self.assertEqual(
            CaseInfo.objects.filter(identity__user=self.user).count(), 0
        )

        self._call(UpdateCaseFacts(case_type="Eviction"), self.user_session)

        self.assertEqual(
            CaseInfo.objects.filter(identity__user=self.user).count(), 1
        )
        case = CaseInfo.objects.get(identity__user=self.user)
        self.assertEqual(case.data["case_type"], "Eviction")

    def test_creates_case_info_for_anonymous_session(self):
        """First call creates a CaseInfo keyed by session_key for anon users."""
        self.assertEqual(
            CaseInfo.objects.filter(
                identity__session_key="anon-key-abc"
            ).count(),
            0,
        )

        self._call(
            UpdateCaseFacts(case_type="Small Claims"), self.anon_session
        )

        self.assertEqual(
            CaseInfo.objects.filter(
                identity__session_key="anon-key-abc"
            ).count(),
            1,
        )
        case = CaseInfo.objects.get(identity__session_key="anon-key-abc")
        self.assertEqual(case.data["case_type"], "Small Claims")

    def test_updates_existing_case_type(self):
        """Subsequent call updates the case_type in the existing CaseInfo."""
        CaseInfo.objects.create(
            identity=self.user_identity, data={"case_type": "Unknown"}
        )

        self._call(UpdateCaseFacts(case_type="Eviction"), self.user_session)

        case = CaseInfo.objects.get(identity__user=self.user)
        self.assertEqual(case.data["case_type"], "Eviction")

    def test_merges_court_info_preserves_existing_fields(self):
        """Merging partial court_info updates given fields without clearing others."""
        CaseInfo.objects.create(
            identity=self.user_identity,
            data={
                "court_info": {
                    "court_name": "Circuit Court",
                    "phone": "555-1234",
                }
            },
        )

        self._call(UpdateCaseFacts(court_county="DuPage"), self.user_session)

        case = CaseInfo.objects.get(identity__user=self.user)
        self.assertEqual(case.data["court_info"]["county"], "DuPage")
        # Existing field must not be overwritten
        self.assertEqual(
            case.data["court_info"]["court_name"], "Circuit Court"
        )
        self.assertEqual(case.data["court_info"]["phone"], "555-1234")

    def test_merges_parties_preserves_existing_fields(self):
        """Merging partial parties updates given fields without clearing others."""
        CaseInfo.objects.create(
            identity=self.user_identity,
            data={
                "parties": {
                    "opposing_party": "Acme Corp",
                    "opposing_phone": "555-9999",
                }
            },
        )

        self._call(
            UpdateCaseFacts(opposing_address="100 Oak Ave"), self.user_session
        )

        case = CaseInfo.objects.get(identity__user=self.user)
        self.assertEqual(
            case.data["parties"]["opposing_address"], "100 Oak Ave"
        )
        self.assertEqual(case.data["parties"]["opposing_party"], "Acme Corp")
        self.assertEqual(case.data["parties"]["opposing_phone"], "555-9999")

    def test_no_session_skips_db_write(self):
        """Tool with no session returns patch but writes nothing to the DB."""
        self._call(UpdateCaseFacts(case_type="Eviction"), session=None)
        self.assertEqual(CaseInfo.objects.count(), 0)


@pytest.mark.postgres
class UpdateCaseFactsDateDeduplicationTests(TestCase):
    """UpdateCaseFacts deduplicates key_dates via Deadline model."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="jane", password="testpass"
        )
        self.identity = UserIdentity.objects.create(user=self.user)
        self.session = ChatSession.objects.create(identity=self.identity)
        self.case = CaseInfo.objects.create(identity=self.identity, data={})
        Deadline.objects.create(
            case=self.case,
            label="Hearing",
            date="2026-04-01",
            is_deadline=True,
        )

    def _call(self, tool):
        return tool(_mock_agent(session=self.session))

    def test_does_not_duplicate_same_label_and_date(self):
        """Calling with a date already in Deadline table does not add a duplicate."""
        duplicate = FactDate(
            label="Hearing", date="2026-04-01", is_deadline=True
        )
        self._call(UpdateCaseFacts(new_dates=[duplicate]))
        self.assertEqual(self.case.deadlines.count(), 1)

    def test_appends_date_with_different_label(self):
        """A date with the same date but a different label is added."""
        new = FactDate(
            label="Notice Date", date="2026-04-01", is_deadline=False
        )
        self._call(UpdateCaseFacts(new_dates=[new]))
        self.assertEqual(self.case.deadlines.count(), 2)

    def test_appends_date_with_different_date(self):
        """A date with the same label but a different date value is added."""
        new = FactDate(label="Hearing", date="2026-05-15", is_deadline=True)
        self._call(UpdateCaseFacts(new_dates=[new]))
        self.assertEqual(self.case.deadlines.count(), 2)

    def test_key_dates_not_in_json(self):
        """key_dates should not be written to CaseInfo.data."""
        new = FactDate(label="Filing", date="2026-06-01", is_deadline=True)
        self._call(UpdateCaseFacts(new_dates=[new]))
        self.case.refresh_from_db()
        self.assertNotIn("key_dates", self.case.data)


# =============================================================================
# UpdateActionPlan tests
# =============================================================================


class UpdateActionPlanPatchBuildingTests(SimpleTestCase):
    """UpdateActionPlan builds the correct patch structure from its fields."""

    def _call_with(self, **kwargs):
        """Instantiate tool and call it with no session (patch-only path)."""
        tool = UpdateActionPlan(**kwargs)
        result = tool(_mock_agent(session=None))
        assert result.data is not None
        return result.data["action_plan_patch"]

    def test_action_items_in_patch(self):
        items = [ActionItem(title="File an Appearance", priority="urgent")]
        patch = self._call_with(new_action_items=items)
        self.assertEqual(len(patch["action_items"]), 1)
        self.assertEqual(
            patch["action_items"][0]["title"], "File an Appearance"
        )
        self.assertEqual(patch["action_items"][0]["priority"], "urgent")

    def test_spotted_issues_in_patch(self):
        issues = [
            SpottedIssue(
                title="Habitability defense",
                statute="765 ILCS 735/2",
            )
        ]
        patch = self._call_with(new_spotted_issues=issues)
        self.assertEqual(len(patch["spotted_issues"]), 1)
        self.assertEqual(
            patch["spotted_issues"][0]["title"], "Habitability defense"
        )
        self.assertEqual(
            patch["spotted_issues"][0]["statute"], "765 ILCS 735/2"
        )

    def test_resources_in_patch(self):
        resources = [
            Resource(
                title="IL Rental Payment Program",
                href="https://example.com",
            )
        ]
        patch = self._call_with(new_resources=resources)
        self.assertEqual(len(patch["resources"]), 1)
        self.assertEqual(
            patch["resources"][0]["title"], "IL Rental Payment Program"
        )

    def test_none_fields_excluded_from_patch(self):
        """Fields left as None should not appear in the patch."""
        patch = self._call_with(new_action_items=[ActionItem(title="Test")])
        self.assertNotIn("spotted_issues", patch)
        self.assertNotIn("resources", patch)

    def test_empty_patch_when_all_none(self):
        """Patch is empty when no lists are provided."""
        patch = self._call_with()
        self.assertEqual(patch, {})

    def test_returns_tool_output_with_action_plan_patch_key(self):
        from litigant_portal.agents.base import ToolOutput

        tool = UpdateActionPlan(new_action_items=[ActionItem(title="Test")])
        result = tool(_mock_agent(session=None))
        self.assertIsInstance(result, ToolOutput)
        self.assertIn("action_plan_patch", result.data)

    def test_none_optional_fields_excluded_from_item_dict(self):
        """ActionItem with no deadline/href excludes those keys."""
        items = [ActionItem(title="Test", description="Do the thing")]
        patch = self._call_with(new_action_items=items)
        item = patch["action_items"][0]
        self.assertNotIn("deadline", item)
        self.assertNotIn("href", item)

    def test_optional_fields_included_when_set(self):
        items = [
            ActionItem(
                title="File form",
                deadline="2026-05-01",
                href="https://courts.il.gov/form",
            )
        ]
        patch = self._call_with(new_action_items=items)
        item = patch["action_items"][0]
        self.assertEqual(item["deadline"], "2026-05-01")
        self.assertEqual(item["href"], "https://courts.il.gov/form")


@pytest.mark.postgres
class UpdateActionPlanDbPersistenceTests(TestCase):
    """UpdateActionPlan creates and updates action plan data in the database."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="jane", password="testpass"
        )
        self.user_identity = UserIdentity.objects.create(user=self.user)
        self.anon_identity = UserIdentity.objects.create(
            session_key="anon-key-xyz"
        )
        self.user_session = ChatSession.objects.create(
            identity=self.user_identity
        )
        self.anon_session = ChatSession.objects.create(
            identity=self.anon_identity
        )

    def _call(self, tool, session):
        return tool(_mock_agent(session=session))

    def test_creates_action_items_for_authenticated_user(self):
        """Action items are stored as ActionItemModel rows for the user."""
        self._call(
            UpdateActionPlan(
                new_action_items=[ActionItem(title="File an Appearance")]
            ),
            self.user_session,
        )

        case = CaseInfo.objects.get(identity__user=self.user)
        self.assertEqual(case.action_items.count(), 1)
        self.assertEqual(case.action_items.first().title, "File an Appearance")

    def test_creates_action_items_for_anonymous_session(self):
        """Action items are stored as ActionItemModel rows keyed by session_key."""
        self._call(
            UpdateActionPlan(
                new_action_items=[ActionItem(title="Call the clerk")]
            ),
            self.anon_session,
        )

        case = CaseInfo.objects.get(identity__session_key="anon-key-xyz")
        self.assertEqual(case.action_items.count(), 1)

    def test_spotted_issues_stored_in_json(self):
        """Spotted issues are stored in CaseInfo.data JSON."""
        self._call(
            UpdateActionPlan(
                new_spotted_issues=[SpottedIssue(title="Habitability defense")]
            ),
            self.user_session,
        )

        case = CaseInfo.objects.get(identity__user=self.user)
        self.assertEqual(len(case.data["spotted_issues"]), 1)
        self.assertEqual(
            case.data["spotted_issues"][0]["title"], "Habitability defense"
        )

    def test_resources_stored_in_json(self):
        """Resources are stored in CaseInfo.data JSON."""
        self._call(
            UpdateActionPlan(
                new_resources=[Resource(title="Legal Aid Hotline")]
            ),
            self.user_session,
        )

        case = CaseInfo.objects.get(identity__user=self.user)
        self.assertEqual(len(case.data["resources"]), 1)

    def test_action_items_not_in_json(self):
        """action_items should not be written to CaseInfo.data."""
        self._call(
            UpdateActionPlan(new_action_items=[ActionItem(title="Test")]),
            self.user_session,
        )
        case = CaseInfo.objects.get(identity__user=self.user)
        self.assertNotIn("action_items", case.data)

    def test_no_session_skips_db_write(self):
        """Tool with no session returns patch but writes nothing to the DB."""
        self._call(
            UpdateActionPlan(new_action_items=[ActionItem(title="Test")]),
            session=None,
        )
        self.assertEqual(CaseInfo.objects.count(), 0)
        self.assertEqual(ActionItemModel.objects.count(), 0)


@pytest.mark.postgres
class UpdateActionPlanDeduplicationTests(TestCase):
    """UpdateActionPlan deduplicates action items via ActionItemModel."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="jane", password="testpass"
        )
        self.identity = UserIdentity.objects.create(user=self.user)
        self.session = ChatSession.objects.create(identity=self.identity)
        self.case = CaseInfo.objects.create(identity=self.identity, data={})
        ActionItemModel.objects.create(
            case=self.case,
            title="File an Appearance",
            description="Submit to clerk",
            priority="urgent",
        )

    def _call(self, tool):
        return tool(_mock_agent(session=self.session))

    def test_does_not_duplicate_same_title(self):
        """Calling with an action item whose title exists does not add a duplicate."""
        self._call(
            UpdateActionPlan(
                new_action_items=[ActionItem(title="File an Appearance")]
            )
        )
        self.assertEqual(self.case.action_items.count(), 1)

    def test_appends_item_with_different_title(self):
        """An action item with a new title is appended."""
        self._call(
            UpdateActionPlan(
                new_action_items=[ActionItem(title="Contact legal aid")]
            )
        )
        self.assertEqual(self.case.action_items.count(), 2)

    def test_spotted_issue_dedup_by_title(self):
        """Spotted issues with the same title are not duplicated."""
        self.case.data = {
            "spotted_issues": [{"title": "Habitability defense"}],
        }
        self.case.save()

        self._call(
            UpdateActionPlan(
                new_spotted_issues=[SpottedIssue(title="Habitability defense")]
            )
        )

        self.case.refresh_from_db()
        self.assertEqual(len(self.case.data["spotted_issues"]), 1)
