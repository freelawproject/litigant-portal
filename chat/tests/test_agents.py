"""
Tests for custom agent tool behavior.

Only tests our business logic — not the Agent base class, Pydantic field
declarations, or LiteLLM interactions.
"""

from unittest.mock import MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase

from chat.agents.litigant_assistant import FactDate, UpdateCaseFacts
from chat.models import CaseInfo, ChatSession

User = get_user_model()


def _mock_agent(session=None):
    """Return a minimal mock agent with an optional session."""
    agent = MagicMock()
    agent.session = session
    return agent


class UpdateCaseFactsPatchBuildingTests(TestCase):
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

    def test_empty_parties_excluded_when_both_none(self):
        """parties key omitted when both opposing_party and opposing_address are None."""
        patch = self._call_with(case_type="Eviction")
        self.assertNotIn("parties", patch)

    def test_returns_tool_output_with_case_patch_key(self):
        from chat.agents.base import ToolOutput

        tool = UpdateCaseFacts(case_type="Small Claims")
        result = tool(_mock_agent(session=None))
        self.assertIsInstance(result, ToolOutput)
        self.assertIn("case_patch", result.data)


class UpdateCaseFactsDbPersistenceTests(TestCase):
    """UpdateCaseFacts creates and updates CaseInfo in the database."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="jane", password="testpass"
        )
        self.user_session = ChatSession.objects.create(user=self.user)
        self.anon_session = ChatSession.objects.create(
            session_key="anon-key-abc"
        )

    def _call(self, tool, session):
        return tool(_mock_agent(session=session))

    def test_creates_case_info_for_authenticated_user(self):
        """First call creates a CaseInfo owned by the user."""
        self.assertEqual(CaseInfo.objects.filter(user=self.user).count(), 0)

        self._call(UpdateCaseFacts(case_type="Eviction"), self.user_session)

        self.assertEqual(CaseInfo.objects.filter(user=self.user).count(), 1)
        case = CaseInfo.objects.get(user=self.user)
        self.assertEqual(case.data["case_type"], "Eviction")

    def test_creates_case_info_for_anonymous_session(self):
        """First call creates a CaseInfo keyed by session_key for anon users."""
        self.assertEqual(
            CaseInfo.objects.filter(session_key="anon-key-abc").count(), 0
        )

        self._call(
            UpdateCaseFacts(case_type="Small Claims"), self.anon_session
        )

        self.assertEqual(
            CaseInfo.objects.filter(session_key="anon-key-abc").count(), 1
        )
        case = CaseInfo.objects.get(session_key="anon-key-abc")
        self.assertEqual(case.data["case_type"], "Small Claims")

    def test_updates_existing_case_type(self):
        """Subsequent call updates the case_type in the existing CaseInfo."""
        CaseInfo.objects.create(user=self.user, data={"case_type": "Unknown"})

        self._call(UpdateCaseFacts(case_type="Eviction"), self.user_session)

        case = CaseInfo.objects.get(user=self.user)
        self.assertEqual(case.data["case_type"], "Eviction")

    def test_merges_court_info_preserves_existing_fields(self):
        """Merging partial court_info updates given fields without clearing others."""
        CaseInfo.objects.create(
            user=self.user,
            data={
                "court_info": {
                    "court_name": "Circuit Court",
                    "phone": "555-1234",
                }
            },
        )

        self._call(UpdateCaseFacts(court_county="DuPage"), self.user_session)

        case = CaseInfo.objects.get(user=self.user)
        self.assertEqual(case.data["court_info"]["county"], "DuPage")
        # Existing field must not be overwritten
        self.assertEqual(
            case.data["court_info"]["court_name"], "Circuit Court"
        )
        self.assertEqual(case.data["court_info"]["phone"], "555-1234")

    def test_merges_parties_preserves_existing_fields(self):
        """Merging partial parties updates given fields without clearing others."""
        CaseInfo.objects.create(
            user=self.user,
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

        case = CaseInfo.objects.get(user=self.user)
        self.assertEqual(
            case.data["parties"]["opposing_address"], "100 Oak Ave"
        )
        self.assertEqual(case.data["parties"]["opposing_party"], "Acme Corp")
        self.assertEqual(case.data["parties"]["opposing_phone"], "555-9999")

    def test_no_session_skips_db_write(self):
        """Tool with no session returns patch but writes nothing to the DB."""
        self._call(UpdateCaseFacts(case_type="Eviction"), session=None)
        self.assertEqual(CaseInfo.objects.count(), 0)


class UpdateCaseFactsDateDeduplicationTests(TestCase):
    """UpdateCaseFacts deduplicates key_dates by label + date pair."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="jane", password="testpass"
        )
        self.session = ChatSession.objects.create(user=self.user)
        CaseInfo.objects.create(
            user=self.user,
            data={
                "key_dates": [
                    {
                        "label": "Hearing",
                        "date": "2026-04-01",
                        "is_deadline": True,
                    }
                ]
            },
        )

    def _call(self, tool):
        return tool(_mock_agent(session=self.session))

    def test_does_not_duplicate_same_label_and_date(self):
        """Calling with a date already in key_dates does not add a duplicate."""
        duplicate = FactDate(
            label="Hearing", date="2026-04-01", is_deadline=True
        )
        self._call(UpdateCaseFacts(new_dates=[duplicate]))

        case = CaseInfo.objects.get(user=self.user)
        self.assertEqual(len(case.data["key_dates"]), 1)

    def test_appends_date_with_different_label(self):
        """A date with the same date but a different label is added."""
        new = FactDate(
            label="Notice Date", date="2026-04-01", is_deadline=False
        )
        self._call(UpdateCaseFacts(new_dates=[new]))

        case = CaseInfo.objects.get(user=self.user)
        self.assertEqual(len(case.data["key_dates"]), 2)

    def test_appends_date_with_different_date(self):
        """A date with the same label but a different date value is added."""
        new = FactDate(label="Hearing", date="2026-05-15", is_deadline=True)
        self._call(UpdateCaseFacts(new_dates=[new]))

        case = CaseInfo.objects.get(user=self.user)
        self.assertEqual(len(case.data["key_dates"]), 2)
