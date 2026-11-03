"""Tiered admin roles (#1135).

Admins becomes FLP Staff and User admins becomes Court Admins, renamed in
place so membership carries over. Developers folds into FLP Staff: it only
added the chat readouts and promoting developers, and FLP Staff now hold
the readouts. ``ensure_permission_groups`` tops up each group's permissions
after migrate, as it always has.
"""

from django.db import migrations

RENAMES = [("Admins", "FLP Staff"), ("User admins", "Court Admins")]
FOLDED = "Developers"


def _move_members(source, target):
    target.user_set.add(*source.user_set.all())
    source.delete()


def forwards(apps, schema_editor):
    group_model = apps.get_model("auth", "Group")
    for old, new in RENAMES:
        source = group_model.objects.filter(name=old).first()
        if source is None:
            continue
        target = group_model.objects.filter(name=new).first()
        if target is None:
            source.name = new
            source.save(update_fields=["name"])
        else:
            _move_members(source, target)
    developers = group_model.objects.filter(name=FOLDED).first()
    if developers is not None:
        staff, _ = group_model.objects.get_or_create(name="FLP Staff")
        _move_members(developers, staff)
    # Django never deletes a permission dropped from Meta.permissions.
    apps.get_model("auth", "Permission").objects.filter(
        content_type__app_label="app", codename="manage_developers"
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0036_bedrock_model_choices"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="site",
            options={
                "permissions": [
                    ("manage_site", "Can manage the site"),
                    ("manage_app_users", "Can manage the app users' accounts"),
                ]
            },
        ),
        # Reversing leaves the new names: the old groups meant something
        # different, and their members would need sorting by hand anyway.
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
