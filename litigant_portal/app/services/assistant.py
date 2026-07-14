from pathlib import Path
from typing import Any

from django.core.files.uploadedfile import UploadedFile
from django.utils.translation import gettext as _

from litigant_portal.app.models import UserIdentity, UserUpload

ALLOWED_UPLOAD_TYPES = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".csv": "text/csv",
    ".rtf": "application/rtf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MB


class UploadValidationError(Exception):
    """A user upload failed validation (bad type or too large)."""


def user_upload_create(
    *, identity: UserIdentity, file: UploadedFile
) -> UserUpload:
    """Validate and store an uploaded file for an identity."""
    extension = Path(file.name or "").suffix.lower()
    content_type = ALLOWED_UPLOAD_TYPES.get(extension)
    if content_type is None:
        raise UploadValidationError(
            _("Unsupported file type: %(ext)s") % {"ext": extension or "?"}
        )
    if file.size > MAX_UPLOAD_SIZE:
        raise UploadValidationError(_("File is too large (max 20 MB)."))

    pages, text_chars = content_metadata(content_type, file)
    return UserUpload.objects.create(
        identity=identity,
        file=file,
        name=file.name,
        content_type=content_type,
        size=file.size,
        pages=pages,
        text_chars=text_chars,
    )


def user_upload_delete(*, identity: UserIdentity, upload_id) -> None:
    """Permanently delete an upload (row and stored file) owned by the
    identity (raises UserUpload.DoesNotExist)."""
    upload = UserUpload.objects.get(id=upload_id, identity=identity)
    upload.file.delete(save=False)
    upload.delete()


def content_metadata(
    content_type: str, file: UploadedFile
) -> tuple[int | None, int | None]:
    """(pages, text_chars) computed once at upload — the size signals that
    classify a file as small (inline) or large (query_document)."""
    from litigant_portal.app.services.attachments import (
        extract_text,
        file_kind,
        pdf_page_count,
    )

    file.seek(0)
    data = file.read()
    file.seek(0)
    kind = file_kind(content_type)
    if kind == "pdf":
        return pdf_page_count(data), None
    if kind == "text":
        text = extract_text(content_type, data)
        return None, len(text) if text is not None else None
    return None, None


def user_upload_serialize(upload: UserUpload) -> dict:
    """JSON shape the chat frontend uses to render an upload."""
    return {
        "id": str(upload.id),
        "name": upload.name,
        "content_type": upload.content_type,
        "size": upload.size,
        "is_image": upload.content_type.startswith("image/"),
        "url": upload.file.url,
        "created_at": upload.created_at.isoformat(),
    }


def attachment_render_list(upload_ids: list[str]) -> list[dict[str, Any]]:
    """Frontend-facing attachment descriptors for a stored user message."""
    uploads = {
        str(u.id): u for u in UserUpload.objects.filter(id__in=upload_ids)
    }
    items = []
    for upload_id in upload_ids:
        upload = uploads.get(str(upload_id))
        if upload is None:
            items.append(
                {
                    "id": str(upload_id),
                    "name": "(deleted file)",
                    "content_type": "",
                    "size": 0,
                    "is_image": False,
                    "url": "",
                    "missing": True,
                }
            )
        else:
            items.append(user_upload_serialize(upload))
    return items
