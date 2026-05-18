"""
Tests for custom model behavior in chat app.

Only tests custom code - not Django built-ins like UUIDField, auto_now, etc.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from chat.models import (
    ActionItemModel,
    CaseInfo,
    ChatSession,
    Deadline,
    Message,
    TimelineEvent,
)

User = get_user_model()


@pytest.mark.postgres
class ChatSessionStrTests(TestCase):
    """Tests for ChatSession.__str__ custom formatting."""

    def test_str_includes_username_for_authenticated_user(self):
        """__str__ should show username, not just 'Anonymous'."""
        user = User.objects.create_user(
            username="testuser", password="testpass"
        )
        session = ChatSession.objects.create(user=user)

        result = str(session)

        self.assertIn("testuser", result)
        self.assertNotIn("Anonymous", result)

    def test_str_shows_anonymous_when_no_user(self):
        """__str__ should show 'Anonymous' for sessions without user."""
        session = ChatSession.objects.create(session_key="abc123")

        result = str(session)

        self.assertIn("Anonymous", result)
        self.assertNotIn("testuser", result)


@pytest.mark.postgres
class MessageStrTests(TestCase):
    """Tests for Message.__str__ truncation logic at 50-char boundary."""

    def setUp(self):
        self.session = ChatSession.objects.create()

    def test_str_no_truncation_at_50_chars(self):
        """Content exactly 50 chars should NOT be truncated."""
        content_50 = "x" * 50
        message = Message.objects.create(
            session=self.session,
            data={"role": "user", "content": content_50},
        )

        result = str(message)

        self.assertIn(content_50, result)
        self.assertNotIn("...", result)

    def test_str_truncates_at_51_chars(self):
        """Content at 51 chars should be truncated."""
        content_51 = "x" * 51
        message = Message.objects.create(
            session=self.session,
            data={"role": "user", "content": content_51},
        )

        result = str(message)

        self.assertIn("...", result)
        # Should show first 50 chars + ellipsis
        self.assertIn("x" * 50, result)
        self.assertNotIn("x" * 51, result)

    def test_str_includes_role_prefix(self):
        """__str__ should include the message role."""
        message = Message.objects.create(
            session=self.session,
            data={"role": "assistant", "content": "Hello"},
        )

        result = str(message)

        self.assertIn("assistant", result)


@pytest.mark.postgres
class CaseInfoStrTests(TestCase):
    """Tests for CaseInfo.__str__ custom formatting."""

    def test_str_shows_case_type_and_username(self):
        user = User.objects.create_user(username="jane", password="testpass")
        case = CaseInfo.objects.create(
            user=user, data={"case_type": "Eviction"}
        )

        result = str(case)

        self.assertIn("Eviction", result)
        self.assertIn("jane", result)

    def test_str_shows_anonymous_when_no_user(self):
        case = CaseInfo.objects.create(
            session_key="abc123", data={"case_type": "Eviction"}
        )

        result = str(case)

        self.assertIn("Eviction", result)
        self.assertIn("Anonymous", result)

    def test_str_shows_unknown_when_no_case_type(self):
        case = CaseInfo.objects.create(data={})

        result = str(case)

        self.assertIn("Unknown", result)


@pytest.mark.postgres
class TimelineEventStrTests(TestCase):
    """Tests for TimelineEvent.__str__ display logic."""

    def setUp(self):
        self.case = CaseInfo.objects.create(data={})

    def test_str_uses_title_when_set(self):
        event = TimelineEvent.objects.create(
            case=self.case,
            event_type="upload",
            title="Lease agreement uploaded",
        )

        result = str(event)

        self.assertIn("Document Upload", result)
        self.assertIn("Lease agreement uploaded", result)

    def test_str_falls_back_to_content_when_no_title(self):
        event = TimelineEvent.objects.create(
            case=self.case,
            event_type="summary",
            content="User discussed eviction timeline with assistant",
        )

        result = str(event)

        self.assertIn("Chat Summary", result)
        self.assertIn("User discussed eviction timeline", result)

    def test_str_truncates_content_at_50_chars(self):
        long_content = "x" * 80
        event = TimelineEvent.objects.create(
            case=self.case,
            event_type="change",
            content=long_content,
        )

        result = str(event)

        self.assertIn("x" * 50, result)
        self.assertNotIn("x" * 51, result)

    def test_resolution_event_type_accepted(self):
        """TimelineEvent should accept 'resolution' as a valid event_type."""
        event = TimelineEvent.objects.create(
            case=self.case,
            event_type="resolution",
            title="Case marked as resolved",
        )

        result = str(event)

        self.assertIn("Resolution", result)


@pytest.mark.postgres
class CaseInfoStatusTests(TestCase):
    """Tests for CaseInfo.status field."""

    def test_default_status_is_active(self):
        """New CaseInfo should default to 'active' status."""
        case = CaseInfo.objects.create(data={})

        self.assertEqual(case.status, "active")

    def test_status_accepts_resolved(self):
        case = CaseInfo.objects.create(data={}, status="resolved")

        case.refresh_from_db()

        self.assertEqual(case.status, "resolved")

    def test_status_accepts_archived(self):
        case = CaseInfo.objects.create(data={}, status="archived")

        case.refresh_from_db()

        self.assertEqual(case.status, "archived")


@pytest.mark.postgres
class DeadlineToDictTests(TestCase):
    """Tests for Deadline.to_dict() serialization."""

    def setUp(self):
        self.case = CaseInfo.objects.create(data={})

    def test_to_dict_includes_id_as_string(self):
        """to_dict() must include id as a string (not UUID object)."""
        deadline = Deadline.objects.create(
            case=self.case,
            label="File Answer",
            date="2026-05-01",
            is_deadline=True,
        )

        result = deadline.to_dict()

        self.assertIn("id", result)
        self.assertEqual(result["id"], str(deadline.id))
        self.assertIsInstance(result["id"], str)

    def test_to_dict_includes_reminder_requested(self):
        """to_dict() must include reminder_requested field."""
        deadline = Deadline.objects.create(
            case=self.case,
            label="File Answer",
            date="2026-05-01",
            is_deadline=True,
        )

        result = deadline.to_dict()

        self.assertIn("reminder_requested", result)
        self.assertIs(result["reminder_requested"], False)

    def test_to_dict_reflects_reminder_requested_true(self):
        deadline = Deadline.objects.create(
            case=self.case,
            label="Court Hearing",
            date="2026-06-15",
            reminder_requested=True,
        )

        result = deadline.to_dict()

        self.assertIs(result["reminder_requested"], True)


@pytest.mark.postgres
class ActionItemToDictTests(TestCase):
    """Tests for ActionItemModel.to_dict() serialization."""

    def setUp(self):
        self.case = CaseInfo.objects.create(data={})

    def test_to_dict_includes_id_as_string(self):
        """to_dict() must include id as a string (not UUID object)."""
        item = ActionItemModel.objects.create(
            case=self.case,
            title="Gather documents",
        )

        result = item.to_dict()

        self.assertIn("id", result)
        self.assertIsInstance(result["id"], str)
        self.assertEqual(result["id"], str(item.id))

    def test_to_dict_includes_completed(self):
        """to_dict() must include completed boolean."""
        item = ActionItemModel.objects.create(
            case=self.case,
            title="File paperwork",
            completed=True,
        )

        result = item.to_dict()

        self.assertIn("completed", result)
        self.assertIs(result["completed"], True)

    def test_to_dict_includes_priority(self):
        """to_dict() must include the priority field (#329 sidebar pin)."""
        urgent = ActionItemModel.objects.create(
            case=self.case, title="Call clerk", priority="urgent"
        )
        normal = ActionItemModel.objects.create(
            case=self.case, title="Gather docs", priority="normal"
        )

        self.assertEqual(urgent.to_dict()["priority"], "urgent")
        self.assertEqual(normal.to_dict()["priority"], "normal")


class ActionItemOrderingTests(TestCase):
    """Tests for ActionItemModel default ordering (#329 sidebar pin).

    Urgent items must come before normal items so blockers pin to the
    top of the sidebar. Within a priority bucket, items sort by title.
    """

    def setUp(self):
        self.case = CaseInfo.objects.create(data={})

    def test_urgent_items_come_before_normal(self):
        ActionItemModel.objects.create(
            case=self.case, title="Gather documents", priority="normal"
        )
        ActionItemModel.objects.create(
            case=self.case, title="Call clerk", priority="urgent"
        )
        ActionItemModel.objects.create(
            case=self.case, title="Review lease", priority="normal"
        )

        titles = [item.title for item in self.case.action_items.all()]

        self.assertEqual(titles[0], "Call clerk")
        self.assertEqual(titles[1:], ["Gather documents", "Review lease"])

    def test_within_priority_sorted_by_title(self):
        ActionItemModel.objects.create(
            case=self.case, title="Zebra task", priority="urgent"
        )
        ActionItemModel.objects.create(
            case=self.case, title="Alpha task", priority="urgent"
        )

        titles = [item.title for item in self.case.action_items.all()]

        self.assertEqual(titles, ["Alpha task", "Zebra task"])
