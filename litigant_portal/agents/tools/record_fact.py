from typing import Any

from litigant_portal.agents.base import Field, Tool, ToolOutput


class RecordFact(Tool):
    """Save facts the user states as answers to the loaded flow's variables.

    Call this as soon as the user states a fact matching a variable from the
    loaded topic flow; do not ask permission first. Use the exact variable
    names the flow lists, and values matching each variable's data type
    (dates as ISO YYYY-MM-DD strings, choices as one of the listed values).
    Facts are saved as unconfirmed suggestions the user reviews later, so
    saving is safe; when the user corrects a fact, save the new value.
    Save only facts the user actually stated: never fill in a guess, a
    default, or an assumption the user has not voiced.
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
        variables = {
            v.name: v for v in Variable.objects.filter(name__in=self.facts)
        }

        # Per-fact upserts, not the atomic batch: facts are independent, and
        # a per-name error is what the model self-corrects from. Valid
        # siblings of a bad value still save.
        saved: list[dict] = []
        errors: dict[str, str] = {}
        for name, value in self.facts.items():
            variable = variables.get(name)
            if variable is None:
                errors[name] = "no variable with this name"
                continue
            try:
                answer = variable_answer_set(
                    identity=identity,
                    variable=variable,
                    value=value,
                    reviewed=False,
                )
            except ValidationError as exc:
                errors[name] = "; ".join(exc.messages)
                continue
            saved.append(
                {
                    "name": name,
                    "label": variable.label or name,
                    # str(): display_value can be a lazy translation proxy
                    # (booleans render as _("Yes")/_("No")), which the
                    # engine's JSON serialization rejects.
                    "value": str(answer.display_value),
                }
            )

        parts = []
        if saved:
            names = ", ".join(fact["name"] for fact in saved)
            parts.append(
                f"Saved as unconfirmed answers the user reviews later: "
                f"{names}."
            )
        if errors:
            parts.append("Not saved:")
            parts += [f"- {name}: {msg}" for name, msg in errors.items()]
            if set(errors) - set(variables):
                parts.append(
                    "Use the exact variable names listed in the loaded "
                    "topic flow."
                )

        return ToolOutput(
            result="\n".join(parts),
            render_data={"saved": saved, "errors": errors},
            refresh_system_prompt=bool(saved),
        )
