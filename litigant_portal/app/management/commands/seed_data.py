from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db import transaction

from litigant_portal.app.models import Site, Topic
from litigant_portal.app.selectors.admin import (
    ACTIVE_SITE_CACHE_KEY,
    ACTIVE_SITE_TOPICS_CACHE_KEY,
)

SEED_TOPICS = [
    {
        "slug": "eviction",
        "title": "Housing & Eviction",
        "subtitle": "Understanding the eviction process, tenant rights, and landlord obligations",
        "description": "Landlord disputes, eviction defense, tenant rights",
        "icon": "home",
        "meta_description": "Learn about the eviction process, tenant rights, and landlord obligations. General legal information for self-represented litigants.",
        "prompts": [
            "I received an eviction notice and need to understand my options",
            "My landlord isn't making repairs — what are my rights?",
            "I'm behind on rent and worried about eviction",
        ],
    },
    {
        "slug": "family",
        "title": "Family & Divorce",
        "subtitle": "Divorce, custody, child support, and domestic violence resources",
        "description": "Divorce, custody, child support, domestic issues",
        "icon": "users",
        "meta_description": "Learn about divorce, child custody, child support, and family court. General legal information for self-represented litigants.",
    },
    {
        "slug": "small-claims",
        "title": "Small Claims",
        "subtitle": "Resolving disputes and understanding the small claims court process",
        "description": "Disputes under $10,000, debt collection defense",
        "icon": "currency-dollar",
        "meta_description": "Learn about filing or defending a small claims case. General legal information for self-represented litigants.",
    },
    {
        "slug": "consumer",
        "title": "Consumer Rights",
        "subtitle": "Debt collection rules, contract disputes, and consumer protections",
        "description": "Scams, unfair business practices, contracts",
        "icon": "shield-check",
        "meta_description": "Learn about consumer rights, debt collection rules, and contract disputes. General legal information for self-represented litigants.",
    },
    {
        "slug": "adult_name_change",
        "title": "Adult Name Change",
        "subtitle": "Legally changing your name — standalone petition process",
        "description": "Petition, publication, and records cascade",
        "icon": "identification",
        "meta_description": "Learn about legally changing your name as an adult — petition process, publication requirements, and updating your records. General legal information for self-represented litigants.",
        "prompts": [
            "I want to change my last name back after a divorce",
            "I want to change my first or middle name",
            "What forms do I need for a name change?",
        ],
    },
    {
        "slug": "traffic",
        "title": "Traffic & Fines",
        "subtitle": "Traffic violations, fines, license issues, and your options",
        "description": "Tickets, license issues, court fines",
        "icon": "truck",
        "meta_description": "Learn about traffic tickets, fines, license suspension, and your options. General legal information for self-represented litigants.",
    },
]


class Command(BaseCommand):
    help = "Seed app with an initial site and topics."

    @transaction.atomic
    def handle(self, *args, **options):
        if Site.objects.exists():
            self.stdout.write("Site rows already exist — nothing to seed.")
            return
        site = Site.objects.create(name="default", active=True)
        for order, data in enumerate(SEED_TOPICS):
            Topic.objects.create(site=site, order=order, **data)
        cache.delete(ACTIVE_SITE_CACHE_KEY)
        cache.delete(ACTIVE_SITE_TOPICS_CACHE_KEY)
        self.stdout.write(
            self.style.SUCCESS(
                f"Created active site '{site.name}' "
                f"with {len(SEED_TOPICS)} topics."
            )
        )
