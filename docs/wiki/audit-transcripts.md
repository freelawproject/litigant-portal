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

For model-backed assistant messages with a captured prompt artifact, both downloads surface the instruction state used for that call: the rendered system prompt and tool-schema snapshot. The Markdown transcript renders the full prompt artifact immediately before its first use and again whenever the active artifact changes. The JSON download provides exact per-message references: each message's `prompt_artifact_id` points to an entry in the top-level `prompt_artifacts` collection containing the system prompt, tool schemas, and content hash. Each message also carries the deployed commit SHA (`git_sha` in JSON, or the `Deployed SHA` line(s) in Markdown), preserving the code version that produced it.

1. For a readable review, open the Markdown transcript. A `Prompt artifact` block appears immediately before its first referenced assistant message and again when a later non-null `prompt_artifact_id` changes. Null references do not reset the renderer's last-known artifact state. Each block includes the artifact ID, content hash, complete system prompt, and tool-schema snapshot.
2. For exact per-message linkage, open the JSON download and find the assistant message for the turn you need. If it has a `prompt_artifact_id`, find that ID in `prompt_artifacts`. Its `system_prompt` and `tool_schemas` are the values captured for that model call.
3. Use the message's `git_sha` when you also need the deployed code, or when a legacy message has no prompt artifact. Check it out with `git checkout <sha>`. Long conversations can span more than one SHA; Markdown flags each change and JSON records it per message.
4. A tool may run its own prompt against another model. Those tool-internal prompts are not captured by prompt artifacts. Currently the only one is the document-query tool, `litigant_portal/agents/tools/query_document.py` (`READER_SYSTEM_PROMPT`), which can be inspected at the recorded SHA.
5. Combine the captured system prompt, any separately reconstructed tool prompts, and the transcript to see what the AI was told and what it said.

A blank or `unknown` SHA means the message predates this feature (it shipped in #801), or ran in local dev where `GIT_SHA` isn't set.

**Known limit:** prompt artifacts cover the system prompt and tool schemas sent for model-backed assistant messages. They do not capture prompts used internally by tools. Legacy messages can have a null `prompt_artifact_id` and still require SHA-based reconstruction.

## Retention

Anonymous conversations are kept for at least **30 days** after their last activity (the `AUDIT_RETENTION_DAYS` setting). The `cleanup_sessions` job never deletes a conversation with activity inside that window. Conversations belonging to logged-in accounts are not deleted by the cleanup job at all. If you need a transcript preserved past the window, download it.

A spot-check has to happen inside that 30-day window, or the transcript has to be downloaded before it closes. Nothing warns you that a conversation is about to age out.

## Known limits

- **Users can delete their own conversations.** The delete button in the portal removes a thread and all its messages immediately and permanently, at any time. The retention window above only protects against the automatic cleanup job, not against the user's own delete. If a transcript matters, download it early. Changing this behavior (for example, hiding a deleted conversation from the user but keeping it for audit) is an open team decision, deliberately deferred.
- **Prompt artifacts are scoped to assistant model calls.** User, tool, hidden, meta, and legacy messages do not carry a prompt artifact. A null reference does not reset the Markdown renderer's last-known artifact state.
- **Unreferenced prompt artifacts are not collected yet.** Prompt artifacts are shared across messages and threads. Deleting the last message that references one currently leaves the artifact row in place; orphan cleanup remains separate retention work.
- **Session keys are lost at login.** If an anonymous user later logs in, their conversations move to their account and the old session key is discarded. The transcript survives; searching by the old session key will not find it, but searching by their email will.
- **The whole transcript loads at once.** The page renders every message, with no paging or cap, so a very long conversation makes for a slow page. Use the Markdown download instead if a thread is unwieldy on screen.
