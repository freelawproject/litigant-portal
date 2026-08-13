# Pulling AI conversation transcripts (audit log)

Who this is for: FLP staff who need to review AI conversations, for the pilot spot-check or after an incident. No database access or developer help is needed once your account is set up.

## One-time setup

You need a portal account with **staff status**. A developer grants this once (in the Django admin, check "Staff status" on your user). After that, everything below is self-service.

## Pull a transcript

1. Go to `/django-admin/` on the portal and log in.
2. Click **Chat threads**. Every AI conversation on the site is listed here, newest first.
3. Find the conversation you need. You can:
   - **Search** by the user's email address, by session key (for anonymous users), by words in the thread description, or by pasting a full thread ID.
   - **Filter** by date or thread type using the sidebar.
4. Click the thread to open it. The page shows who the conversation belongs to, when it started, and the full transcript: user messages, AI answers, tool calls the AI made, and tool results. Rows marked `[hidden]` or `[meta]` were not visible to the user; they are included because an audit needs the complete record.
5. To save a copy, use the **Downloads** links on the same page:
   - **Markdown**: a readable transcript, good for review and sharing.
   - **JSON**: the raw record with timestamps, token counts, and cost, good for deeper analysis or archiving.

Everything is read-only. You cannot change or delete a conversation from this screen.

## Retention

Anonymous conversations are kept for at least **30 days** after their last activity (the `AUDIT_RETENTION_DAYS` setting). The `cleanup_sessions` job never deletes a conversation with activity inside that window. Conversations belonging to logged-in accounts are not deleted by the cleanup job at all. If you need a transcript preserved past the window, download it.

A spot-check has to happen inside that 30-day window, or the transcript has to be downloaded before it closes. Nothing warns you that a conversation is about to age out.

## Known limits

- **Users can delete their own conversations.** The delete button in the portal removes a thread and all its messages immediately and permanently, at any time. The retention window above only protects against the automatic cleanup job, not against the user's own delete. If a transcript matters, download it early. Changing this behavior (for example, hiding a deleted conversation from the user but keeping it for audit) is an open team decision, deliberately deferred.
- **The system prompt is not stored.** Transcripts show what the user and the AI said, but not the behind-the-scenes instructions the AI had at the time. Those instructions live in code and change with releases.
- **Session keys are lost at login.** If an anonymous user later logs in, their conversations move to their account and the old session key is discarded. The transcript survives; searching by the old session key will not find it, but searching by their email will.
- **The whole transcript loads at once.** The page renders every message, with no paging or cap, so a very long conversation makes for a slow page. Use the Markdown download instead if a thread is unwieldy on screen.
