"""Pydantic models for Topic Flow corpora.

A corpus is one ``(court, topic, role)`` recipe authored as YAML on disk and
loaded into these typed models. AI-free — nothing here calls an LLM.

Sections are a discriminated union on ``kind`` (``info`` / ``fact_gather`` /
``screener`` / ``output``); ``output`` sections are a sub-union on ``output_type``
(``ics`` / ``vcf`` / ``packet`` / ``summary``). Pydantic resolves this nested
discriminated union natively. Id-reference cross-checks (a deadline's
``offset_from`` pointing at a question, outputs pointing at deadlines/contacts,
a ``when`` gate's ``fact`` pointing at an earlier question) span sibling
lists, so they live in ``loader.py`` rather than here.

Sections, questions, packet forms and deadlines may carry an optional ``when``
``Condition``. Absent means it always applies, so a corpus without any gate
renders exactly as before.

These models are the partner-facing corpus contract: this schema
(``extra="forbid"``), the loader's id cross-reference checks, and the
``checks.py`` startup guard together define the boundary. Any conformant
producer works identically — hand-authored YAML, a partner's CMS, an
AI-authoring tool — and a non-conformant corpus fails loudly here, never
downstream. LP depends only on this contract, never on how a corpus was made.
"""

from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    model_validator,
)

# Shared slug shape for court/topic/role and every id — alphanumeric start,
# then alphanumeric / underscore / hyphen. Mirrors the chat/prompts slug rule.
Slug = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")]

# docassemble executes these as assignment statements, so identifiers only.
InterviewVariable = Annotated[str, Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")]

# A docassemble interview reference, the ``?i=`` value: the installed package
# (a Python name, so underscores are fine) plus the full data/questions path.
# Never a URL: where it is sent comes from settings (#879). The short alias
# (``docassemble.pkg:file.yml``) is rejected too — the API keys a prefilled
# session under the canonical path, so the resume link for a session created
# under the alias dead-ends on "Unable to locate interview session".
InterviewReference = Annotated[
    str,
    Field(
        pattern=r"^docassemble\.[A-Za-z_][A-Za-z0-9_]*"
        r":data/questions/[A-Za-z0-9_\-./]+\.yml$"
    ),
]


class _Base(BaseModel):
    # Reject unknown keys so an author's typo fails loudly instead of silently
    # dropping data.
    model_config = ConfigDict(extra="forbid")


class Condition(_Base):
    """A ``when`` gate: a leaf test on one fact, or a combinator of gates.

    A leaf names a ``fact`` (a question id) plus exactly one operator:
    ``equals``, ``not_equals``, ``in`` or ``answered``. A combinator is
    exactly one of ``all``, ``any`` (non-empty lists) or ``not`` (one gate),
    and they nest. Which question ids exist, and which values a choice
    question allows, are cross-checks in ``loader.py``.
    """

    fact: Slug | None = None
    equals: str | None = None
    not_equals: str | None = None
    in_: list[str] | None = Field(default=None, alias="in", min_length=1)
    answered: bool | None = None
    all: list["Condition"] | None = Field(default=None, min_length=1)
    any: list["Condition"] | None = Field(default=None, min_length=1)
    not_: "Condition | None" = Field(default=None, alias="not")

    @property
    def operators(self) -> dict:
        """``{operator name: value}`` for the leaf operators that are set."""
        return {
            name: value
            for name, value in (
                ("equals", self.equals),
                ("not_equals", self.not_equals),
                ("in", self.in_),
                ("answered", self.answered),
            )
            if value is not None
        }

    @property
    def combinators(self) -> dict:
        return {
            name: value
            for name, value in (
                ("all", self.all),
                ("any", self.any),
                ("not", self.not_),
            )
            if value is not None
        }

    @model_validator(mode="after")
    def _leaf_or_combinator(self):
        operators = self.operators
        combinators = self.combinators
        if combinators:
            if self.fact is not None or operators:
                raise ValueError(
                    "a combinator (all/any/not) takes no fact or operator"
                )
            if len(combinators) != 1:
                raise ValueError("use exactly one of all, any or not")
            return self
        if self.fact is None:
            raise ValueError("a condition needs a fact, or all/any/not")
        if len(operators) != 1:
            raise ValueError(
                "a fact takes exactly one of equals, not_equals, in or "
                "answered"
            )
        return self


class Metadata(_Base):
    court: Slug
    topic: Slug
    role: Slug
    title: str = Field(min_length=1)
    # Optional render order for the chat→flow handoff links (lower first).
    # Absent → the registry falls back to file/alpha order. Lets authors put
    # Tenant ahead of Landlord without renaming files.
    order: int | None = None


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


class Resource(_Base):
    """An official/jurisdictional link for a flow (self-help center, statute).

    Unlike ``Contact``, whose ``url`` is one of several optional affordances, a
    resource *is* a link — ``url`` is required. Courts supply these as data, so
    the engine renders trustworthy official links without authors hand-coding
    HTML or smuggling URLs into contact cards / info-body prose.
    """

    id: Slug
    label: str = Field(min_length=1)
    url: str = Field(min_length=1)
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
    when: Condition | None = None


class Question(_Base):
    """One datum collected from the user, addressable corpus-wide by id."""

    id: Slug
    label: str = Field(min_length=1)
    type: Literal["text", "date", "choice"] = "text"
    required: bool = False
    choices: list[str] | None = None
    help_text: str | None = None
    when: Condition | None = None


class InfoSection(_Base):
    kind: Literal["info"]
    id: Slug
    heading: str = Field(min_length=1)
    body: str = Field(min_length=1)
    when: Condition | None = None


class FactGatherSection(_Base):
    kind: Literal["fact_gather"]
    id: Slug
    heading: str | None = None
    questions: list[Question] = Field(min_length=1)
    when: Condition | None = None


class Outcome(_Base):
    """One way a screener can resolve: a ``value`` for the screener's ``fact``.

    The first outcome whose ``when`` holds renders a confirm button labelled
    ``label`` that stores ``value``. The loader checks ``value`` is one of the
    fact's choices.
    """

    value: str = Field(min_length=1)
    label: str = Field(min_length=1)
    when: Condition


class ScreenerSection(_Base):
    """A fact_gather whose answers propose a value for an earlier choice fact.

    The screener never derives a fact on its own: the litigant confirms the
    proposed outcome with a button, which stores it like any other answer.
    """

    kind: Literal["screener"]
    id: Slug
    heading: str | None = None
    fact: Slug
    questions: list[Question] = Field(min_length=1)
    outcomes: list[Outcome] = Field(min_length=1)
    when: Condition | None = None


# The section kinds that ask questions; everything that walks questions
# corpus-wide (loader, renderer, validation, rules) dispatches on this.
QUESTION_SECTIONS = (FactGatherSection, ScreenerSection)


class IcsOutput(_Base):
    kind: Literal["output"]
    output_type: Literal["ics"]
    id: Slug
    heading: str = Field(min_length=1)
    deadline_ids: list[Slug] = Field(min_length=1)
    when: Condition | None = None


class VcfOutput(_Base):
    kind: Literal["output"]
    output_type: Literal["vcf"]
    id: Slug
    heading: str = Field(min_length=1)
    contact_ids: list[Slug] = Field(min_length=1)
    when: Condition | None = None


class PacketForm(_Base):
    """One court form in a packet — a name, optionally linked to its official PDF.

    Authoring shorthand: a bare string is the form name with no link, so
    ``forms: ['Petition', ...]`` keeps working. An object adds the link:
    ``- {name: 'Petition', url: 'https://…/petition.pdf'}``.
    """

    name: str = Field(min_length=1)
    url: str | None = None
    when: Condition | None = None


def _as_packet_form(value):
    return {"name": value} if isinstance(value, str) else value


PacketFormEntry = Annotated[PacketForm, BeforeValidator(_as_packet_form)]


class PacketOutput(_Base):
    kind: Literal["output"]
    output_type: Literal["packet"]
    id: Slug
    heading: str = Field(min_length=1)
    forms: list[PacketFormEntry] = Field(min_length=1)
    # Optional warm handoff to a docassemble interview that fills these forms.
    # Unset (None) => the packet renders as a plain form list, so existing
    # corpora are unaffected.
    interview_reference: InterviewReference | None = None
    # ``{fact_gather question id: interview variable}``; the loader checks
    # each key resolves. Empty => the interview asks everything.
    interview_prefill: dict[Slug, InterviewVariable] = Field(
        default_factory=dict
    )
    when: Condition | None = None


class ResourcesOutput(_Base):
    kind: Literal["output"]
    output_type: Literal["resources"]
    id: Slug
    heading: str = Field(min_length=1)
    resource_ids: list[Slug] = Field(min_length=1)
    when: Condition | None = None


class SummaryOutput(_Base):
    kind: Literal["output"]
    output_type: Literal["summary"]
    id: Slug
    heading: str = Field(min_length=1)
    when: Condition | None = None


# output sections discriminate on output_type ...
OutputSection = Annotated[
    IcsOutput | VcfOutput | PacketOutput | ResourcesOutput | SummaryOutput,
    Field(discriminator="output_type"),
]

# ... and the section list discriminates on kind, with the output sub-union as
# one branch (all output members share kind="output").
Section = Annotated[
    InfoSection | FactGatherSection | ScreenerSection | OutputSection,
    Field(discriminator="kind"),
]


class Corpus(_Base):
    metadata: Metadata
    contacts: list[Contact] = Field(default_factory=list)
    deadlines: list[Deadline] = Field(default_factory=list)
    resources: list[Resource] = Field(default_factory=list)
    sections: list[Section] = Field(min_length=1)
