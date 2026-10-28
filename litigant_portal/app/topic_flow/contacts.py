"""Flatten ``Contact`` rows for the page and the ``.vcf`` download — pure,
DB-free.

Both the page block (which displays the contacts) and the download (which
turns them into vCards) consume this one shape, so the downloaded card can't
drift from what's shown on the page.
"""

_FIELDS = ("name", "phone", "email", "url", "address", "hours", "note")


def contact_dicts(contacts, *, id_attr="id"):
    """One flat dict per contact, in the given order.

    ``{id, name, phone, email, url, address, hours, note}`` — already
    template-ready and decoupled from the model, so the page binds it
    directly and the download maps it to vCard fields. ``id_attr`` names the
    attribute that becomes ``id``: ``ref`` on a ``Contact`` row.
    """
    return [
        {
            "id": getattr(contact, id_attr),
            **{field: getattr(contact, field) for field in _FIELDS},
        }
        for contact in contacts
    ]
