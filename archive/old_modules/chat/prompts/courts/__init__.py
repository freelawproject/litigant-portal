"""Court prompts — jurisdictional content: forms, fees, clerk contacts, branding.

Each court lives in its own directory: `<slug>/court.json` holds the
court's identity (name today; address, contact, theme later) and
`<slug>/prompt.md` holds the corpus content. Markdown lets non-engineer
contributors edit corpus content via PR; JSON lets templates and chat
infrastructure read structured fields. The composing loader lives at
`chat.prompts.build_system_prompt`. This is the layer courts will
eventually self-serve via court-configurable schemas (see #197).

The directory layout matches the eventual wiki tree (#355) so when AI-team
ingestion + retrieval lands, today's `prompt.md` becomes the seed corpus
and `court.json` becomes the structured identity record.

When RAG over court corpus or court-configurable data sources land, this
layer shrinks to branding and conventions; content comes from the data
layer.
"""
