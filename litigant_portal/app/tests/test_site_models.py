"""Schema tests for the site's contacts and resources.

Both are unique on their display name because the court library upserts on
it: re-importing a config has to update the row it already created rather
than append a second copy. That is the constraint worth pinning before the
importer exists to depend on it.
"""

import pytest
from django.db import IntegrityError, transaction
from django.test import TestCase

from litigant_portal.app.models import Contact, Resource


@pytest.mark.postgres
class ContactTests(TestCase):
    def test_name_is_unique(self):
        Contact.objects.create(name="Self Help Center")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Contact.objects.create(name="Self Help Center")

    def test_only_a_name_is_required(self):
        contact = Contact.objects.create(name="Clerk of Court")
        self.assertEqual(
            (contact.phone, contact.email, contact.url, contact.note),
            ("", "", "", ""),
        )

    def test_listed_in_display_order(self):
        Contact.objects.create(name="second", order=1)
        Contact.objects.create(name="first", order=0)
        self.assertEqual(
            [c.name for c in Contact.objects.all()], ["first", "second"]
        )


@pytest.mark.postgres
class ResourceTests(TestCase):
    def test_label_is_unique(self):
        Resource.objects.create(label="Tenant guide", url="https://a.test")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Resource.objects.create(label="Tenant guide", url="https://b.test")

    def test_listed_in_display_order(self):
        Resource.objects.create(label="second", url="https://b.test", order=1)
        Resource.objects.create(label="first", url="https://a.test", order=0)
        self.assertEqual(
            [r.label for r in Resource.objects.all()], ["first", "second"]
        )
