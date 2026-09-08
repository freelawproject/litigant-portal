"""
Access gates and host configuration for the new agent development page.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from litigant_portal.app.models.choices import (
    DEFAULT_BEDROCK_MODEL,
    BedrockModel,
)
from litigant_portal.app.permissions import ADMINS_GROUP, DEVELOPERS_GROUP
from litigant_portal.app.selectors.agent import agent_scope_choices
from litigant_portal.app.services.site import site_update


@override_settings(LP_AGENT_DEV_ENABLED=True, SITE_PASSWORD="")
@pytest.mark.postgres
class AgentDevelopmentPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.developer = get_user_model().objects.create_user(username="dev")
        cls.developer.groups.add(Group.objects.get(name=DEVELOPERS_GROUP))
        cls.admin = get_user_model().objects.create_user(username="admin")
        cls.admin.groups.add(Group.objects.get(name=ADMINS_GROUP))

    def setUp(self):
        self.url = reverse("pages:agent_development")

    def test_signed_out_visitors_are_sent_to_login(self):
        response = self.client.get(self.url)
        self.assertRedirects(
            response,
            f"{reverse('account_login')}?next={self.url}",
            fetch_redirect_response=False,
        )

    def test_signed_in_non_developers_cannot_open_the_page(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    @override_settings(LP_AGENT_DEV_ENABLED=False)
    def test_disabled_page_is_unavailable_to_developers(self):
        self.client.force_login(self.developer)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_developer_sees_site_default_and_catalog_choices(self):
        self.client.force_login(self.developer)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["selected_model"], DEFAULT_BEDROCK_MODEL
        )
        self.assertEqual(
            response.context["model_choices"], BedrockModel.choices
        )
        self.assertTrue(response.context["courts"])
        self.assertTrue(response.context["topics"])

    def test_page_uses_the_configured_assistant_model(self):
        with self.captureOnCommitCallbacks(execute=True):
            site_update(assistant_model=BedrockModel.GPT_5_6_SOL)
        self.client.force_login(self.developer)
        response = self.client.get(self.url)
        self.assertEqual(
            response.context["selected_model"], BedrockModel.GPT_5_6_SOL
        )

    def test_page_does_not_accept_message_submissions(self):
        self.client.force_login(self.developer)
        response = self.client.post(self.url, {"message": "Hello"})
        self.assertEqual(response.status_code, 405)


class AgentScopeChoicesTests(SimpleTestCase):
    def setUp(self):
        courts = {
            "first-court": SimpleNamespace(name="First court"),
            "second-court": SimpleNamespace(name="Second court"),
        }
        topics = {
            ("first-court", "first-topic"): SimpleNamespace(title="First"),
            ("second-court", "second-topic"): SimpleNamespace(title="Second"),
            ("unknown-court", "orphan-topic"): SimpleNamespace(title="Orphan"),
        }
        self.enterContext(
            patch(
                "litigant_portal.app.selectors.agent.corpus_load_courts",
                return_value=courts,
            )
        )
        self.enterContext(
            patch(
                "litigant_portal.app.selectors.agent.corpus_load_topics",
                return_value=topics,
            )
        )

    @override_settings(CORPUS_COURT=None)
    def test_multi_court_choices_preserve_valid_pairs(self):
        courts, topics = agent_scope_choices()
        self.assertEqual(len(courts), 2)
        self.assertEqual(
            [(topic["court"], topic["slug"]) for topic in topics],
            [("first-court", "first-topic"), ("second-court", "second-topic")],
        )

    @override_settings(CORPUS_COURT="second-court")
    def test_single_court_filters_both_selectors(self):
        courts, topics = agent_scope_choices()
        self.assertEqual([court["slug"] for court in courts], ["second-court"])
        self.assertEqual([topic["slug"] for topic in topics], ["second-topic"])

    @override_settings(CORPUS_COURT="missing-court")
    def test_unknown_configured_court_exposes_no_choices(self):
        self.assertEqual(agent_scope_choices(), ([], []))
