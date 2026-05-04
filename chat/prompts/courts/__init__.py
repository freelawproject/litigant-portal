"""Court prompts — jurisdictional content: forms, fees, clerk contacts, branding.

Each `<slug>.md` file holds the jurisdiction-specific content for a court
(and where relevant, topic + court combinations). Markdown lets non-engineer
contributors edit corpus content via PR. The composing loader lives at
`chat.prompts.build_system_prompt`. This is the layer courts will eventually
self-serve via court-configurable schemas (see #197).

When RAG over court corpus or court-configurable data sources land, this
layer shrinks to branding and conventions; content comes from the data
layer.
"""
