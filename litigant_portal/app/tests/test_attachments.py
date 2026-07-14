"""Unit tests for attachment hydration (services/attachments.py)."""

import io
import tempfile

import pytest
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings

from litigant_portal.app.models import UserIdentity, UserUpload
from litigant_portal.app.services.attachments import (
    INLINE_MAX_BYTES,
    INLINE_MAX_PAGES,
    READER_MAX_PAGES,
    READER_MAX_TEXT_TOKENS,
    attachments_for_llm,
    reader_limit_error,
)

OPENAI = "gpt-5-mini"
BEDROCK = "bedrock/us.anthropic.claude-sonnet-4-20250514-v1:0"

DOCX_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


def make_pdf(pages: int = 1) -> bytes:
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


@pytest.mark.postgres
@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class AttachmentHydrationTests(TestCase):
    def setUp(self):
        self.identity = UserIdentity.objects.create(session_key="abc123")

    def _upload(
        self,
        name,
        content_type,
        data=b"x",
        size=None,
        pages=None,
        text_chars=None,
    ):
        upload = UserUpload.objects.create(
            identity=self.identity,
            file=ContentFile(data, name=name),
            name=name,
            content_type=content_type,
            size=len(data) if size is None else size,
            pages=pages,
            text_chars=text_chars,
        )
        return upload

    def _history(self, *uploads_per_message):
        return [
            {
                "role": "user",
                "content": f"message {i}",
                "attachments": [str(u.id) for u in uploads],
            }
            for i, uploads in enumerate(uploads_per_message)
        ]

    def test_text_file_inlines_as_text_part(self):
        upload = self._upload("notes.txt", "text/plain", b"secret: BANANA-42")
        history = self._history([upload])
        hydrated = attachments_for_llm(history=history, model=OPENAI, cache={})
        parts = hydrated[0]
        self.assertEqual(parts[0], {"type": "text", "text": "message 0"})
        self.assertEqual(parts[1]["type"], "text")
        self.assertIn("BANANA-42", parts[1]["text"])

    def test_image_inlines_as_image_part(self):
        upload = self._upload("photo.png", "image/png", b"\x89PNGfake")
        hydrated = attachments_for_llm(
            history=self._history([upload]), model=OPENAI, cache={}
        )
        part = hydrated[0][1]
        self.assertEqual(part["type"], "image_url")
        self.assertTrue(
            part["image_url"]["url"].startswith("data:image/png;base64,")
        )

    def test_pdf_inlines_as_file_part_on_both_providers(self):
        upload = self._upload("lease.pdf", "application/pdf", make_pdf())
        for model in (OPENAI, BEDROCK):
            hydrated = attachments_for_llm(
                history=self._history([upload]), model=model, cache={}
            )
            part = hydrated[0][1]
            self.assertEqual(part["type"], "file", model)
            self.assertEqual(part["file"]["filename"], "lease.pdf")

    def test_docx_native_on_bedrock_but_extracted_on_openai(self):
        # Invalid docx bytes: Bedrock ships them natively as a file part;
        # OpenAI extraction fails and degrades to an unreadable stub.
        upload = self._upload("motion.docx", DOCX_TYPE, b"not a real docx")
        hydrated = attachments_for_llm(
            history=self._history([upload]), model=BEDROCK, cache={}
        )
        self.assertEqual(hydrated[0][1]["type"], "file")

        hydrated = attachments_for_llm(
            history=self._history([upload]), model=OPENAI, cache={}
        )
        part = hydrated[0][1]
        self.assertEqual(part["type"], "text")
        self.assertIn("can't be read", part["text"])
        self.assertIn(str(upload.id), part["text"])

    def test_oversized_file_stubs_without_reading(self):
        upload = self._upload(
            "big.pdf", "application/pdf", size=INLINE_MAX_BYTES + 1
        )
        cache: dict = {}
        hydrated = attachments_for_llm(
            history=self._history([upload]), model=OPENAI, cache=cache
        )
        part = hydrated[0][1]
        self.assertIn("too large", part["text"])
        self.assertNotIn(str(upload.id), cache.get("bytes", {}))

    def test_legacy_pdf_without_page_count_backfills_and_gates(self):
        # Rows uploaded before density metadata existed have pages=None;
        # hydration must count pages itself rather than inline blindly.
        upload = self._upload(
            "legacy.pdf", "application/pdf", make_pdf(INLINE_MAX_PAGES + 5)
        )
        self.assertIsNone(upload.pages)
        hydrated = attachments_for_llm(
            history=self._history([upload]), model=OPENAI, cache={}
        )
        part = hydrated[0][1]
        self.assertEqual(part["type"], "text")
        self.assertIn("query_document", part["text"])
        upload.refresh_from_db()
        self.assertEqual(upload.pages, INLINE_MAX_PAGES + 5)

    def test_long_pdf_stubs_despite_small_byte_size(self):
        # Byte-efficient but page-dense: must not inline.
        upload = self._upload(
            "long.pdf", "application/pdf", make_pdf(2), pages=150
        )
        hydrated = attachments_for_llm(
            history=self._history([upload]), model=OPENAI, cache={}
        )
        part = hydrated[0][1]
        self.assertEqual(part["type"], "text")
        self.assertIn("too large", part["text"])
        self.assertIn("query_document", part["text"])

    def test_text_dense_file_stubs_on_any_provider(self):
        # Zipped docx with a huge extracted-text count is large everywhere.
        upload = self._upload(
            "tome.docx", DOCX_TYPE, b"tiny bytes", text_chars=500_000
        )
        for model in (OPENAI, BEDROCK):
            hydrated = attachments_for_llm(
                history=self._history([upload]), model=model, cache={}
            )
            part = hydrated[0][1]
            self.assertEqual(part["type"], "text", model)
            self.assertIn("query_document", part["text"])

    def test_doc_budget_ages_out_oldest_attachments(self):
        uploads = [
            self._upload(f"doc{i}.pdf", "application/pdf", make_pdf())
            for i in range(5)
        ]
        history = self._history(*[[u] for u in uploads])
        hydrated = attachments_for_llm(history=history, model=OPENAI, cache={})
        # Budget is 4 docs, newest first: the oldest message gets a stub.
        self.assertEqual(hydrated[0][1]["type"], "text")
        self.assertIn("no longer inlined", hydrated[0][1]["text"])
        for i in range(1, 5):
            self.assertEqual(hydrated[i][1]["type"], "file")

    def test_text_budget_ages_out_by_extracted_chars(self):
        # Four 35k-char text files: each is small enough to inline, but the
        # 120k char pool fits only the three newest.
        uploads = [
            self._upload(f"notes{i}.txt", "text/plain", b"x" * 35_000)
            for i in range(4)
        ]
        history = self._history(*[[u] for u in uploads])
        hydrated = attachments_for_llm(history=history, model=OPENAI, cache={})
        self.assertIn("no longer inlined", hydrated[0][1]["text"])
        for i in (1, 2, 3):
            self.assertIn("xxx", hydrated[i][1]["text"])

    def test_text_extracts_do_not_consume_document_slots(self):
        # Four PDFs exhaust the doc budget, but an older text file still
        # inlines — extracts spend the char pool, not document slots.
        text = self._upload("notes.txt", "text/plain", b"the facts")
        pdfs = [
            self._upload(f"doc{i}.pdf", "application/pdf", make_pdf())
            for i in range(4)
        ]
        history = self._history([text], *[[u] for u in pdfs])
        hydrated = attachments_for_llm(history=history, model=OPENAI, cache={})
        self.assertIn("the facts", hydrated[0][1]["text"])
        for i in range(1, 5):
            self.assertEqual(hydrated[i][1]["type"], "file")

    def test_missing_upload_stubs(self):
        history = [
            {
                "role": "user",
                "content": "hi",
                "attachments": ["00000000-0000-0000-0000-000000000000"],
            }
        ]
        hydrated = attachments_for_llm(history=history, model=OPENAI, cache={})
        self.assertIn("no longer available", hydrated[0][1]["text"])

    def test_no_attachments_returns_empty(self):
        history = [{"role": "user", "content": "hi"}]
        self.assertEqual(
            attachments_for_llm(history=history, model=OPENAI, cache={}), {}
        )


@pytest.mark.postgres
@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class UploadMetadataTests(TestCase):
    """user_upload_create computes the density metadata the gates rely on."""

    def setUp(self):
        self.identity = UserIdentity.objects.create(session_key="abc123")

    def test_pdf_gets_page_count(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from litigant_portal.app.services.assistant import user_upload_create

        upload = user_upload_create(
            identity=self.identity,
            file=SimpleUploadedFile("doc.pdf", make_pdf(3)),
        )
        self.assertEqual(upload.pages, 3)
        self.assertIsNone(upload.text_chars)

    def test_text_file_gets_char_count(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from litigant_portal.app.services.assistant import user_upload_create

        upload = user_upload_create(
            identity=self.identity,
            file=SimpleUploadedFile("notes.txt", b"hello world"),
        )
        self.assertEqual(upload.text_chars, 11)
        self.assertIsNone(upload.pages)

    def test_delete_removes_row_and_stored_file(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from litigant_portal.app.services.assistant import (
            user_upload_create,
            user_upload_delete,
        )

        upload = user_upload_create(
            identity=self.identity,
            file=SimpleUploadedFile("notes.txt", b"bye"),
        )
        storage, path = upload.file.storage, upload.file.name
        self.assertTrue(storage.exists(path))
        user_upload_delete(identity=self.identity, upload_id=upload.id)
        self.assertFalse(storage.exists(path))
        self.assertFalse(UserUpload.objects.filter(id=upload.id).exists())

    def test_delete_requires_ownership(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from litigant_portal.app.services.assistant import (
            user_upload_create,
            user_upload_delete,
        )

        other = UserIdentity.objects.create(session_key="other")
        upload = user_upload_create(
            identity=other, file=SimpleUploadedFile("theirs.txt", b"x")
        )
        with self.assertRaises(UserUpload.DoesNotExist):
            user_upload_delete(identity=self.identity, upload_id=upload.id)


class ReaderLimitTests(TestCase):
    """Documents past the reader ceilings are refused, never cropped."""

    def test_pdf_within_limits_passes(self):
        upload = UserUpload(content_type="application/pdf", pages=3)
        self.assertIsNone(reader_limit_error(upload, make_pdf(3)))

    def test_very_long_pdf_is_refused(self):
        upload = UserUpload(
            content_type="application/pdf", pages=READER_MAX_PAGES + 1
        )
        error = reader_limit_error(upload, make_pdf(1))
        self.assertIn(f"{READER_MAX_PAGES + 1} pages", error)

    def test_huge_text_is_refused_by_token_count(self):
        upload = UserUpload(content_type="text/plain")
        # Distinct numbers tokenize to at least one token apiece — repeated
        # characters would BPE-compress and never trip the gate.
        data = " ".join(
            str(i) for i in range(READER_MAX_TEXT_TOKENS + 10_000)
        ).encode()
        error = reader_limit_error(upload, data)
        self.assertIn("tokens of text", error)

    def test_small_text_passes(self):
        upload = UserUpload(content_type="text/plain")
        self.assertIsNone(reader_limit_error(upload, b"a short note"))
