"""The QA court switcher's endpoint (#886).

On wherever ``features().court_switcher`` is (dev and QA). It resyncs the
site to one court or to every court, so the view's own job is the gate, the
court check, and handing the right scope to ``corpus_court_switch``.
"""

from unittest import mock

import pytest
from django.test import override_settings
from django.urls import reverse

from litigant_portal.app.views import pages

pytestmark = [pytest.mark.postgres, pytest.mark.django_db]

COURT_SWITCH = reverse("pages:court_switch")
SUMMARY = dict.fromkeys(
    ("variables", "forms", "topics", "flows", "deleted", "orphaned"), 0
)


@pytest.fixture
def court_switch():
    with mock.patch.object(
        pages, "corpus_court_switch", return_value=SUMMARY
    ) as service:
        yield service


@override_settings(DEPLOYMENT_ENV="prod", PILOT=True)
@pytest.mark.parametrize("method", ["get", "post"])
def test_off_outside_dev_and_qa(client, court_switch, method):
    response = getattr(client, method)(COURT_SWITCH, {"court": "all"})
    assert response.status_code == 404
    court_switch.assert_not_called()


@override_settings(DEPLOYMENT_ENV="qa")
def test_only_accepts_a_post(client, court_switch):
    assert client.get(COURT_SWITCH).status_code == 405
    court_switch.assert_not_called()


@override_settings(DEPLOYMENT_ENV="qa")
@pytest.mark.parametrize(
    ("posted", "scope"),
    [("north-dakota", "north-dakota"), ("all", None)],
    ids=["one-court", "all-courts"],
)
def test_switches_to_the_posted_court(client, court_switch, posted, scope):
    response = client.post(COURT_SWITCH, {"court": posted})
    court_switch.assert_called_once_with(court=scope)
    assert response.status_code == 302
    assert response.url == reverse("pages:home")


@override_settings(DEPLOYMENT_ENV="qa")
@pytest.mark.parametrize("posted", ["gamma", ""], ids=["unknown", "blank"])
def test_rejects_a_court_the_corpus_lacks(client, court_switch, posted):
    response = client.post(COURT_SWITCH, {"court": posted})
    assert response.status_code == 400
    court_switch.assert_not_called()
