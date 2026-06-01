"""Generate downloadable artifacts from corpus data.

Currently: a vCard (``.vcf``) from a :class:`Contact` — a pure projection with
no user input, no session, no host page. The future ``.ics`` generator
(Deadline + a gathered date) needs the session-backed AnswerStore and lands
separately.

The view layer only orchestrates (look the entity up, set download headers);
the bytes are produced here so the field mapping is unit-testable without
Django, and ``vobject`` owns vCard escaping and line folding.
"""

import vobject

from litigant_portal.app.topic_flow.schema import Contact


def contact_to_vcard(contact: Contact) -> str:
    """Serialize a Contact to a vCard 3.0 string.

    Only the fields the Contact actually has are emitted — an absent field
    means an absent line, never an empty one.
    """
    card = vobject.vCard()
    card.add("fn").value = contact.name
    # vCard 3.0 requires N alongside FN. These are office/person names with no
    # given/family split, so the whole name goes in the family slot.
    card.add("n").value = vobject.vcard.Name(family=contact.name)
    if contact.phone:
        card.add("tel").value = contact.phone
    if contact.email:
        card.add("email").value = contact.email
    if contact.url:
        card.add("url").value = contact.url
    if contact.address:
        card.add("adr").value = vobject.vcard.Address(street=contact.address)
    if contact.note:
        card.add("note").value = contact.note
    return card.serialize()
