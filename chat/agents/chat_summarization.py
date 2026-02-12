from .base import Agent

SYSTEM_PROMPT = """\
The user will submit a conversation history in their first message.
Summarize ONLY the questions the USER explicitly typed and their answers.

IMPORTANT RULES:
- Only include questions that appear after "USER:" in the conversation
- SKIP any document analysis (messages about "I've analyzed your document...")
- SKIP questions the assistant generated or suggested
- If the user only uploaded a file and didn't ask follow-up questions, respond with just: "No user questions asked."

Format (only for actual user questions):
Q: [The user's actual question]
A: [Specific answer with details: addresses, costs, times, deadlines. If no specifics, note that.]

Example - user asked a real question:
Q: Where can I park at DuPage County Courthouse?
A: Parking garage at 505 N County Farm Rd, $6/day. Street meters on County Farm Rd.

Example - user only uploaded a file, no questions:
No user questions asked."""


class ChatSummarizationAgent(Agent):
    """An agent that summarizes chat conversations into Q&A pairs."""

    default_model = "groq/llama-3.3-70b-versatile"
    default_messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]
    default_completion_args = {
        "max_tokens": 1024,
    }

    def __call__(self, message_history: list[dict]) -> str | None:
        """Generate a summary of from a conversation history."""
        conversation_text = "\n".join(
            f"{msg.get('role', 'unknown').upper()}: {msg.get('content', '')}"
            for msg in message_history
            if msg.get("content")
        )
        for _ in self.stream_run(messages=conversation_text):
            pass
        return self.messages[-1].get("content", None)
