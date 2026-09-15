"""
Validated conversation tools for procedure selection, facts, and acknowledgement.
"""

import re
from datetime import date

from pydantic import (
    Field,
    JsonValue,
    StrictBool,
    StrictFloat,
    StrictInt,
    ValidationError,
)

from lp_agent.errors import AgentValidationError
from lp_agent.flows.procedure import ProcedureState
from lp_agent.types import ContractModel, NonBlankText, ToolDefinition


class SelectProcedure(ContractModel):
    slug: NonBlankText
    evidence: NonBlankText


class FactUpdate(ContractModel):
    key: NonBlankText
    value: str | StrictBool | StrictInt | StrictFloat
    evidence: NonBlankText


class RecordFacts(ContractModel):
    facts: tuple[FactUpdate, ...] = Field(min_length=1, max_length=50)


class AcknowledgePhase(ContractModel):
    phase_key: NonBlankText
    evidence: NonBlankText


SELECT_PROCEDURE = ToolDefinition(
    name="select_procedure",
    description="Select an available preparation procedure when the user's stated intent identifies it. Quote exact evidence from the current message. Clarify ambiguous intent before selecting; a general question alone does not request guided preparation.",
    parameters=SelectProcedure.model_json_schema(),
)
FACT_TOOLS = (
    ToolDefinition(
        name="record_facts",
        description="Save facts explicitly stated in the current user message. Use known fact keys and quote exact current-message evidence for each value. Corrections replace earlier assertions with provenance.",
        parameters=RecordFacts.model_json_schema(),
    ),
    ToolDefinition(
        name="acknowledge_phase",
        description="Record the user's explicit acknowledgement of the current optional preparation step, or confirmation of the final facts summary. Use progress.current_phase.key exactly. Requires a separate user reply; never acknowledge on their behalf.",
        parameters=AcknowledgePhase.model_json_schema(),
    ),
)


class EngagementTools:
    """
    Keep database identifiers and ownership out of model-supplied arguments.
    """

    def __init__(
        self,
        state: ProcedureState,
        message: str,
        acknowledgement_phase: str | None = None,
    ) -> None:
        self.state = state
        self.message = message
        self.acknowledgement_phase = acknowledgement_phase

    def definitions(self) -> tuple[ToolDefinition, ...]:
        if self.state.procedure is None:
            return (SELECT_PROCEDURE,)
        current = self.state.current
        return (
            FACT_TOOLS[0],
            *(
                (FACT_TOOLS[1],)
                if current and current.key == self.acknowledgement_phase
                else ()
            ),
        )

    def _evidence(self, quote: str) -> None:
        if quote not in self.message:
            raise AgentValidationError(
                "Evidence must quote the current user message exactly."
            )

    async def call(self, name: str, arguments: str) -> dict[str, JsonValue]:
        try:
            if name == "select_procedure":
                selection = SelectProcedure.model_validate_json(arguments)
                self._evidence(selection.evidence)
                await self.state.select(selection.slug)
                self.acknowledgement_phase = None
            elif name == "record_facts":
                await self.record(RecordFacts.model_validate_json(arguments))
            elif name == "acknowledge_phase":
                acknowledgement = AcknowledgePhase.model_validate_json(
                    arguments
                )
                self._evidence(acknowledgement.evidence)
                if acknowledgement.phase_key != self.acknowledgement_phase:
                    raise AgentValidationError(
                        "Ask for a separate reply to acknowledge this preparation step."
                    )
                # This is a conservative demo guard, not an intent classifier.
                if not re.search(
                    r"\b(yes|confirm|confirmed|correct|continue|skip|done|ready|okay|ok|understand)\b|looks good|go ahead",
                    acknowledgement.evidence,
                    re.I,
                ) or re.search(
                    r"\b(no|not|never)\b|don't", self.message, re.I
                ):
                    raise AgentValidationError(
                        "The reply does not explicitly acknowledge the preparation step."
                    )
                await self.state.acknowledge(acknowledgement.phase_key)
                self.acknowledgement_phase = None
            else:
                raise AgentValidationError("Unknown preparation tool.")
            return self.state.snapshot().model_dump(mode="json")
        except ValidationError as error:
            raise AgentValidationError.from_validation_error(
                error,
                models=(
                    SelectProcedure,
                    RecordFacts,
                    FactUpdate,
                    AcknowledgePhase,
                ),
            ) from None

    async def record(self, query: RecordFacts) -> None:
        from jsonschema import Draft202012Validator
        from jsonschema.exceptions import ValidationError as SchemaError

        if len({fact.key for fact in query.facts}) != len(query.facts):
            raise AgentValidationError("Provide each fact only once per call.")
        definitions = self.state.definitions
        for fact in query.facts:
            self._evidence(fact.evidence)
            definition = definitions.get(fact.key)
            if definition is None:
                raise AgentValidationError(
                    "Use a fact key defined by the selected procedure."
                )
            try:
                Draft202012Validator(definition.value_schema).validate(
                    fact.value
                )
                if definition.value_schema.get("format") == "date":
                    if not isinstance(fact.value, str):
                        raise ValueError
                    if (
                        date.fromisoformat(fact.value).isoformat()
                        != fact.value
                    ):
                        raise ValueError
            except (SchemaError, ValueError, TypeError):
                raise AgentValidationError(
                    "A fact has an invalid type, choice, or date."
                ) from None
        changed = False
        for fact in query.facts:
            old = self.state.assertions.get(fact.key)
            if (
                old
                and old.value == fact.value
                and type(old.value) is type(fact.value)
            ):
                continue
            await self.state.session.record_fact(
                definitions[fact.key],
                fact.value,
                fact.evidence,
                old.id if old else None,
            )
            changed = True
        await self.state.refresh()
        if changed:
            self.state.reopen_review()
            self.acknowledgement_phase = None
