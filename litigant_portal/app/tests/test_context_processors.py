from django.conf import settings
from django.test import RequestFactory, SimpleTestCase

from litigant_portal.app.context_processors import app_meta


class AppMetaTests(SimpleTestCase):
    """Tests for app_meta context processor."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_exposes_deployment_env_and_build_time(self):
        result = app_meta(self.factory.get("/"))

        self.assertEqual(result["deployment_env"], settings.DEPLOYMENT_ENV)
        self.assertEqual(result["app_build_time"], settings.APP_BUILD_TIME)

    def test_app_build_time_matches_yyyy_mm_dd_hh_mm(self):
        result = app_meta(self.factory.get("/"))

        self.assertRegex(
            result["app_build_time"], r"^\d{4}/\d{2}/\d{2} \d{2}:\d{2}$"
        )
