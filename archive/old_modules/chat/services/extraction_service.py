"""Document extraction service using LLM for structured data extraction."""

import logging
from dataclasses import dataclass, field
from typing import Any

from chat.providers.base import ChatMessage
from chat.providers.factory import get_provider

logger = logging.getLogger(__name__)

EXTRACTION_SYSTEM_PROMPT = """You are a legal document analyzer. Extract structured information from the provided legal document text.

Return a JSON object with the following structure:
{
    "case_type": "string - The type of legal matter (e.g., 'Eviction', 'Small Claims', 'Divorce', 'Child Custody', 'Debt Collection')",
    "court_info": {
        "county": "string or null - The county name if mentioned",
        "court_name": "string or null - The full court name if mentioned",
        "case_number": "string or null - The case/cause number if present",
        "address": "string or null - Full street address of the courthouse",
        "phone": "string or null - Court phone number",
        "email": "string or null - Court email or clerk email"
    },
    "parties": {
        "user_name": "string or null - The name of the person who likely received this document (defendant in eviction, respondent, etc.)",
        "user_address": "string or null - User's address if shown",
        "opposing_party": "string or null - The other party (plaintiff, petitioner, landlord, etc.)",
        "opposing_address": "string or null - Opposing party's address",
        "opposing_phone": "string or null - Opposing party's phone number",
        "opposing_email": "string or null - Opposing party's email",
        "opposing_website": "string or null - Opposing party's website if shown",
        "attorney_name": "string or null - Attorney name if represented",
        "attorney_phone": "string or null - Attorney phone",
        "attorney_email": "string or null - Attorney email"
    },
    "key_dates": [
        {
            "label": "string - Description of what the date is for",
            "date": "string - The date in YYYY-MM-DD format if possible, otherwise as written",
            "is_deadline": "boolean - True if this is a deadline the user needs to act on"
        }
    ],
    "summary": "string - A concise, actionable summary with SPECIFIC details: what action is required, exact deadline dates, court address if shown, and consequences of not acting. Example: 'You must appear at 505 N County Farm Rd, Wheaton IL on Feb 14, 2026 at 9:00 AM for your eviction hearing. If you don't appear, the judge may rule against you.' Include actual dates, addresses, amounts - not vague descriptions.",
    "confidence": "number between 0 and 1 - How confident you are in the extraction accuracy"
}

Guidelines:
- If information is not found, use null for optional fields
- For dates, try to parse them into YYYY-MM-DD format when possible
- Focus on deadlines that require action from the document recipient
- The summary should be helpful and reassuring, not alarming
- Be conservative with confidence scores - lower if text is unclear or partially extracted"""


@dataclass
class KeyDate:
    """A date extracted from a legal document."""

    label: str
    date: str
    is_deadline: bool = False


@dataclass
class CourtInfo:
    """Court information extracted from a document."""

    county: str | None = None
    court_name: str | None = None
    case_number: str | None = None
    address: str | None = None
    phone: str | None = None
    email: str | None = None


@dataclass
class Parties:
    """Parties involved in the case."""

    user_name: str | None = None
    user_address: str | None = None
    opposing_party: str | None = None
    opposing_address: str | None = None
    opposing_phone: str | None = None
    opposing_email: str | None = None
    opposing_website: str | None = None
    attorney_name: str | None = None
    attorney_phone: str | None = None
    attorney_email: str | None = None


@dataclass
class ExtractionResult:
    """Result of document extraction."""

    success: bool
    case_type: str = ""
    court_info: CourtInfo = field(default_factory=CourtInfo)
    parties: Parties = field(default_factory=Parties)
    key_dates: list[KeyDate] = field(default_factory=list)
    summary: str = ""
    confidence: float = 0.0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "case_type": self.case_type,
            "court_info": {
                "county": self.court_info.county,
                "court_name": self.court_info.court_name,
                "case_number": self.court_info.case_number,
                "address": self.court_info.address,
                "phone": self.court_info.phone,
                "email": self.court_info.email,
            },
            "parties": {
                "user_name": self.parties.user_name,
                "user_address": self.parties.user_address,
                "opposing_party": self.parties.opposing_party,
                "opposing_address": self.parties.opposing_address,
                "opposing_phone": self.parties.opposing_phone,
                "opposing_email": self.parties.opposing_email,
                "opposing_website": self.parties.opposing_website,
                "attorney_name": self.parties.attorney_name,
                "attorney_phone": self.parties.attorney_phone,
                "attorney_email": self.parties.attorney_email,
            },
            "key_dates": [
                {
                    "label": d.label,
                    "date": d.date,
                    "is_deadline": d.is_deadline,
                }
                for d in self.key_dates
            ],
            "summary": self.summary,
            "confidence": self.confidence,
            "error": self.error,
        }


class ExtractionService:
    """Service for extracting structured data from legal documents."""

    def extract_from_text(self, document_text: str) -> ExtractionResult:
        """
        Extract structured information from document text using LLM.

        Args:
            document_text: The full text extracted from the PDF.

        Returns:
            ExtractionResult with structured data or error.
        """
        if not document_text or not document_text.strip():
            return ExtractionResult(
                success=False,
                error="No document text provided",
            )

        try:
            provider = get_provider()

            # Prepare the message with document text
            messages = [
                ChatMessage(
                    role="user",
                    content=f"Please analyze this legal document and extract the relevant information:\n\n{document_text}",
                )
            ]

            # Get structured JSON response
            result = provider.generate_json_response(
                messages=messages,
                system_prompt=EXTRACTION_SYSTEM_PROMPT,
            )

            return self._parse_extraction_result(result)

        except Exception as e:
            logger.error(f"Error extracting document info: {e}")
            return ExtractionResult(
                success=False,
                error="Failed to analyze document. Please try again.",
            )

    def _parse_extraction_result(
        self, raw_result: dict[str, Any]
    ) -> ExtractionResult:
        """Parse raw LLM output into ExtractionResult."""
        try:
            # Parse court info
            court_data = raw_result.get("court_info", {})
            court_info = CourtInfo(
                county=court_data.get("county"),
                court_name=court_data.get("court_name"),
                case_number=court_data.get("case_number"),
                address=court_data.get("address"),
                phone=court_data.get("phone"),
                email=court_data.get("email"),
            )

            # Parse parties
            parties_data = raw_result.get("parties", {})
            parties = Parties(
                user_name=parties_data.get("user_name"),
                user_address=parties_data.get("user_address"),
                opposing_party=parties_data.get("opposing_party"),
                opposing_address=parties_data.get("opposing_address"),
                opposing_phone=parties_data.get("opposing_phone"),
                opposing_email=parties_data.get("opposing_email"),
                opposing_website=parties_data.get("opposing_website"),
                attorney_name=parties_data.get("attorney_name"),
                attorney_phone=parties_data.get("attorney_phone"),
                attorney_email=parties_data.get("attorney_email"),
            )

            # Parse key dates
            key_dates = []
            for date_data in raw_result.get("key_dates", []):
                key_dates.append(
                    KeyDate(
                        label=date_data.get("label", ""),
                        date=date_data.get("date", ""),
                        is_deadline=date_data.get("is_deadline", False),
                    )
                )

            return ExtractionResult(
                success=True,
                case_type=raw_result.get("case_type", ""),
                court_info=court_info,
                parties=parties,
                key_dates=key_dates,
                summary=raw_result.get("summary", ""),
                confidence=float(raw_result.get("confidence", 0.0)),
            )

        except Exception as e:
            logger.error(f"Error parsing extraction result: {e}")
            return ExtractionResult(
                success=False,
                error="Failed to parse document analysis results.",
            )


# Singleton instance
extraction_service = ExtractionService()
