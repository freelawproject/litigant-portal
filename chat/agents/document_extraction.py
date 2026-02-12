import json
from typing import Any

from .base import Agent, Field, Tool

SYSTEM_PROMPT = """\
You are a legal document analyzer. Extract structured information from \
the provided legal document text. Return a JSON object matching the \
provided schema.

Guidelines:
- If information is not found, use null for optional fields
- For dates, try to parse them into YYYY-MM-DD format when possible
- Focus on deadlines that require action from the document recipient
- The summary should be helpful and reassuring, not alarming
- Be conservative with confidence scores - lower if text is unclear \
or partially extracted"""


class KeyDate(Tool):
    """A date extracted from a legal document."""

    label: str = Field("", description="Description of what the date is for")
    date: str = Field(
        "",
        description="The date in YYYY-MM-DD format if possible, "
        "otherwise as written",
    )
    is_deadline: bool = Field(
        False,
        description="True if this is a deadline the user needs to act on",
    )


class CourtInfo(Tool):
    """Court information extracted from a document."""

    county: str | None = Field(
        None, description="The county name if mentioned"
    )
    court_name: str | None = Field(
        None, description="The full court name if mentioned"
    )
    case_number: str | None = Field(
        None, description="The case/cause number if present"
    )
    address: str | None = Field(
        None, description="Full street address of the courthouse"
    )
    phone: str | None = Field(None, description="Court phone number")
    email: str | None = Field(None, description="Court email or clerk email")


class Parties(Tool):
    """Parties involved in the case."""

    user_name: str | None = Field(
        None,
        description="The name of the person who likely received this "
        "document (defendant in eviction, respondent, etc.)",
    )
    user_address: str | None = Field(
        None, description="User's address if shown"
    )
    opposing_party: str | None = Field(
        None,
        description="The other party (plaintiff, petitioner, landlord, etc.)",
    )
    opposing_address: str | None = Field(
        None, description="Opposing party's address"
    )
    opposing_phone: str | None = Field(
        None, description="Opposing party's phone number"
    )
    opposing_email: str | None = Field(
        None, description="Opposing party's email"
    )
    opposing_website: str | None = Field(
        None, description="Opposing party's website if shown"
    )
    attorney_name: str | None = Field(
        None, description="Attorney name if represented"
    )
    attorney_phone: str | None = Field(None, description="Attorney phone")
    attorney_email: str | None = Field(None, description="Attorney email")


class CourtDocumentData(Tool):
    """Structured data extracted from a legal document."""

    case_type: str = Field(
        "",
        description="The type of legal matter (e.g., 'Eviction', "
        "'Small Claims', 'Divorce', 'Child Custody', 'Debt Collection')",
    )
    court_info: CourtInfo
    parties: Parties
    key_dates: list[KeyDate]
    summary: str = Field(
        "",
        description="A concise, actionable summary with SPECIFIC details: "
        "what action is required, exact deadline dates, court address if "
        "shown, and consequences of not acting. Include actual dates, "
        "addresses, amounts - not vague descriptions.",
    )
    confidence: float = Field(
        0.0,
        description="How confident you are in the extraction accuracy",
        ge=0,
        le=1,
    )


class DocumentExtractionAgent(Agent):
    """An agent that extracts structured case data from legal documents."""

    default_model = "groq/llama-3.3-70b-versatile"
    default_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    default_completion_args = {
        "max_tokens": 2048,
        "response_format": CourtDocumentData,
    }

    def __call__(self, document_text: str) -> dict[str, Any] | None:
        """Extract structured information from a legal document."""
        for _ in self.stream_run(document_text):
            pass
        result = self.messages[-1].get("content", None)
        if result is not None:
            return json.loads(result)
        return None
