import pytest
from django.conf import settings
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.test import RequestFactory, SimpleTestCase, TestCase

from litigant_portal.app.cache import SITE_CACHE_KEY
from litigant_portal.app.context_processors import app_meta, court_branding
from litigant_portal.app.models import Site
from litigant_portal.app.topic_flow.registry import registry


class AppMetaTests(SimpleTestCase):
    """Tests for app_meta context processor."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_exposes_build_provenance(self):
        result = app_meta(self.factory.get("/"))

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

    def test_production_gets_no_tester_tools_or_flow_links(self):
        with self.settings(DEPLOYMENT_ENV="prod", PILOT=False):
            result = app_meta(self.factory.get("/"))

        self.assertFalse(result["features"].start_over)
        self.assertEqual(result["tester_flow_links"], [])

    def test_flow_links_cover_every_court_when_no_court_is_set(self):
        with self.settings(DEPLOYMENT_ENV="dev", CORPUS_COURT=None):
            result = app_meta(self.factory.get("/"))

        keys = registry.keys()
        expected = {
            f"/t/{court}/{topic}/{role}/" for court, topic, role in keys
        }
        urls = {link["url"] for link in result["tester_flow_links"]}
        self.assertEqual(urls, expected)

    def test_flow_links_cover_only_the_instances_court(self):
        with self.settings(
            DEPLOYMENT_ENV="prod", PILOT=True, CORPUS_COURT="arizona"
        ):
            result = app_meta(self.factory.get("/"))

        urls = [link["url"] for link in result["tester_flow_links"]]
        self.assertTrue(urls)
        self.assertTrue(all(url.startswith("/t/arizona/") for url in urls))


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
