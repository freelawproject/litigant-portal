import importlib
import os
from unittest import mock

from django.core.exceptions import ImproperlyConfigured
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


class TopicFlowSourceSettingTests(SimpleTestCase):
    """Tests for TOPIC_FLOW_SOURCE, which picks the guided page's source."""

    def _reload_settings(self, environ):
        # A failed reload leaves the module half-executed, so put it back.
        self.addCleanup(importlib.reload, litigant_portal.settings)
        with mock.patch.dict(os.environ, environ, clear=True):
            return importlib.reload(litigant_portal.settings)

    def test_topic_flow_source_defaults_to_content(self):
        self.assertEqual(
            self._reload_settings({}).TOPIC_FLOW_SOURCE, "content"
        )

    def test_topic_flow_source_accepts_corpus(self):
        module = self._reload_settings({"TOPIC_FLOW_SOURCE": "corpus"})
        self.assertEqual(module.TOPIC_FLOW_SOURCE, "corpus")

    def test_unknown_source_setting_is_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            self._reload_settings({"TOPIC_FLOW_SOURCE": "bogus"})
