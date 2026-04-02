from typing import Literal

from pydantic import BaseModel

from chat.prompts import build_system_prompt

from .base import Agent, Field, Tool, ToolOutput


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


class ActionItem(BaseModel):
    """A concrete next step the user should take."""

    title: str = Field(
        description="Short action title (e.g. 'File an Appearance')"
    )
    description: str = Field(
        "", description="Why this matters and how to do it"
    )
    priority: Literal["urgent", "normal"] = Field(
        "normal",
        description="'urgent' for deadline-sensitive, 'normal' otherwise",
    )
    deadline: str | None = Field(
        None, description="Due date in YYYY-MM-DD format if applicable"
    )
    href: str | None = Field(
        None, description="URL to a resource or form if applicable"
    )


class SpottedIssue(BaseModel):
    """A legal issue, defense, or right identified from conversation."""

    title: str = Field(description="Short label (e.g. 'Habitability defense')")
    description: str = Field(
        "", description="Plain-language explanation of why this applies"
    )
    statute: str | None = Field(
        None,
        description="Statute citation if applicable (e.g. '765 ILCS 735/2')",
    )


class Resource(BaseModel):
    """A program, service, or organization the user may benefit from."""

    title: str = Field(
        description="Name of the resource (e.g. 'Illinois Rental Payment Program')"
    )
    description: str = Field(
        "", description="What it is and why it's relevant"
    )
    href: str | None = Field(None, description="URL if available")


class UpdateCaseFacts(Tool):
    """Update the user's briefcase with facts discovered in conversation.

    Call this tool immediately when you learn any fact about the user's case:
    party names, dates, court location, case type, contact info, or attorney
    details. Call it as soon as you have facts — partial updates are fine and
    preferred. Do not wait until you know everything.

    NOTE: Field schema mirrors chat.agents.document_extraction.CourtDocumentData.
    Keep both in sync until #207 consolidates them.
    """

    case_type: str | None = Field(
        None,
        description="Type of legal case, e.g. 'Eviction', 'Small Claims', 'Divorce'",
    )
    summary: str | None = Field(
        None,
        description="Brief summary of the case so far",
    )

    # Court info
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
    court_address: str | None = Field(
        None,
        description="Full street address of the courthouse",
    )
    court_phone: str | None = Field(
        None,
        description="Court phone number",
    )
    court_email: str | None = Field(
        None,
        description="Court email or clerk email",
    )

    # Parties — user
    user_name: str | None = Field(
        None,
        description="The user's name as it appears on court paperwork",
    )
    user_address: str | None = Field(
        None,
        description="The user's address",
    )

    # Parties — opposing
    opposing_party: str | None = Field(
        None,
        description="Name of the opposing party (landlord, plaintiff, company, etc.)",
    )
    opposing_address: str | None = Field(
        None,
        description="Address of the opposing party",
    )
    opposing_phone: str | None = Field(
        None,
        description="Opposing party's phone number",
    )
    opposing_email: str | None = Field(
        None,
        description="Opposing party's email",
    )
    opposing_website: str | None = Field(
        None,
        description="Opposing party's website",
    )

    # Parties — attorney
    attorney_name: str | None = Field(
        None,
        description="Attorney name if the opposing side is represented",
    )
    attorney_phone: str | None = Field(
        None,
        description="Attorney phone number",
    )
    attorney_email: str | None = Field(
        None,
        description="Attorney email",
    )

    # Dates
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
        if self.summary:
            patch["summary"] = self.summary

        # Court info — mirrors document_extraction.CourtInfo fields
        court_info: dict = {}
        for attr, key in [
            ("court_name", "court_name"),
            ("court_county", "county"),
            ("case_number", "case_number"),
            ("court_address", "address"),
            ("court_phone", "phone"),
            ("court_email", "email"),
        ]:
            value = getattr(self, attr)
            if value:
                court_info[key] = value
        if court_info:
            patch["court_info"] = court_info

        # Parties — mirrors document_extraction.Parties fields
        parties: dict = {}
        for attr in [
            "user_name",
            "user_address",
            "opposing_party",
            "opposing_address",
            "opposing_phone",
            "opposing_email",
            "opposing_website",
            "attorney_name",
            "attorney_phone",
            "attorney_email",
        ]:
            value = getattr(self, attr)
            if value:
                parties[attr] = value
        if parties:
            patch["parties"] = parties

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
            if "summary" in patch:
                data["summary"] = patch["summary"]

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


class UpdateActionPlan(Tool):
    """Update the user's action plan with next steps, spotted issues, and resources.

    Call this tool when you:
    - Identify a legal defense or right that applies to the user's situation
    - Discover an assistance program the user may qualify for
    - Surface a filing requirement or concrete next step
    - Find a resource (legal aid, self-help center, program) relevant to them

    Call it incrementally as issues emerge — don't wait until the end of the
    conversation. Each call adds to (not replaces) the existing action plan.
    """

    new_action_items: list[ActionItem] | None = Field(
        None,
        description="Concrete next steps for the user to take",
    )
    new_spotted_issues: list[SpottedIssue] | None = Field(
        None,
        description="Legal issues, defenses, or rights you've identified",
    )
    new_resources: list[Resource] | None = Field(
        None,
        description="Programs, services, or organizations the user may benefit from",
    )

    def __call__(self, agent: "Agent") -> ToolOutput:
        from chat.models import CaseInfo

        patch: dict = {}

        if self.new_action_items:
            patch["action_items"] = [
                item.model_dump(exclude_none=True)
                for item in self.new_action_items
            ]

        if self.new_spotted_issues:
            patch["spotted_issues"] = [
                issue.model_dump(exclude_none=True)
                for issue in self.new_spotted_issues
            ]

        if self.new_resources:
            patch["resources"] = [
                resource.model_dump(exclude_none=True)
                for resource in self.new_resources
            ]

        # Persist: append to existing action plan in CaseInfo
        if agent.session:
            session = agent.session
            ownership = (
                {"user": session.user}
                if session.user
                else {"session_key": session.session_key}
            )
            case, _ = CaseInfo.objects.get_or_create(**ownership)
            data = dict(case.data) if case.data else {}

            for key in ("action_items", "spotted_issues", "resources"):
                if key in patch:
                    existing = data.get(key, [])
                    for new_item in patch[key]:
                        already_present = any(
                            item["title"] == new_item["title"]
                            for item in existing
                        )
                        if not already_present:
                            existing.append(new_item)
                    data[key] = existing

            case.data = data
            case.save()

        return ToolOutput(
            response="Action plan updated.",
            data={"action_plan_patch": patch},
        )


class LitigantAssistantAgent(Agent):
    """Main agent for the litigant portal assistant.

    System prompt is composed from base + optional topic/jurisdiction layers
    via chat.prompts.build_system_prompt(). For the beta demo, the eviction/IL
    layer bakes domain knowledge directly into the prompt ("fake RAG").

    Topic and jurisdiction can be passed as kwargs to from_session_id() or
    __init__() to activate topic-specific prompt layers.
    """

    default_tools = [UpdateCaseFacts, UpdateActionPlan]
    default_messages = [{"role": "system", "content": build_system_prompt()}]

    def __init__(
        self,
        topic: str | None = None,
        jurisdiction: str | None = None,
        **kwargs,
    ):
        if topic or jurisdiction:
            prompt = build_system_prompt(
                topic=topic, jurisdiction=jurisdiction
            )
            if "messages" not in kwargs:
                kwargs["messages"] = [{"role": "system", "content": prompt}]
        super().__init__(**kwargs)
