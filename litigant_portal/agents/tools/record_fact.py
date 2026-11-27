from typing import Any

from litigant_portal.agents.base import Field, Tool, ToolOutput
from litigant_portal.app.topic_flow.formatting import format_answer
from litigant_portal.state.types import FactInputType


class RecordFact(Tool):
    """Save facts the user states as answers to the portal's variables.

    Call this as soon as the user states a fact; do not ask permission
    first. Save every fact the user volunteers in one call; the reply
    shape rule in the system prompt says what to ask next. Use exact variable
    names (the loaded flow lists them) and typed values (ISO dates,
    listed choice values); a null value clears a saved answer. Saves are
    unconfirmed suggestions the user reviews later; when the user
    corrects a fact, save the new value. Never save a guess or a default
    the user has not voiced (confirming a value you stated counts as
    voiced), and confirm first when a value looks impossible for the
    jurisdiction, like a county that does not exist in the state.
    """

    facts: dict[str, Any] = Field(
        description=(
            "Mapping of variable name to value, e.g. "
            '{"county": "Burleigh", "date_of_birth": "1990-01-31"}. '
            "To re-save a listed fact, pass its `value`, not its "
            "`display_value`."
        )
    )
    evidence: dict[str, dict[str, str | None]] = Field(
        default_factory=dict,
        description=(
            "Optional supporting evidence keyed by variable name, e.g. "
            '{"county": {"quote": "I live in Burleigh County."}}. '
            "Use a short excerpt copied verbatim from the user's message, "
            "the document, or its QueryDocument response; never reconstruct it. "
            "For document excerpts, also include the document's upload_id. "
            "For unchanged answers, evidence is added only when none is "
            "stored; existing evidence is kept."
        ),
    )

    tool_call_template = "tools/record_fact_call.html"
    tool_result_template = "tools/record_fact_result.html"

    def __call__(self, *, thread_id) -> ToolOutput:
        from django.core.exceptions import ValidationError

        from litigant_portal.app.models import Variable
        from litigant_portal.app.selectors.chat_engine import (
            chat_thread_identity_get,
        )
        from litigant_portal.app.services.topic_flow import (
            variable_answers_record,
            variable_value_validate,
        )

        if not self.facts:
            return ToolOutput(
                result=(
                    "Error: no facts were given. Pass a mapping of variable "
                    "names to values."
                )
            )

        identity = chat_thread_identity_get(thread_id=thread_id)
        # No in_schema=False writes: the facts prompt never lists those.
        variables = {
            v.name: v
            for v in Variable.objects.filter(
                name__in=self.facts, in_schema=True
            )
        }
        # Reject bad values individually, then reduce the valid facts once.
        saved: list[dict] = []
        unchanged: list[dict] = []
        errors: list[dict] = []
        valid: dict[str, FactInputType] = {}
        for name, value in self.facts.items():
            variable = variables.get(name)
            if variable is None:
                errors.append(
                    {
                        "name": name,
                        "label": name,
                        "message": "no variable with this name",
                    }
                )
                continue
            try:
                variable_value_validate(
                    data_type=variable.data_type,
                    choices=variable.choices,
                    value=value,
                )
            except ValidationError as exc:
                errors.append(
                    {
                        "name": name,
                        "label": variable.label or name,
                        "message": "; ".join(exc.messages),
                    }
                )
                continue
            valid[name] = FactInputType(
                value=value, evidence=self.evidence.get(name)
            )

        change = variable_answers_record(identity=identity, facts=valid)
        for name, incoming in valid.items():
            answer = change.answers[name]
            variable = answer.variable
            if name not in change.value_changed_names:
                unchanged.append(
                    {
                        "name": name,
                        "label": variable.label or name,
                        "display_value": format_answer(answer),
                    }
                )
                continue
            saved.append(
                {
                    "name": name,
                    "label": variable.label or name,
                    "display_value": format_answer(answer),
                    "cleared": incoming.value is None,
                }
            )

        parts = []
        stored = [fact["name"] for fact in saved if not fact["cleared"]]
        cleared = [fact["name"] for fact in saved if fact["cleared"]]
        if stored:
            parts.append(
                f"Saved as unconfirmed answers the user reviews later: "
                f"{', '.join(stored)}."
            )
        if cleared:
            parts.append(f"Cleared saved answers: {', '.join(cleared)}.")
        if unchanged:
            parts.append(
                "Answer values unchanged: "
                f"{', '.join(fact['name'] for fact in unchanged)}."
            )
        if errors:
            parts.append("Not saved:")
            parts += [f"- {e['name']}: {e['message']}" for e in errors]
            if any(e["name"] not in variables for e in errors):
                parts.append(
                    "Use the exact variable names listed in the loaded "
                    "topic flow."
                )

        return ToolOutput(
            result="\n".join(parts),
            render_data={
                "saved": saved,
                "unchanged": unchanged,
                "errors": errors,
            },
            refresh_system_prompt=bool(saved),
        )
