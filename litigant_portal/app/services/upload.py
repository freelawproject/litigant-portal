import base64
import io
import logging
from functools import lru_cache
from typing import Any

import mammoth
import openpyxl
import tiktoken
from pypdf import PdfReader

from litigant_portal.app.models import UserUpload

logger = logging.getLogger(__name__)

IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}
TEXT_TYPES = {"text/plain", "text/markdown", "text/csv"}
PDF_TYPE = "application/pdf"
DOCX_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# Document types with native Bedrock Converse API support.
BEDROCK_DOC_TYPES = {
    PDF_TYPE,
    DOCX_TYPE,
    XLSX_TYPE,
    "application/msword",
    "application/vnd.ms-excel",
    *TEXT_TYPES,
}

# Thresholds for small vs large attachments.
INLINE_MAX_BYTES = 4 * 1024 * 1024
INLINE_MAX_PAGES = 20
INLINE_MAX_TEXT_CHARS = 40_000

# Threshold reader model's limits for large attachments.
READER_MAX_PAGES = 100
READER_MAX_TEXT_TOKENS = 150_000

# Thresholds for when inline attachments "age" into stubs.
REQUEST_DOC_BUDGET = 4
REQUEST_IMAGE_BUDGET = 8
REQUEST_BYTE_BUDGET = 16 * 1024 * 1024
REQUEST_TEXT_BUDGET = 120_000


def file_kind(content_type: str) -> str:
    """Group content types by processing family."""
    if content_type in IMAGE_TYPES:
        return "image"
    if content_type == PDF_TYPE:
        return "pdf"
    if content_type in TEXT_TYPES or content_type in (DOCX_TYPE, XLSX_TYPE):
        return "text"
    return "other"


def is_bedrock(model: str) -> bool:
    return model.startswith("bedrock/")


def is_small(upload: UserUpload) -> bool:
    """Apply small vs large thresholds by filetype."""
    if upload.size > INLINE_MAX_BYTES:
        return False
    kind = file_kind(upload.content_type)
    if kind == "pdf":
        return (upload.pages or 0) <= INLINE_MAX_PAGES
    if kind == "text":
        return (upload.text_chars or 0) <= INLINE_MAX_TEXT_CHARS
    return True


def extract_text(content_type: str, data: bytes) -> str | None:
    """Plain text for text-family and office files, or None on failure."""
    try:
        if content_type in TEXT_TYPES:
            return data.decode("utf-8", errors="replace")
        if content_type == DOCX_TYPE:
            return mammoth.extract_raw_text(io.BytesIO(data)).value
        if content_type == XLSX_TYPE:
            workbook = openpyxl.load_workbook(
                io.BytesIO(data), read_only=True, data_only=True
            )
            lines = []
            for sheet in workbook.worksheets:
                lines.append(f"# Sheet: {sheet.title}")
                for row in sheet.iter_rows(values_only=True):
                    lines.append(
                        "\t".join("" if v is None else str(v) for v in row)
                    )
            return "\n".join(lines)
    except Exception:
        logger.exception("Attachment text extraction failed")
    return None


def pdf_page_count(data: bytes) -> int | None:
    """Page count of a PDF, or None if it can't be parsed."""
    try:
        return len(PdfReader(io.BytesIO(data)).pages)
    except Exception:
        logger.exception("PDF page count failed")
        return None


@lru_cache
def tokenizer() -> tiktoken.Encoding:
    return tiktoken.get_encoding("o200k_base")


def token_count(text: str) -> int:
    """Approximate LLM token count for gating purposes."""
    return len(tokenizer().encode(text))


def reader_limit_error(upload: UserUpload, data: bytes) -> str | None:
    """Check if an attachment exceeds the reader model's limits."""
    kind = file_kind(upload.content_type)
    if kind == "pdf":
        pages = upload.pages or pdf_page_count(data) or 0
        if pages > READER_MAX_PAGES:
            return f"{pages} pages (max {READER_MAX_PAGES})"
    if kind == "text":
        text = extract_text(upload.content_type, data)
        tokens = token_count(text) if text else 0
        if tokens > READER_MAX_TEXT_TOKENS:
            return (
                f"~{tokens:,} tokens of text (max {READER_MAX_TEXT_TOKENS:,})"
            )
    return None


def data_url(content_type: str, data: bytes) -> str:
    return f"data:{content_type};base64,{base64.b64encode(data).decode()}"


def file_part(upload: UserUpload, data: bytes) -> dict[str, Any]:
    return {
        "type": "file",
        "file": {
            "file_data": data_url(upload.content_type, data),
            "filename": upload.name,
        },
    }


def content_part(
    *, upload: UserUpload, data: bytes, model: str
) -> dict[str, Any] | None:
    """One llm content part, or None if the model can't consume the type.

    Images and PDFs are native everywhere. Office and text files are
    native document blocks on Bedrock and extracted text elsewhere.
    """
    kind = file_kind(upload.content_type)
    if kind == "image":
        return {
            "type": "image_url",
            "image_url": {"url": data_url(upload.content_type, data)},
        }
    if kind == "pdf":
        return file_part(upload, data)
    if is_bedrock(model) and upload.content_type in BEDROCK_DOC_TYPES:
        return file_part(upload, data)
    if kind != "text":
        return None
    text = extract_text(upload.content_type, data)
    if text is None:
        return None
    return {
        "type": "text",
        "text": (
            f'Attached file "{upload.name}" '
            f"(upload_id={upload.id}):\n---\n{text}\n---"
        ),
    }


def human_size(size: int) -> str:
    kb = size / 1024
    return f"{kb / 1024:.1f} MB" if kb >= 1024 else f"{kb:.0f} KB"


def attachment_stub(upload: UserUpload, reason: str) -> dict[str, Any]:
    """A text part standing in for a file that isn't inlined."""
    return {
        "type": "text",
        "text": (
            f'[Attached file "{upload.name}" ({upload.content_type}, '
            f"{human_size(upload.size)}, upload_id={upload.id}) — {reason}.]"
        ),
    }


def read_bytes(upload: UserUpload, cache: dict) -> bytes:
    """File bytes, cached for the lifetime of one stream request."""
    store = cache.setdefault("bytes", {})
    key = str(upload.id)
    if key not in store:
        with upload.file.open("rb") as f:
            store[key] = f.read()
    return store[key]


def ensure_metadata(upload: UserUpload, cache: dict) -> None:
    """Backfill pages/text_chars for rows uploaded before capture existed."""
    if upload.size > INLINE_MAX_BYTES:
        return
    kind = file_kind(upload.content_type)
    if kind == "pdf" and upload.pages is None:
        upload.pages = pdf_page_count(read_bytes(upload, cache))
        if upload.pages is not None:
            upload.save(update_fields=["pages", "updated_at"])
    elif kind == "text" and upload.text_chars is None:
        text = extract_text(upload.content_type, read_bytes(upload, cache))
        if text is not None:
            upload.text_chars = len(text)
            upload.save(update_fields=["text_chars", "updated_at"])


def hydrate_attachment(
    upload_id: str,
    uploads: dict[str, UserUpload],
    cache: dict,
    model: str,
    budgets: dict[str, int],
) -> dict[str, Any]:
    """Inline one attachment as a content part, or degrade to a stub."""
    upload = uploads.get(upload_id)
    if upload is None:
        return {
            "type": "text",
            "text": (
                f"[Attached file upload_id={upload_id} "
                f"is no longer available.]"
            ),
        }

    ensure_metadata(upload, cache)
    if not is_small(upload):
        return attachment_stub(
            upload,
            "too large to include inline; "
            "use the query_document tool to read it",
        )

    part = content_part(
        upload=upload, data=read_bytes(upload, cache), model=model
    )
    if part is None:
        return attachment_stub(
            upload, "this file type can't be read by the current model"
        )

    aged = attachment_stub(
        upload,
        "attached earlier and no longer inlined; "
        "use the query_document tool to re-read it",
    )
    if part["type"] == "text":
        charge = len(part["text"])
        if charge > budgets["text"]:
            return aged
        budgets["text"] -= charge
        return part

    slot = "images" if part["type"] == "image_url" else "docs"
    if budgets[slot] <= 0 or budgets["bytes"] < upload.size:
        return aged
    budgets[slot] -= 1
    budgets["bytes"] -= upload.size
    return part


def attachments_for_llm(
    *, history: list[dict[str, Any]], model: str, cache: dict
) -> dict[int, list[dict[str, Any]]]:
    """Inject llm content parts for user messages that carry attachments."""
    ids = {
        str(upload_id)
        for msg in history
        if msg.get("role") == "user"
        for upload_id in msg.get("attachments") or []
    }
    if not ids:
        return {}

    uploads = cache.setdefault("uploads", {})
    missing = ids - uploads.keys()
    if missing:
        for upload in UserUpload.objects.filter(id__in=missing):
            uploads[str(upload.id)] = upload

    budgets = {
        "docs": REQUEST_DOC_BUDGET,
        "images": REQUEST_IMAGE_BUDGET,
        "bytes": REQUEST_BYTE_BUDGET,
        "text": REQUEST_TEXT_BUDGET,
    }
    hydrated: dict[int, list[dict[str, Any]]] = {}
    for i in reversed(range(len(history))):
        msg = history[i]
        if msg.get("role") != "user" or not msg.get("attachments"):
            continue
        parts = [{"type": "text", "text": msg.get("content", "")}]
        for upload_id in msg["attachments"]:
            parts.append(
                hydrate_attachment(
                    str(upload_id), uploads, cache, model, budgets
                )
            )
        hydrated[i] = parts
    return hydrated
