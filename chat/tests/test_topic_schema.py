"""Tests for the topic.json schema, iter_topics() helper, and the Django
system check that enforces the schema at app startup (#372)."""

import json
import tempfile
from pathlib import Path
from unittest import mock

import jsonschema
from django.test import TestCase

from chat import checks as chat_checks
from chat.checks import check_topic_json_schema
from chat.prompts import _PROMPTS_DIR, get_topic_name, iter_topics

TOPICS_DIR = _PROMPTS_DIR / "topics"
SCHEMA_PATH = TOPICS_DIR / "_schema.json"


class TopicSchemaTests(TestCase):
    """The schema itself, and that every registered topic conforms."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.validator = jsonschema.Draft202012Validator(cls.schema)

    def test_schema_is_valid_2020_12(self):
        jsonschema.Draft202012Validator.check_schema(self.schema)

    def test_every_registered_topic_conforms(self):
        for slug, meta in iter_topics():
            errors = list(self.validator.iter_errors(meta))
            self.assertEqual(
                errors,
                [],
                msg=f"{slug}/topic.json failed schema: {[e.message for e in errors]}",
            )

    def test_required_fields_enforced(self):
        with self.assertRaises(jsonschema.ValidationError):
            self.validator.validate({"name": "Eviction"})  # missing icon
        with self.assertRaises(jsonschema.ValidationError):
            self.validator.validate({"icon": "home"})  # missing name

    def test_icon_pattern_enforced(self):
        for bad_icon in ("Home", "home_icon", "home/icon", "home icon", ""):
            with self.assertRaises(jsonschema.ValidationError):
                self.validator.validate({"name": "Test", "icon": bad_icon})
        # Sanity: a well-formed icon passes.
        self.validator.validate({"name": "Test", "icon": "identification"})

    def test_additional_properties_rejected(self):
        # additionalProperties: false catches typos and unscoped fields.
        bad = {"name": "Test", "icon": "home", "badge": "new"}
        with self.assertRaises(jsonschema.ValidationError):
            self.validator.validate(bad)

    def test_name_min_length_enforced(self):
        with self.assertRaises(jsonschema.ValidationError):
            self.validator.validate({"name": "", "icon": "home"})


class IterTopicsTests(TestCase):
    """Tests for the iter_topics() public helper."""

    def test_returns_known_topics(self):
        topics = dict(iter_topics())
        self.assertIn("eviction", topics)
        self.assertIn("adult_name_change", topics)

    def test_metadata_includes_required_fields(self):
        for slug, meta in iter_topics():
            self.assertIn("name", meta, msg=f"{slug} missing name")
            self.assertIn("icon", meta, msg=f"{slug} missing icon")

    def test_sorted_by_slug(self):
        slugs = [slug for slug, _ in iter_topics()]
        self.assertEqual(slugs, sorted(slugs))


class TopicNameTests(TestCase):
    """Tests for get_topic_name display-name lookup from topic.json."""

    def test_known_topic_eviction(self):
        self.assertEqual(get_topic_name("eviction"), "Housing & Eviction")

    def test_known_topic_adult_name_change(self):
        self.assertEqual(
            get_topic_name("adult_name_change"), "Adult Name Change"
        )

    def test_empty_topic_returns_empty(self):
        self.assertEqual(get_topic_name(""), "")
        self.assertEqual(get_topic_name(None), "")

    def test_unknown_topic_returns_empty(self):
        self.assertEqual(get_topic_name("not_a_topic"), "")

    def test_case_insensitive_lookup(self):
        self.assertEqual(get_topic_name("EVICTION"), "Housing & Eviction")


class TopicJsonCheckTests(TestCase):
    """Tests for the Django system check that validates topic.json files."""

    def test_check_passes_for_current_state(self):
        errors = check_topic_json_schema(app_configs=None)
        self.assertEqual(
            errors,
            [],
            msg=f"Topic schema check failed: {[e.msg for e in errors]}",
        )


class TopicJsonCheckErrorPathTests(TestCase):
    """Exercise the check function's error-emission paths against fixture
    dirs. Complements TopicJsonCheckTests, which only proves the green path
    against the real chat/prompts/topics/ tree."""

    def _run_check_with_fixture(self, topic_json_text: str) -> list:
        """Set up a temp topics dir with one fake topic whose topic.json
        contains the given raw text, then run the check against it."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "_schema.json").write_text(
                SCHEMA_PATH.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            topic_dir = tmpdir_path / "fake-topic"
            topic_dir.mkdir()
            (topic_dir / "prompt.md").write_text("placeholder corpus\n")
            (topic_dir / "topic.json").write_text(
                topic_json_text, encoding="utf-8"
            )
            with (
                mock.patch.object(chat_checks, "_TOPICS_DIR", tmpdir_path),
                mock.patch.object(
                    chat_checks,
                    "_TOPIC_SCHEMA_PATH",
                    tmpdir_path / "_schema.json",
                ),
            ):
                return check_topic_json_schema(app_configs=None)

    def test_invalid_json_emits_e007(self):
        errors = self._run_check_with_fixture("not valid json {")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].id, "chat.E007")
        self.assertIn("invalid JSON", errors[0].msg)

    def test_schema_violation_emits_e008(self):
        # Missing the required icon field.
        errors = self._run_check_with_fixture(
            json.dumps({"name": "Fake Topic"})
        )
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].id, "chat.E008")
        self.assertIn("icon", errors[0].msg)

    def test_missing_schema_emits_e005(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            with (
                mock.patch.object(chat_checks, "_TOPICS_DIR", tmpdir_path),
                mock.patch.object(
                    chat_checks,
                    "_TOPIC_SCHEMA_PATH",
                    tmpdir_path / "missing.json",
                ),
            ):
                errors = check_topic_json_schema(app_configs=None)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].id, "chat.E005")

    def test_invalid_schema_json_emits_e006(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "_schema.json").write_text(
                "not valid json {", encoding="utf-8"
            )
            with (
                mock.patch.object(chat_checks, "_TOPICS_DIR", tmpdir_path),
                mock.patch.object(
                    chat_checks,
                    "_TOPIC_SCHEMA_PATH",
                    tmpdir_path / "_schema.json",
                ),
            ):
                errors = check_topic_json_schema(app_configs=None)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].id, "chat.E006")
