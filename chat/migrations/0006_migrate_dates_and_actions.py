"""Move key_dates and action_items from CaseInfo.data JSON to Deadline and
ActionItemModel rows. Strips both keys from CaseInfo.data after migration.

Reversible: backward migration reads from models back into JSON, then deletes
the rows.
"""

import uuid

from django.db import migrations


def migrate_forward(apps, schema_editor):
    CaseInfo = apps.get_model("chat", "CaseInfo")
    Deadline = apps.get_model("chat", "Deadline")
    ActionItemModel = apps.get_model("chat", "ActionItemModel")

    for case in CaseInfo.objects.exclude(data={}):
        for d in case.data.get("key_dates", []):
            Deadline.objects.create(
                id=uuid.uuid4(),
                case=case,
                label=d.get("label", ""),
                date=d.get("date", ""),
                is_deadline=d.get("is_deadline", False),
            )

        for item in case.data.get("action_items", []):
            ActionItemModel.objects.create(
                id=uuid.uuid4(),
                case=case,
                title=item.get("title", ""),
                description=item.get("description", ""),
                priority=item.get("priority", "normal"),
                deadline=item.get("deadline") or "",
                href=item.get("href") or "",
            )

        new_data = {
            k: v
            for k, v in case.data.items()
            if k not in ("key_dates", "action_items")
        }
        if new_data != case.data:
            case.data = new_data
            case.save(update_fields=["data"])


def migrate_backward(apps, schema_editor):
    CaseInfo = apps.get_model("chat", "CaseInfo")
    Deadline = apps.get_model("chat", "Deadline")
    ActionItemModel = apps.get_model("chat", "ActionItemModel")

    for case in CaseInfo.objects.all():
        key_dates = [
            {
                "label": d.label,
                "date": d.date,
                "is_deadline": d.is_deadline,
            }
            for d in Deadline.objects.filter(case=case)
        ]
        action_items = [
            {
                k: v
                for k, v in {
                    "title": i.title,
                    "description": i.description,
                    "priority": i.priority,
                    "deadline": i.deadline or None,
                    "href": i.href or None,
                }.items()
                if v is not None
            }
            for i in ActionItemModel.objects.filter(case=case)
        ]

        new_data = dict(case.data)
        if key_dates:
            new_data["key_dates"] = key_dates
        if action_items:
            new_data["action_items"] = action_items
        case.data = new_data
        case.save(update_fields=["data"])

    Deadline.objects.all().delete()
    ActionItemModel.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("chat", "0005_deadline_actionitem")]
    operations = [migrations.RunPython(migrate_forward, migrate_backward)]
