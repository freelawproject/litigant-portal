"""Corpus schema contract tests.

These lock the authoring rules the corpus validates at the boundary, so a
typo in a court form fails the check rather than printing a wrong PDF.
"""

from unittest import mock

import pytest
from pydantic import ValidationError

from litigant_portal.app.selectors import corpus as selectors
from litigant_portal.app.selectors.corpus import (
    BrandingSchema,
    CorpusSchema,
    FlowSchema,
    FormFieldMappingSchema,
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


# Source ids: the citation targets stored in user threads


def _section(id, heading="H"):
    return {"id": id, "heading": heading, "content": "Read."}


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
