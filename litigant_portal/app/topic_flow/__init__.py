"""Topic Flow — AI-free legal topic engine.

Loads court-authored YAML corpora into validated, typed objects (see
``schema.py`` / ``loader.py``) and indexes them by ``(court, topic, role)``
(``registry.py``). Nothing here calls an LLM. See issue #389 for the epic.
"""
