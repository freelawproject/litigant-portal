import os

from django.conf import settings
from django.test import SimpleTestCase


class GitShaSettingTests(SimpleTestCase):
    """Tests for the GIT_SHA deploy-provenance setting."""

    def test_git_sha_defaults_to_unknown(self):
        # CI and local test runs don't set GIT_SHA; only image builds do.
        if "GIT_SHA" in os.environ:
            self.skipTest("GIT_SHA set in this environment")
        self.assertEqual(settings.GIT_SHA, "unknown")
