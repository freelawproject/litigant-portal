"""Resolve a vcf output section's contacts — pure, AI-free, DB-free.

Parallels ``deadlines.py``'s ``resolve_ics_deadlines``: the single place a vcf
output section's ``contact_ids`` are resolved against corpus-level contacts, in
the section's declared order. Both the page renderer (which displays the
contacts) and the ``.vcf`` download handler (which turns them into vCards)
consume this one resolver, so the downloaded card can't drift from what's shown
on the page.

Unlike deadlines there is no computation — a contact needs no user input — so
this is a pure id lookup. The loader guarantees every ``contact_id`` resolves
for a valid corpus, so the lookup never misses.

``contact_dicts`` is the flattening half on its own, so the rows path
(``rows.py``) can feed ``Contact`` rows through the same shape.
"""

_FIELDS = ("name", "phone", "email", "url", "address", "hours", "note")


def contact_dicts(contacts, *, id_attr="id"):
    """One flat dict per contact, in the given order.

    ``{id, name, phone, email, url, address, hours, note}`` — already
    template-ready and decoupled from the schema model, so the renderer binds
    it directly and the download handler maps it to vCard fields. ``id_attr``
    names the attribute that becomes ``id``: ``id`` on a corpus contact,
    ``ref`` on a ``Contact`` row.
    """
    return [
        {
            "id": getattr(contact, id_attr),
            **{field: getattr(contact, field) for field in _FIELDS},
        }
        for contact in contacts
    ]


def resolve_vcf_contacts(section, corpus):
    """Return one flat dict per referenced contact, in declared order."""
    by_id = {contact.id: contact for contact in corpus.contacts}
    return contact_dicts(
        by_id[contact_id] for contact_id in section.contact_ids
    )
