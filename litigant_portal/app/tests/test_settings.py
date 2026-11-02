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
