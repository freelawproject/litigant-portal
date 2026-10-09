import pytest
from django.conf import settings
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.test import RequestFactory, SimpleTestCase, TestCase

from litigant_portal.app.cache import SITE_CACHE_KEY
from litigant_portal.app.context_processors import app_meta, court_branding
from litigant_portal.app.models import Site


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


@pytest.mark.postgres
class CourtBrandingTests(TestCase):
    """The header's court name and art come from the Site row (#979)."""

    def setUp(self):
        self.request = RequestFactory().get("/")

    def test_exposes_the_sites_court_and_its_art(self):
        site = Site.objects.get()
        site.court_name = "Alpha Court"
        site.logo.save("alpha-logo.svg", ContentFile(b"<svg/>"), save=False)
        site.save()
        cache.delete(SITE_CACHE_KEY)

        result = court_branding(self.request)

        self.assertEqual(result["court_name"], "Alpha Court")
        self.assertEqual(result["court_logo"], site.logo.url)
        self.assertEqual(result["court_name_image"], "")

    def test_a_branding_name_replaces_the_court_name(self):
        site = Site.objects.get()
        site.court_name = "Alpha City Court"
        site.branding_name = "Alpha State Courts"
        site.save()
        cache.delete(SITE_CACHE_KEY)

        result = court_branding(self.request)

        self.assertEqual(result["court_name"], "Alpha State Courts")

    def test_a_site_with_no_court_leaves_the_header_to_free_law_project(self):
        result = court_branding(self.request)

        self.assertEqual(
            result,
            {"court_name": "", "court_logo": "", "court_name_image": ""},
        )
