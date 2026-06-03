"""Session-backed store for fact_gather answers, namespaced per flow.

A deliberately dumb key-value bag over ``request.session``: it holds the raw
string answers a guest submits for one ``(court, topic, role)`` Topic Flow,
keyed by question id. It knows nothing about the corpus, question types, or
validation — parsing (e.g. a date) lives in the deadline layer, and data
validity is guaranteed upstream at corpus load. Guest-first: no DB model, no
login.

All answers live under one top-level session key, with each flow namespaced by
a flat composite string (``court/topic/role``) so one guest can hold answers
for more than one flow without collision. The composite key is a string (not a
tuple) because the session is JSON-serialized.
"""


class AnswerStore:
    SESSION_KEY = "topic_flow"

    def __init__(self, session, court, topic, role):
        self._session = session
        self._flow_key = f"{court}/{topic}/{role}"

    def get(self, question_id):
        """Return the raw answer for ``question_id``, or None if unanswered."""
        return self.all().get(question_id)

    def all(self):
        """Return a copy of this flow's answers (empty dict if none)."""
        flows = self._session.get(self.SESSION_KEY, {})
        return dict(flows.get(self._flow_key, {}))

    def set(self, question_id, value):
        """Store a single answer."""
        self.update({question_id: value})

    def update(self, answers):
        """Merge ``answers`` into this flow (last-write-wins per question id)."""
        flows = dict(self._session.get(self.SESSION_KEY, {}))
        flow = dict(flows.get(self._flow_key, {}))
        flow.update(answers)
        flows[self._flow_key] = flow
        self._save(flows)

    def clear(self):
        """Drop this flow's answers, leaving any other flows untouched."""
        flows = dict(self._session.get(self.SESSION_KEY, {}))
        flows.pop(self._flow_key, None)
        self._save(flows)

    def _save(self, flows):
        # Reassigning the top-level key triggers SessionBase.__setitem__ (which
        # sets ``modified``); we also set it explicitly, since Django never sees
        # the in-place nested-dict edits this store makes.
        self._session[self.SESSION_KEY] = flows
        self._session.modified = True
