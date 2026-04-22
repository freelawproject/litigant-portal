"""Court prompts — jurisdictional content: forms, fees, clerk contacts, branding.

Each file exports a PROMPT string that holds the jurisdiction-specific
content for a court (and where relevant, topic + court combinations). This
is the layer courts will eventually self-serve via court-configurable
schemas (see #197).

When RAG over court corpus or court-configurable data sources land, this
prompt shrinks to branding and conventions; content comes from the data
layer.
"""
