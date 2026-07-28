# Attachment System

How user-uploaded files flow into the chat engine: uploaded once, attached to
messages by id, inlined into the LLM request while small and recent, and read
through a subagent tool otherwise.

Code: [`services/assistant.py`](../litigant_portal/app/services/assistant.py)
(upload lifecycle) ·
[`services/attachments.py`](../litigant_portal/app/services/attachments.py)
(LLM hydration) ·
[`agents/tools/query_document.py`](../litigant_portal/agents/tools/query_document.py)
(reader subagent)

## 1. Supported types & upload

- **Allowed types** (`ALLOWED_UPLOAD_TYPES`): pdf, doc/docx, xls/xlsx, txt,
  md, csv, rtf, png, jpg/jpeg, gif, webp. The **file extension is the source
  of truth** for the stored content type — client-sent MIME types are
  unreliable. Max size **20 MB**.
- **Endpoints**: `api/agents/assistant/uploads/` (list / create / delete),
  backed by `user_upload_create` / `user_upload_delete`.
- **Storage**: a `UserUpload` row owned by a `UserIdentity`, with the file at
  `uploads/<uuid>/<filename>` in default storage (S3 in deployment). Uploads
  are identity-scoped everywhere — every lookup filters by owner.
- **Metadata at upload**: `content_metadata` computes `pages` (PDFs) and
  `text_chars` (text-family files) once, so later small/large decisions don't
  re-parse the file. Rows from before this existed are backfilled lazily
  (`ensure_metadata`).
- Messages store only **attachment ids**: `chat_stream` saves
  `attachments: [upload_id, ...]` on the user message; content is hydrated
  fresh on every request.

## 2. Small vs. large

`is_small` classifies each attachment by its filetype's own criteria:

| Check              | Limit                                 |
| ------------------ | ------------------------------------- |
| Any file           | ≤ 4 MB (`INLINE_MAX_BYTES`)           |
| PDF                | ≤ 20 pages (`INLINE_MAX_PAGES`)       |
| Text / docx / xlsx | ≤ 40k chars (`INLINE_MAX_TEXT_CHARS`) |
| Image              | byte cap only                         |

Small files attach inline; large files ride as a stub pointing at the
`query_document` tool. Content is never silently truncated — a file is either
fully inline or fully behind the tool.

## 3. Inlining small files

`attachments_for_llm` maps each user message that carries attachments to
litellm content parts (`content_part`):

- **Images** → `image_url` data URLs (native everywhere).
- **PDFs** → `file` parts (native everywhere).
- **Office / text files** → native document blocks on Bedrock
  (`BEDROCK_DOC_TYPES`); extracted plain text elsewhere (`extract_text`:
  mammoth for docx, openpyxl for xlsx, utf-8 decode for text).
- File bytes are read once per stream request via a request-lifetime cache.

Inlining is subject to **per-request budgets**: 4 documents, 8 images, 16 MB
total bytes, 120k chars of extracted text.

## 4. Large files: the reader subagent

The `QueryDocument` tool (`upload_id` + `request`) hands the _whole document_
to a reader model in one call:

- Loads the upload (identity-checked via the thread), then gates on
  **reader limits**: 100 PDF pages, ~150k text tokens (counted with
  tiktoken `o200k_base` as an approximation). Past those it returns a
  too-large error rather than cropping.
- Builds the same `content_part` the inline path uses, and makes a one-shot
  litellm call: a document-analyzer system prompt plus
  `File: "<name>" / Request: <request>` and the file itself.
- Returns the reader's answer as the tool result (cost tracked), with call /
  result cards rendered from `render_data`.

The main agent's prompt tells it: a `[Attached file ...]` note means the file
is available but not shown — query it, never guess its contents.

## 5. Aging out

Inline budgets are spent **newest-message-first**: `attachments_for_llm` walks
the history in reverse, so the most recent attachments claim the budget and
older ones degrade to stubs.

Every non-inlined attachment becomes a text stub (`attachment_stub`) naming
the file, type, size, and `upload_id`, plus the reason:

- **Aged out** — "attached earlier and no longer inlined; use the
  query_document tool to re-read it."
- **Too large** — "too large to include inline; use the query_document tool."
- **Unreadable type** — "this file type can't be read by the current model."
- **Deleted** — "no longer available."

So a thread can accumulate any number of attachments: recent ones are in
context verbatim, and everything else remains reachable on demand through
`query_document`.
