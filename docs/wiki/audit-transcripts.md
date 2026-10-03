# Pulling AI conversation transcripts (audit log)

Who this is for: FLP staff who need to review AI conversations, for the pilot spot-check or after an incident. No database access or developer help is needed once your account is set up.

## One-time setup

You need a portal account with **staff status**. A developer grants this once (in the Django admin, check "Staff status" on your user). After that, everything below is self-service.

## Pull a transcript

1. Go to `/django-admin/` on the portal and log in.
2. Click **Chat threads**. Every AI conversation on the site is listed here, newest first.
3. Find the conversation you need. You can:
   - **Search** by the user's email address, by session key (for anonymous users), by words in the thread description, or by pasting a full thread ID. Session key search matches the whole key, even though only the first 8 characters are ever displayed (see [Session keys](#session-keys)).
   - **Filter** by date or thread type using the sidebar.
4. Click the thread to open it. The page shows who the conversation belongs to, when it started, and the full transcript: user messages, AI answers, tool calls the AI made, and tool results. Rows marked `[hidden]` or `[meta]` were not visible to the user; they are included because an audit needs the complete record.
5. To save a copy, use the **Downloads** links on the same page:
   - **Markdown**: a readable transcript, including captured instruction states on first use and whenever they change, good for review and sharing.
   - **JSON**: the raw record with timestamps, token counts, and cost, good for deeper analysis or archiving.

Everything is read-only. You cannot change or delete a conversation from this screen.

## Session keys

Anonymous visitors have no email address, so a conversation of theirs is labeled by session key: `anonymous (session k3f9ab21)`. **Only the first 8 characters are shown**, everywhere: the thread list, the thread page, the User identities list, and both downloads.

The reason is that a session key is the value of that visitor's browser cookie. While their session is still active, anyone holding the whole key could use it to take over the session, so a transcript you hand to court staff should not carry it.

What this means in practice:

- **Searching still works with the whole key.** If you already have a full session key, paste it into the search box and it will find the thread. Search matches the stored value, and the box echoes back what you typed, but the key is never printed in a thread listing or a download.
- **To tie several conversations to the same visitor, use the identity ID, not the shortened key.** The JSON download carries it as `owner.identity_id`. Matching identity IDs mean the same visitor. Matching 8-character keys are a hint, not proof.

## Reconstituting a conversation's prompts

The system prompt the model receives for an assistant message is stored in two parts, and both downloads surface both:

- **The shared part** is the prompt artifact: the instructions, court context, topic flow list, and tool-schema snapshot. It contains nothing about the person, so one artifact row is shared by every thread and identity that received the same text. The Markdown transcript renders the full artifact immediately before its first use and again whenever the active artifact changes. In JSON, each message's `prompt_artifact_id` points to an entry in the top-level `prompt_artifacts` collection with the system prompt, tool schemas, and content hash.
- **The identity part** is the section about the person, today the list of facts they have provided (name, date of birth, county, and so on). It is stored on the assistant message itself, not in the artifact, so it is deleted with the conversation. The Markdown transcript prints an `Identity prompt` block before an assistant message whenever its text changes from the last one printed, including a "None" marker when a later model call was made with no identity part (for example, after the user cleared their facts). In JSON, each message carries `identity_prompt` with `text` (the section exactly as sent) and `values` (each variable name mapped to the value as it appears in the text). Messages without one carry an empty object.

The exact prompt sent for a turn is the artifact's `system_prompt`, a blank line, then the message's `identity_prompt.text`. When the identity part is empty, the artifact text alone is the prompt.

Each message also carries the deployed commit SHA (`git_sha` in JSON, or the `Deployed SHA` line(s) in Markdown), preserving the code version that produced it.

1. For a readable review, open the Markdown transcript. A `Prompt artifact` block appears immediately before its first referenced assistant message and again when a later non-null `prompt_artifact_id` changes. Null references do not reset the renderer's last-known artifact state. Each block includes the artifact ID, content hash, complete system prompt, and tool-schema snapshot. An `Identity prompt` block appears before the first assistant message that has one and again whenever the text changes. Unlike the artifact rule, an assistant message that has a prompt artifact but no identity part does reset it: a `None` marker is printed, because on a model call an empty identity part means no facts were sent.
2. For exact per-message linkage, open the JSON download and find the assistant message for the turn you need. If it has a `prompt_artifact_id`, find that ID in `prompt_artifacts`. Its `system_prompt` and `tool_schemas` are the shared values captured for that model call. The message's own `identity_prompt.text` is the identity part for the same call.
3. Use the message's `git_sha` when you also need the deployed code, or when a legacy message has no prompt artifact. Check it out with `git checkout <sha>`. Long conversations can span more than one SHA; Markdown flags each change and JSON records it per message.
4. A tool may run its own prompt against another model. Those tool-internal prompts are not captured by prompt artifacts. Currently the only one is the document-query tool, `litigant_portal/agents/tools/query_document.py` (`READER_SYSTEM_PROMPT`), which can be inspected at the recorded SHA.
5. Combine the shared system prompt, the identity part, any separately reconstructed tool prompts, and the transcript to see what the AI was told and what it said.

A blank or `unknown` SHA means the message predates this feature (it shipped in #801), or ran in local dev where `GIT_SHA` isn't set.

**Known limit:** prompt artifacts cover the shared system prompt and tool schemas sent for model-backed assistant messages. They do not capture prompts used internally by tools. Legacy messages can have a null `prompt_artifact_id` and still require SHA-based reconstruction.

### Why the prompt is split (decided 2026-10-03, #958)

Until #958, the facts section was rendered into the one system prompt and so into the shared artifact table, which has no link to the person and is protected from deletion while any message references it. Personal values therefore outlived the conversation the user deleted, and every saved fact produced a new artifact row.

The decision: the audit need is the exact text sent, and it is met by keeping that text where the conversation's own lifetime already applies. The shared part stays in the artifact and holds nothing personal. The identity part lives on the assistant message, which is deleted with the thread, with the identity, and by the retention job. The audit keeps the exact prompt for as long as the transcript exists, which is the limit this document already states. Artifacts written before the split that contained the facts section were deleted by a data migration; their messages now show as legacy rows with no artifact reference.

The `values` map exists for a later step: redacting a transcript on user delete by replacing each value with its variable name, instead of erasing the transcript. That work is a separate issue and does not change anything described here.

## Retention

Anonymous conversations are kept for at least **30 days** after their last activity (the `AUDIT_RETENTION_DAYS` setting). The `cleanup_sessions` job never deletes a conversation with activity inside that window. Conversations belonging to logged-in accounts are not deleted by the cleanup job at all. If you need a transcript preserved past the window, download it.

The identity part of each prompt is stored on the message, so it falls under the same rule: it is gone when the conversation is gone, whether by the cleanup job or by the user's own delete. The shared prompt artifacts hold nothing personal and are not subject to this window.

A spot-check has to happen inside that 30-day window, or the transcript has to be downloaded before it closes. Nothing warns you that a conversation is about to age out.

## Known limits

- **Users can delete their own conversations.** The delete button in the portal removes a thread and all its messages immediately and permanently, at any time. The retention window above only protects against the automatic cleanup job, not against the user's own delete. If a transcript matters, download it early. Changing this behavior (for example, hiding a deleted conversation from the user but keeping it for audit) is an open team decision, deliberately deferred.
- **Prompt artifacts are scoped to assistant model calls.** User, tool, hidden, meta, and legacy messages do not carry a prompt artifact. A null reference does not reset the Markdown renderer's last-known artifact state.
- **The identity part lives and dies with the message.** It is stored only on the assistant message that used it. Once the conversation is deleted there is no other copy, so an audit of a deleted conversation can recover the shared prompt from the artifact but not the person's facts. Download early if that matters.
- **Unreferenced prompt artifacts are not collected yet.** Prompt artifacts are shared across messages and threads. Deleting the last message that references one currently leaves the artifact row in place; orphan cleanup remains separate retention work.
- **Session keys are lost at login.** If an anonymous user later logs in, their conversations move to their account and the old session key is discarded. The transcript survives; searching by the old session key will not find it, but searching by their email will.
- **The whole transcript loads at once.** The page renders every message, with no paging or cap, so a very long conversation makes for a slow page. Use the Markdown download instead if a thread is unwieldy on screen.
