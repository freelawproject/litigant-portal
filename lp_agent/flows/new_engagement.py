"""
Corpus-grounded questions and conversation-driven preparation through scoped services.
"""

import json
import re
from collections.abc import Callable
from contextlib import aclosing
from dataclasses import dataclass, field
from uuid import UUID

from pydantic import JsonValue

from lp_agent.errors import AgentValidationError
from lp_agent.flows.checks import AgentChecker
from lp_agent.flows.engagement import Engagement, EngagementFlow
from lp_agent.flows.judge import AgentJudge
from lp_agent.flows.procedure import ProcedureState
from lp_agent.flows.prompts import PromptBuilder
from lp_agent.interfaces import RunStore
from lp_agent.preparation import (
    PreparationSession,
    PreparedContext,
    source_references,
)
from lp_agent.tools.agent_search import SEARCH_TOOLS
from lp_agent.tools.engagement import EngagementTools
from lp_agent.types import (
    CompletedOutcome,
    EventPayload,
    FunctionCallOutput,
    ModelFinished,
    ModelItem,
    ModelMessage,
    ModelOutputItem,
    ModelRequest,
    OutputText,
    Refusal,
    RunOutcome,
    RunRequest,
    TextEvent,
    ToolCall,
    ToolEvent,
)
from lp_agent.utils.audit import InstructionArtifact


def message_text(item: ModelMessage) -> str:
    if isinstance(item.content, str):
        return item.content
    return "".join(
        part.text if isinstance(part, OutputText) else part.refusal
        for part in item.content
        if isinstance(part, OutputText | Refusal)
    )


class NewEngagementFlow(EngagementFlow):
    """
    Resolve the corpus before procedure selection; keep the caller's contract intact.
    """

    async def prepare(self, request: RunRequest) -> Engagement:
        scoped = await self._bind_scope()
        if scoped.preparation is None:
            return await super().prepare(request)
        if request.attachment_ids:
            raise AgentValidationError(
                "Attachments are not implemented for preparation yet."
            )
        if request.conversation_id:
            try:
                UUID(request.conversation_id)
            except ValueError:
                raise AgentValidationError(
                    "Conversation is unavailable."
                ) from None
        session = await scoped.preparation.open()
        try:
            async with session.transaction():
                context = await session.prepare(request, self.configuration)
                state = ProcedureState(session, context)
                await state.refresh()
                context_item = PromptBuilder.inject_model_message(
                    state.snapshot()
                )
                await session.save_context(context_item)
                model_request = ModelRequest(
                    instructions=PromptBuilder.build_system_prompt(
                        context.corpus, state.procedure, state.snapshot()
                    ),
                    input=(context_item, *context.history),
                )
                return PreparedEngagement(
                    environment=self.environment,
                    scoped=scoped,
                    initial_status=context.status,
                    request=request,
                    limits=self.configuration.limits,
                    model_request=model_request,
                    instruction_artifact=InstructionArtifact.from_request(
                        model_request
                    ),
                    session=session,
                    context=context,
                    procedure_state=state,
                )
        except BaseException:
            await session.aclose()
            raise


@dataclass(kw_only=True)
class PreparedEngagement(Engagement):
    """
    Execute auditable model/tool steps; the service commits effects and history together.
    """

    session: PreparationSession = field(repr=False)
    context: PreparedContext = field(repr=False)
    procedure_state: ProcedureState = field(repr=False)
    operation_count: int = field(default=0, init=False)

    @property
    def checkpoint_store(self) -> RunStore:
        return self.session.runs

    async def aclose(self) -> None:
        await self.session.aclose()

    def _checkpoint_data(self) -> dict[str, JsonValue]:
        return {
            **super()._checkpoint_data(),
            "procedure_revision": self.procedure_state.procedure.id
            if self.procedure_state.procedure
            else None,
            "model_identifier": self.context.model_identifier,
            "progress": self.procedure_state.snapshot().model_dump(
                mode="json"
            ),
            "operation_count": self.operation_count,
        }

    def _progress_event(self) -> ToolEvent:
        return ToolEvent(
            call_id=f"preparation:{self.initial_status.run_id}:{self.operation_count}",
            name="preparation_progress",
            state="completed",
            data=self.procedure_state.snapshot().model_dump(mode="json"),
        )

    async def _model_response(
        self, emit: Callable[[EventPayload], None]
    ) -> RunOutcome:
        state = self.procedure_state
        prior_phase = (
            self.context.previous.progress.current_phase
            if self.context.previous
            else None
        )
        preparation_tools = EngagementTools(
            state,
            self.request.message,
            prior_phase.key
            if prior_phase and self.context.previous_completed
            else None,
        )
        emit(self._progress_event())
        history = list(self.model_request.input)
        while self.operation_count < self.limits.max_steps:
            self.operation_count += 1
            index = self.operation_count
            self.model_request = ModelRequest(
                instructions=PromptBuilder.build_system_prompt(
                    self.context.corpus, state.procedure, state.snapshot()
                ),
                input=tuple(history),
                tools=(*SEARCH_TOOLS, *preparation_tools.definitions()),
            )
            self.instruction_artifact = InstructionArtifact.from_request(
                self.model_request
            )
            items: list[ModelItem] = []
            self.model_finished = None
            async with aclosing(
                self.scoped.model.stream(self.model_request)
            ) as stream:
                async for event in stream:
                    if isinstance(event, ModelOutputItem):
                        items.append(event.item.model_copy(deep=True))
                        self.output_items.append(
                            event.item.model_copy(deep=True)
                        )
                    elif isinstance(event, ModelFinished):
                        self.model_finished = event
            calls = [item for item in items if isinstance(item, ToolCall)]
            if (
                self.model_finished is None
                or self.model_finished.reason not in ("stop", "tool_calls")
                or (self.model_finished.reason == "tool_calls" and not calls)
                or any(
                    item.status in ("incomplete", "in_progress")
                    for item in items
                )
            ):
                return self._failure(
                    "incomplete_response",
                    "The model did not finish its response.",
                )
            async with self.session.transaction():
                step_id = await self.session.save_step(
                    key=f"model:{index}",
                    kind="model",
                    input=self.model_request.model_dump(mode="json"),
                    output=[item.model_dump(mode="json") for item in items],
                    instructions=self.instruction_artifact,
                )
                await self.session.save_model_items(
                    tuple(items), step_id, visible=not calls
                )
                await state.persist(step_id)
                await self._save("running", lambda event: None)
            history.extend(items)
            if calls:
                for call in calls:
                    if self.operation_count >= self.limits.max_steps:
                        return self._failure(
                            "step_limit", "The run reached its step limit."
                        )
                    self.operation_count += 1
                    history.append(
                        await self._tool_response(
                            call, preparation_tools, emit
                        )
                    )
                continue
            text = "".join(
                message_text(item)
                for item in items
                if isinstance(item, ModelMessage)
            )
            if not text.strip():
                return self._failure(
                    "empty_response", "The model returned no answer."
                )
            cited = set(re.findall(r"\[source:([^\]]+)\]", text))
            available = source_references(self.context.corpus)
            if cited - available.keys():
                return self._failure(
                    "invalid_source",
                    "The response cited an unavailable source. Please try again.",
                )
            findings = AgentChecker.upl_findings(text)
            judge = AgentJudge.check_upl(
                run_id=self.initial_status.run_id, findings=findings
            )
            async with self.session.transaction():
                await self.session.save_step(
                    key=f"check:{index}",
                    kind="check",
                    input={"model_step": step_id},
                    output={
                        "upl_findings": list(findings),
                        "mode": "observational",
                    },
                )
                await self.session.save_step(
                    key=f"judge:{index}",
                    kind="judge",
                    input={"model_step": step_id},
                    output=judge,
                )
                await self._save("running", lambda event: None)
            emit(
                ToolEvent(
                    call_id=f"judge:{index}",
                    name="judge_and_retry",
                    state="skipped",
                    data=judge,
                )
            )
            emit(TextEvent(delta=text))
            emit(self._progress_event())
            return CompletedOutcome(
                **self.reference,
                text=text,
                sources=tuple(available[key] for key in sorted(cited)),
            )
        return self._failure("step_limit", "The run reached its step limit.")

    async def _tool_response(
        self,
        call: ToolCall,
        tools: EngagementTools,
        emit: Callable[[EventPayload], None],
    ) -> FunctionCallOutput:
        emit(ToolEvent(call_id=call.call_id, name=call.name, state="started"))
        state = self.procedure_state
        selected_before = state.procedure
        acknowledgement_before = tools.acknowledgement_phase
        failed = False
        result: JsonValue
        try:
            async with self.session.transaction():
                if call.name not in {
                    tool.name for tool in self.model_request.tools
                }:
                    raise AgentValidationError(
                        "This tool is not available in the current step."
                    )
                result = (
                    await self.session.search(call.name, call.arguments)
                    if call.name in {tool.name for tool in SEARCH_TOOLS}
                    else await tools.call(call.name, call.arguments)
                )
                output = await self._save_tool(call, result)
        except AgentValidationError as error:
            failed = True
            state.procedure = selected_before
            tools.acknowledgement_phase = acknowledgement_before
            result = {"error": str(error)}
            async with self.session.transaction():
                await state.refresh()
                output = await self._save_tool(call, result)
        emit(
            ToolEvent(
                call_id=call.call_id,
                name=call.name,
                state="failed" if failed else "completed",
                data=result,
            )
        )
        emit(self._progress_event())
        return output

    async def _save_tool(
        self, call: ToolCall, result: JsonValue
    ) -> FunctionCallOutput:
        # Effects, the completed operation with its actual output, and checkpoint
        # share one transaction. Completed steps are never rewritten.
        step_id = await self.session.save_step(
            key=f"tool:{self.operation_count}",
            kind="tool",
            input=call.model_dump(mode="json"),
            output=result,
        )
        output = FunctionCallOutput(
            call_id=call.call_id, output=json.dumps(result, ensure_ascii=False)
        )
        await self.session.save_tool_output(output, step_id)
        await self.procedure_state.persist(step_id)
        await self._save("running", lambda event: None)
        return output

    async def finish(
        self, outcome: RunOutcome, emit: Callable[[EventPayload], None]
    ) -> None:
        events: list[EventPayload] = []
        async with self.session.transaction():
            if outcome.state != "completed":
                await self.session.discard_response()
            await super().finish(outcome, events.append)
        for event in events:
            emit(event)
