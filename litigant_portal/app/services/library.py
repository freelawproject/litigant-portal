from pathlib import Path

from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Max

from litigant_portal.app.models import (
    Contact,
    Resource,
    Site,
    Topic,
    TopicFlow,
    TopicFlowDeadline,
    TopicFlowField,
    TopicFlowFieldGroup,
    TopicFlowForm,
    TopicFlowLink,
    TopicFlowSection,
)
from litigant_portal.app.models.choices import JurisdictionLevel, State
from litigant_portal.app.selectors.site import site_get
from litigant_portal.app.services.site import busts_site_cache
from litigant_portal.app.services.topic_flow import (
    busts_topic_list_cache,
    topic_flow_form_mappings_replace,
)


def _flow_replace_children(
    flow: TopicFlow,
    *,
    sections: list,
    field_groups: list,
    links: list,
    deadlines: list,
) -> None:
    """Replace a flow's sections/field groups/links/deadlines, in order.

    Sections and links replace wholesale. Field groups are the config's
    interview pages: groups are reused by position (extras created,
    surplus deleted) and fields upsert by name across the whole flow —
    an existing field keeps its id even when it moves to another group,
    so litigants' stored answers (which cascade-delete with their field)
    and deadline calendar UIDs survive a re-apply; fields absent from
    the config are deleted. Deadline rows carry ``offset_from`` as a
    field NAME; it resolves against the just-saved fields (a row naming
    an unknown field is dropped).
    """
    flow.sections.all().delete()
    flow.links.all().delete()
    TopicFlowSection.objects.bulk_create(
        TopicFlowSection(flow=flow, order=i, **row)
        for i, row in enumerate(sections)
    )
    TopicFlowLink.objects.bulk_create(
        TopicFlowLink(flow=flow, order=i, **row) for i, row in enumerate(links)
    )
    existing_fields = {}
    for field in flow.fields:
        existing_fields.setdefault(field.name, []).append(field)
    existing_groups = list(flow.field_groups.all())
    fields_by_name = {}
    field_ids = []
    for g_index, group_config in enumerate(field_groups):
        if g_index < len(existing_groups):
            group = existing_groups[g_index]
            group.title = group_config["title"]
            group.description = group_config["description"]
            group.order = g_index
            group.save(
                update_fields=["title", "description", "order", "updated_at"]
            )
        else:
            group = TopicFlowFieldGroup.objects.create(
                flow=flow,
                title=group_config["title"],
                description=group_config["description"],
                order=g_index,
            )
        for f_index, row in enumerate(group_config["fields"]):
            matches = existing_fields.get(row["name"]) or [TopicFlowField()]
            field = matches.pop(0)
            for name, value in {
                **row,
                "group": group,
                "order": f_index,
            }.items():
                setattr(field, name, value)
            field.save()
            fields_by_name[field.name] = field
            field_ids.append(field.id)
    # Drop fields the config no longer names, then the groups the config
    # no longer has — kept fields were already reassigned above, so a
    # surplus group's cascade can't take anything that should survive.
    TopicFlowField.objects.filter(group__flow=flow).exclude(
        id__in=field_ids
    ).delete()
    for group in existing_groups[len(field_groups) :]:
        group.delete()
    kept = [row for row in deadlines if row["offset_from"] in fields_by_name]
    existing_deadlines = {}
    for deadline in flow.deadlines.all():
        existing_deadlines.setdefault(deadline.label, []).append(deadline)
    deadline_ids = []
    for i, row in enumerate(kept):
        matches = existing_deadlines.get(row["label"]) or [
            TopicFlowDeadline(flow=flow)
        ]
        deadline = matches.pop(0)
        for name, value in {
            **row,
            "offset_from": fields_by_name[row["offset_from"]],
            "order": i,
        }.items():
            setattr(deadline, name, value)
        deadline.save()
        deadline_ids.append(deadline.id)
    flow.deadlines.exclude(id__in=deadline_ids).delete()


def _flow_forms_upsert(flow: TopicFlow, forms: list) -> None:
    """Upsert library form configs onto ``flow`` by slug: an existing form
    keeps its position and gets the library name/PDF, a new one is appended.
    Mappings replace wholesale; forms not in the config are left alone."""
    last = flow.forms.aggregate(m=Max("order"))["m"]
    next_order = 0 if last is None else last + 1
    for config in forms:
        form = flow.forms.filter(slug=config["slug"]).first()
        if form is None:
            form = TopicFlowForm(
                flow=flow, slug=config["slug"], order=next_order
            )
            next_order += 1
        form.name = config["name"]
        if form.file:
            form.file.delete(save=False)
        form.file.save(
            config["file"],
            ContentFile(Path(config["file_path"]).read_bytes()),
            save=False,
        )
        form.save()
        topic_flow_form_mappings_replace(form, config["mappings"])


def _topic_flow_apply(topic: Topic, config: dict) -> TopicFlow:
    """Upsert one library flow onto ``topic`` by slug: an existing flow is
    replaced with the library version, a new one is created."""
    valid_types = set(TopicFlowField.DataType.values)
    field_groups = [
        cleaned
        for group in config["field_groups"]
        if (
            cleaned := {
                **group,
                "fields": [
                    row
                    for row in group["fields"]
                    if row["data_type"] in valid_types
                ],
            }
        )["fields"]
    ]
    with transaction.atomic():
        flow = topic.flows.filter(slug=config["slug"]).first()
        if flow:
            flow.name = config["name"]
            flow.enabled = True
            flow.save(update_fields=["name", "enabled", "updated_at"])
        else:
            flow = TopicFlow.objects.create(
                topic=topic,
                slug=config["slug"],
                name=config["name"],
                enabled=True,
            )
        _flow_replace_children(
            flow,
            sections=config["sections"],
            field_groups=field_groups,
            links=config["links"],
            deadlines=config["deadlines"],
        )
        _flow_forms_upsert(flow, config["forms"])
    return flow


TOPIC_CONFIG_FIELDS = (
    "title",
    "subtitle",
    "description",
    "icon",
    "meta_description",
    "prompts",
)


def _topic_upsert_from_config(*, config: dict) -> Topic:
    """Get-or-create the config's topic by slug, overwriting its fields."""
    fields = {name: config[name] for name in TOPIC_CONFIG_FIELDS}
    topic = Topic.objects.filter(slug=config["slug"]).first()
    if topic:
        for name, value in fields.items():
            setattr(topic, name, value)
        topic.save(update_fields=[*fields, "updated_at"])
    else:
        last = Topic.objects.aggregate(m=Max("order"))["m"]
        topic = Topic.objects.create(
            slug=config["slug"],
            order=0 if last is None else last + 1,
            **fields,
        )
    return topic


@busts_topic_list_cache
def topic_library_apply(*, config: dict) -> Topic:
    """Apply a full topic library config: upsert the topic's fields and
    every one of its flows (by slug)."""
    with transaction.atomic():
        topic = _topic_upsert_from_config(config=config)
        for flow_config in config["flows"]:
            _topic_flow_apply(topic, flow_config)
    return topic


@busts_topic_list_cache
def topic_flow_library_apply(*, config: dict, flow_config: dict) -> TopicFlow:
    """Apply a single library flow: reuse its topic when it exists
    (leaving the topic's fields untouched), otherwise create it from the
    config."""
    with transaction.atomic():
        topic = Topic.objects.filter(slug=config["slug"]).first()
        if topic is None:
            topic = _topic_upsert_from_config(config=config)
        flow = _topic_flow_apply(topic, flow_config)
    return flow


@busts_site_cache
def court_library_apply(*, config: dict, prune: bool = False) -> Site:
    """Pre-populate the site from a court library config.

    Overwrites the site's court detail fields. Contacts/resources are
    upserted by name/label: a conflicting row is replaced with the library
    version (keeping its position), new rows are appended. With ``prune``,
    contacts/resources not named in the config are deleted first.
    """
    jurisdiction_level = config["jurisdiction_level"]
    if jurisdiction_level not in JurisdictionLevel.values:
        jurisdiction_level = ""
    state = config["state"]
    if state not in State.values:
        state = ""
    with transaction.atomic():
        site = site_get()
        site.court_name = config["court_name"]
        site.jurisdiction_level = jurisdiction_level
        site.state = state
        site.official_url = config["official_url"]
        site.official_resources_url = config["official_resources_url"]
        site.save(
            update_fields=[
                "court_name",
                "jurisdiction_level",
                "state",
                "official_url",
                "official_resources_url",
                "updated_at",
            ]
        )
        if prune:
            Contact.objects.exclude(
                name__in=[row["name"] for row in config["contacts"]]
            ).delete()
            Resource.objects.exclude(
                label__in=[row["label"] for row in config["resources"]]
            ).delete()
        last = Contact.objects.aggregate(m=Max("order"))["m"]
        next_order = 0 if last is None else last + 1
        for row in config["contacts"]:
            existing = Contact.objects.filter(name=row["name"]).first()
            if existing:
                for field in ("phone", "email", "url", "note"):
                    setattr(existing, field, row[field])
                existing.save(
                    update_fields=[
                        "phone",
                        "email",
                        "url",
                        "note",
                        "updated_at",
                    ]
                )
            else:
                Contact.objects.create(order=next_order, **row)
                next_order += 1
        last = Resource.objects.aggregate(m=Max("order"))["m"]
        next_order = 0 if last is None else last + 1
        for row in config["resources"]:
            existing = Resource.objects.filter(label=row["label"]).first()
            if existing:
                for field in ("url", "note"):
                    setattr(existing, field, row[field])
                existing.save(update_fields=["url", "note", "updated_at"])
            else:
                Resource.objects.create(order=next_order, **row)
                next_order += 1
    return site
