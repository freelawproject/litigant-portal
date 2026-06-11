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
"""


def resolve_vcf_contacts(section, corpus):
    """Return one flat dict per referenced contact, in declared order.

    ``{id, name, phone, email, url, address, hours, note}`` — already
    template-ready and decoupled from the schema model, so the renderer binds
    it directly and the download handler maps it to vCard fields.
    """
    by_id = {contact.id: contact for contact in corpus.contacts}
    resolved = []
    for contact_id in section.contact_ids:
        contact = by_id[contact_id]
        resolved.append(
            {
                "id": contact.id,
                "name": contact.name,
                "phone": contact.phone,
                "email": contact.email,
                "url": contact.url,
                "address": contact.address,
                "hours": contact.hours,
                "note": contact.note,
            }
        )
    return resolved
