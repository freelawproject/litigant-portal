"""Tests for Topic Flow artifact generation + the download view.

The generator (`contact_to_vcard`) is pure and tested directly; the result is
parsed back with vobject so assertions ride on field values, not on brittle
serialized-text formatting. The view is exercised through the Django test
client with the module-level registry monkeypatched onto a fixture corpus.
"""

from pathlib import Path

import vobject
from django.urls import reverse

from litigant_portal.app.topic_flow.artifacts import contact_to_vcard
from litigant_portal.app.topic_flow.registry import CorpusRegistry
from litigant_portal.app.topic_flow.schema import Contact

FIXTURE = Path(__file__).resolve().parents[2] / "content" / "_test_fixture.yml"
FIXTURE_KEY = ("test-court", "test_topic", "petitioner")


def _contact(**overrides):
    base = {"id": "clerk", "name": "Test County Clerk"}
    base.update(overrides)
    return Contact(**base)


# --- generator: field mapping --------------------------------------------


def test_vcard_is_wellformed_with_name():
    card = vobject.readOne(contact_to_vcard(_contact()))
    assert card.fn.value == "Test County Clerk"


def test_vcard_includes_every_present_field():
    contact = _contact(
        phone="701-555-0100",
        email="clerk@example.gov",
        url="https://example.gov/clerk",
        address="100 Courthouse Square, Test City",
        note="Call before filing.",
    )
    card = vobject.readOne(contact_to_vcard(contact))
    assert card.tel.value == "701-555-0100"
    assert card.email.value == "clerk@example.gov"
    assert card.url.value == "https://example.gov/clerk"
    assert card.adr.value.street == "100 Courthouse Square, Test City"
    assert card.note.value == "Call before filing."


def test_vcard_omits_absent_fields():
    # Name only — no phone/email/url/address/note set.
    card = vobject.readOne(contact_to_vcard(_contact()))
    assert "tel" not in card.contents
    assert "email" not in card.contents
    assert "url" not in card.contents
    assert "adr" not in card.contents
    assert "note" not in card.contents


def test_vcard_phone_without_email_emits_only_tel():
    card = vobject.readOne(contact_to_vcard(_contact(phone="701-555-0100")))
    assert card.tel.value == "701-555-0100"
    assert "email" not in card.contents


# --- download view --------------------------------------------------------


def _patch_registry(monkeypatch, tmp_path):
    """Point the view's registry at a fixture corpus (renamed so it indexes)."""
    (tmp_path / "real.yml").write_text(
        FIXTURE.read_text(encoding="utf-8"), encoding="utf-8"
    )
    monkeypatch.setattr(
        "litigant_portal.app.views.pages.registry",
        CorpusRegistry(content_dir=tmp_path),
    )


def _vcard_url(contact_id="clerk", key=FIXTURE_KEY):
    court, topic, role = key
    return reverse(
        "pages:contact_vcard",
        kwargs={
            "court": court,
            "topic": topic,
            "role": role,
            "contact_id": contact_id,
        },
    )


def test_view_returns_vcard_attachment(client, monkeypatch, tmp_path):
    _patch_registry(monkeypatch, tmp_path)
    response = client.get(_vcard_url())
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/vcard")
    assert (
        response["Content-Disposition"] == 'attachment; filename="clerk.vcf"'
    )
    card = vobject.readOne(response.content.decode())
    assert card.tel.value == "701-555-0100"


def test_view_404_for_unknown_corpus(client, monkeypatch, tmp_path):
    _patch_registry(monkeypatch, tmp_path)
    response = client.get(
        _vcard_url(key=("no-court", "no_topic", "petitioner"))
    )
    assert response.status_code == 404


def test_view_404_for_unknown_contact(client, monkeypatch, tmp_path):
    _patch_registry(monkeypatch, tmp_path)
    response = client.get(_vcard_url(contact_id="ghost"))
    assert response.status_code == 404
