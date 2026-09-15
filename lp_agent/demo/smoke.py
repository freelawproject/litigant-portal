"""
Exercise live preparation and corpus questions through the unchanged Python API.

This writes synthetic demonstration conversations to the configured development
agent database and makes real Bedrock requests. Output contains no credentials
or internal reasoning. It is a smoke check, not an evaluation or legal review.
"""

import argparse
import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import JsonValue

from lp_agent import LPAgent
from lp_agent.adapters.bedrock import MODEL_CHOICES, BedrockClient
from lp_agent.adapters.environment import create_environment
from lp_agent.demo.seed import TOPICS, VariableSchema
from lp_agent.flows.new_engagement import message_text
from lp_agent.preparation import PreparationSnapshot
from lp_agent.types import (
    ModelMessage,
    ModelOutputItem,
    ModelRequest,
    RunLimits,
)

QUESTIONS = (
    "What is the filing fee for an adult name change in North Dakota?",
    "How recent must the criminal-history check be when I file for an adult name change in North Dakota?",
    "Will the North Dakota court always hold a hearing for an adult name change?",
    "I lived in two North Dakota counties during the last 12 months. Where must I publish my adult name-change notice?",
    "Does Burleigh County offer a same-day adult name-change service for an extra $25?",
)
STARTS = {
    "standard": "I am an adult in North Dakota changing my own first and last name in a standalone petition unrelated to divorce. Please guide me through standard name-change preparation with publication.",
    "waiver": "I am an adult in North Dakota changing only my first and middle names in a standalone petition unrelated to divorce. I want to request a waiver of publication. Please guide me through that preparation.",
    "tenant": "I rent a home in Franklin County, Ohio and have received eviction papers. Please guide me through eviction preparation as a tenant.",
    "landlord": "I am a landlord in Franklin County, Ohio. Please guide me through landlord eviction preparation.",
}


def example_facts(
    root: Path, court: str, topic: str, procedure: str
) -> dict[str, JsonValue]:
    """
    Produce explicitly fictional values for the repository's existing fact schemas.
    """
    import yaml

    variables = {
        item["name"]: item
        for item in yaml.safe_load(
            (root / "corpus/variables.yml").read_text()
        )["variables"]
    }
    flow = yaml.safe_load(
        (
            root
            / "corpus/courts"
            / court
            / "topics"
            / topic
            / "flows"
            / f"{procedure}.yml"
        ).read_text()
    )
    values: dict[str, JsonValue] = {}
    for page in flow["interview"]:
        for key in page["variables"]:
            definition = VariableSchema.model_validate(variables[key])
            if definition.choices:
                value: JsonValue = definition.choices[0].value
            elif definition.data_type == "boolean":
                value = False
            elif definition.data_type == "number":
                value = 0
            elif definition.data_type == "date":
                value = "2026-10-01"
            else:
                value = "Demo value"
            if key == "name_change_fee_waiver_needed":
                value = True
            values[key] = value
    return values


async def walkthrough(
    *,
    root: Path,
    model: str,
    api_key: str,
    court: str,
    topic: str,
    procedure: str,
) -> dict[str, JsonValue]:
    environment = create_environment(
        identity_id="demo-" + uuid4().hex,
        model=model,
        api_key=api_key,
        resource_root=root,
        court=court,
        topic=topic,
    )
    turns: list[JsonValue] = []
    conversation_id: str | None = None
    progress = PreparationSnapshot()
    facts = example_facts(root, court, topic, procedure)
    async with LPAgent(
        environment=environment, limits=RunLimits(max_active_seconds=180.0)
    ) as agent:

        async def send(message: str) -> bool:
            nonlocal conversation_id, progress
            run = await agent.run(
                message=message, conversation_id=conversation_id
            )
            conversation_id = run.conversation_id
            outcome = await run.result()
            checkpoint = await environment.runs.checkpoint(
                access=environment.access, run_id=run.run_id
            )
            if checkpoint is None:
                raise RuntimeError("Missing demonstration checkpoint.")
            progress = PreparationSnapshot.model_validate(
                checkpoint.data["progress"]
            )
            turns.append(
                {
                    "message": message,
                    "outcome": outcome.model_dump(mode="json"),
                    "progress": {
                        "procedure": progress.procedure,
                        "current_phase": progress.current_phase.key
                        if progress.current_phase
                        else None,
                        "complete": progress.complete,
                        "percent_complete": progress.percent_complete,
                        "saved_fact_count": len(progress.facts),
                    },
                }
            )
            print(
                f"{court}/{procedure}: turn {len(turns)}, {outcome.state}, preparation {progress.percent_complete}%",
                flush=True,
            )
            return outcome.state == "completed"

        ready = await send(STARTS[procedure])
        if ready and progress.procedure is None:
            ready = await send(
                f"This is a standalone preparation request. Please use the {procedure} procedure I described."
            )
        if (
            ready
            and progress.procedure == procedure
            and await send(
                "These are fictional facts for this demonstration. Save the supplied values: "
                + json.dumps(facts)
            )
        ):
            for _ in range(10):
                if progress.complete or progress.current_phase is None:
                    break
                if progress.current_phase.missing:
                    supplied = {
                        key: facts[key]
                        for key in progress.current_phase.missing
                    }
                    message = (
                        "Here are the requested fictional values: "
                        + json.dumps(supplied)
                    )
                else:
                    message = "Yes, I confirm the saved facts are correct and I understand this preparation step. Continue to the next step or provide the preparation handoff."
                if not await send(message):
                    break
    return {
        "court": court,
        "topic": topic,
        "procedure": procedure,
        "complete": progress.complete,
        "final_progress": progress.model_dump(mode="json"),
        "turns": turns,
    }


async def question(
    *, model: str, api_key: str, root: Path, text: str, compare: bool
) -> dict[str, JsonValue]:
    environment = create_environment(
        identity_id="demo-question-" + uuid4().hex,
        model=model,
        api_key=api_key,
        resource_root=root,
        court="north-dakota",
        topic="adult-name-change",
    )
    async with LPAgent(environment=environment) as agent:
        run = await agent.run(message=text)
        outcome = await run.result()
        checkpoint = await environment.runs.checkpoint(
            access=environment.access, run_id=run.run_id
        )
        if checkpoint is None:
            raise RuntimeError("Missing demonstration checkpoint.")
        progress = PreparationSnapshot.model_validate(
            checkpoint.data["progress"]
        )
    baseline = None
    if compare:
        parts: list[str] = []
        async for event in BedrockClient(model, api_key=api_key).stream(
            ModelRequest(
                instructions="Provide clear, concise legal information in response to the user's question. State uncertainty when appropriate.",
                input=(ModelMessage(role="user", content=text),),
            )
        ):
            if isinstance(event, ModelOutputItem) and isinstance(
                event.item, ModelMessage
            ):
                parts.append(message_text(event.item))
        baseline = "".join(parts)
    print(
        f"Corpus question: {outcome.state}, procedure selected: {progress.procedure}",
        flush=True,
    )
    return {
        "question": text,
        "grounded": outcome.model_dump(mode="json"),
        "selected_procedure": progress.procedure,
        "without_corpus": baseline,
    }


def main() -> None:
    """
    Run a repeatable local check with real provider calls and synthetic facts.
    """
    from django.conf import settings

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings")
    parser.add_argument("--resource-root", required=True, type=Path)
    parser.add_argument(
        "--model",
        choices=[item[0] for item in MODEL_CHOICES[:-1]],
        default=MODEL_CHOICES[0][0],
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Also ask the same model the five questions without corpus or tools",
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.settings:
        os.environ["DJANGO_SETTINGS_MODULE"] = args.settings
    if (
        not settings.DEBUG
        or getattr(settings, "DEPLOYMENT_ENV", None) != "dev"
    ):
        parser.error(
            "Live demo checks require DEBUG=true and DEPLOYMENT_ENV=dev."
        )

    async def run() -> dict[str, JsonValue]:
        options = {
            "root": args.resource_root,
            "model": args.model,
            "api_key": settings.BEDROCK_API_KEY,
        }
        # Independent conversations share no connection or transaction.
        flows = await asyncio.gather(
            *(
                walkthrough(
                    **options, court=court, topic=topic, procedure=procedure
                )
                for court, topic, procedures in TOPICS
                for procedure in procedures
            )
        )
        questions = await asyncio.gather(
            *(
                question(**options, text=text, compare=args.compare)
                for text in QUESTIONS
            )
        )
        return {
            "recorded_at": datetime.now(UTC).isoformat(),
            "model": args.model,
            "all_flows_complete": all(
                flow["complete"] is True for flow in flows
            ),
            "flows": list(flows),
            "questions": list(questions),
        }

    report = asyncio.run(run())
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    )
    print(f"Saved live observations to {args.output}")
    if report["all_flows_complete"] is not True:
        raise SystemExit(
            "Some preparation walkthroughs did not finish; inspect the saved observations."
        )


if __name__ == "__main__":
    main()
