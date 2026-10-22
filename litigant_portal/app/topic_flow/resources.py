"""Flatten a resources section's links — pure, DB-free.

The twin of ``contacts.contact_dicts``: the one shape the content renderer
and the rows path (``rows.py``) both bind to the resources template.
"""

_FIELDS = ("label", "url", "note")


def resource_dicts(resources, *, id_attr="id"):
    """One flat ``{id, label, url, note}`` per resource, in the given order.
    ``id_attr`` names the attribute that becomes ``id``: ``id`` on a corpus
    resource, ``ref`` on a ``Resource`` row."""
    return [
        {
            "id": getattr(resource, id_attr),
            **{field: getattr(resource, field) for field in _FIELDS},
        }
        for resource in resources
    ]
