"""Topic prompts — topic-specific legal framing, court-agnostic.

Each topic lives in its own directory: `<slug>/prompt.md` holds the legal
concepts, track forks, domain vocabulary, and conversation framing for a
single topic (eviction, adult_name_change, etc.). Markdown lets
non-engineer contributors edit corpus content via PR. The composing loader
lives at `chat.prompts.build_system_prompt`. Topic prompts are reusable
across courts: when a second jurisdiction adopts the same topic, the Topic
prompt stays; only the Court prompt changes.

`<slug>/topic.json` carries structural identity for the topic — display
name and icon today (validated at app startup via `chat.checks`). The
schema is intentionally minimal in v1; translatable copy (subtitle,
description, prompts, context_sections) stays in `portal/views.py:TOPICS`
where `makemessages` can extract `gettext_lazy` strings. Full consolidation
of TOPICS into topic.json is tracked as a follow-up to #372 once the
i18n-for-JSON pattern is decided.

When RAG over topic corpus lands, the Topic prompt shrinks to framing
only; factual content is retrieved dynamically.
"""
