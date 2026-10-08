from django.conf import settings
from django.test import RequestFactory, SimpleTestCase

from litigant_portal.app.context_processors import app_meta


class AppMetaTests(SimpleTestCase):
    """Tests for app_meta context processor."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_exposes_deployment_env_and_build_provenance(self):
        result = app_meta(self.factory.get("/"))

        self.assertEqual(result["deployment_env"], settings.DEPLOYMENT_ENV)
        self.assertEqual(result["app_build_time"], settings.APP_BUILD_TIME)
        self.assertEqual(result["app_git_sha"], settings.GIT_SHA)
        self.assertEqual(result["app_git_branch"], settings.GIT_BRANCH)

    def test_branch_and_build_time_are_blank_without_a_baked_build(self):
        """They are build args, so a bind-mounted working tree has none.

        The header renders "local working tree" on a blank branch rather
        than a commit that the uncommitted source may not match.
        """
        with self.settings(GIT_BRANCH="", APP_BUILD_TIME=""):
            result = app_meta(self.factory.get("/"))

        self.assertEqual(result["app_git_branch"], "")
        self.assertEqual(result["app_build_time"], "")

    def test_reports_the_baked_build_when_one_is_present(self):
        with self.settings(
            GIT_BRANCH="936-version-section",
            GIT_SHA="abc1234",
            APP_BUILD_TIME="2026/09/23 09:14",
        ):
            result = app_meta(self.factory.get("/"))

        self.assertEqual(result["app_git_branch"], "936-version-section")
        self.assertEqual(result["app_git_sha"], "abc1234")
        self.assertEqual(result["app_build_time"], "2026/09/23 09:14")
