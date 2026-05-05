"""Topic prompts — topic-specific legal framing, court-agnostic.

Each topic lives in its own directory: `<slug>/prompt.md` holds the legal
concepts, track forks, domain vocabulary, and conversation framing for a
single topic (eviction, adult_name_change, etc.). Markdown lets
non-engineer contributors edit corpus content via PR. The composing loader
lives at `chat.prompts.build_system_prompt`. Topic prompts are reusable
across courts: when a second jurisdiction adopts the same topic, the Topic
prompt stays; only the Court prompt changes.

A `<slug>/topic.json` for card display data (title, subtitle, prompts,
context_sections currently in `portal/views.py:TOPICS`) lands with #363.

When RAG over topic corpus lands, the Topic prompt shrinks to framing
only; factual content is retrieved dynamically.
"""
