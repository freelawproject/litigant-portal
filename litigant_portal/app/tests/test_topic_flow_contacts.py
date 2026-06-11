"""Contact resolution for Topic Flow — pure, DB-free (runs in the fast suite).

``resolve_vcf_contacts`` is the shared resolver a vcf section's renderer AND its
.vcf download view both call, so the page and the downloaded vCard build from
one source. It duck-types on ``section.contact_ids`` and ``corpus.contacts``;
the stand-ins below carry just those attributes (real Contact objects supply
the fields the resolver reads).
"""

from types import SimpleNamespace

from litigant_portal.app.topic_flow.contacts import resolve_vcf_contacts
from litigant_portal.app.topic_flow.schema import Contact


def _contact(id, name, **fields):
    return Contact(id=id, name=name, **fields)


def _section(*contact_ids):
    return SimpleNamespace(contact_ids=list(contact_ids))


def _corpus(*contacts):
    return SimpleNamespace(contacts=list(contacts))


def test_resolves_a_referenced_contacts_fields():
    contact = _contact(
        "clerk",
        "Clerk of Court",
        phone="555-1234",
        email="clerk@court.gov",
        url="https://court.gov",
        address="100 Main St",
        hours="9-4 M-F",
        note="Window 3",
    )
    (resolved,) = resolve_vcf_contacts(_section("clerk"), _corpus(contact))
    assert resolved == {
        "id": "clerk",
        "name": "Clerk of Court",
        "phone": "555-1234",
        "email": "clerk@court.gov",
        "url": "https://court.gov",
        "address": "100 Main St",
        "hours": "9-4 M-F",
        "note": "Window 3",
    }


def test_absent_optional_fields_resolve_to_none():
    # Only id + name supplied; the rest must come through as None, not missing.
    contact = _contact("aid", "Legal Aid")
    (resolved,) = resolve_vcf_contacts(_section("aid"), _corpus(contact))
    assert resolved["phone"] is None
    assert resolved["email"] is None
    assert resolved["note"] is None


def test_resolves_in_contact_ids_order_not_corpus_order():
    # Order follows the section's contact_ids, not corpus.contacts order.
    clerk = _contact("clerk", "Clerk")
    aid = _contact("aid", "Legal Aid")
    resolved = resolve_vcf_contacts(
        _section("aid", "clerk"), _corpus(clerk, aid)
    )
    assert [c["name"] for c in resolved] == ["Legal Aid", "Clerk"]


def test_resolves_every_referenced_contact():
    clerk = _contact("clerk", "Clerk")
    aid = _contact("aid", "Legal Aid")
    resolved = resolve_vcf_contacts(
        _section("clerk", "aid"), _corpus(clerk, aid)
    )
    assert len(resolved) == 2
