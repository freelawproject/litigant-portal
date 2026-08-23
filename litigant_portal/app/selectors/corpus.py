from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, Literal

import yaml
from django.conf import settings
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)
from pypdf import PdfReader

from litigant_portal.app.models.choices import (
    JurisdictionLevel,
    State,
    TopicFlowFormConditionOperator,
    VariableDataType,
)

CORPUS_DIR = settings.BASE_DIR / "corpus"
FORMS_DIR = CORPUS_DIR / "forms"
COURTS_DIR = CORPUS_DIR / "courts"
VARIABLES_PATH = CORPUS_DIR / "variables.yml"


# -----------------------------------------------------------------------------
# Corpus schemas
# -----------------------------------------------------------------------------


SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
TEMPLATE_VARIABLE_PATTERN = re.compile(r"\{([a-z0-9_]+)(?::[^}]*)?\}")

SlugField = Annotated[str, Field(pattern=SLUG_PATTERN.pattern)]
VariableNameField = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]

ValueType = bool | int | float | str


def _variable_value_problem(value, variable) -> str | None:
    """Why ``value`` is not a legal value for ``variable``, or None."""
    data_type = variable.data_type
    if data_type == "boolean":
        return None if isinstance(value, bool) else "must be true or false"
    if data_type == "number":
        ok = isinstance(value, int | float) and not isinstance(value, bool)
        return None if ok else "must be a number"
    if data_type == "choice":
        values = [c.value for c in variable.choices or []]
        if isinstance(value, str) and value in values:
            return None
        return f"must be one of {values}"
    if data_type in ("date", "datetime"):
        parse = (
            date.fromisoformat
            if data_type == "date"
            else datetime.fromisoformat
        )
        try:
            parse(value)
        except (TypeError, ValueError):
            return f"must be an ISO {data_type} string"
        return None
    return None if isinstance(value, str) else "must be a string"


class BaseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


# Variables


class ChoiceSchema(BaseSchema):
    """Populates one ``Variable.choices`` entry."""

    value: str = Field(min_length=1)
    label: str = Field(min_length=1)


class AskedWhenSchema(BaseSchema):
    """Populates ``Variable.asked_when`` and ``Variable.asked_when_value``."""

    variable: VariableNameField
    value: ValueType


class VariableSchema(BaseSchema):
    """Populates a ``Variable`` row."""

    name: VariableNameField
    label: str = Field(min_length=1)
    question: str = ""
    help_text: str = ""
    required: bool = False
    data_type: VariableDataType = VariableDataType.TEXT
    choices: list[ChoiceSchema] = []
    default: ValueType | None = None
    is_global: bool = Field(default=False, alias="global")
    asked_when: AskedWhenSchema | None = None

    @model_validator(mode="after")
    def _choices_iff_choice_type(self):
        """Validates:
        - choice-typed variables declare choices, and only they do
        - choice values are unique
        """
        if self.data_type == "choice":
            if not self.choices:
                raise ValueError("choice-typed variable must declare choices")
            values = [c.value for c in self.choices]
            if len(values) != len(set(values)):
                raise ValueError("choice values must be unique")
        elif self.choices:
            raise ValueError("only choice-typed variables take choices")
        return self

    @model_validator(mode="after")
    def _default_is_legal(self):
        """Validates:
        - default is a legal value for the variable's data type
        """
        if self.default is None:
            return self
        problem = _variable_value_problem(self.default, self)
        if problem is not None:
            raise ValueError(f"default {self.default!r} {problem}")
        return self


class VariablesSchema(BaseSchema):
    """Populates the ``Variable`` table."""

    variables: list[VariableSchema] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_names(self):
        """Validates:
        - variable names are unique
        """
        names = [v.name for v in self.variables]
        if len(names) != len(set(names)):
            duplicates = sorted({n for n in names if names.count(n) > 1})
            raise ValueError(f"duplicate variable names: {duplicates}")
        return self

    @model_validator(mode="after")
    def _gates_resolve(self):
        """Validates:
        - asked_when names a known variable
        - asked_when value is legal for the gate's data type
        - no asked_when cycles
        """
        by_name = {v.name: v for v in self.variables}
        problems = []
        for v in self.variables:
            if v.asked_when is None:
                continue
            gate = by_name.get(v.asked_when.variable)
            if gate is None:
                problems.append(
                    f"{v.name}: asked_when names unknown variable "
                    f"{v.asked_when.variable!r}"
                )
                continue
            value_problem = _variable_value_problem(v.asked_when.value, gate)
            if value_problem is not None:
                problems.append(
                    f"{v.name}: asked_when value {v.asked_when.value!r} "
                    f"{value_problem} (gate {gate.name} is {gate.data_type})"
                )

        done: set[str] = set()
        for start in by_name:
            chain: list[str] = []
            name: str | None = start
            while name is not None and name not in done:
                if name in chain:
                    cycle = chain[chain.index(name) :] + [name]
                    problems.append(f"asked_when cycle: {' -> '.join(cycle)}")
                    break
                chain.append(name)
                gate_ref = by_name[name].asked_when
                name = (
                    gate_ref.variable
                    if gate_ref is not None and gate_ref.variable in by_name
                    else None
                )
            done.update(chain)
        if problems:
            raise ValueError("; ".join(problems))
        return self


# Forms


class FormFieldMappingSchema(BaseSchema):
    """Populates a ``FormField`` row."""

    pdf_field: str = Field(min_length=1)
    template: str = ""
    checked_when: str = ""


class FormSchema(BaseSchema):
    """Populates a ``Form`` row."""

    name: str = Field(min_length=1)
    fields: list[FormFieldMappingSchema]


# Courts


class ContactSchema(BaseSchema):
    """Populates a ``Contact`` row."""

    name: str = Field(min_length=1)
    phone: str = ""
    email: str = ""
    url: str = ""
    note: str = ""


class ResourceSchema(BaseSchema):
    """Populates a ``Resource`` row."""

    label: str = Field(min_length=1)
    url: str = Field(min_length=1)
    note: str = ""


class CourtSchema(BaseSchema):
    """Populates the ``Site`` singleton's court fields, ``Contact``, and
    ``Resource`` rows."""

    name: str = Field(min_length=1)
    court_name: str = Field(min_length=1)
    jurisdiction_level: JurisdictionLevel | Literal[""] = ""
    state: State | Literal[""] = ""
    official_url: str = ""
    official_resources_url: str = ""
    contacts: list[ContactSchema] = []
    resources: list[ResourceSchema] = []


# Topics


class TopicSchema(BaseSchema):
    """Populates a ``Topic`` row."""

    title: str = Field(min_length=1)
    subtitle: str = ""
    description: str = ""
    icon: str = ""
    meta_description: str = ""
    prompts: list[str] = []
    order: int = 0


# Flows


class SectionSchema(BaseSchema):
    """Populates a ``TopicFlowSection`` row."""

    heading: str = Field(min_length=1)
    content: str = Field(min_length=1)


class InterviewPageSchema(BaseSchema):
    """Populates a ``TopicFlowInterviewPage`` row and its
    ``TopicFlowInterviewVariable`` rows."""

    title: str = Field(min_length=1)
    description: str = ""
    variables: list[VariableNameField] = Field(min_length=1)


class WhenSchema(BaseSchema):
    """Populates ``TopicFlowFormCondition``'s condition fields."""

    variable: VariableNameField
    operator: TopicFlowFormConditionOperator = (
        TopicFlowFormConditionOperator.EQUALS
    )
    value: ValueType


class PacketEntrySchema(BaseSchema):
    """Populates a ``TopicFlowFormCondition`` row."""

    form: SlugField
    when: WhenSchema | None = None


class DeadlineSchema(BaseSchema):
    """Populates a ``TopicFlowDeadline`` row."""

    label: str = Field(min_length=1)
    description: str = ""
    offset_days: int
    offset_from: VariableNameField


class LinkSchema(BaseSchema):
    """Populates a ``TopicFlowLink`` row."""

    name: str = Field(min_length=1)
    url: str = Field(min_length=1)


class FlowSchema(BaseSchema):
    """Populates a ``TopicFlow`` row."""

    name: str = Field(min_length=1)
    enabled: bool = False
    order: int = 0
    sections: list[SectionSchema] = Field(min_length=1)
    interview: list[InterviewPageSchema] = []
    packet: list[PacketEntrySchema] = []
    deadlines: list[DeadlineSchema] = []
    links: list[LinkSchema] = []

    @model_validator(mode="after")
    def _no_duplicate_packet_entries(self):
        """Validates:
        - a form repeats in the packet only under different conditions
        """
        seen = set()
        for entry in self.packet:
            when = entry.when
            key = (
                (entry.form,)
                if when is None
                else (entry.form, when.variable, when.operator, when.value)
            )
            if key in seen:
                raise ValueError(
                    f"duplicate packet entry for form {entry.form!r}; repeating "
                    "a form is only allowed under different conditions"
                )
            seen.add(key)
        return self

    @model_validator(mode="after")
    def _no_duplicate_placements(self):
        """Validates:
        - each variable is placed on at most one interview page
        """
        placed = set()
        for page in self.interview:
            for name in page.variables:
                if name in placed:
                    raise ValueError(
                        f"variable {name} placed on more than one page"
                    )
                placed.add(name)
        return self


# Corpus


class CorpusSchema(BaseSchema):
    """The whole corpus, cross-checked."""

    variables: dict[VariableNameField, VariableSchema]
    forms: dict[SlugField, FormSchema]
    form_acro_fields: dict[str, set[str]]
    courts: dict[SlugField, CourtSchema]
    topics: dict[tuple[SlugField, SlugField], TopicSchema]
    flows: dict[tuple[SlugField, SlugField, SlugField], FlowSchema]

    @model_validator(mode="after")
    def _forms_resolve(self):
        """Validates:
        - each form has its matching ``<slug>.pdf``
        - each mapped pdf_field exists in the PDF's AcroForm
        - each template placeholder names a known variable
        - each PDF has its matching form document
        """
        variables = set(self.variables)
        for slug, form in sorted(self.forms.items()):
            if slug not in self.form_acro_fields:
                raise ValueError(
                    f"form {slug}: no matching {slug}.pdf in the corpus"
                )
            pdf_fields = self.form_acro_fields[slug]
            for mapping in form.fields:
                if mapping.pdf_field not in pdf_fields:
                    raise ValueError(
                        f"form {slug}: pdf_field {mapping.pdf_field!r} "
                        f"does not exist in {slug}.pdf"
                    )
                unknown = sorted(
                    set(TEMPLATE_VARIABLE_PATTERN.findall(mapping.template))
                    - variables
                )
                if unknown:
                    raise ValueError(
                        f"form {slug}: template references unknown "
                        f"variable {unknown[0]}"
                    )
        for stem in sorted(set(self.form_acro_fields) - set(self.forms)):
            raise ValueError(f"{stem}.pdf: no matching form document")
        return self

    @model_validator(mode="after")
    def _flows_resolve(self):
        """Validates, per flow:
        - packet entries name known forms
        - interview pages place known variables
        - condition variables exist and their values are legal
        - deadline offset_from names a date variable
        - every consumed variable is placed in the interview
        - gate variables are placed before the variables they gate
        - condition variables are placed before variables only their
          conditional forms consume
        """
        for key, flow in sorted(self.flows.items()):
            self._flow_resolves("/".join(key), flow, self.variables)
        return self

    def _flow_resolves(self, label, flow, variables):
        for entry in flow.packet:
            if entry.form not in self.forms:
                raise ValueError(
                    f"flow {label}: packet names unknown form {entry.form}"
                )

        position = {
            name: index
            for index, name in enumerate(
                name for page in flow.interview for name in page.variables
            )
        }
        for name in position:
            if name not in variables:
                raise ValueError(
                    f"flow {label}: interview places unknown variable {name}"
                )

        consumed: set[str] = set()
        unconditional: set[str] = set()
        conditional: list[tuple[str, set[str]]] = []
        for entry in flow.packet:
            form_names: set[str] = set()
            for mapping in self.forms[entry.form].fields:
                form_names |= set(
                    TEMPLATE_VARIABLE_PATTERN.findall(mapping.template)
                )
            form_names &= set(variables)
            consumed |= form_names
            if entry.when is None:
                unconditional |= form_names
                continue
            condition = entry.when
            variable = variables.get(condition.variable)
            if variable is None:
                raise ValueError(
                    f"flow {label}: condition names unknown variable "
                    f"{condition.variable}"
                )
            consumed.add(condition.variable)
            unconditional.add(condition.variable)
            conditional.append((condition.variable, form_names))
            value_problem = _variable_value_problem(condition.value, variable)
            if value_problem is not None:
                raise ValueError(
                    f"flow {label}: condition value {condition.value!r} "
                    f"{value_problem} ({condition.variable} is "
                    f"{variable.data_type})"
                )
        for deadline in flow.deadlines:
            variable = variables.get(deadline.offset_from)
            if variable is None:
                raise ValueError(
                    f"flow {label}: deadline offset_from names unknown "
                    f"variable {deadline.offset_from}"
                )
            if variable.data_type not in ("date", "datetime"):
                raise ValueError(
                    f"flow {label}: deadline offset_from "
                    f"{deadline.offset_from} is {variable.data_type}, "
                    f"not a date"
                )
            consumed.add(deadline.offset_from)
            unconditional.add(deadline.offset_from)

        missing = sorted(consumed - set(position))
        if missing:
            raise ValueError(
                f"flow {label}: consumed but not on any interview page: "
                f"{missing}"
            )
        for name in sorted(position, key=position.get):
            gate_spec = variables[name].asked_when
            if gate_spec is None:
                continue
            gate = gate_spec.variable
            if gate not in position:
                raise ValueError(
                    f"flow {label}: {name} is gated on {gate}, which is "
                    f"not placed"
                )
            if position[gate] > position[name]:
                raise ValueError(
                    f"flow {label}: gate variable {gate} must be placed "
                    f"before {name}"
                )
        for condition, form_names in conditional:
            for name in sorted(form_names - unconditional):
                if position[name] < position[condition]:
                    raise ValueError(
                        f"flow {label}: condition variable {condition} must "
                        f"be placed before {name}, which only its "
                        f"conditional form consumes"
                    )

    @model_validator(mode="after")
    def _no_orphans(self):
        """Validates:
        - every form is referenced by some flow's packet
        - topic slugs are unique across courts
        """
        referenced = {
            entry.form for flow in self.flows.values() for entry in flow.packet
        }
        for slug in sorted(set(self.forms) - referenced):
            raise ValueError(
                f"form {slug}: not referenced by any flow's packet"
            )
        by_topic: dict[str, list[str]] = {}
        for court_slug, topic_slug in self.topics:
            by_topic.setdefault(topic_slug, []).append(court_slug)
        for topic_slug, court_slugs in sorted(by_topic.items()):
            if len(court_slugs) > 1:
                raise ValueError(
                    f"topic {topic_slug} is defined by more than one "
                    f"court: {sorted(court_slugs)}"
                )
        return self


# -----------------------------------------------------------------------------
# Corpus loaders
# -----------------------------------------------------------------------------


def corpus_parse_yaml(path: Path, model: type[BaseSchema]):
    """Parse and validate one YAML document."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"{path}: cannot load: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: top level must be a mapping")
    try:
        return model.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"{path}: {exc}") from exc


def corpus_load_variables() -> dict[str, VariableSchema]:
    """Every variable, app-wide, by name."""
    doc = corpus_parse_yaml(VARIABLES_PATH, VariablesSchema)
    return {v.name: v for v in doc.variables}


def corpus_load_forms() -> dict[str, FormSchema]:
    """Every form document, by form slug."""
    return {
        path.stem: corpus_parse_yaml(path, FormSchema)
        for path in sorted(FORMS_DIR.glob("*.yml"))
    }


def corpus_load_form_acro_fields() -> dict[str, set[str]]:
    """Every fillable PDF's AcroForm field names, by form slug."""
    pdfs = {}
    for path in sorted(FORMS_DIR.glob("*.pdf")):
        try:
            reader = PdfReader(path)
        except Exception as exc:
            raise ValueError(f"{path}: cannot read PDF: {exc}") from exc
        pdfs[path.stem] = set((reader.get_fields() or {}).keys())
    return pdfs


def corpus_load_courts() -> dict[str, CourtSchema]:
    """Every court document, by court slug."""
    return {
        path.parts[-2]: corpus_parse_yaml(path, CourtSchema)
        for path in sorted(COURTS_DIR.glob("*/court.yml"))
    }


def corpus_load_topics() -> dict[tuple[str, str], TopicSchema]:
    """Every topic document, by (court, topic) slug."""
    return {
        (path.parts[-4], path.parts[-2]): corpus_parse_yaml(path, TopicSchema)
        for path in sorted(COURTS_DIR.glob("*/topics/*/topic.yml"))
    }


def corpus_load_flows() -> dict[tuple[str, str, str], FlowSchema]:
    """Every flow document, by (court, topic, flow) slug."""
    return {
        (path.parts[-5], path.parts[-3], path.stem): corpus_parse_yaml(
            path, FlowSchema
        )
        for path in sorted(COURTS_DIR.glob("*/topics/*/flows/*.yml"))
    }


def corpus_load() -> CorpusSchema:
    """Load and validate the whole content corpus."""
    return CorpusSchema(
        variables=corpus_load_variables(),
        forms=corpus_load_forms(),
        form_acro_fields=corpus_load_form_acro_fields(),
        courts=corpus_load_courts(),
        topics=corpus_load_topics(),
        flows=corpus_load_flows(),
    )
