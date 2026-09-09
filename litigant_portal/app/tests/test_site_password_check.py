"""The deployed-environment guard on the site-password gate.

`SitePasswordMiddleware` treats a blank `SITE_PASSWORD` as "no gate", which is
right in dev and silently serves a pre-launch portal to the public anywhere
else. The check turns that into a failed startup.
"""

from django.core.checks import Error
from django.test import TestCase, override_settings

from litigant_portal.app.checks.site_password import (
    SITE_PASSWORD_CHECK_ID,
    check_site_password_set_when_deployed,
)


class SitePasswordCheckTests(TestCase):
    def _run(self):
        return check_site_password_set_when_deployed(app_configs=None)

    @override_settings(DEPLOYMENT_ENV="prod", SITE_PASSWORD="")
    def test_blank_gate_in_prod_is_an_error(self):
        errors = self._run()
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], Error)
        self.assertEqual(errors[0].id, SITE_PASSWORD_CHECK_ID)

    @override_settings(DEPLOYMENT_ENV="qa", SITE_PASSWORD="")
    def test_blank_gate_in_qa_is_an_error(self):
        self.assertEqual(len(self._run()), 1)

    @override_settings(DEPLOYMENT_ENV="dev", SITE_PASSWORD="")
    def test_blank_gate_in_dev_is_fine(self):
        # The dev default. Erroring here would make every fresh clone fail to
        # start, which is how a check gets silenced permanently.
        self.assertEqual(self._run(), [])

    @override_settings(DEPLOYMENT_ENV="prod", SITE_PASSWORD="a-real-password")
    def test_gate_set_in_prod_passes(self):
        self.assertEqual(self._run(), [])

    @override_settings(DEPLOYMENT_ENV="prod", SITE_PASSWORD="   ")
    def test_whitespace_only_gate_is_an_error(self):
        # `not password` in the middleware is False for "   ", so the gate is
        # live and every visitor is locked out by an unguessable value. That's
        # a different failure from a blank gate, and just as much a typo.
        self.assertEqual(len(self._run()), 1)

    @override_settings(DEPLOYMENT_ENV="prod", SITE_PASSWORD=None)
    def test_unset_gate_in_prod_is_an_error(self):
        self.assertEqual(len(self._run()), 1)

    @override_settings(DEPLOYMENT_ENV="staging", SITE_PASSWORD="")
    def test_unrecognized_environment_is_treated_as_deployed(self):
        # settings.py keeps an unknown DEPLOYMENT_ENV as-is and only warns, so
        # the check must fail closed rather than read "not qa or prod" as dev.
        self.assertEqual(len(self._run()), 1)
