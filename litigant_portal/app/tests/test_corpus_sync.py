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
from django.test import TestCase, override_settings

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
from litigant_portal.app.services import corpus as services
from litigant_portal.app.services.corpus import corpus_sync


def _make_corpus(*, include_beta=True, include_vestigial=True):
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
            "contacts": [{"name": "Alpha Help"}],
            "resources": [{"label": "Alpha Guide", "url": "https://a.test"}],
        }
    }
    topics = {("alpha", "pets"): {"title": "Pets"}}
    flows = {
        ("alpha", "pets", "standard"): {
            "name": "Standard",
            "sections": [{"heading": "Start", "content": "Read."}],
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
            "contacts": [{"name": "Beta Help"}],
            "resources": [{"label": "Beta Guide", "url": "https://b.test"}],
        }
        topics[("beta", "eviction")] = {"title": "Eviction"}
        flows[("beta", "eviction", "tenant")] = {
            "name": "Tenant",
            "sections": [{"heading": "Start", "content": "Read."}],
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
        conditional = FormField.objects.get(pdf_field="Check Box1")
        self.assertEqual(conditional.checked_when.name, "pet_kind")
        self.assertEqual(conditional.checked_when_value, "dog")
        self.assertIs(
            FormField.objects.get(pdf_field="Check Box2").checked, True
        )
        self.assertIsNone(FormField.objects.get(pdf_field="Name").checked)


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
