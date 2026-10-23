"""Corpus schema contract tests.

These lock the authoring rules the corpus validates at the boundary, so a
typo in a court form fails the check rather than printing a wrong PDF.
"""

from unittest import mock

import pytest
from django.core.cache import cache
from pydantic import ValidationError

from litigant_portal.app.cache import CORPUS_TOPIC_KEYS_CACHE_KEY
from litigant_portal.app.selectors import corpus as selectors
from litigant_portal.app.selectors.corpus import (
    BrandingSchema,
    CorpusSchema,
    FlowSchema,
    FormFieldMappingSchema,
    FormSchema,
    VariableSchema,
    VariablesSchema,
    corpus_load,
    corpus_load_courts,
    corpus_parse_yaml,
)


def _corpus_data():
    """A minimal corpus that validates, for tests to break one rule at a
    time. ``form_acro_fields`` stands in for reading a real PDF."""
    return {
        "variables": {
            "full_name": {"name": "full_name", "label": "Full name"},
            "pet_kind": {
                "name": "pet_kind",
                "label": "Kind of pet",
                "data_type": "choice",
                "choices": [
                    {"value": "dog", "label": "Dog"},
                    {"value": "cat", "label": "Cat"},
                ],
            },
            "licensed": {
                "name": "licensed",
                "label": "Already licensed",
                "data_type": "boolean",
            },
            "adopted_on": {
                "name": "adopted_on",
                "label": "Adoption date",
                "data_type": "date",
            },
        },
        "forms": {
            "license": {
                "name": "Pet license application",
                "fields": [
                    {"pdf_field": "Name", "template": "{full_name}"},
                    {
                        "pdf_field": "Check Box1",
                        "checked_when": {
                            "variable": "pet_kind",
                            "value": "dog",
                        },
                    },
                    {"pdf_field": "Check Box2", "checked": True},
                    {"pdf_field": "Check Box3", "checked": False},
                ],
            }
        },
        "form_acro_fields": {
            "license": {
                "Name": "/Tx",
                "Check Box1": "/Btn",
                "Check Box2": "/Btn",
                "Check Box3": "/Btn",
            }
        },
        "courts": {
            "north-dakota": {
                "name": "North Dakota",
                "court_name": "District Court",
                "contacts": [{"id": "clerk", "name": "Clerk"}],
                "resources": [
                    {"id": "guide", "label": "Guide", "url": "https://a.test"}
                ],
            }
        },
        "topics": {("north-dakota", "pets"): {"title": "Pets"}},
        "flows": {
            ("north-dakota", "pets", "standard"): {
                "name": "Standard",
                "sections": [
                    {
                        "id": "start",
                        "heading": "Start here",
                        "content": "Read.",
                    }
                ],
                "interview": [
                    {
                        "title": "About your pet",
                        "variables": [
                            "full_name",
                            "pet_kind",
                            "licensed",
                            "adopted_on",
                        ],
                    }
                ],
                "packet": [{"form": "license"}],
                "deadlines": [
                    {
                        "id": "license_due",
                        "label": "License due",
                        "offset_days": 30,
                        "offset_from": "adopted_on",
                    }
                ],
            }
        },
    }


def _checkbox(**mapping):
    """The fixture corpus with its conditional checkbox replaced."""
    data = _corpus_data()
    data["forms"]["license"]["fields"][1] = {
        "pdf_field": "Check Box1",
        **mapping,
    }
    return data


def test_fixture_corpus_validates():
    CorpusSchema.model_validate(_corpus_data())


def test_shipped_corpus_validates():
    corpus_load()


ND_TOPIC = ("north-dakota", "adult-name-change")


def test_shipped_flows_carry_their_page_content():
    corpus = corpus_load()
    for key, flow in corpus.flows.items():
        assert flow.layout, f"{key} has no authored layout"
        if flow.packet:
            assert "packet" in flow.layout, f"{key} does not place packet"
        if flow.deadlines:
            assert "calendar" in flow.layout, f"{key} does not place calendar"
    standard = corpus.flows[(*ND_TOPIC, "standard")]
    waiver = corpus.flows[(*ND_TOPIC, "waiver")]
    assert standard.handoff is not None, "ND standard flow has no handoff"
    assert waiver.handoff is not None, "ND waiver flow has no handoff"
    assert standard.handoff.interview_reference.endswith(
        "petition-standard.yml"
    )
    assert waiver.handoff.interview_reference.endswith("petition-waiver.yml")
    assert "name_change_publication_date" in standard.handoff.interview_prefill
    assert waiver.handoff.interview_prefill == {
        key: value
        for key, value in standard.handoff.interview_prefill.items()
        if key != "name_change_publication_date"
    }
    for slug, form in corpus.forms.items():
        if slug.startswith("nd-"):
            assert form.url, f"{slug} has no url"


def test_shipped_nd_links_repeat_the_form_urls():
    """The ND ``links`` lists stay until the render piece decides whether
    they survive forms carrying a url (#1012). Until then both copies of
    each court PDF url must agree."""
    corpus = corpus_load()
    form_urls = {
        form.url
        for slug, form in corpus.forms.items()
        if slug.startswith("nd-")
    }
    for slug in ("standard", "waiver"):
        for link in corpus.flows[(*ND_TOPIC, slug)].links:
            assert link.url in form_urls, f"{slug} link {link.id} has no form"


# One mapping, one mode


def test_plain_text_fill():
    mapping = FormFieldMappingSchema(pdf_field="Name", template="{full_name}")
    assert mapping.is_text


def test_blank_template_records_an_empty_field():
    FormFieldMappingSchema(pdf_field="Text1", template="")


def test_checked_and_checked_when_do_not_combine():
    with pytest.raises(ValidationError, match="do not combine"):
        FormFieldMappingSchema(
            pdf_field="Check Box1",
            checked=True,
            checked_when={"variable": "pet_kind", "value": "dog"},
        )


def test_checkbox_takes_no_template():
    with pytest.raises(ValidationError, match="no template"):
        FormFieldMappingSchema(
            pdf_field="Check Box1", template="{pet_kind}", checked=True
        )


def test_constant_off_takes_no_template_either():
    with pytest.raises(ValidationError, match="no template"):
        FormFieldMappingSchema(
            pdf_field="Check Box1", template="{pet_kind}", checked=False
        )


def test_constant_off_and_checked_when_do_not_combine():
    with pytest.raises(ValidationError, match="do not combine"):
        FormFieldMappingSchema(
            pdf_field="Check Box1",
            checked=False,
            checked_when={"variable": "pet_kind", "value": "dog"},
        )


def test_string_checked_when_is_rejected():
    with pytest.raises(ValidationError):
        FormFieldMappingSchema(pdf_field="Check Box1", checked_when="dog")


def test_form_url_is_optional():
    form = FormSchema(name="Pet license", fields=[])
    assert form.url == ""
    form = FormSchema(
        name="Pet license", fields=[], url="https://a.test/f.pdf"
    )
    assert form.url == "https://a.test/f.pdf"


def test_form_url_fits_the_column():
    url = "https://a.test/" + "f" * 486
    with pytest.raises(ValidationError, match="url"):
        FormSchema(name="Pet license", fields=[], url=url)


@pytest.mark.parametrize(
    "url",
    [
        "a.test/f.pdf",
        "/forms/f.pdf",
        "htps://a.test/f.pdf",
        "https:///f.pdf",
        "javascript:alert(1)",
        "mailto:clerk@a.test",
    ],
    ids=["no-scheme", "relative", "misspelled", "no-host", "script", "mailto"],
)
def test_form_url_must_be_absolute_http(url):
    with pytest.raises(ValidationError, match="absolute, http or https"):
        FormSchema(name="Pet license", fields=[], url=url)


def test_form_url_takes_http_and_https():
    for url in ("http://a.test/f.pdf", "https://a.test/f.pdf?v=2"):
        assert FormSchema(name="Pet license", fields=[], url=url).url == url


def test_duplicate_pdf_field_is_rejected():
    data = _corpus_data()
    data["forms"]["license"]["fields"].append(
        {"pdf_field": "Check Box2", "checked": False}
    )
    with pytest.raises(ValidationError, match="mapped more than once"):
        CorpusSchema.model_validate(data)


# The PDF's field types police the modes


def test_bare_checkbox_mapping_is_rejected():
    data = _checkbox()
    with pytest.raises(ValidationError, match="declare checked"):
        CorpusSchema.model_validate(data)


def test_text_template_on_a_checkbox_is_rejected():
    data = _checkbox(template="{full_name}")
    with pytest.raises(ValidationError, match="declare checked"):
        CorpusSchema.model_validate(data)


def test_checkbox_mode_on_a_text_field_is_rejected():
    data = _corpus_data()
    data["forms"]["license"]["fields"][0] = {
        "pdf_field": "Name",
        "checked": True,
    }
    with pytest.raises(ValidationError, match="is not a checkbox"):
        CorpusSchema.model_validate(data)


# checked_when, against the variable it names


def test_unknown_variable_is_rejected():
    data = _checkbox(checked_when={"variable": "pet_knid", "value": "dog"})
    with pytest.raises(ValidationError, match="unknown variable pet_knid"):
        CorpusSchema.model_validate(data)


def test_choice_value_off_the_list_is_rejected():
    data = _checkbox(checked_when={"variable": "pet_kind", "value": "dgo"})
    with pytest.raises(ValidationError, match="must be one of"):
        CorpusSchema.model_validate(data)


def test_boolean_condition_takes_a_boolean():
    CorpusSchema.model_validate(
        _checkbox(checked_when={"variable": "licensed", "value": True})
    )


def test_boolean_condition_rejects_a_string():
    data = _checkbox(checked_when={"variable": "licensed", "value": "yes"})
    with pytest.raises(ValidationError, match="must be true or false"):
        CorpusSchema.model_validate(data)


# The flow consumes a checkbox's variable


def test_checkbox_variable_must_be_placed_in_the_interview():
    data = _corpus_data()
    data["flows"][("north-dakota", "pets", "standard")]["interview"] = [
        {"title": "About your pet", "variables": ["full_name", "licensed"]}
    ]
    with pytest.raises(ValidationError, match="consumed but not on any"):
        CorpusSchema.model_validate(data)


FLOW_KEY = ("north-dakota", "pets", "standard")


def _flow(data):
    return data["flows"][FLOW_KEY]


# Variable rules


def test_choice_type_must_declare_choices():
    with pytest.raises(ValidationError, match="must declare choices"):
        VariableSchema(name="pet_kind", label="Kind", data_type="choice")


def test_only_choice_type_takes_choices():
    with pytest.raises(ValidationError, match="only choice-typed"):
        VariableSchema(
            name="full_name",
            label="Name",
            choices=[{"value": "a", "label": "A"}],
        )


def test_duplicate_choice_values_are_rejected():
    with pytest.raises(ValidationError, match="must be unique"):
        VariableSchema(
            name="pet_kind",
            label="Kind",
            data_type="choice",
            choices=[
                {"value": "dog", "label": "Dog"},
                {"value": "dog", "label": "Also dog"},
            ],
        )


def test_default_must_be_legal_for_the_data_type():
    with pytest.raises(ValidationError, match="must be a number"):
        VariableSchema(
            name="age", label="Age", data_type="number", default="old"
        )


def test_private_is_an_optional_glossary_flag_authored_as_private():
    assert VariableSchema(name="age", label="Age").is_private is False
    variable = VariableSchema.model_validate(
        {"name": "age", "label": "Age", "private": True}
    )
    assert variable.is_private is True
    assert variable.model_dump()["is_private"] is True


# Drift guard, the sibling of test_content_never_prefill: the facts the ND
# interview asks that identify a person never echo back on the rows path.
@pytest.mark.parametrize(
    "name",
    [
        "first_name",
        "middle_name",
        "last_name",
        "street_address",
        "city",
        "county",
        "zip_code",
        "date_of_birth",
        "place_of_birth",
        "phone_number",
        "name_change_requested_first",
        "name_change_requested_middle",
        "name_change_requested_last",
        "name_change_criminal_history",
        "name_change_conviction_charge",
        "name_change_conviction_class",
        "name_change_conviction_court",
        "name_change_conviction_year",
        "name_change_publication_date",
        "name_change_waiver_domestic_violence",
    ],
)
def test_shipped_identity_variable_is_private(name):
    assert corpus_load().variables[name].is_private is True


def test_help_text_and_required_are_optional_glossary_fields():
    variable = VariableSchema(name="age", label="Age")
    assert variable.help_text == ""
    assert variable.required is False
    variable = VariableSchema(
        name="age", label="Age", help_text="In years.", required=True
    )
    assert variable.help_text == "In years."
    assert variable.required is True


# Glossary rules


def _glossary(*variables):
    return VariablesSchema.model_validate({"variables": list(variables)})


def test_duplicate_variable_names_are_rejected():
    with pytest.raises(ValidationError, match="duplicate variable names"):
        _glossary(
            {"name": "full_name", "label": "Name"},
            {"name": "full_name", "label": "Name again"},
        )


def test_asked_when_must_name_a_known_variable():
    with pytest.raises(ValidationError, match="unknown variable 'ghost'"):
        _glossary(
            {
                "name": "vaccinated",
                "label": "Vaccinated",
                "asked_when": {"variable": "ghost", "value": True},
            }
        )


def test_asked_when_value_must_be_legal_for_the_gate():
    with pytest.raises(ValidationError, match="must be true or false"):
        _glossary(
            {"name": "licensed", "label": "Licensed", "data_type": "boolean"},
            {
                "name": "vaccinated",
                "label": "Vaccinated",
                "asked_when": {"variable": "licensed", "value": "yes"},
            },
        )


def test_asked_when_cycles_are_rejected():
    with pytest.raises(ValidationError, match="asked_when cycle"):
        _glossary(
            {
                "name": "a",
                "label": "A",
                "data_type": "boolean",
                "asked_when": {"variable": "b", "value": True},
            },
            {
                "name": "b",
                "label": "B",
                "data_type": "boolean",
                "asked_when": {"variable": "a", "value": True},
            },
        )


# Flow document rules


def _flow_doc(**overrides):
    return FlowSchema.model_validate(
        {
            "name": "Standard",
            "sections": [
                {"id": "start", "heading": "Start", "content": "Read."}
            ],
            **overrides,
        }
    )


def test_duplicate_packet_entry_is_rejected():
    with pytest.raises(ValidationError, match="duplicate packet entry"):
        _flow_doc(packet=[{"form": "license"}, {"form": "license"}])


def test_same_form_under_different_conditions_is_allowed():
    _flow_doc(
        packet=[
            {
                "form": "license",
                "when": {"variable": "licensed", "value": True},
            },
            {
                "form": "license",
                "when": {"variable": "licensed", "value": False},
            },
        ]
    )


def test_variable_placed_on_two_pages_is_rejected():
    with pytest.raises(ValidationError, match="more than one page"):
        _flow_doc(
            interview=[
                {"title": "One", "variables": ["full_name"]},
                {"title": "Two", "variables": ["full_name"]},
            ]
        )


def _section(id, heading="H"):
    return {"id": id, "heading": heading, "content": "Read."}


# Layout: the page's order of sections and blocks


def test_layout_defaults_to_sections_then_blocks():
    flow = _flow_doc(sections=[_section("start"), _section("fees")])
    assert flow.layout == []
    assert flow.resolved_layout == [
        "start",
        "fees",
        "interview",
        "packet",
        "calendar",
        "contacts",
        "resources",
    ]


def test_authored_layout_is_kept_as_written():
    layout = ["start", "packet", "fees", "interview"]
    flow = _flow_doc(
        sections=[_section("start"), _section("fees")], layout=layout
    )
    assert flow.resolved_layout == layout


def test_blank_layout_means_the_default_order():
    flow = _flow_doc(layout=None)
    assert flow.layout == []
    assert flow.resolved_layout[:2] == ["start", "interview"]


def test_layout_must_place_every_section():
    with pytest.raises(ValidationError, match="missing section.*fees"):
        _flow_doc(
            sections=[_section("start"), _section("fees")], layout=["start"]
        )


def test_layout_places_a_section_once():
    with pytest.raises(ValidationError, match="more than once.*start"):
        _flow_doc(layout=["start", "start"])


def test_layout_places_a_block_at_most_once():
    with pytest.raises(ValidationError, match="more than once.*packet"):
        _flow_doc(layout=["start", "packet", "packet"])


def test_layout_rejects_an_unknown_name():
    with pytest.raises(ValidationError, match="unknown.*summary"):
        _flow_doc(layout=["start", "summary"])


_FILLED_BLOCKS = {
    "interview": {"interview": [{"title": "About you", "variables": ["age"]}]},
    "packet": {"packet": [{"form": "license"}]},
    "calendar": {
        "deadlines": [
            {
                "id": "due",
                "label": "Due",
                "offset_days": 30,
                "offset_from": "adopted_on",
            }
        ]
    },
}


@pytest.mark.parametrize("block", sorted(_FILLED_BLOCKS))
def test_layout_must_place_a_block_the_flow_fills(block):
    with pytest.raises(ValidationError, match=f"missing blocks.*{block}"):
        _flow_doc(layout=["start"], **_FILLED_BLOCKS[block])


@pytest.mark.parametrize("block", sorted(_FILLED_BLOCKS))
def test_layout_places_a_block_the_flow_fills(block):
    flow = _flow_doc(layout=["start", block], **_FILLED_BLOCKS[block])
    assert flow.resolved_layout == ["start", block]


def test_layout_may_omit_an_empty_block():
    assert _flow_doc(layout=["start"]).resolved_layout == ["start"]


def test_section_id_may_not_be_a_block_name():
    with pytest.raises(ValidationError, match="reserved.*packet"):
        _flow_doc(sections=[_section("packet")])


# Handoff: the docassemble interview a flow's packet opens


def _handoff(**overrides):
    return {
        "interview_reference": "docassemble.pets:data/questions/license.yml",
        "interview_prefill": {"full_name": "owner_name"},
        **overrides,
    }


def test_handoff_is_optional():
    assert _flow_doc().handoff is None


def test_handoff_keeps_its_reference_and_prefill():
    flow = _flow_doc(handoff=_handoff())
    assert flow.handoff.interview_reference.startswith("docassemble.pets:")
    assert flow.handoff.interview_prefill == {"full_name": "owner_name"}


def test_handoff_prefill_defaults_to_nothing():
    flow = _flow_doc(handoff=_handoff(interview_prefill=None))
    assert flow.handoff.interview_prefill == {}


@pytest.mark.parametrize(
    "reference",
    [
        "",
        "docassemble.pets:license.yml",
        "license.yml",
        "https://da.test/interview?i=docassemble.pets:data/questions/l.yml",
        "docassemble.pets:data/questions/" + "f" * 230 + ".yml",
    ],
    ids=["blank", "short-alias", "bare-file", "url", "over-column"],
)
def test_handoff_reference_is_the_full_docassemble_path(reference):
    with pytest.raises(ValidationError, match="interview_reference"):
        _flow_doc(handoff=_handoff(interview_reference=reference))


@pytest.mark.parametrize("name", ["Owner Name", "1st", "", "Full_name"])
def test_handoff_prefill_keys_are_glossary_names(name):
    with pytest.raises(ValidationError, match="interview_prefill"):
        _flow_doc(handoff=_handoff(interview_prefill={name: "owner_name"}))


@pytest.mark.parametrize("name", ["Owner Name", "1st", ""])
def test_handoff_prefill_values_are_identifiers(name):
    with pytest.raises(ValidationError, match="interview_prefill"):
        _flow_doc(handoff=_handoff(interview_prefill={"full_name": name}))


@pytest.mark.parametrize("name", ["ownerName", "_owner", "Owner1"])
def test_handoff_prefill_values_take_any_identifier(name):
    flow = _flow_doc(handoff=_handoff(interview_prefill={"full_name": name}))
    assert flow.handoff.interview_prefill == {"full_name": name}


def test_handoff_prefill_key_must_be_a_known_variable():
    data = _corpus_data()
    data["flows"][FLOW_KEY]["handoff"] = _handoff(
        interview_prefill={"full_name": "owner_name", "pet_age": "age"}
    )
    with pytest.raises(ValidationError, match="prefill.*unknown.*pet_age"):
        CorpusSchema.model_validate(data)


def test_handoff_prefill_key_must_be_placed_in_the_flow():
    data = _corpus_data()
    flow = data["flows"][FLOW_KEY]
    flow["interview"][0]["variables"].remove("licensed")
    flow["handoff"] = _handoff(interview_prefill={"licensed": "has_license"})
    with pytest.raises(
        ValidationError, match="not on any interview page.*licensed"
    ):
        CorpusSchema.model_validate(data)


def test_handoff_prefill_of_known_variables_validates():
    data = _corpus_data()
    data["flows"][FLOW_KEY]["handoff"] = _handoff()
    CorpusSchema.model_validate(data)


# Source ids: the citation targets stored in user threads


def test_section_without_an_id_is_rejected():
    with pytest.raises(ValidationError, match="id"):
        _flow_doc(sections=[{"heading": "Start", "content": "Read."}])


@pytest.mark.parametrize(
    "overrides",
    [
        {"sections": [_section("start"), _section("start")]},
        {
            "deadlines": [
                {
                    "id": "start",
                    "label": "Due",
                    "offset_days": 1,
                    "offset_from": "adopted_on",
                }
            ]
        },
        {"links": [{"id": "start", "name": "Court", "url": "https://a.test"}]},
        {"sections": [_section("license")], "packet": [{"form": "license"}]},
    ],
    ids=[
        "two-sections",
        "deadline-and-section",
        "link-and-section",
        "section-and-packet-form-slug",
    ],
)
def test_duplicate_ids_in_one_flow_are_rejected(overrides):
    with pytest.raises(ValidationError, match="duplicate ids in flow"):
        _flow_doc(**overrides)


def test_duplicate_id_error_names_the_id():
    with pytest.raises(ValidationError, match=r"\['start'\]"):
        _flow_doc(sections=[_section("start"), _section("start")])


def test_contact_and_resource_sharing_an_id_are_rejected():
    data = _corpus_data()
    data["courts"]["north-dakota"]["resources"][0]["id"] = "clerk"
    with pytest.raises(ValidationError, match="duplicate ids in court"):
        CorpusSchema.model_validate(data)


@pytest.mark.parametrize(
    ("block", "entry"),
    [
        ("contacts", {"id": "clerk_2", "name": "Clerk"}),
        (
            "resources",
            {"id": "guide_2", "label": "Guide", "url": "https://b.test"},
        ),
    ],
    ids=["contact-name", "resource-label"],
)
def test_repeated_contact_name_or_resource_label_in_a_court_is_rejected(
    block, entry
):
    data = _corpus_data()
    data["courts"]["north-dakota"][block].append(entry)
    with pytest.raises(ValidationError, match="duplicate .* in court"):
        CorpusSchema.model_validate(data)


def test_two_courts_keying_the_same_contact_are_rejected():
    data = _corpus_data()
    data["courts"]["other-court"] = {
        "name": "Other",
        "court_name": "Other Court",
        "contacts": [{"id": "clerk", "name": "Other clerk"}],
    }
    with pytest.raises(ValidationError, match="'clerk'.*more than one court"):
        CorpusSchema.model_validate(data)


def test_topic_slugged_court_is_rejected():
    data = _corpus_data()
    data["topics"][("north-dakota", "court")] = {"title": "Court"}
    with pytest.raises(ValidationError, match="'court' is reserved"):
        CorpusSchema.model_validate(data)


@pytest.mark.parametrize(
    "id",
    ["Filing_Fee", "filing fee", "filing/fee", ""],
    ids=["uppercase", "space", "slash", "empty"],
)
def test_id_must_be_a_slug(id):
    with pytest.raises(ValidationError, match="pattern"):
        _flow_doc(sections=[_section(id)])


# Forms resolve against their PDFs


def test_form_without_its_pdf_is_rejected():
    data = _corpus_data()
    del data["form_acro_fields"]["license"]
    with pytest.raises(ValidationError, match="no matching license.pdf"):
        CorpusSchema.model_validate(data)


def test_pdf_without_its_form_document_is_rejected():
    data = _corpus_data()
    data["form_acro_fields"]["stray"] = {"Name": "/Tx"}
    with pytest.raises(ValidationError, match="no matching form document"):
        CorpusSchema.model_validate(data)


def test_unknown_pdf_field_is_rejected():
    data = _corpus_data()
    data["forms"]["license"]["fields"][0]["pdf_field"] = "Nmae"
    with pytest.raises(ValidationError, match="does not exist in license.pdf"):
        CorpusSchema.model_validate(data)


def test_template_naming_an_unknown_variable_is_rejected():
    data = _corpus_data()
    data["forms"]["license"]["fields"][0]["template"] = "{full_nmae}"
    with pytest.raises(ValidationError, match="unknown variable full_nmae"):
        CorpusSchema.model_validate(data)


# Flows resolve against forms and variables


def test_packet_naming_an_unknown_form_is_rejected():
    data = _corpus_data()
    _flow(data)["packet"].append({"form": "nope"})
    with pytest.raises(ValidationError, match="unknown form nope"):
        CorpusSchema.model_validate(data)


def test_interview_placing_an_unknown_variable_is_rejected():
    data = _corpus_data()
    _flow(data)["interview"][0]["variables"].append("ghost")
    with pytest.raises(ValidationError, match="unknown variable ghost"):
        CorpusSchema.model_validate(data)


def test_condition_naming_an_unknown_variable_is_rejected():
    data = _corpus_data()
    _flow(data)["packet"][0]["when"] = {"variable": "ghost", "value": True}
    with pytest.raises(ValidationError, match="unknown variable ghost"):
        CorpusSchema.model_validate(data)


def test_condition_value_must_be_legal_for_the_variable():
    data = _corpus_data()
    _flow(data)["packet"][0]["when"] = {"variable": "licensed", "value": "yes"}
    with pytest.raises(ValidationError, match="must be true or false"):
        CorpusSchema.model_validate(data)


def test_deadline_naming_an_unknown_variable_is_rejected():
    data = _corpus_data()
    _flow(data)["deadlines"][0]["offset_from"] = "ghost"
    with pytest.raises(ValidationError, match="unknown variable ghost"):
        CorpusSchema.model_validate(data)


def test_deadline_offset_from_must_be_a_date():
    data = _corpus_data()
    _flow(data)["deadlines"][0]["offset_from"] = "full_name"
    with pytest.raises(ValidationError, match="not a date"):
        CorpusSchema.model_validate(data)


def test_template_variable_must_be_placed_in_the_interview():
    data = _corpus_data()
    _flow(data)["interview"][0]["variables"].remove("full_name")
    with pytest.raises(ValidationError, match="consumed but not on any"):
        CorpusSchema.model_validate(data)


def test_gate_variable_must_be_placed():
    data = _corpus_data()
    data["variables"]["vaccinated"] = {
        "name": "vaccinated",
        "label": "Vaccinated",
        "data_type": "boolean",
        "asked_when": {"variable": "licensed", "value": True},
    }
    page = _flow(data)["interview"][0]["variables"]
    page.remove("licensed")
    page.append("vaccinated")
    with pytest.raises(ValidationError, match="licensed, which is not placed"):
        CorpusSchema.model_validate(data)


def test_gate_must_be_placed_before_the_variable_it_gates():
    data = _corpus_data()
    data["variables"]["vaccinated"] = {
        "name": "vaccinated",
        "label": "Vaccinated",
        "data_type": "boolean",
        "asked_when": {"variable": "licensed", "value": True},
    }
    page = _flow(data)["interview"][0]["variables"]
    page.remove("licensed")
    page.insert(0, "vaccinated")
    page.append("licensed")
    with pytest.raises(ValidationError, match="must be placed before"):
        CorpusSchema.model_validate(data)


def test_condition_variable_placed_before_its_conditional_consumers():
    data = _corpus_data()
    data["variables"]["vet_name"] = {"name": "vet_name", "label": "Vet"}
    data["forms"]["addendum"] = {
        "name": "Vet addendum",
        "fields": [{"pdf_field": "Vet", "template": "{vet_name}"}],
    }
    data["form_acro_fields"]["addendum"] = {"Vet": "/Tx"}
    _flow(data)["packet"].append(
        {
            "form": "addendum",
            "when": {"variable": "licensed", "value": True},
        }
    )
    page = _flow(data)["interview"][0]["variables"]
    page.insert(0, "vet_name")  # before licensed, the condition variable
    with pytest.raises(ValidationError, match="must be placed before"):
        CorpusSchema.model_validate(data)


# Orphans


def test_unreferenced_form_is_rejected():
    data = _corpus_data()
    data["forms"]["extra"] = {"name": "Extra", "fields": []}
    data["form_acro_fields"]["extra"] = {}
    with pytest.raises(ValidationError, match="not referenced by any flow"):
        CorpusSchema.model_validate(data)


def test_topic_defined_by_two_courts_is_rejected():
    data = _corpus_data()
    data["topics"][("other-court", "pets")] = {"title": "Pets"}
    with pytest.raises(ValidationError, match="more than one court"):
        CorpusSchema.model_validate(data)


# Document parsing


def test_unparseable_yaml_names_its_file(tmp_path):
    path = tmp_path / "broken.yml"
    path.write_text("name: [unclosed")
    with pytest.raises(ValueError, match="broken.yml: cannot load"):
        corpus_parse_yaml(path, FlowSchema)


def test_non_mapping_document_is_rejected(tmp_path):
    path = tmp_path / "list.yml"
    path.write_text("- 1\n- 2\n")
    with pytest.raises(ValueError, match="top level must be a mapping"):
        corpus_parse_yaml(path, FlowSchema)


# Court branding


@pytest.mark.parametrize(
    "path",
    ["branding/logo.svg", "branding/court-name_2.png"],
)
def test_branding_accepts_an_svg_or_png_in_the_branding_folder(path):
    BrandingSchema(name="Alpha Courts", logo=path, name_image=path)


def test_a_name_image_without_the_name_it_shows_is_rejected():
    # The header uses the name as the image's alt text (WCAG 1.1.1, 2.5.3);
    # falling back to court_name voices words the image doesn't show.
    with pytest.raises(ValidationError, match="name_image"):
        BrandingSchema(name_image="branding/name.png")


@pytest.mark.parametrize(
    "path",
    [
        "logo.svg",
        "branding/../court.yml",
        "branding/art/logo.svg",
        "/branding/logo.svg",
        "branding/logo.gif",
    ],
    ids=[
        "outside-folder",
        "climbs-out",
        "nested",
        "absolute",
        "not-svg-or-png",
    ],
)
def test_branding_rejects_a_path_outside_the_folder_or_another_format(path):
    with pytest.raises(ValidationError):
        BrandingSchema(logo=path)


def _court_folder(root, branding):
    folder = root / "alpha"
    (folder / "branding").mkdir(parents=True)
    (folder / "court.yml").write_text(
        "name: Alpha\ncourt_name: Alpha Court\n" + branding
    )
    return folder


def test_a_branding_file_that_does_not_exist_is_rejected(tmp_path):
    _court_folder(tmp_path, "branding:\n  logo: branding/logo.svg\n")
    with (
        mock.patch.object(selectors, "COURTS_DIR", tmp_path),
        pytest.raises(ValueError, match="branding/logo.svg"),
    ):
        corpus_load_courts()


def test_a_branding_file_that_exists_loads(tmp_path):
    folder = _court_folder(tmp_path, "branding:\n  logo: branding/logo.svg\n")
    (folder / "branding" / "logo.svg").write_text("<svg/>")
    with mock.patch.object(selectors, "COURTS_DIR", tmp_path):
        courts = corpus_load_courts()
    assert courts["alpha"].branding.logo == "branding/logo.svg"


# Contact kinds


def test_a_contact_takes_a_help_kind():
    data = _corpus_data()
    data["courts"]["north-dakota"]["contacts"][0]["kind"] = "legal_aid"
    CorpusSchema.model_validate(data)


def test_an_unknown_contact_kind_is_rejected():
    data = _corpus_data()
    data["courts"]["north-dakota"]["contacts"][0]["kind"] = "bailiff"
    with pytest.raises(ValidationError):
        CorpusSchema.model_validate(data)


# Contact address and hours


def test_a_contact_takes_an_address_and_hours():
    data = _corpus_data()
    contact = data["courts"]["north-dakota"]["contacts"][0]
    contact["address"] = "100 Main St, Bismarck"
    contact["hours"] = "Mon-Fri 8am-4pm"
    court = CorpusSchema.model_validate(data).courts["north-dakota"]
    assert court.contacts[0].address == "100 Main St, Bismarck"
    assert court.contacts[0].hours == "Mon-Fri 8am-4pm"


def test_a_contacts_address_and_hours_default_to_empty():
    court = CorpusSchema.model_validate(_corpus_data()).courts["north-dakota"]
    assert court.contacts[0].address == ""
    assert court.contacts[0].hours == ""


@pytest.mark.parametrize("field", ["address", "hours"])
def test_a_contact_field_longer_than_its_column_is_rejected(field):
    data = _corpus_data()
    data["courts"]["north-dakota"]["contacts"][0][field] = "x" * 256
    with pytest.raises(ValidationError):
        CorpusSchema.model_validate(data)


@pytest.mark.parametrize(
    ("corpus_court", "court", "known"),
    [
        ("north-dakota", "north-dakota", True),
        ("north-dakota", "arizona", False),
        (None, "north-dakota", True),
        (None, "arizona", False),
    ],
    ids=[
        "set-accepts-the-configured-court",
        "set-rejects-another-court-even-if-authored",
        "unset-accepts-a-court-authoring-the-topic",
        "unset-rejects-a-court-the-corpus-lacks",
    ],
)
def test_corpus_court_known_follows_the_setting_then_the_topic_index(
    settings, corpus_court, court, known
):
    settings.CORPUS_COURT = corpus_court
    topics = {("north-dakota", "adult-name-change"): object()}
    with mock.patch.object(
        selectors, "corpus_load_topics", return_value=topics
    ):
        assert (
            selectors.corpus_court_known(court, "adult-name-change") is known
        )


def test_corpus_court_known_reads_the_topic_index_from_disk_once(settings):
    settings.CORPUS_COURT = None
    topics = {("north-dakota", "adult-name-change"): object()}
    with mock.patch.object(
        selectors, "corpus_load_topics", return_value=topics
    ) as load:
        assert selectors.corpus_court_known(
            "north-dakota", "adult-name-change"
        )
        assert not selectors.corpus_court_known("arizona", "adult-name-change")
    assert load.call_count == 1


@pytest.mark.parametrize(
    "stale",
    [
        ("other-tree", [("arizona", "adult-name-change")]),
        [("arizona", "adult-name-change")],
        [],
    ],
    ids=["another-tree", "unfingerprinted-list", "unfingerprinted-empty"],
)
def test_corpus_court_known_ignores_an_index_cached_from_another_tree(
    settings, stale
):
    """A list another release's process cached is a miss, not an answer,
    whatever shape that release stored it in."""
    settings.CORPUS_COURT = None
    cache.set(CORPUS_TOPIC_KEYS_CACHE_KEY, stale, timeout=None)
    topics = {("north-dakota", "adult-name-change"): object()}
    with mock.patch.object(
        selectors, "corpus_load_topics", return_value=topics
    ) as load:
        assert not selectors.corpus_court_known("arizona", "adult-name-change")
        assert selectors.corpus_court_known(
            "north-dakota", "adult-name-change"
        )
    assert load.call_count == 1
