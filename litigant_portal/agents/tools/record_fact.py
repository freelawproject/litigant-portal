from typing import Any

from litigant_portal.agents.base import Field, Tool, ToolOutput


class RecordFact(Tool):
    """Save facts the user states as answers to the loaded flow's variables.

    Call this as soon as the user states a fact; do not ask permission
    first. Save every fact the user volunteers in one call; when asking for
    more, ask for the next missing fact (a closely related pair like the
    current and new name is fine), not a list. Use the flow's exact variable
    names and
    typed values (ISO dates, listed choice values); a null value clears a
    saved answer. Saves are unconfirmed suggestions the user reviews later;
    when the user corrects a fact, save the new value. Never save a guess
    or a default the user has not voiced (confirming a value you stated
    counts as voiced), and confirm first when a value looks impossible for
    the jurisdiction, like a county that does not exist in the state.
    """

    facts: dict[str, Any] = Field(
        description=(
            "Mapping of variable name to value, e.g. "
            '{"county": "Burleigh", "date_of_birth": "1990-01-31"}'
        )
    )

    tool_call_template = "tools/record_fact_call.html"
    tool_result_template = "tools/record_fact_result.html"

    def __call__(self, *, thread_id) -> ToolOutput:
        from django.core.exceptions import ValidationError

        from litigant_portal.app.models import Variable
        from litigant_portal.app.selectors.chat_engine import (
            chat_thread_identity_get,
        )
        from litigant_portal.app.services.topic_flow import variable_answer_set

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

        # Per-fact, not atomic: a bad value must not block sibling saves.
        saved: list[dict] = []
        errors: list[dict] = []
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
                answer = variable_answer_set(
                    identity=identity,
                    variable=variable,
                    value=value,
                    reviewed=False,
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
            saved.append(
                {
                    "name": name,
                    "label": variable.label or name,
                    # str(): lazy translation proxies break JSON encoding.
                    "value": str(answer.display_value),
                    "cleared": value is None,
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
            render_data={"saved": saved, "errors": errors},
            refresh_system_prompt=bool(saved),
        )
