from django.utils import timezone

from litigant_portal.agents.base import Tool, ToolOutput
from litigant_portal.agents.tools.load_topic_flow import topic_flow_from_path
from litigant_portal.app.topic_flow.formatting import format_answer


class ReviewFacts(Tool):
    """Show the user a card to review and confirm their saved facts.

    Call this when all the facts the active topic flow needs are saved,
    or whenever the user asks to review their answers, finish up, or fill
    out their forms. This tool takes no fact names and no values: the
    card is built from the user's stored answers, and only the user can
    confirm them (you cannot confirm facts). The result tells you which
    required facts are still missing, if any.
    """

    tool_call_template = "tools/review_facts_call.html"
    tool_result_template = "tools/review_facts_result.html"
    render_after_reply = True

    def __call__(self, *, thread_id) -> ToolOutput:
        from litigant_portal.app.models import ChatThread
        from litigant_portal.app.selectors.site import (
            contact_list,
            resource_list,
        )
        from litigant_portal.app.selectors.state import flow_state
        from litigant_portal.app.selectors.topic_flow import (
            topic_flow_url_kwargs,
        )
        from litigant_portal.app.services.docassemble import (
            interview_launch_url,
        )
        from litigant_portal.app.topic_flow.prefill import (
            flow_interview_target,
        )

        thread = ChatThread.objects.select_related("identity").get(
            id=thread_id
        )
        path = (thread.state or {}).get("active_topic_flow")
        flow = topic_flow_from_path(path) if path else None
        if flow is None:
            return ToolOutput(
                result=(
                    "Error: no active topic flow. Load the topic flow that "
                    "matches the user's situation first."
                )
            )

        # Stamped before the read: the confirm endpoint refuses rows written
        # after it, so a value this card never showed cannot be confirmed.
        as_of = timezone.now()
        current = flow_state(
            identity=thread.identity,
            flow=flow,
            contacts=contact_list(court=flow.topic.court),
            resources=resource_list(court=flow.topic.court),
        )
        facts = []
        for name in current.projection.answered:
            variable = current.variables[name]
            answer = current.answers[name]
            facts.append(
                {
                    "name": name,
                    "label": variable.label or name,
                    "display_value": format_answer(answer),
                    "reviewed": answer.reviewed,
                    "evidence": answer.evidence,
                }
            )
        missing = [
            {"name": name, "label": current.variables[name].label or name}
            for name in current.projection.missing_required
        ]

        # Same launch check as the guided page's packet section; no page
        # means no interview to launch from it.
        page = topic_flow_url_kwargs(flow) or {}
        target = flow_interview_target(flow) if page else None
        interview_available = bool(target and interview_launch_url(target[0]))

        result = "The review card is now shown to the user."
        if missing:
            result += " Still missing required facts: " + ", ".join(
                m["name"] for m in missing
            )
        else:
            result += " No required facts are missing."
        result += " Only the user can confirm facts, using the card's button."

        return ToolOutput(
            result=result,
            render_data={
                "facts": facts,
                "missing": missing,
                "confirm_names": [f["name"] for f in facts],
                "as_of": as_of.isoformat(),
                "all_reviewed": bool(facts)
                and all(f["reviewed"] for f in facts),
                "court": page.get("court"),
                "topic": page.get("topic"),
                "role": page.get("role"),
                "interview_available": interview_available,
            },
        )
