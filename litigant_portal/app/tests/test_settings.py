import importlib
import os
import runpy
from unittest import mock

from django.test import SimpleTestCase

import litigant_portal.settings


class GitShaSettingTests(SimpleTestCase):
    """Tests for the GIT_SHA deploy-provenance setting."""

    def _reload_settings(self, environ):
        with mock.patch.dict(os.environ, environ, clear=True):
            return importlib.reload(litigant_portal.settings)

    def test_git_sha_defaults_to_unknown(self):
        self.assertEqual(self._reload_settings({}).GIT_SHA, "unknown")

    def test_git_sha_reads_environment(self):
        module = self._reload_settings({"GIT_SHA": "abc1234"})
        self.assertEqual(module.GIT_SHA, "abc1234")


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
                with mock.patch.dict(os.environ, environ, clear=True):
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
                with mock.patch.dict(os.environ, environ, clear=True):
                    config = runpy.run_path(litigant_portal.settings.__file__)
                self.assertEqual(
                    config["BEDROCK_ALLOWED_GEOGRAPHY"],
                    "US",
                )
