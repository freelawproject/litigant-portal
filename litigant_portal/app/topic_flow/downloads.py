"""Download dispatch for Topic Flow output sections.

The seam that parallels ``renderer.py``'s ``SECTION_RENDERERS``: a downloadable
output ``output_type`` registers a handler that turns its section + the user's
answers into file bytes — a ``DownloadArtifact`` (content type, filename,
body). The view resolves the output section by id and calls ``build_download``;
an output_type with no registered handler (``summary``/``packet`` — on-page
only) is simply not downloadable, surfaced as a 404 by the view.

This keeps the download path open-ended *by design* (#441's "design the
download path before the first generator lands"): a new file type — ``.vcf``
(#473) and beyond — slots in as one ``@download_handler`` registration, with no
new URL or view code. Generation lives in ``artifacts.py`` and resolution /
date math in ``deadlines.py``; this module only wires ``output_type`` to *how
to assemble the file*.
"""

from dataclasses import dataclass

from litigant_portal.app.topic_flow.artifacts import deadlines_to_ics
from litigant_portal.app.topic_flow.deadlines import resolve_ics_deadlines


@dataclass(frozen=True)
class DownloadArtifact:
    filename: str
    content_type: str
    body: str


# output_type -> handler(section, corpus, answers) -> DownloadArtifact
DOWNLOAD_HANDLERS = {}


def download_handler(output_type):
    """Register a download handler under its output_type. Used as a decorator."""

    def register(fn):
        DOWNLOAD_HANDLERS[output_type] = fn
        return fn

    return register


def find_downloadable(corpus, output_id):
    """Return the downloadable output section with ``output_id``, or ``None``.

    ``None`` covers both an unknown id and a section whose output_type has no
    download handler (info / fact_gather / summary / packet) — the view turns
    either into a 404, so a stray ``/download/overview/`` can't 500.
    """
    for section in corpus.sections:
        if (
            section.id == output_id
            and getattr(section, "output_type", None) in DOWNLOAD_HANDLERS
        ):
            return section
    return None


def build_download(section, corpus, answers):
    """Assemble the ``DownloadArtifact`` for a downloadable output section.

    Callers resolve the section via ``find_downloadable`` first, so the handler
    is guaranteed present here.
    """
    handler = DOWNLOAD_HANDLERS[section.output_type]
    return handler(section, corpus, answers)


@download_handler("ics")
def _build_ics(section, corpus, answers):
    """An ``ics`` output section's computed deadlines → a ``.ics`` calendar.

    Only deadlines with a computable date become events — an unanswered date
    question yields no event (the "enter your dates first" state), so an
    all-pending section downloads an empty but valid calendar. The per-deadline
    ``UID`` is stable across re-downloads (keyed by the flow + section + deadline
    ids) so a calendar app updates the event instead of duplicating it.
    """
    meta = corpus.metadata
    events = []
    for resolved in resolve_ics_deadlines(section, corpus, answers):
        if resolved["date"] is None:
            continue
        uid = (
            f"{meta.court}-{meta.topic}-{meta.role}-"
            f"{section.id}-{resolved['id']}@litigantportal.com"
        )
        events.append(
            {
                "uid": uid,
                "summary": resolved["label"],
                "description": resolved["description"],
                "date": resolved["date"],
            }
        )
    return DownloadArtifact(
        filename=f"{section.id}.ics",
        content_type="text/calendar",
        body=deadlines_to_ics(events),
    )
