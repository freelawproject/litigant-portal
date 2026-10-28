"""Contact flattening for Topic Flow — pure, DB-free (runs in the fast suite).

``contact_dicts`` is the one shape the page block and the ``.vcf`` download
both consume, so the downloaded card can't drift from what's on the page.
"""

from types import SimpleNamespace

from litigant_portal.app.models import Contact
from litigant_portal.app.topic_flow.contacts import contact_dicts

FULL = {
    "name": "Clerk of Court",
    "phone": "555-1234",
    "email": "clerk@court.gov",
    "url": "https://court.gov",
    "address": "100 Main St",
    "hours": "9-4 M-F",
    "note": "Window 3",
}


def test_contact_dicts_flatten_rows_in_order_with_the_ref_as_id():
    rows = [Contact(key="clerk", **FULL), Contact(key="aid", name="Legal Aid")]
    assert contact_dicts(rows, id_attr="ref") == [
        {"id": "clerk", **FULL},
        {
            "id": "aid",
            "name": "Legal Aid",
            "phone": "",
            "email": "",
            "url": "",
            "address": "",
            "hours": "",
            "note": "",
        },
    ]


def test_contact_dicts_read_the_id_from_the_named_attribute():
    contact = SimpleNamespace(
        id="clerk", **{**dict.fromkeys(FULL), "name": "Clerk"}
    )
    (resolved,) = contact_dicts([contact])
    assert resolved["id"] == "clerk"
    assert resolved["name"] == "Clerk"
    assert resolved["phone"] is None
