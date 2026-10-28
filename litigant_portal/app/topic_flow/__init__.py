"""Topic Flow — the AI-free guided page engine.

Builds the page at /t/{court}/{topic}/{role}/ from the TopicFlow rows
``sync_corpus`` writes (``rows.py``), plus the pure helpers behind it: the
download files (``downloads.py``, ``artifacts.py``), deadline math
(``deadlines.py``), contact and resource flattening (``contacts.py``,
``resources.py``) and the docassemble prefill mapping (``prefill.py``).
Nothing here calls an LLM. See issue #389 for the epic.
"""
