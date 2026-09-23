from litigant_portal.agents.base import Tool, ToolOutput
from litigant_portal.agents.tools.load_topic_flow import topic_flow_from_path


def _flow_variables(flow) -> list:
    """The flow's interview variables, in page order, without duplicates."""
    seen = set()
    variables = []
    for page in flow.interview_pages.all():
        for pv in page.variables.all():
            if pv.variable.name in seen:
                continue
            seen.add(pv.variable.name)
            variables.append(pv.variable)
    return variables


def _is_asked(variable, values: dict) -> bool:
    """Whether a gated variable's question currently applies."""
    if variable.asked_when is None:
        return True
    return values.get(variable.asked_when.name) == variable.asked_when_value


class ReviewFacts(Tool):
    """Show the user a card to review and confirm their saved facts.

    Call this when all the facts the active topic flow needs are gathered,
    or whenever the user asks to review their answers, finish up, or fill
    out their forms. This tool takes no fact names and no values: the card
    is built from the user's stored answers, and only the user can confirm
    them (you cannot confirm facts). The result tells you which required
    facts are still missing, if any.
    """

    tool_call_template = "tools/review_facts_call.html"
    tool_result_template = "tools/review_facts_result.html"

    def __call__(self, *, thread_id) -> ToolOutput:
        from litigant_portal.app.models import ChatThread
        from litigant_portal.app.selectors.chat_engine import (
            chat_thread_identity_get,
        )
        from litigant_portal.app.selectors.topic_flow import (
            variable_answer_list,
        )
        from litigant_portal.app.services.docassemble import (
            interview_launch_url,
        )
        from litigant_portal.app.topic_flow.prefill import interview_target
        from litigant_portal.app.topic_flow.registry import (
            registry,
            topic_flow_track_find,
        )

        thread = ChatThread.objects.get(id=thread_id)
        path = (thread.state or {}).get("active_topic_flow")
        flow = topic_flow_from_path(path) if path else None
        if flow is None:
            return ToolOutput(
                result=(
                    "Error: no active topic flow. Load the topic flow that "
                    "matches the user's situation first."
                )
            )

        identity = chat_thread_identity_get(thread_id=thread_id)
        answers = {
            a.variable.name: a
            for a in variable_answer_list(
                identity=identity, answered_only=True
            )
        }
        values = {name: a.value for name, a in answers.items()}

        facts = []
        missing = []
        for variable in _flow_variables(flow):
            answer = answers.get(variable.name)
            if answer is not None:
                facts.append(
                    {
                        "name": variable.name,
                        "label": variable.label or variable.name,
                        "value": str(answer.display_value),
                        "reviewed": answer.reviewed,
                    }
                )
            elif variable.required and _is_asked(variable, values):
                missing.append(
                    {
                        "name": variable.name,
                        "label": variable.label or variable.name,
                    }
                )

        # The launch target, resolved like the guided page's packet section:
        # a matching content-registry page, an interview in its corpus, and a
        # docassemble in this environment. Without all three the card offers
        # the guided page (or nothing) as the next step.
        track = topic_flow_track_find(flow)
        corpus = (
            registry.get(track["court"], track["topic"], track["role"])
            if track
            else None
        )
        target = interview_target(corpus) if corpus else None
        interview_available = bool(target and interview_launch_url(target[0]))

        result = "The review card is now shown to the user."
        if missing:
            result += " Still missing required facts: " + ", ".join(
                m["name"] for m in missing
            )
        else:
            result += " No required facts are missing."
        result += " Only the user can confirm facts, using the card's buttons."

        return ToolOutput(
            result=result,
            render_data={
                "facts": facts,
                "missing": missing,
                "confirm_names": [f["name"] for f in facts],
                "all_reviewed": bool(facts)
                and all(f["reviewed"] for f in facts),
                "court": track["court"] if track else None,
                "topic": track["topic"] if track else None,
                "role": track["role"] if track else None,
                "interview_available": interview_available,
            },
        )
