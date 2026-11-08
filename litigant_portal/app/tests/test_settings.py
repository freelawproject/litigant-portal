import importlib
import os
import runpy
from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

import litigant_portal.settings

SECRET = {"SECRET_KEY": "test-secret-key"}


class GitShaSettingTests(SimpleTestCase):
    """Tests for the GIT_SHA deploy-provenance setting."""

    def _reload_settings(self, environ):
        with mock.patch.dict(os.environ, {**SECRET, **environ}, clear=True):
            return importlib.reload(litigant_portal.settings)

    def test_git_sha_defaults_to_unknown(self):
        self.assertEqual(self._reload_settings({}).GIT_SHA, "unknown")

    def test_git_sha_reads_environment(self):
        module = self._reload_settings({"GIT_SHA": "abc1234"})
        self.assertEqual(module.GIT_SHA, "abc1234")


class SecretKeySettingTests(SimpleTestCase):
    def _load(self, environ):
        with mock.patch.dict(os.environ, environ, clear=True):
            return runpy.run_path(litigant_portal.settings.__file__)

    def test_missing_key_raises_when_debug_off(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "SECRET_KEY"):
            self._load({"DEBUG": "false"})

    def test_empty_key_raises_when_debug_off(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "SECRET_KEY"):
            self._load({"DEBUG": "false", "SECRET_KEY": ""})

    def test_blank_key_raises_when_debug_off(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "SECRET_KEY"):
            self._load({"DEBUG": "false", "SECRET_KEY": " \n"})

    def test_key_reads_environment_when_debug_off(self):
        config = self._load({"DEBUG": "false", "SECRET_KEY": "from-env"})
        self.assertEqual(config["SECRET_KEY"], "from-env")

    def test_missing_key_is_generated_when_debug_on(self):
        config = self._load({"DEBUG": "true"})
        self.assertEqual(len(config["SECRET_KEY"]), 50)


class BedrockSettingTests(SimpleTestCase):
    def test_region_defaults_to_us_east_1_and_preserves_overrides(self):
        for value, expected in (
            (None, "us-east-1"),
            ("", "us-east-1"),
            ("   ", "us-east-1"),
            (" us-west-2 ", "us-west-2"),
            ("eu-west-1", "eu-west-1"),
        ):
            with self.subTest(value=value):
                environ = {} if value is None else {"AWS_REGION": value}
                with mock.patch.dict(
                    os.environ, {**SECRET, **environ}, clear=True
                ):
                    config = runpy.run_path(litigant_portal.settings.__file__)
                self.assertEqual(config["AWS_REGION"], expected)

    def test_geography_is_optional_and_defaults_to_us(self):
        for value in (None, "", "   ", "us"):
            with self.subTest(value=value):
                environ = (
                    {}
                    if value is None
                    else {"BEDROCK_ALLOWED_GEOGRAPHY": value}
                )
                with mock.patch.dict(
                    os.environ, {**SECRET, **environ}, clear=True
                ):
                    config = runpy.run_path(litigant_portal.settings.__file__)
                self.assertEqual(
                    config["BEDROCK_ALLOWED_GEOGRAPHY"],
                    "US",
                )
