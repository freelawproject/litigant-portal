"""Tests for corpus_sync: idempotency, strict deletion, court scoping,
and the trust boundary (user answers survive a re-sync).

The corpus is built programmatically and patched over ``corpus_load``, so
these tests exercise the sync logic without reading the real 1.5 MB court
PDFs; the fake FORMS_DIR holds stand-in bytes for the file writes.
"""

import tempfile
from pathlib import Path
from unittest import mock

import pytest
from django.core.cache import cache
from django.test import TestCase, override_settings

from litigant_portal.app.cache import (
    CONTACT_LIST_CACHE_KEY,
    RESOURCE_LIST_CACHE_KEY,
)
from litigant_portal.app.models import (
    Contact,
    Form,
    FormField,
    Resource,
    Site,
    Topic,
    TopicFlow,
    UserIdentity,
    Variable,
    VariableAnswer,
)
from litigant_portal.app.selectors.corpus import CorpusSchema
from litigant_portal.app.selectors.site import contact_list, resource_list
from litigant_portal.app.services import corpus as services
from litigant_portal.app.services.corpus import corpus_sync

START_SECTION = {"id": "start", "heading": "Start", "content": "Read."}


def _make_corpus(
    *,
    include_beta=True,
    include_vestigial=True,
    alpha_sections=None,
    alpha_contacts=None,
):
    """A small valid corpus: two courts, two forms, one gated variable."""
    variables = {
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
        "vaccinated": {
            "name": "vaccinated",
            "label": "Vaccinated",
            "data_type": "boolean",
            "asked_when": {"variable": "licensed", "value": True},
        },
    }
    if include_vestigial:
        variables["vestigial"] = {"name": "vestigial", "label": "Unused"}
    forms = {
        "license": {
            "name": "Pet license",
            "fields": [
                {"pdf_field": "Name", "template": "{full_name}"},
                {
                    "pdf_field": "Check Box1",
                    "checked_when": {"variable": "pet_kind", "value": "dog"},
                },
                {"pdf_field": "Check Box2", "checked": True},
            ],
        }
    }
    acro = {
        "license": {
            "Name": "/Tx",
            "Check Box1": "/Btn",
            "Check Box2": "/Btn",
        }
    }
    courts = {
        "alpha": {
            "name": "Alpha",
            "court_name": "Alpha District Court",
            "contacts": alpha_contacts
            or [{"id": "alpha_help", "name": "Alpha Help"}],
            "resources": [
                {
                    "id": "alpha_guide",
                    "label": "Alpha Guide",
                    "url": "https://a.test",
                }
            ],
        }
    }
    topics = {("alpha", "pets"): {"title": "Pets"}}
    flows = {
        ("alpha", "pets", "standard"): {
            "name": "Standard",
            "sections": alpha_sections or [START_SECTION],
            "interview": [
                {
                    "title": "About your pet",
                    "variables": ["full_name", "pet_kind", "licensed"],
                }
            ],
            "packet": [{"form": "license"}],
        }
    }
    if include_beta:
        forms["addendum"] = {
            "name": "Addendum",
            "fields": [{"pdf_field": "Name", "template": "{full_name}"}],
        }
        acro["addendum"] = {"Name": "/Tx"}
        courts["beta"] = {
            "name": "Beta",
            "court_name": "Beta Municipal Court",
            "contacts": [{"id": "beta_help", "name": "Beta Help"}],
            "resources": [
                {
                    "id": "beta_guide",
                    "label": "Beta Guide",
                    "url": "https://b.test",
                }
            ],
        }
        topics[("beta", "eviction")] = {"title": "Eviction"}
        flows[("beta", "eviction", "tenant")] = {
            "name": "Tenant",
            "sections": [START_SECTION],
            "interview": [{"title": "About you", "variables": ["full_name"]}],
            "packet": [{"form": "addendum"}],
        }
    return CorpusSchema.model_validate(
        {
            "variables": variables,
            "forms": forms,
            "form_acro_fields": acro,
            "courts": courts,
            "topics": topics,
            "flows": flows,
        }
    )


@override_settings(CORPUS_COURT=None)
class CorpusSyncTests(TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.forms_dir = Path(tmp.name)
        for slug in ("license", "addendum"):
            (self.forms_dir / f"{slug}.pdf").write_bytes(b"%PDF-stand-in")

    def _sync(self, corpus, **kwargs):
        with (
            mock.patch.object(services, "corpus_load", return_value=corpus),
            mock.patch.object(services, "FORMS_DIR", self.forms_dir),
        ):
            return corpus_sync(**kwargs)


@pytest.mark.postgres
class IdempotencyTests(CorpusSyncTests):
    def _snapshot(self):
        return {
            model: set(model.objects.values_list("pk", flat=True))
            for model in (
                Variable,
                Form,
                Topic,
                TopicFlow,
                Contact,
                Resource,
            )
        }

    def test_second_sync_changes_nothing(self):
        corpus = _make_corpus()
        first = self._sync(corpus, court=None, strict=True)
        before = self._snapshot()
        field_count = FormField.objects.count()
        second = self._sync(corpus, court=None, strict=True)
        self.assertEqual(self._snapshot(), before)
        self.assertEqual(FormField.objects.count(), field_count)
        self.assertEqual(first, second)
        self.assertEqual(second["deleted"], 0)

    def test_stored_file_names_stay_deterministic(self):
        corpus = _make_corpus()
        self._sync(corpus, court=None)
        self._sync(corpus, court=None)
        for form in Form.objects.all():
            self.assertEqual(form.file.name, f"forms/{form.slug}.pdf")

    def test_gate_wiring(self):
        self._sync(_make_corpus(), court=None)
        vaccinated = Variable.objects.get(name="vaccinated")
        self.assertEqual(vaccinated.asked_when.name, "licensed")
        self.assertIs(vaccinated.asked_when_value, True)

    def test_checkbox_wiring(self):
        self._sync(_make_corpus(), court=None)
        # Both fixture forms map a "Name" field, so scope to one form.
        fields = {
            row.pdf_field: row
            for row in FormField.objects.filter(form__slug="license")
        }
        conditional = fields["Check Box1"]
        self.assertEqual(conditional.checked_when.name, "pet_kind")
        self.assertEqual(conditional.checked_when_value, "dog")
        self.assertIs(fields["Check Box2"].checked, True)
        self.assertIsNone(fields["Name"].checked)
        self.assertIsNone(fields["Name"].checked_when)


@pytest.mark.postgres
class StrictDeletionTests(CorpusSyncTests):
    def test_strict_deletes_stale_rows_but_only_flags_variables(self):
        self._sync(_make_corpus(), court=None, strict=True)
        result = self._sync(
            _make_corpus(include_beta=False, include_vestigial=False),
            court=None,
            strict=True,
        )
        self.assertFalse(Topic.objects.filter(slug="eviction").exists())
        self.assertFalse(TopicFlow.objects.filter(slug="tenant").exists())
        self.assertFalse(Form.objects.filter(slug="addendum").exists())
        self.assertFalse(Contact.objects.filter(name="Beta Help").exists())
        self.assertFalse(Resource.objects.filter(label="Beta Guide").exists())
        vestigial = Variable.objects.get(name="vestigial")
        self.assertFalse(vestigial.in_schema)
        self.assertEqual(result["orphaned"], 1)

    def test_without_strict_stale_rows_survive(self):
        self._sync(_make_corpus(), court=None, strict=True)
        self._sync(_make_corpus(include_beta=False), court=None)
        self.assertTrue(Topic.objects.filter(slug="eviction").exists())
        self.assertTrue(Form.objects.filter(slug="addendum").exists())


@pytest.mark.postgres
class CourtScopingTests(CorpusSyncTests):
    def test_court_set_scopes_the_import_and_writes_the_site(self):
        self._sync(_make_corpus(), court="alpha")
        self.assertEqual(
            set(Topic.objects.values_list("slug", flat=True)), {"pets"}
        )
        self.assertEqual(Site.objects.get().court_name, "Alpha District Court")

    def test_court_unset_imports_everything_but_the_site(self):
        court_name = Site.objects.get().court_name
        self._sync(_make_corpus(), court=None)
        self.assertEqual(
            set(Topic.objects.values_list("slug", flat=True)),
            {"pets", "eviction"},
        )
        self.assertEqual(Site.objects.get().court_name, court_name)
        # Both courts' contacts land; flow-level linking (#815) scopes them.
        self.assertEqual(
            set(Contact.objects.values_list("name", flat=True)),
            {"Alpha Help", "Beta Help"},
        )

    def test_unknown_court_is_rejected(self):
        with self.assertRaises(ValueError):
            self._sync(_make_corpus(), court="gamma")


@pytest.mark.postgres
class SourceKeyTests(CorpusSyncTests):
    """The authored id lands on the row as ``key`` and survives edits
    around it; a removed id is reported, since threads may cite it."""

    def _alpha_sections(self):
        flow = TopicFlow.objects.get(topic__slug="pets", slug="standard")
        return list(flow.sections.values_list("key", "order"))

    def test_sync_stores_each_sections_authored_id_in_order(self):
        self._sync(
            _make_corpus(
                alpha_sections=[
                    START_SECTION,
                    {"id": "fees", "heading": "Fees", "content": "Pay."},
                ]
            ),
            court=None,
        )
        self.assertEqual(self._alpha_sections(), [("start", 0), ("fees", 1)])

    def test_sync_stores_contact_and_resource_ids(self):
        self._sync(_make_corpus(), court=None)
        self.assertEqual(
            Contact.objects.get(name="Alpha Help").key, "alpha_help"
        )
        self.assertEqual(
            Resource.objects.get(label="Alpha Guide").key, "alpha_guide"
        )

    def test_inserting_a_section_before_an_old_one_keeps_the_old_key(self):
        self._sync(_make_corpus(), court=None)
        self._sync(
            _make_corpus(
                alpha_sections=[
                    {"id": "intro", "heading": "Intro", "content": "Hi."},
                    START_SECTION,
                ]
            ),
            court=None,
        )
        self.assertEqual(self._alpha_sections(), [("intro", 0), ("start", 1)])

    def test_renaming_a_section_key_logs_the_old_key_and_the_flow(self):
        self._sync(_make_corpus(), court=None)
        with self.assertLogs(services.logger, level="WARNING") as logs:
            self._sync(
                _make_corpus(
                    alpha_sections=[{**START_SECTION, "id": "begin"}]
                ),
                court=None,
            )
        (line,) = logs.output
        self.assertIn("pets/standard", line)
        self.assertIn("'start'", line)
        self.assertNotIn("begin", line)

    def test_removing_a_contact_logs_its_key_with_or_without_strict(self):
        for strict in (True, False):
            with self.subTest(strict=strict):
                self._sync(_make_corpus(), court=None, strict=True)
                with self.assertLogs(services.logger, level="WARNING") as logs:
                    self._sync(
                        _make_corpus(include_beta=False),
                        court=None,
                        strict=strict,
                    )
                self.assertTrue(
                    any("'beta_help'" in line for line in logs.output)
                )
                self.assertTrue(
                    any("'beta_guide'" in line for line in logs.output)
                )

    def test_a_renamed_contact_keeps_its_row_by_key(self):
        self._sync(_make_corpus(), court=None)
        row_id = Contact.objects.get(key="alpha_help").id
        self._sync(
            _make_corpus(
                alpha_contacts=[{"id": "alpha_help", "name": "Alpha Desk"}]
            ),
            court=None,
        )
        self.assertEqual(Contact.objects.get(id=row_id).name, "Alpha Desk")
        self.assertFalse(Contact.objects.filter(name="Alpha Help").exists())

    def test_a_keyless_row_is_adopted_by_name(self):
        row = Contact.objects.create(name="Alpha Help")
        self._sync(_make_corpus(), court=None)
        row.refresh_from_db()
        self.assertEqual(row.key, "alpha_help")
        self.assertEqual(Contact.objects.filter(name="Alpha Help").count(), 1)

    def test_two_courts_in_one_sync_sharing_a_contact_name_are_rejected(self):
        corpus = _make_corpus(
            alpha_contacts=[{"id": "alpha_help", "name": "Beta Help"}]
        )
        with self.assertRaisesRegex(ValueError, r"\['Beta Help'\]"):
            self._sync(corpus, court=None)
        self.assertFalse(Contact.objects.exists())
        # Scoped to one court the name is unique, so the same corpus syncs.
        self._sync(corpus, court="alpha")
        self.assertEqual(
            Contact.objects.get(key="alpha_help").name, "Beta Help"
        )

    def test_sync_drops_the_cached_contact_and_resource_lists(self):
        self._sync(_make_corpus(), court=None)
        self.assertEqual(
            [c.key for c in contact_list()], ["alpha_help", "beta_help"]
        )
        self.assertEqual(
            [r.key for r in resource_list()], ["alpha_guide", "beta_guide"]
        )
        with self.captureOnCommitCallbacks(execute=True):
            self._sync(_make_corpus(include_beta=False), court=None)
        for key in (CONTACT_LIST_CACHE_KEY, RESOURCE_LIST_CACHE_KEY):
            self.assertIsNone(cache.get(key), key)


@pytest.mark.postgres
class TrustBoundaryTests(CorpusSyncTests):
    def test_variable_answers_survive_a_resync(self):
        self._sync(_make_corpus(), court=None, strict=True)
        identity = UserIdentity.objects.create()
        variable = Variable.objects.get(name="full_name")
        answer = VariableAnswer.objects.create(
            identity=identity,
            variable=variable,
            value="Jane Doe",
            reviewed=True,
        )
        self._sync(_make_corpus(), court=None, strict=True)
        answer.refresh_from_db()
        self.assertEqual(answer.value, "Jane Doe")
        self.assertTrue(answer.reviewed)
        self.assertEqual(answer.variable_id, variable.id)
