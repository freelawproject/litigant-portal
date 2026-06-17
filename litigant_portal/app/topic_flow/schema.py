"""Pydantic models for Topic Flow corpora.

A corpus is one ``(court, topic, role)`` recipe authored as YAML on disk and
loaded into these typed models. AI-free — nothing here calls an LLM.

Sections are a discriminated union on ``kind`` (``info`` / ``fact_gather`` /
``output``); ``output`` sections are themselves a sub-union on ``output_type``
(``ics`` / ``vcf`` / ``packet`` / ``summary``). Pydantic resolves this nested
discriminated union natively. Id-reference cross-checks (a deadline's
``offset_from`` pointing at a question, outputs pointing at deadlines/contacts)
span sibling lists, so they live in ``loader.py`` rather than here.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

# Shared slug shape for court/topic/role and every id — alphanumeric start,
# then alphanumeric / underscore / hyphen. Mirrors the chat/prompts slug rule.
Slug = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")]


class _Base(BaseModel):
    # Reject unknown keys so an author's typo fails loudly instead of silently
    # dropping data.
    model_config = ConfigDict(extra="forbid")


class Metadata(_Base):
    court: Slug
    topic: Slug
    role: Slug
    title: str = Field(min_length=1)


class Contact(_Base):
    """A person or office the user can contact (clerk, legal aid, etc.)."""

    id: Slug
    name: str = Field(min_length=1)
    phone: str | None = None
    email: str | None = None
    url: str | None = None
    address: str | None = None
    hours: str | None = None
    note: str | None = None


class Deadline(_Base):
    """A date computed as ``offset_days`` from a gathered date.

    ``offset_from`` names a ``fact_gather`` question id; the loader checks it
    resolves.
    """

    id: Slug
    label: str = Field(min_length=1)
    offset_days: int
    offset_from: Slug
    description: str | None = None


class Question(_Base):
    """One datum collected from the user, addressable corpus-wide by id."""

    id: Slug
    label: str = Field(min_length=1)
    type: Literal["text", "date", "choice"] = "text"
    required: bool = False
    choices: list[str] | None = None
    help_text: str | None = None


class InfoSection(_Base):
    kind: Literal["info"]
    id: Slug
    heading: str = Field(min_length=1)
    body: str = Field(min_length=1)


class FactGatherSection(_Base):
    kind: Literal["fact_gather"]
    id: Slug
    heading: str | None = None
    questions: list[Question] = Field(min_length=1)


class IcsOutput(_Base):
    kind: Literal["output"]
    output_type: Literal["ics"]
    id: Slug
    heading: str = Field(min_length=1)
    deadline_ids: list[Slug] = Field(min_length=1)


class VcfOutput(_Base):
    kind: Literal["output"]
    output_type: Literal["vcf"]
    id: Slug
    heading: str = Field(min_length=1)
    contact_ids: list[Slug] = Field(min_length=1)


class PacketOutput(_Base):
    kind: Literal["output"]
    output_type: Literal["packet"]
    id: Slug
    heading: str = Field(min_length=1)
    forms: list[str] = Field(min_length=1)
    # Optional warm handoff to a docassemble interview that fills these forms.
    # Unset (None) => the packet renders as a plain form list, so existing
    # corpora are unaffected. v1 is link-out + manual return, no prefill (#543).
    interview_url: str | None = None


class SummaryOutput(_Base):
    kind: Literal["output"]
    output_type: Literal["summary"]
    id: Slug
    heading: str = Field(min_length=1)


# output sections discriminate on output_type ...
OutputSection = Annotated[
    IcsOutput | VcfOutput | PacketOutput | SummaryOutput,
    Field(discriminator="output_type"),
]

# ... and the section list discriminates on kind, with the output sub-union as
# one branch (all output members share kind="output").
Section = Annotated[
    InfoSection | FactGatherSection | OutputSection,
    Field(discriminator="kind"),
]


class Corpus(_Base):
    metadata: Metadata
    contacts: list[Contact] = Field(default_factory=list)
    deadlines: list[Deadline] = Field(default_factory=list)
    sections: list[Section] = Field(min_length=1)
