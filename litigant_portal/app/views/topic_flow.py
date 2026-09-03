from django.http import Http404, HttpResponse

from litigant_portal.app.topic_flow.downloads import (
    build_download,
    find_downloadable,
)
from litigant_portal.app.topic_flow.registry import registry
from litigant_portal.app.views.utils import topic_flow_answers


def topic_flow_download(request, court, topic, role, output_id):
    """Download a Topic Flow output section as a file (e.g. an ``.ics``).

    The endpoint counterpart to the ``pages.topic_flow`` render: resolve the
    corpus and the downloadable output section (404 on either miss — an
    unknown id or a non-downloadable section), then dispatch on
    ``output_type`` to assemble the file from the visitor's stored answers.
    The view stays thin — file bytes come from the download handlers in
    downloads.py, computed from the same stored answers the page renders, so
    the download matches what's on screen.
    """
    corpus = registry.get(court, topic, role)
    if corpus is None:
        raise Http404(f"No Topic Flow for {court}/{topic}/{role}")

    section = find_downloadable(corpus, output_id)
    if section is None:
        raise Http404(f"No downloadable output {output_id!r}")

    artifact = build_download(
        section, corpus, topic_flow_answers(request, corpus)
    )
    response = HttpResponse(artifact.body, content_type=artifact.content_type)
    response["Content-Disposition"] = (
        f'attachment; filename="{artifact.filename}"'
    )
    return response
