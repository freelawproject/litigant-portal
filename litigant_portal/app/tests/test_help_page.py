"""The Get help page (#1022): the court's own details and its help contacts.

Help shows only what the corpus knows. A contact appears when its court
marks it with a help kind, so a court without a legal-aid contact shows no
legal-aid line rather than a dead link.
"""

import pytest
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from litigant_portal.app.cache import SITE_CACHE_KEY
from litigant_portal.app.models import Contact, Site
from litigant_portal.app.models.choices import ContactKind
from litigant_portal.app.selectors.site import contact_help_list

HELP = reverse("pages:help")


def _contact(name, kind="", order=0):
    return Contact.objects.create(name=name, kind=kind, order=order)


@pytest.mark.postgres
class ContactHelpListTests(TestCase):
    def test_help_contacts_come_in_help_order_and_others_are_left_out(self):
        _contact("Referral line", ContactKind.REFERRAL, order=0)
        _contact("Bailiff", order=1)
        _contact("Legal aid", ContactKind.LEGAL_AID, order=2)
        _contact("Self help center", ContactKind.SELF_HELP, order=3)
        _contact("Clerk", ContactKind.CLERK, order=4)

        self.assertEqual(
            [c.name for c in contact_help_list()],
            ["Clerk", "Self help center", "Legal aid", "Referral line"],
        )

    def test_contacts_of_one_kind_keep_their_corpus_order(self):
        _contact("Second aid", ContactKind.LEGAL_AID, order=1)
        _contact("First aid", ContactKind.LEGAL_AID, order=0)

        self.assertEqual(
            [c.name for c in contact_help_list()], ["First aid", "Second aid"]
        )


@pytest.mark.postgres
class HelpPageTests(TestCase):
    def test_shows_the_court_and_its_help_contacts(self):
        site = Site.objects.get()
        site.court_name = "Alpha City Court"
        site.save()
        cache.delete(SITE_CACHE_KEY)
        clerk = _contact("Clerk", ContactKind.CLERK)
        _contact("Bailiff")

        response = self.client.get(HELP)

        self.assertEqual(
            response.context["site"].court_name, "Alpha City Court"
        )
        self.assertEqual(list(response.context["help_contacts"]), [clerk])

    def test_an_instance_with_no_court_has_nothing_to_show(self):
        response = self.client.get(HELP)

        self.assertEqual(response.context["site"].court_name, "")
        self.assertEqual(list(response.context["help_contacts"]), [])
