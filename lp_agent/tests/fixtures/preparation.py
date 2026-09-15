"""
Load repository corpus material into an isolated preparation test database.
"""

import re
from pathlib import Path

import yaml
from pypdf import PdfReader

from lp_agent.adapters.db import AgentDatabase
from lp_agent.flows.prompts import BASE

SCOPES = (
    ("north-dakota", "adult-name-change", ("standard", "waiver")),
    ("franklin-county-oh", "eviction", ("tenant", "landlord")),
)


def value_schema(variable):
    """
    Translate the repository variable glossary into fact validation schemas.
    """
    kind = variable.get("data_type", "text")
    schema = {
        "type": {
            "text": "string",
            "date": "string",
            "choice": "string",
            "number": "number",
            "boolean": "boolean",
        }[kind]
    }
    if kind == "choice":
        schema["enum"] = [choice["value"] for choice in variable["choices"]]
    if kind == "date":
        schema["format"] = "date"
    if kind == "text" and variable.get("required"):
        schema["minLength"] = 1
    return schema


async def load_preparation_fixture(db: AgentDatabase, resource_root: Path):
    """
    Populate an empty test database with all four existing preparation procedures.
    """
    root = Path(resource_root)
    variables = {
        item["name"]: item
        for item in yaml.safe_load(
            (root / "corpus/variables.yml").read_text()
        )["variables"]
    }
    definitions = {}
    async with db.transaction():
        await db.ensure_user()
        await db.save_catalog(
            "prompt",
            {
                "key": "agent.base",
                "version": 1,
                "body": BASE,
                "state": "published",
            },
        )
        for court_slug, topic_slug, procedures in SCOPES:
            court_path = root / "corpus/courts" / court_slug
            topic_path = court_path / "topics" / topic_slug
            court_data = yaml.safe_load((court_path / "court.yml").read_text())
            topic_data = yaml.safe_load((topic_path / "topic.yml").read_text())
            court = await db.save_catalog(
                "court",
                {
                    "slug": court_slug,
                    "name": court_data["name"],
                    "jurisdiction_level": court_data["jurisdiction_level"],
                    "config": court_data,
                },
            )
            topic = await db.save_catalog(
                "topic",
                {
                    "slug": topic_slug,
                    "title": topic_data["title"],
                    "description": topic_data["description"],
                },
            )
            pair = await db.save_catalog(
                "court_topic",
                {"court_id": court["id"], "topic_id": topic["id"]},
            )
            for key, path in (
                (
                    f"agent.court.{court_slug}",
                    root / "prompts/courts" / court_slug / "prompt.md",
                ),
                (
                    f"agent.topic.{topic_slug}",
                    root
                    / "prompts/topics"
                    / topic_slug.replace("-", "_")
                    / "prompt.md",
                ),
            ):
                await db.save_catalog(
                    "prompt",
                    {
                        "key": key,
                        "version": 1,
                        "body": path.read_text(),
                        "state": "published",
                    },
                )
            for slug in procedures:
                flow = yaml.safe_load(
                    (topic_path / "flows" / f"{slug}.yml").read_text()
                )
                form_sources = []
                for packet in flow.get("packet", []):
                    form = root / "corpus/forms" / packet["form"]
                    form_sources.append(
                        {
                            "slug": packet["form"],
                            "mapping": yaml.safe_load(
                                form.with_suffix(".yml").read_text()
                            ),
                            "text": "\n".join(
                                page.extract_text() or ""
                                for page in PdfReader(
                                    form.with_suffix(".pdf")
                                ).pages
                            ),
                        }
                    )
                for key in {
                    key
                    for page in flow["interview"]
                    for key in page["variables"]
                }:
                    if key not in definitions:
                        variable = variables[key]
                        definitions[key] = await db.save_catalog(
                            "fact_definition",
                            {
                                "key": key,
                                "version": 1,
                                "scope": "user"
                                if variable.get("global")
                                else "matter",
                                "label": variable["label"],
                                "description": variable.get("help_text", ""),
                                "value_schema": value_schema(variable),
                            },
                        )
                procedure = await db.save_catalog(
                    "procedure",
                    {
                        "court_topic_id": pair["id"],
                        "slug": slug,
                        "title": flow["name"],
                        "version": 1,
                        "guidance": "\n\n".join(
                            section["heading"] + "\n" + section["content"]
                            for section in flow["sections"]
                        ),
                        "metadata": {
                            "public_flow_url": f"/t/{court_slug}/{topic_slug}/{slug}/",
                            "packet": flow.get("packet", []),
                            "links": flow.get("links", []),
                            "form_sources": form_sources,
                        },
                    },
                )
                for position, page in enumerate(
                    [
                        *flow["interview"],
                        {
                            "title": "Review preparation and next steps",
                            "variables": [],
                            "review": True,
                        },
                    ],
                    1,
                ):
                    phase = await db.save_catalog(
                        "phase",
                        {
                            "procedure_id": procedure["id"],
                            "key": "review"
                            if page.get("review")
                            else re.sub(
                                r"[^a-z0-9]+", "-", page["title"].lower()
                            ).strip("-"),
                            "position": position,
                            "title": page["title"],
                            "instructions": page.get("description", "")
                            or "Ask for the relevant facts or confirmation of this preparation step.",
                            "completion_criteria": [
                                {
                                    "type": "required_facts"
                                    if any(
                                        variables[key].get("required")
                                        for key in page["variables"]
                                    )
                                    else "user_acknowledgement"
                                }
                            ],
                        },
                    )
                    for order, key in enumerate(page["variables"], 1):
                        variable = variables[key]
                        await db.save_catalog(
                            "phase_fact",
                            {
                                "phase_id": phase["id"],
                                "fact_definition_id": definitions[key]["id"],
                                "position": order,
                                "required": variable.get("required", False),
                                "condition": variable.get("asked_when"),
                            },
                        )
                await db.save_catalog(
                    "procedure",
                    {"state": "published"},
                    record_id=str(procedure["id"]),
                )
