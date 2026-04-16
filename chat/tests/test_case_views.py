"""
Tests for case info API endpoints.

Tests CRUD operations, ownership isolation, input validation,
auto-creation of CaseInfo on timeline event, and clear cascade.
"""

import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from chat.models import ActionItemModel, CaseInfo, Deadline, TimelineEvent

User = get_user_model()

SAMPLE_CASE_DATA = {
    "case_type": "Eviction",
    "summary": "Tenant eviction case in Bexar County",
    "court_info": {
        "court_name": "Bexar County Justice Court",
        "county": "Bexar",
        "case_number": "2026-CV-1234",
    },
    "parties": {
        "user_name": "Jane Doe",
        "opposing_party": "ABC Apartments",
    },
    "key_dates": [
        {
            "label": "Answer deadline",
            "date": "2026-03-15",
            "is_deadline": True,
        },
    ],
}


@pytest.mark.postgres
class CaseGetTests(TestCase):
    """Tests for GET /api/chat/case/."""

    def setUp(self):
        self.client = Client()

    def test_returns_null_when_no_case(self):
        """Should return null case_info and empty timeline when none exists."""
        response = self.client.get("/api/chat/case/")

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIsNone(data["case_info"])
        self.assertEqual(data["timeline"], [])

    def test_returns_saved_case_info(self):
        """Should return previously saved case data."""
        # Save via the save endpoint first
        self.client.post(
            "/api/chat/case/save/",
            {"data": json.dumps(SAMPLE_CASE_DATA)},
        )

        response = self.client.get("/api/chat/case/")

        data = json.loads(response.content)
        self.assertEqual(data["case_info"]["case_type"], "Eviction")
        self.assertEqual(
            data["case_info"]["court_info"]["case_number"], "2026-CV-1234"
        )

    def test_returns_timeline_events(self):
        """Should include timeline events with the case."""
        self.client.post(
            "/api/chat/case/timeline/",
            {
                "event_type": "upload",
                "title": "Uploaded: petition.pdf",
                "content": "3 page document",
            },
        )

        response = self.client.get("/api/chat/case/")

        data = json.loads(response.content)
        self.assertEqual(len(data["timeline"]), 1)
        self.assertEqual(
            data["timeline"][0]["title"], "Uploaded: petition.pdf"
        )
        self.assertEqual(data["timeline"][0]["event_type"], "upload")


@pytest.mark.postgres
class CaseSaveTests(TestCase):
    """Tests for POST /api/chat/case/save/."""

    def setUp(self):
        self.client = Client()

    def test_creates_case_info(self):
        """Should create CaseInfo on first save."""
        response = self.client.post(
            "/api/chat/case/save/",
            {"data": json.dumps(SAMPLE_CASE_DATA)},
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["created"])
        self.assertEqual(CaseInfo.objects.count(), 1)

    def test_updates_existing_case_info(self):
        """Should update existing CaseInfo on subsequent save."""
        self.client.post(
            "/api/chat/case/save/",
            {"data": json.dumps(SAMPLE_CASE_DATA)},
        )
        updated_data = {**SAMPLE_CASE_DATA, "case_type": "Foreclosure"}
        response = self.client.post(
            "/api/chat/case/save/",
            {"data": json.dumps(updated_data)},
        )

        data = json.loads(response.content)
        self.assertFalse(data["created"])
        self.assertEqual(CaseInfo.objects.count(), 1)
        self.assertEqual(
            CaseInfo.objects.first().data["case_type"], "Foreclosure"
        )

    def test_rejects_missing_data(self):
        """Should reject request without data field."""
        response = self.client.post("/api/chat/case/save/")
        self.assertEqual(response.status_code, 400)

    def test_rejects_invalid_json(self):
        """Should reject malformed JSON."""
        response = self.client.post(
            "/api/chat/case/save/", {"data": "not json"}
        )
        self.assertEqual(response.status_code, 400)

    def test_rejects_non_object_json(self):
        """Should reject JSON that is not an object."""
        response = self.client.post(
            "/api/chat/case/save/", {"data": json.dumps([1, 2, 3])}
        )
        self.assertEqual(response.status_code, 400)


@pytest.mark.postgres
class CaseTimelineAddTests(TestCase):
    """Tests for POST /api/chat/case/timeline/."""

    def setUp(self):
        self.client = Client()

    def test_creates_timeline_event(self):
        """Should create a timeline event."""
        response = self.client.post(
            "/api/chat/case/timeline/",
            {
                "event_type": "upload",
                "title": "Uploaded: petition.pdf",
                "content": "3 page document",
                "metadata": json.dumps({"filename": "petition.pdf"}),
            },
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn("id", data)
        self.assertEqual(TimelineEvent.objects.count(), 1)

    def test_auto_creates_case_info(self):
        """Should auto-create CaseInfo if none exists."""
        self.assertEqual(CaseInfo.objects.count(), 0)

        self.client.post(
            "/api/chat/case/timeline/",
            {"event_type": "upload", "title": "Test"},
        )

        self.assertEqual(CaseInfo.objects.count(), 1)

    def test_reuses_existing_case_info(self):
        """Should add event to existing CaseInfo."""
        self.client.post(
            "/api/chat/case/save/",
            {"data": json.dumps(SAMPLE_CASE_DATA)},
        )

        self.client.post(
            "/api/chat/case/timeline/",
            {"event_type": "upload", "title": "Test"},
        )

        self.assertEqual(CaseInfo.objects.count(), 1)
        self.assertEqual(TimelineEvent.objects.count(), 1)

    def test_rejects_invalid_event_type(self):
        """Should reject unknown event types."""
        response = self.client.post(
            "/api/chat/case/timeline/",
            {"event_type": "invalid", "title": "Test"},
        )
        self.assertEqual(response.status_code, 400)

    def test_rejects_invalid_metadata_json(self):
        """Should reject malformed metadata JSON."""
        response = self.client.post(
            "/api/chat/case/timeline/",
            {"event_type": "upload", "metadata": "not json"},
        )
        self.assertEqual(response.status_code, 400)


@pytest.mark.postgres
class CaseClearTests(TestCase):
    """Tests for POST /api/chat/case/clear/ — archives instead of deleting."""

    def setUp(self):
        self.client = Client()

    def test_archives_case_instead_of_deleting(self):
        """Should set status='archived' rather than deleting."""
        self.client.post(
            "/api/chat/case/save/",
            {"data": json.dumps(SAMPLE_CASE_DATA)},
        )

        response = self.client.post("/api/chat/case/clear/")

        data = json.loads(response.content)
        self.assertTrue(data["archived"])
        self.assertEqual(CaseInfo.objects.count(), 1)
        self.assertEqual(CaseInfo.objects.first().status, "archived")

    def test_returns_false_when_nothing_to_archive(self):
        """Should return archived=false when no active case exists."""
        response = self.client.post("/api/chat/case/clear/")

        data = json.loads(response.content)
        self.assertFalse(data["archived"])

    def test_clears_chat_session_id(self):
        """Should remove chat_session_id from Django session."""
        session = self.client.session
        session["chat_session_id"] = "some-id"
        session.save()

        self.client.post("/api/chat/case/clear/")

        response = self.client.get("/api/chat/case/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("chat_session_id", self.client.session)

    def test_archived_case_not_returned_by_case_get(self):
        """After archiving, case_get should return null (only active cases)."""
        self.client.post(
            "/api/chat/case/save/",
            {"data": json.dumps(SAMPLE_CASE_DATA)},
        )
        self.client.post("/api/chat/case/clear/")

        response = self.client.get("/api/chat/case/")

        data = json.loads(response.content)
        self.assertIsNone(data["case_info"])


@pytest.mark.postgres
class OwnershipIsolationTests(TestCase):
    """Tests that separate sessions/users can't see each other's data."""

    def test_anonymous_sessions_isolated(self):
        """Two anonymous clients should not see each other's cases."""
        client_a = Client()
        client_b = Client()

        client_a.post(
            "/api/chat/case/save/",
            {"data": json.dumps({"case_type": "Eviction"})},
        )
        client_b.post(
            "/api/chat/case/save/",
            {"data": json.dumps({"case_type": "Foreclosure"})},
        )

        response_a = client_a.get("/api/chat/case/")
        response_b = client_b.get("/api/chat/case/")

        data_a = json.loads(response_a.content)
        data_b = json.loads(response_b.content)
        self.assertEqual(data_a["case_info"]["case_type"], "Eviction")
        self.assertEqual(data_b["case_info"]["case_type"], "Foreclosure")

    def test_authenticated_user_isolation(self):
        """Authenticated users should only see their own cases."""
        User.objects.create_user(username="alice", password="pass")
        User.objects.create_user(username="bob", password="pass")

        client_a = Client()
        client_b = Client()
        client_a.login(username="alice", password="pass")
        client_b.login(username="bob", password="pass")

        client_a.post(
            "/api/chat/case/save/",
            {"data": json.dumps({"case_type": "Eviction"})},
        )

        response_b = client_b.get("/api/chat/case/")

        data_b = json.loads(response_b.content)
        self.assertIsNone(data_b["case_info"])

    def test_clear_only_affects_own_data(self):
        """Clear should only archive the requesting user's case."""
        client_a = Client()
        client_b = Client()

        client_a.post(
            "/api/chat/case/save/",
            {"data": json.dumps({"case_type": "Eviction"})},
        )
        client_b.post(
            "/api/chat/case/save/",
            {"data": json.dumps({"case_type": "Foreclosure"})},
        )

        client_a.post("/api/chat/case/clear/")

        # A's case should be archived (not visible via case_get)
        data_a = json.loads(client_a.get("/api/chat/case/").content)
        self.assertIsNone(data_a["case_info"])

        # B should still have active data
        data_b = json.loads(client_b.get("/api/chat/case/").content)
        self.assertEqual(data_b["case_info"]["case_type"], "Foreclosure")


@pytest.mark.postgres
class CaseGetStatusFilterTests(TestCase):
    """Tests that case_get only returns active cases."""

    def setUp(self):
        self.client = Client()

    def test_case_get_includes_status_field(self):
        """Response should include the status field."""
        self.client.post(
            "/api/chat/case/save/",
            {"data": json.dumps(SAMPLE_CASE_DATA)},
        )

        response = self.client.get("/api/chat/case/")

        data = json.loads(response.content)
        self.assertEqual(data["case_info"]["status"], "active")

    def test_case_save_after_archive_creates_new_active(self):
        """Saving after archive should create a new active case."""
        self.client.post(
            "/api/chat/case/save/",
            {"data": json.dumps(SAMPLE_CASE_DATA)},
        )
        self.client.post("/api/chat/case/clear/")

        self.client.post(
            "/api/chat/case/save/",
            {"data": json.dumps({"case_type": "Small Claims"})},
        )

        response = self.client.get("/api/chat/case/")
        data = json.loads(response.content)
        self.assertEqual(data["case_info"]["case_type"], "Small Claims")
        self.assertEqual(data["case_info"]["status"], "active")
        # Archived + new active = 2 total
        self.assertEqual(CaseInfo.objects.count(), 2)


@pytest.mark.postgres
class CaseResolveTests(TestCase):
    """Tests for POST /api/chat/case/resolve/."""

    def setUp(self):
        self.client = Client()

    def test_resolves_active_case(self):
        """Should set status to 'resolved' and create timeline event."""
        self.client.post(
            "/api/chat/case/save/",
            {"data": json.dumps(SAMPLE_CASE_DATA)},
        )

        response = self.client.post("/api/chat/case/resolve/")

        data = json.loads(response.content)
        self.assertTrue(data["resolved"])
        case = CaseInfo.objects.first()
        self.assertEqual(case.status, "resolved")
        self.assertTrue(
            case.timeline_events.filter(event_type="resolution").exists()
        )

    def test_returns_false_when_no_active_case(self):
        response = self.client.post("/api/chat/case/resolve/")

        data = json.loads(response.content)
        self.assertFalse(data["resolved"])


@pytest.mark.postgres
class ActionItemToggleTests(TestCase):
    """Tests for POST /api/chat/case/action-item/<id>/toggle/."""

    def setUp(self):
        self.client = Client()
        self.client.post(
            "/api/chat/case/save/",
            {"data": json.dumps(SAMPLE_CASE_DATA)},
        )
        self.case = CaseInfo.objects.first()
        self.item = ActionItemModel.objects.create(
            case=self.case, title="File paperwork"
        )

    def test_toggles_completed_false_to_true(self):
        response = self.client.post(
            f"/api/chat/case/action-item/{self.item.id}/toggle/"
        )

        data = json.loads(response.content)
        self.assertTrue(data["completed"])
        self.item.refresh_from_db()
        self.assertTrue(self.item.completed)

    def test_toggles_completed_true_to_false(self):
        self.item.completed = True
        self.item.save()

        response = self.client.post(
            f"/api/chat/case/action-item/{self.item.id}/toggle/"
        )

        data = json.loads(response.content)
        self.assertFalse(data["completed"])

    def test_returns_404_for_nonexistent_item(self):
        import uuid

        response = self.client.post(
            f"/api/chat/case/action-item/{uuid.uuid4()}/toggle/"
        )
        self.assertEqual(response.status_code, 404)


@pytest.mark.postgres
class DeadlineReminderToggleTests(TestCase):
    """Tests for POST /api/chat/case/deadline/<id>/remind/."""

    def setUp(self):
        self.client = Client()
        self.client.post(
            "/api/chat/case/save/",
            {"data": json.dumps(SAMPLE_CASE_DATA)},
        )
        self.case = CaseInfo.objects.first()
        self.deadline = Deadline.objects.create(
            case=self.case,
            label="Answer deadline",
            date="2026-05-01",
            is_deadline=True,
        )

    def test_toggles_reminder_false_to_true(self):
        response = self.client.post(
            f"/api/chat/case/deadline/{self.deadline.id}/remind/"
        )

        data = json.loads(response.content)
        self.assertTrue(data["reminder_requested"])
        self.deadline.refresh_from_db()
        self.assertTrue(self.deadline.reminder_requested)

    def test_toggles_reminder_true_to_false(self):
        self.deadline.reminder_requested = True
        self.deadline.save()

        response = self.client.post(
            f"/api/chat/case/deadline/{self.deadline.id}/remind/"
        )

        data = json.loads(response.content)
        self.assertFalse(data["reminder_requested"])

    def test_returns_404_for_nonexistent_deadline(self):
        import uuid

        response = self.client.post(
            f"/api/chat/case/deadline/{uuid.uuid4()}/remind/"
        )
        self.assertEqual(response.status_code, 404)


@pytest.mark.postgres
class TimelineResolutionTypeTests(TestCase):
    """Tests that timeline endpoint accepts 'resolution' event type."""

    def setUp(self):
        self.client = Client()

    def test_accepts_resolution_event_type(self):
        response = self.client.post(
            "/api/chat/case/timeline/",
            {"event_type": "resolution", "title": "Case resolved"},
        )

        self.assertEqual(response.status_code, 200)
