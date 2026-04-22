"""Topic prompts — topic-specific legal framing, court-agnostic.

Each file exports a PROMPT string that holds the legal concepts, track
forks, domain vocabulary, and conversation framing for a single topic
(eviction, adult_name_change, etc.). Topic prompts are reusable across
courts: when a second jurisdiction adopts the same topic, the Topic prompt
stays; only the Court prompt changes.

When RAG over topic corpus lands, the Topic prompt shrinks to framing
only; factual content is retrieved dynamically.
"""
