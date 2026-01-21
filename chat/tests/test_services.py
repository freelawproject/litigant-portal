"""
Tests for chat service layer - custom business logic.

Only tests custom code, not Django ORM basics.
"""

from unittest.mock import MagicMock

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings

from chat.agents import agent_registry
from chat.agents.base import Agent, Tool
from chat.models import ChatSession, Document, Message
from chat.services.chat_service import ChatService
from chat.services.search_service import KeywordSearchService

User = get_user_model()


class MockTool(Tool):
    """Mock tool for testing."""

    def __call__(self, agent: Agent) -> str:
        return "Tool executed"


class MockAgent(Agent):
    """Mock agent for testing that yields predictable events."""

    default_model = "mock/model"
    default_tools = []
    default_messages = [
        {"role": "system", "content": "You are a test assistant."}
    ]

    def ping(self) -> bool:
        return True

    def stream_run(self, messages=None, **kwargs):
        """Yield mock events for testing."""
        # Add user message if provided
        if messages is not None:
            if isinstance(messages, str):
                self.add_message({"role": "user", "content": messages})
            else:
                for msg in messages:
                    self.add_message(msg)

        # Add assistant response
        self.add_message({"role": "assistant", "content": "Hello world"})

        yield {"type": "content_delta", "content": "Hello"}
        yield {"type": "content_delta", "content": " world"}
        yield {"type": "done"}


class MockAgentWithTools(Agent):
    """Mock agent that simulates tool calls."""

    default_model = "mock/model"
    default_tools = [MockTool]
    default_messages = [
        {"role": "system", "content": "You are a test assistant with tools."}
    ]

    def ping(self) -> bool:
        return True

    def stream_run(self, messages=None, **kwargs):
        """Yield mock events including tool calls."""
        # Add user message if provided
        if messages is not None:
            if isinstance(messages, str):
                self.add_message({"role": "user", "content": messages})
            else:
                for msg in messages:
                    self.add_message(msg)

        # Add assistant message with tool call
        self.add_message(
            {
                "role": "assistant",
                "content": "Let me check",
                "tool_calls": [
                    {
                        "id": "call_123",
                        "type": "function",
                        "function": {"name": "MockTool", "arguments": "{}"},
                    }
                ],
            }
        )

        # Add tool response
        self.add_message(
            {
                "role": "tool",
                "tool_call_id": "call_123",
                "name": "MockTool",
                "content": "Tool executed",
            }
        )

        # Add final assistant message
        self.add_message({"role": "assistant", "content": " Done!"})

        yield {"type": "content_delta", "content": "Let me check"}
        yield {
            "type": "tool_call",
            "id": "call_123",
            "name": "MockTool",
            "args": {},
        }
        yield {
            "type": "tool_response",
            "id": "call_123",
            "name": "MockTool",
        }
        yield {"type": "content_delta", "content": " Done!"}
        yield {"type": "done"}


class MockAgentError(Agent):
    """Mock agent that raises an error."""

    default_model = "mock/model"
    default_messages = [{"role": "system", "content": "Error agent."}]

    def ping(self) -> bool:
        return True

    def stream_run(self, messages=None, **kwargs):
        raise Exception("Connection refused")


# Register mock agents for testing
agent_registry["MockAgent"] = MockAgent
agent_registry["MockAgentWithTools"] = MockAgentWithTools
agent_registry["MockAgentError"] = MockAgentError


class ChatServiceSessionManagementTests(TestCase):
    """Tests for session creation and retrieval logic."""

    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(DEFAULT_CHAT_AGENT="MockAgent")
    def test_creates_new_session_for_authenticated_user(self):
        """First request from auth user creates a new session."""
        user = User.objects.create_user(
            username="testuser", password="testpass"
        )
        request = self.factory.post("/chat/stream/")
        request.user = user
        request.session = MagicMock()
        request.session.session_key = None
        request.session.create = MagicMock()

        chat = ChatService(request)

        self.assertEqual(chat.agent.session.user, user)
        self.assertEqual(ChatSession.objects.count(), 1)

    @override_settings(DEFAULT_CHAT_AGENT="MockAgent")
    def test_loads_existing_session_by_id(self):
        """Providing a session_id loads that session."""
        user = User.objects.create_user(
            username="testuser", password="testpass"
        )
        existing = ChatSession.objects.create(user=user)
        # Add a system message to the session
        Message.objects.create(
            session=existing,
            data={"role": "system", "content": "You are a test assistant."},
        )

        request = self.factory.post("/chat/stream/")
        request.user = user
        request.session = MagicMock()
        request.session.session_key = None

        chat = ChatService(request, session_id=existing.id)

        self.assertEqual(chat.agent.session.id, existing.id)

    @override_settings(DEFAULT_CHAT_AGENT="MockAgent")
    def test_anonymous_user_gets_session_by_session_key(self):
        """Anonymous users are tracked by Django session key."""
        request = self.factory.post("/chat/stream/")
        request.user = MagicMock(is_authenticated=False)
        request.session = MagicMock()
        request.session.session_key = "test-session-key"

        chat = ChatService(request)

        self.assertIsNone(chat.agent.session.user)
        self.assertEqual(chat.agent.session.session_key, "test-session-key")

    @override_settings(DEFAULT_CHAT_AGENT="MockAgent")
    def test_creates_django_session_if_missing(self):
        """Should create Django session for anonymous user if none exists."""
        request = self.factory.post("/chat/stream/")
        request.user = MagicMock(is_authenticated=False)
        request.session = MagicMock()
        request.session.session_key = None

        def set_key():
            request.session.session_key = "new-key"

        request.session.create.side_effect = set_key

        ChatService(request)

        request.session.create.assert_called_once()

    @override_settings(DEFAULT_CHAT_AGENT="MockAgent")
    def test_raises_for_invalid_session_id(self):
        """Raises ValueError for non-existent session ID."""
        request = self.factory.post("/chat/stream/")
        request.user = MagicMock(is_authenticated=False)
        request.session = MagicMock()
        request.session.session_key = "test-key"

        with self.assertRaises(ValueError) as ctx:
            ChatService(
                request, session_id="00000000-0000-0000-0000-000000000000"
            )

        self.assertIn("not found", str(ctx.exception))

    @override_settings(DEFAULT_CHAT_AGENT="MockAgent")
    def test_raises_for_unauthorized_session_access(self):
        """Raises PermissionError when user doesn't own the session."""
        other_user = User.objects.create_user(
            username="other", password="pass"
        )
        session = ChatSession.objects.create(user=other_user)

        user = User.objects.create_user(
            username="testuser", password="testpass"
        )
        request = self.factory.post("/chat/stream/")
        request.user = user
        request.session = MagicMock()
        request.session.session_key = None

        with self.assertRaises(PermissionError):
            ChatService(request, session_id=session.id)


class ChatServiceInitializationTests(TestCase):
    """Tests for session initialization and default messages."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="testuser", password="testpass"
        )

    @override_settings(DEFAULT_CHAT_AGENT="MockAgent")
    def test_new_session_saves_default_messages(self):
        """New session should save agent's default messages (system prompt)."""
        request = self.factory.post("/chat/stream/")
        request.user = self.user
        request.session = MagicMock()
        request.session.session_key = None

        chat = ChatService(request)

        # Should have saved the system message from MockAgent.default_messages
        messages = list(chat.agent.session.messages.all())
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].role, "system")
        self.assertIn("test assistant", messages[0].content.lower())

    @override_settings(DEFAULT_CHAT_AGENT="MockAgent")
    def test_existing_session_does_not_duplicate_messages(self):
        """Loading existing session should not re-save default messages."""
        request = self.factory.post("/chat/stream/")
        request.user = self.user
        request.session = MagicMock()
        request.session.session_key = None

        # Create initial session
        chat1 = ChatService(request)
        session_id = chat1.agent.session.id
        initial_count = chat1.agent.session.messages.count()

        # Load the same session
        chat2 = ChatService(request, session_id=session_id)

        # Should not have added more messages
        self.assertEqual(chat2.agent.session.messages.count(), initial_count)


class ChatServiceStreamTests(TestCase):
    """Tests for stream method and message saving."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="testuser", password="testpass"
        )

    @override_settings(DEFAULT_CHAT_AGENT="MockAgent")
    def test_stream_saves_user_and_assistant_messages(self):
        """Stream should save both user message and assistant response."""
        request = self.factory.post("/chat/stream/")
        request.user = self.user
        request.session = MagicMock()
        request.session.session_key = None

        chat = ChatService(request)
        response = chat.stream("Hello")

        # Consume the generator to trigger message saving
        list(response.streaming_content)

        # Should have: system, user, assistant
        messages = list(chat.agent.session.messages.order_by("created_at"))
        roles = [m.role for m in messages]
        self.assertEqual(roles, ["system", "user", "assistant"])

        # Check content
        user_msg = messages[1]
        self.assertEqual(user_msg.content, "Hello")

        assistant_msg = messages[2]
        self.assertEqual(assistant_msg.content, "Hello world")

    @override_settings(DEFAULT_CHAT_AGENT="MockAgentError")
    def test_stream_handles_error(self):
        """Agent failure should yield error event."""
        request = self.factory.post("/chat/stream/")
        request.user = self.user
        request.session = MagicMock()
        request.session.session_key = None

        chat = ChatService(request)
        response = chat.stream("Hello")

        # Consume the generator to trigger error handling
        content = b"".join(response.streaming_content)

        self.assertIn(b'"type": "error"', content)

    @override_settings(DEFAULT_CHAT_AGENT="MockAgent")
    def test_stream_includes_session_event(self):
        """Stream should include session event with session_id."""
        request = self.factory.post("/chat/stream/")
        request.user = self.user
        request.session = MagicMock()
        request.session.session_key = None

        chat = ChatService(request)
        response = chat.stream("Hello")
        content = b"".join(response.streaming_content)

        self.assertIn(b'"type": "session"', content)
        self.assertIn(str(chat.agent.session.id).encode(), content)

    @override_settings(DEFAULT_CHAT_AGENT="MockAgent")
    def test_stream_includes_done_event(self):
        """Stream should include done event."""
        request = self.factory.post("/chat/stream/")
        request.user = self.user
        request.session = MagicMock()
        request.session.session_key = None

        chat = ChatService(request)
        response = chat.stream("Hello")
        content = list(response.streaming_content)

        self.assertTrue(any(b'"type": "done"' in chunk for chunk in content))

    @override_settings(DEFAULT_CHAT_AGENT="MockAgentWithTools")
    def test_stream_saves_tool_messages(self):
        """Stream should save tool call and tool response messages."""
        request = self.factory.post("/chat/stream/")
        request.user = self.user
        request.session = MagicMock()
        request.session.session_key = None

        chat = ChatService(request)
        response = chat.stream("Hello")
        list(response.streaming_content)

        # Check all message types were saved
        messages = list(chat.agent.session.messages.order_by("created_at"))
        roles = [m.role for m in messages]

        # Should have: system, user, assistant (with tool_calls), tool, assistant
        self.assertIn("system", roles)
        self.assertIn("user", roles)
        self.assertIn("assistant", roles)
        self.assertIn("tool", roles)

        # Find the assistant message with tool_calls
        assistant_with_tools = [
            m
            for m in messages
            if m.role == "assistant" and m.data.get("tool_calls")
        ]
        self.assertEqual(len(assistant_with_tools), 1)

        # Find the tool response message
        tool_msg = [m for m in messages if m.role == "tool"][0]
        self.assertEqual(tool_msg.data.get("name"), "MockTool")


class KeywordSearchTests(TestCase):
    """Tests for keyword search service logic."""

    def setUp(self):
        self.service = KeywordSearchService()

    def test_empty_query_returns_empty(self):
        """Empty/whitespace queries should return no results."""
        Document.objects.create(
            title="Test", content="Content", category="test"
        )

        results = list(self.service.search(""))
        results_whitespace = list(self.service.search("   "))

        self.assertEqual(results, [])
        self.assertEqual(results_whitespace, [])

    def test_category_filter_works(self):
        """Category parameter should filter results."""
        Document.objects.create(
            title="Doc 1", content="legal info", category="family"
        )
        Document.objects.create(
            title="Doc 2", content="legal info", category="tax"
        )

        results = list(self.service.search("legal", category="family"))

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].category, "family")

    def test_limit_parameter_works(self):
        """Limit should cap the number of results."""
        for i in range(10):
            Document.objects.create(
                title=f"Doc {i}", content="test content", category="test"
            )

        results = list(self.service.search("test", limit=3))

        self.assertEqual(len(results), 3)


class KeywordSearchCategoriesTests(TestCase):
    """Tests for category listing."""

    def setUp(self):
        self.service = KeywordSearchService()

    def test_get_categories_returns_unique_values(self):
        """Should return unique categories, not duplicates."""
        Document.objects.create(title="A", content="c", category="family")
        Document.objects.create(title="B", content="c", category="family")
        Document.objects.create(title="C", content="c", category="tax")

        categories = self.service.get_categories()

        self.assertEqual(len(categories), 2)
        self.assertIn("family", categories)
        self.assertIn("tax", categories)

    def test_get_categories_sorted_alphabetically(self):
        """Categories should be in alphabetical order."""
        Document.objects.create(title="A", content="c", category="tax")
        Document.objects.create(title="B", content="c", category="criminal")
        Document.objects.create(title="C", content="c", category="family")

        categories = self.service.get_categories()

        self.assertEqual(categories, ["criminal", "family", "tax"])
