"""Tests for the court.json schema, iter_courts() helper, and the Django
system check that enforces the schema at app startup (#371)."""

import json
import tempfile
from pathlib import Path
from unittest import mock

import jsonschema
from django.test import TestCase

from litigant_portal.app import checks as chat_checks
from litigant_portal.app.checks import check_court_json_schema
from litigant_portal.prompts import _PROMPTS_DIR, iter_courts

COURTS_DIR = _PROMPTS_DIR / "courts"
SCHEMA_PATH = COURTS_DIR / "_schema.json"


class CourtSchemaTests(TestCase):
    """The schema itself, and that every registered court conforms."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.validator = jsonschema.Draft202012Validator(cls.schema)

    def test_schema_is_valid_2020_12(self):
        # Self-validates against the metaschema; raises on a malformed schema.
        jsonschema.Draft202012Validator.check_schema(self.schema)

    def test_every_registered_court_conforms(self):
        for slug, meta in iter_courts():
            errors = list(self.validator.iter_errors(meta))
            self.assertEqual(
                errors,
                [],
                msg=f"{slug}/court.json failed schema: {[e.message for e in errors]}",
            )

    def test_required_fields_enforced(self):
        with self.assertRaises(jsonschema.ValidationError):
            self.validator.validate(
                {"name": "Test"}
            )  # missing jurisdiction_level
        with self.assertRaises(jsonschema.ValidationError):
            self.validator.validate(
                {"jurisdiction_level": "state"}
            )  # missing name

    def test_jurisdiction_level_enum_enforced(self):
        bad = {"name": "Test", "jurisdiction_level": "galactic"}
        with self.assertRaises(jsonschema.ValidationError):
            self.validator.validate(bad)

    def test_state_pattern_enforced(self):
        # Must be USPS two-letter uppercase code.
        for bad_state in ("California", "ca", "ND-1", ""):
            with self.assertRaises(jsonschema.ValidationError):
                self.validator.validate(
                    {
                        "name": "Test",
                        "jurisdiction_level": "state",
                        "state": bad_state,
                    }
                )

    def test_additional_properties_rejected(self):
        # additionalProperties: false catches typos and unscoped fields.
        bad = {
            "name": "Test",
            "jurisdiction_level": "state",
            "branding_color": "#ff0000",
        }
        with self.assertRaises(jsonschema.ValidationError):
            self.validator.validate(bad)

    def test_url_pattern_enforced(self):
        # Court URLs must use http(s) scheme; "format": "uri" alone wouldn't
        # be enforced by Draft202012Validator without a FormatChecker, so the
        # schema uses an explicit pattern.
        for field in ("official_url", "official_resources_url"):
            for bad_url in ("not a url", "ftp://example.com", "example.com"):
                meta = {
                    "name": "Test",
                    "jurisdiction_level": "state",
                    field: bad_url,
                }
                with self.assertRaises(jsonschema.ValidationError):
                    self.validator.validate(meta)
        # Sanity: a well-formed URL passes.
        self.validator.validate(
            {
                "name": "Test",
                "jurisdiction_level": "state",
                "official_url": "https://example.gov",
            }
        )


class IterCourtsTests(TestCase):
    """Tests for the iter_courts() public helper."""

    def test_returns_known_courts(self):
        courts = dict(iter_courts())
        self.assertIn("north-dakota", courts)
        self.assertIn("dupage-il", courts)

    def test_metadata_includes_required_fields(self):
        for slug, meta in iter_courts():
            self.assertIn("name", meta, msg=f"{slug} missing name")
            self.assertIn(
                "jurisdiction_level",
                meta,
                msg=f"{slug} missing jurisdiction_level",
            )

    def test_sorted_by_slug(self):
        slugs = [slug for slug, _ in iter_courts()]
        self.assertEqual(slugs, sorted(slugs))


class CourtJsonCheckTests(TestCase):
    """Tests for the Django system check that validates court.json files."""

    def test_check_passes_for_current_state(self):
        # Current courts must not produce any check errors.
        errors = check_court_json_schema(app_configs=None)
        self.assertEqual(
            errors,
            [],
            msg=f"Court schema check failed: {[e.msg for e in errors]}",
        )

    def test_validator_surfaces_incomplete_meta(self):
        """Confirm the validator the check uses surfaces missing fields. We
        test against the validator directly rather than mutate fixtures in
        chat/prompts/courts/ — the check function itself is exercised by the
        no-errors test above."""
        validator = jsonschema.Draft202012Validator(
            json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        )
        broken = {"name": "Test"}  # missing jurisdiction_level
        errors = list(validator.iter_errors(broken))
        self.assertTrue(
            errors, "Expected schema errors for incomplete court.json"
        )


class CourtJsonCheckErrorPathTests(TestCase):
    """Exercise the check function's error-emission paths against fixture
    dirs. Complements CourtJsonCheckTests, which only proves the green path
    against the real chat/prompts/courts/ tree."""

    def _run_check_with_fixture(self, court_json_text: str) -> list:
        """Set up a temp courts dir with one fake court whose court.json
        contains the given raw text, then run the check against it."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "_schema.json").write_text(
                SCHEMA_PATH.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            court_dir = tmpdir_path / "fake-court"
            court_dir.mkdir()
            (court_dir / "prompt.md").write_text("placeholder corpus\n")
            (court_dir / "court.json").write_text(
                court_json_text, encoding="utf-8"
            )
            with (
                mock.patch.object(chat_checks, "_COURTS_DIR", tmpdir_path),
                mock.patch.object(
                    chat_checks,
                    "_SCHEMA_PATH",
                    tmpdir_path / "_schema.json",
                ),
            ):
                return check_court_json_schema(app_configs=None)

    def test_invalid_json_emits_e003(self):
        errors = self._run_check_with_fixture("not valid json {")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].id, "chat.E003")
        self.assertIn("invalid JSON", errors[0].msg)

    def test_schema_violation_emits_e004(self):
        # Missing the required jurisdiction_level field.
        errors = self._run_check_with_fixture(
            json.dumps({"name": "Fake Court"})
        )
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].id, "chat.E004")
        self.assertIn("jurisdiction_level", errors[0].msg)

    def test_missing_schema_emits_e001(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            with (
                mock.patch.object(chat_checks, "_COURTS_DIR", tmpdir_path),
                mock.patch.object(
                    chat_checks,
                    "_SCHEMA_PATH",
                    tmpdir_path / "missing.json",
                ),
            ):
                errors = check_court_json_schema(app_configs=None)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].id, "chat.E001")
