"""Tests for the Site singleton and its cache.

Three invariants: the row always exists, a second row is impossible, and
the cached copy never outlives a committed write. The last one is the
subtle case — invalidation is deferred to commit, so the cache stays warm
inside an open transaction and is dropped only once it lands.
"""

import uuid
from importlib import import_module
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.test import TestCase

from litigant_portal.app.cache import (
    SITE_CACHE_KEY,
    TOPIC_FLOW_LIST_CACHE_KEY,
    TOPIC_LIST_CACHE_KEY,
)
from litigant_portal.app.models import (
    Contact,
    Resource,
    Site,
    Topic,
    TopicFlow,
)
from litigant_portal.app.models.site import SITE_ID
from litigant_portal.app.selectors.site import (
    contact_list,
    resource_list,
    site_get,
    site_get_model_target,
)
from litigant_portal.app.selectors.topic_flow import (
    topic_flow_list,
    topic_list,
)
from litigant_portal.app.services.site import site_update
from litigant_portal.app.services.topic_flow import topic_create, topic_delete
from lp_agent.adapters.bedrock_models import (
    ResolvedBedrockModel,
    model_choices,
)

MODEL_CHOICES = model_choices()


@pytest.fixture(autouse=True)
def available_models(monkeypatch):
    for module in ("pages", "admin"):
        monkeypatch.setattr(
            f"litigant_portal.app.views.{module}.bedrock_model_choices",
            model_choices,
        )
    monkeypatch.setattr(
        "litigant_portal.app.selectors.site.bedrock_available_models",
        lambda **kwargs: {
            model: ResolvedBedrockModel(model, "us-east-1")
            for model, _ in model_choices()
        },
    )


@pytest.mark.postgres
class SingletonRowTests(TestCase):
    def test_the_row_exists_and_is_pinned(self):
        # Created by the post_migrate receiver, not by any test fixture.
        self.assertEqual(Site.objects.count(), 1)
        self.assertEqual(Site.objects.get().id, SITE_ID)

    def test_a_second_row_is_rejected_by_the_database(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Site.objects.create(id=uuid.uuid4())

    def test_a_second_row_is_rejected_even_at_the_pinned_id(self):
        # The primary key blocks this one rather than the check constraint,
        # but the outcome callers depend on is the same.
        with self.assertRaises(IntegrityError), transaction.atomic():
            Site.objects.create(id=SITE_ID)

    def test_site_get_needs_no_arguments(self):
        self.assertEqual(site_get().id, SITE_ID)


@pytest.mark.postgres
class SiteCacheTests(TestCase):
    # No setUp clearing the key: the autouse test_cache fixture calls
    # cache.clear() before each test, and pytest sets fixtures up before
    # unittest's setUp runs.

    def test_site_get_populates_the_cache(self):
        self.assertIsNone(cache.get(SITE_CACHE_KEY))
        site_get()
        self.assertIsNotNone(cache.get(SITE_CACHE_KEY))

    def test_a_committed_write_drops_the_cached_copy(self):
        site_get()
        # captureOnCommitCallbacks is required: TestCase wraps each test in a
        # transaction that never commits, so on_commit hooks would otherwise
        # never run and this would pass for the wrong reason.
        with self.captureOnCommitCallbacks(execute=True):
            site_update(court_name="Cass County")
        self.assertIsNone(cache.get(SITE_CACHE_KEY))
        self.assertEqual(site_get().court_name, "Cass County")

    def test_invalidation_is_deferred_until_commit(self):
        site_get()
        with self.captureOnCommitCallbacks() as callbacks:
            site_update(court_name="Pending")
            # Queued, not run. Deleting here instead would let a reader on
            # another connection refill the key with the pre-commit row, and
            # nothing would bust it again — the keys have no timeout, so that
            # stale copy would be permanent.
            self.assertIsNotNone(cache.get(SITE_CACHE_KEY))
        self.assertEqual(len(callbacks), 1)

    def test_contact_and_resource_lists_are_served_from_cache(self):
        Contact.objects.create(key="clerk", name="Clerk of Court")
        Resource.objects.create(
            key="fees", label="Fee table", url="https://example.test/fees"
        )
        contact_list()
        resource_list()
        with self.assertNumQueries(0):
            self.assertEqual([c.key for c in contact_list()], ["clerk"])
            self.assertEqual([r.key for r in resource_list()], ["fees"])

    def test_assistant_defaults_to_the_first_balanced_model(self):
        with self.captureOnCommitCallbacks(execute=True):
            site_update(assistant_model="")
        self.assertEqual(
            site_get_model_target(role="assistant").model, "auto/openai.terra"
        )

    def test_fast_role_defaults_to_the_first_economy_model(self):
        with self.captureOnCommitCallbacks(execute=True):
            site_update(fast_model="")
        self.assertEqual(
            site_get_model_target(role="fast").model, "auto/openai.luna"
        )

    def test_site_model_resolution_preserves_an_explicit_selection(self):
        # Not the default model, so the assertion below can't pass on a
        # broken fallback.
        model = "bedrock_mantle/openai.gpt-5.6-sol"
        with self.captureOnCommitCallbacks(execute=True):
            site_update(assistant_model=model)
        with patch(
            "litigant_portal.app.selectors.site.bedrock_model_target"
        ) as resolve:
            self.assertIs(
                site_get_model_target(role="assistant"), resolve.return_value
            )
        resolve.assert_called_once_with(
            model=model, required=frozenset({"text"})
        )

    def test_judge_setting_round_trip_and_validation(self):
        self.assertIsNone(site_get().judge_model)
        user = get_user_model().objects.create_superuser(
            username="judge-admin", email="judge@example.test", password="test"
        )
        self.client.force_login(user)
        for model in ("auto/openai.sol", ""):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    "/api/admin/site/update/", {"judge_model": model}
                )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["judge_model"], model)
            self.assertEqual(site_get().judge_model, model or None)
            self.assertEqual(
                self.client.get("/api/admin/site/").json()["judge_model"],
                model,
            )
        response = self.client.post(
            "/api/admin/site/update/", {"judge_model": "not-a-model"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(Site.objects.get().judge_model)

    def test_all_settings_dropdowns_offer_available_models_and_preserve_saved_values(
        self,
    ):
        user = get_user_model().objects.create_superuser(
            username="model-admin"
        )
        self.client.force_login(user)
        with self.captureOnCommitCallbacks(execute=True):
            site_update(fast_model="auto/zai.glm-flash")
        response = self.client.get("/admin/")
        self.assertEqual(response.context["model_choices"], MODEL_CHOICES)
        for value, label in MODEL_CHOICES:
            self.assertContains(
                response,
                f'<option value="{value}">{label}</option>',
                count=3,
                html=True,
            )
        self.assertNotContains(response, '<option value="auto/zai.glm-flash">')
        self.assertContains(
            response, 'value="auto/zai.glm-flash" hidden disabled'
        )
        self.assertContains(response, "The saved model is unavailable.")
        with patch(
            "litigant_portal.app.views.admin.bedrock_model_choices",
            return_value=(),
        ):
            unavailable = self.client.post(
                "/api/admin/site/update/",
                {"assistant_model": "auto/openai.luna"},
            )
        self.assertEqual(unavailable.status_code, 400)
        self.assertEqual(
            unavailable.json()["error"], "Selected model is unavailable"
        )
        self.assertEqual(
            self.client.post(
                "/api/admin/site/update/",
                {
                    "fast_model": "auto/zai.glm-flash",
                    "assistant_model": "auto/openai.terra",
                    "judge_model": "auto/openai.sol",
                },
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                "/api/admin/site/update/",
                {
                    "assistant_model": "bedrock_mantle/openai.gpt-5.6-luna",
                },
            ).status_code,
            400,
        )

    def test_discovery_failure_keeps_settings_and_saved_models_accessible(
        self,
    ):
        from lp_agent.adapters.bedrock_models import BedrockModelUnavailable

        user = get_user_model().objects.create_superuser(
            username="offline-admin"
        )
        self.client.force_login(user)
        with self.captureOnCommitCallbacks(execute=True):
            site_update(assistant_model="auto/openai.sol")
        with patch(
            "litigant_portal.app.views.pages.bedrock_model_choices",
            side_effect=BedrockModelUnavailable("Discovery failed."),
        ):
            response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Discovery failed.")
        self.assertEqual(response.context["model_choices"], ())
        response = self.client.post(
            "/api/admin/site/update/", {"court_name": "Changed"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["assistant_model"], "auto/openai.sol")

    def test_model_curation_changes_need_no_migration_or_aws(self):
        from lp_agent.adapters.bedrock_models import (
            MODEL_CHOICES,
            MODEL_MAPPING,
        )

        with (
            patch.dict(
                MODEL_MAPPING, {"auto/anthropic.sonnet": "Claude Sonnet"}
            ),
            patch.dict(MODEL_CHOICES, {"best": ["Claude Sonnet", "GPT Sol"]}),
            patch(
                "litigant_portal.app.selectors.bedrock.bedrock_client"
            ) as client,
        ):
            call_command(
                "makemigrations", check=True, dry_run=True, stdout=StringIO()
            )
        client.assert_not_called()

    def test_model_migration_preserves_classes_and_disabled_judging(self):
        migration = import_module(
            "litigant_portal.app.migrations.0035_bedrock_model_choices"
        )
        schema_editor = SimpleNamespace(connection=connection)
        for old, new in migration.MODEL_MAPPING.items():
            Site.objects.update(**dict.fromkeys(migration.MODEL_FIELDS, old))
            migration.migrate_preferences(apps, schema_editor)
            self.assertEqual(
                Site.objects.values_list(*migration.MODEL_FIELDS).get(),
                (new, new, new),
            )
            migration.restore_preferences(apps, schema_editor)
            self.assertEqual(
                Site.objects.values_list(*migration.MODEL_FIELDS).get(),
                (old, old, old),
            )
        Site.objects.update(
            assistant_model="unknown", fast_model="", judge_model=None
        )
        with self.assertWarnsRegex(
            UserWarning, "Unrecognized assistant_model"
        ):
            migration.migrate_preferences(apps, schema_editor)
        migration.restore_preferences(apps, schema_editor)
        site = Site.objects.get()
        self.assertEqual(
            (site.assistant_model, site.fast_model, site.judge_model),
            ("unknown", "", None),
        )


@pytest.mark.postgres
class TopicScopingTests(TestCase):
    """Topics are no longer scoped to a site."""

    def test_topic_needs_no_site(self):
        topic = topic_create(title="Evictions")
        self.assertEqual(topic.slug, "evictions")

    def test_slug_is_globally_unique(self):
        topic_create(title="Evictions")
        second = topic_create(title="Evictions")
        self.assertEqual(second.slug, "evictions-2")

    def test_duplicate_slug_is_rejected_by_the_database(self):
        topic_create(title="Evictions")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Topic.objects.create(slug="evictions", title="Clash")

    def test_topic_list_is_cached_and_busted_by_writes(self):
        topic_list()
        self.assertIsNotNone(cache.get(TOPIC_LIST_CACHE_KEY))

        with self.captureOnCommitCallbacks(execute=True):
            topic_create(title="Small Claims")
        self.assertIsNone(cache.get(TOPIC_LIST_CACHE_KEY))
        self.assertEqual(len(topic_list()), 1)

    def test_topic_flow_list_is_cached_and_busted_by_topic_writes(self):
        topic = topic_create(title="Evictions")
        TopicFlow.objects.create(topic=topic, slug="tenant", enabled=True)
        self.assertEqual([f.slug for f in topic_flow_list()], ["tenant"])
        with self.assertNumQueries(0):
            self.assertEqual([f.slug for f in topic_flow_list()], ["tenant"])

        # Deleting the topic takes its flows with it.
        with self.captureOnCommitCallbacks(execute=True):
            topic_delete(topic=topic)
        self.assertIsNone(cache.get(TOPIC_FLOW_LIST_CACHE_KEY))
        self.assertEqual(topic_flow_list(), [])
