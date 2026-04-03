"""Tests for action_plan view context building."""

from django.test import Client, TestCase

from chat.models import CaseInfo


SAMPLE_CASE_DATA = {
    "case_type": "Eviction",
    "summary": "Tenant eviction case",
    "court_info": {"court_name": "Bexar County Justice Court"},
    "parties": {"user_name": "Jane Doe"},
    "key_dates": [{"label": "Answer deadline", "date": "2026-03-15"}],
    "action_items": [{"title": "File answer", "priority": "high"}],
    "spotted_issues": [{"title": "Late notice"}],
    "resources": [{"title": "Legal aid hotline"}],
}


class ActionPlanViewTests(TestCase):
    """Tests for action_plan view context with and without case data."""

    def setUp(self):
        self.client = Client()

    def test_populated_case_passes_all_context_keys(self):
        """View should pass all 8 data fields plus has_data=True."""
        # Force a session so ownership filter works
        session = self.client.session
        session["force_create"] = True
        session.save()
        self.client.cookies["sessionid"] = session.session_key

        CaseInfo.objects.create(
            session_key=session.session_key, data=SAMPLE_CASE_DATA
        )

        response = self.client.get("/chat/action-plan/")

        self.assertEqual(response.status_code, 200)
        ctx = response.context
        self.assertEqual(ctx["case_type"], "Eviction")
        self.assertEqual(ctx["summary"], "Tenant eviction case")
        self.assertEqual(ctx["court_info"]["court_name"], "Bexar County Justice Court")
        self.assertEqual(ctx["parties"]["user_name"], "Jane Doe")
        self.assertEqual(len(ctx["key_dates"]), 1)
        self.assertEqual(len(ctx["action_items"]), 1)
        self.assertEqual(len(ctx["spotted_issues"]), 1)
        self.assertEqual(len(ctx["resources"]), 1)
        self.assertTrue(ctx["has_data"])

    def test_no_case_returns_empty_defaults(self):
        """View should return empty defaults and has_data=False when no case exists."""
        response = self.client.get("/chat/action-plan/")

        self.assertEqual(response.status_code, 200)
        ctx = response.context
        self.assertEqual(ctx["case_type"], "")
        self.assertEqual(ctx["summary"], "")
        self.assertEqual(ctx["court_info"], {})
        self.assertEqual(ctx["parties"], {})
        self.assertEqual(ctx["key_dates"], [])
        self.assertEqual(ctx["action_items"], [])
        self.assertEqual(ctx["spotted_issues"], [])
        self.assertEqual(ctx["resources"], [])
        self.assertFalse(ctx["has_data"])
