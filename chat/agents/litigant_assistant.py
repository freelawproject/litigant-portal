from pydantic import BaseModel

from .base import Agent, Field, Tool, ToolOutput

SYSTEM_PROMPT = """You are a compassionate legal assistant helping self-represented \
litigants understand their situation and navigate the legal system.

FACT GATHERING (PRIORITY ONE)
Your first goal is to understand the facts of the user's case through natural \
conversation. As users describe their situation, ask clarifying questions to uncover:
- Who the other party is (landlord name, company name, etc.)
- Key dates (when they received notices, hearing dates, deadlines)
- Where the case is (court name, county)
- What type of legal matter this is (eviction, small claims, etc.)
- Case or docket number if they have paperwork

Call UpdateCaseFacts immediately whenever you learn any fact — don't wait until you \
know everything. Partial updates as facts emerge are preferred. For example, if the \
user says "my landlord Acme Properties sent me an eviction notice," call \
UpdateCaseFacts right away with what you know.

DOCUMENT UPLOADS
The app has a document upload feature. Users can upload PDF documents using the \
upload button (document icon) next to the chat input. When they ask about uploading \
documents, tell them to click the upload button. Do NOT say you cannot receive \
files — the app handles PDF uploads and extracts the text for you automatically.

When the user uploads a legal document, you'll receive context in a [Document \
Context] block. Use this information to:
- Reference specific deadlines and urge timely action when applicable
- Explain what the document means for the user in plain language
- Suggest concrete next steps based on the case type and deadlines
- Ask clarifying questions to better assist them

COMMUNICATION STYLE
- Plain language, no legal jargon
- Empathetic and reassuring — people are often frightened when dealing with legal issues
- Format responses using markdown: **bold** for key info, bullet lists for steps, \
clear paragraph breaks
- Keep responses concise and focused
- Always recommend consulting with a licensed attorney for specific legal advice"""


class FactDate(BaseModel):
    """A date or deadline discovered in conversation."""

    label: str = Field(
        description="What this date is for (e.g. 'Eviction hearing', 'Notice date')"
    )
    date: str = Field(
        description="The date in YYYY-MM-DD format if known, otherwise as stated"
    )
    is_deadline: bool = Field(
        False,
        description="True if the user must take action by this date",
    )


class UpdateCaseFacts(Tool):
    """Update the user's briefcase with facts discovered in conversation.

    Call this tool immediately when you learn any fact about the user's case:
    party names, dates, court location, case type, or case number. Call it
    as soon as you have facts — partial updates are fine and preferred.
    Do not wait until you know everything.
    """

    case_type: str | None = Field(
        None,
        description="Type of legal case, e.g. 'Eviction', 'Small Claims', 'Divorce'",
    )
    opposing_party: str | None = Field(
        None,
        description="Name of the opposing party (landlord, plaintiff, company, etc.)",
    )
    opposing_address: str | None = Field(
        None,
        description="Address of the opposing party",
    )
    court_name: str | None = Field(
        None,
        description="Full name of the court",
    )
    court_county: str | None = Field(
        None,
        description="County where the court is located",
    )
    case_number: str | None = Field(
        None,
        description="Case number, docket number, or cause number",
    )
    new_dates: list[FactDate] | None = Field(
        None,
        description="New dates or deadlines discovered in this exchange",
    )

    def __call__(self, agent: "Agent") -> ToolOutput:
        from chat.models import CaseInfo

        # Build a patch dict in CaseInfo data format (same shape as extracted docs)
        patch: dict = {}

        if self.case_type:
            patch["case_type"] = self.case_type

        parties: dict = {}
        if self.opposing_party:
            parties["opposing_party"] = self.opposing_party
        if self.opposing_address:
            parties["opposing_address"] = self.opposing_address
        if parties:
            patch["parties"] = parties

        court_info: dict = {}
        if self.court_name:
            court_info["court_name"] = self.court_name
        if self.court_county:
            court_info["county"] = self.court_county
        if self.case_number:
            court_info["case_number"] = self.case_number
        if court_info:
            patch["court_info"] = court_info

        if self.new_dates:
            patch["key_dates"] = [
                {
                    "label": d.label,
                    "date": d.date,
                    "is_deadline": d.is_deadline,
                }
                for d in self.new_dates
            ]

        # Persist: merge patch into existing CaseInfo for this session's owner
        if agent.session:
            session = agent.session
            ownership = (
                {"user": session.user}
                if session.user
                else {"session_key": session.session_key}
            )
            case, _ = CaseInfo.objects.get_or_create(**ownership)
            data = dict(case.data) if case.data else {}

            if "case_type" in patch:
                data["case_type"] = patch["case_type"]

            if "court_info" in patch:
                data.setdefault("court_info", {})
                data["court_info"].update(patch["court_info"])

            if "parties" in patch:
                data.setdefault("parties", {})
                data["parties"].update(patch["parties"])

            if "key_dates" in patch:
                existing = data.get("key_dates", [])
                for new_date in patch["key_dates"]:
                    already_present = any(
                        d["label"] == new_date["label"]
                        and d["date"] == new_date["date"]
                        for d in existing
                    )
                    if not already_present:
                        existing.append(new_date)
                data["key_dates"] = existing

            case.data = data
            case.save()

        return ToolOutput(
            response="Case facts noted.",
            data={"case_patch": patch},
        )


class LitigantAssistantAgent(Agent):
    """Main agent for the litigant portal assistant."""

    default_tools = [UpdateCaseFacts]
    default_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
