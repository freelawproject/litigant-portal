# Hand-written: Site becomes a singleton (#731). makemigrations produces the
# schema operations but not the two data steps between them, and without
# those `migrate` aborts — an environment carrying more than one Site row, or
# one row whose id is not SITE_ID, fails validating the new check constraint.
# seed_data mints a random uuid4 on every fresh startup, so every existing
# environment is in that state.

import uuid

from django.db import migrations, models

SITE_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _prune_extra_sites(apps, schema_editor):
    """Keep one site — the active one, falling back to the oldest — and
    cascade-delete the rest with their scoped topics.

    Runs while ``active`` still exists, so before it is removed below.
    """
    Site = apps.get_model("app", "Site")
    sites = Site.objects.using(schema_editor.connection.alias)
    keeper = (
        sites.filter(active=True).first()
        or sites.order_by("created_at").first()
    )
    if keeper is None:
        return
    deleted, _ = sites.exclude(pk=keeper.pk).delete()
    # The cascade queues deferred FK trigger events on app_site, and Postgres
    # refuses to ALTER a table with those pending — which a later operation
    # does. Flush them inside this transaction.
    if deleted and schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("SET CONSTRAINTS ALL IMMEDIATE")


def _pin_site_pk(apps, schema_editor):
    """Move the surviving row onto the fixed singleton id.

    Ordering is load-bearing: this runs after ``Topic.site`` is dropped,
    otherwise the update trips that foreign key.
    """
    Site = apps.get_model("app", "Site")
    Site.objects.using(schema_editor.connection.alias).update(id=SITE_ID)


def _ensure_site_row(apps, schema_editor):
    """Create the singleton row if the database has none.

    The post_migrate receiver does this too, but a migration that runs with
    ``run_syncdb`` disabled or inside a test fixture may not fire it, and
    every read assumes the row exists.
    """
    Site = apps.get_model("app", "Site")
    sites = Site.objects.using(schema_editor.connection.alias)
    if not sites.exists():
        sites.create(id=SITE_ID)


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0011_site_permissions_delete_sitemembership'),
    ]

    operations = [
        # 1. Collapse to one row while `active` is still available to pick it.
        migrations.RunPython(
            _prune_extra_sites, migrations.RunPython.noop, elidable=True
        ),
        # 2. Drop the per-site scoping.
        migrations.RemoveConstraint(
            model_name='topic',
            name='unique_site_topic_slug',
        ),
        migrations.RemoveField(
            model_name='topic',
            name='site',
        ),
        migrations.AlterField(
            model_name='topic',
            name='slug',
            field=models.SlugField(max_length=64, unique=True),
        ),
        # 3. Drop the multi-site fields.
        migrations.RemoveConstraint(
            model_name='site',
            name='unique_active_site',
        ),
        migrations.RemoveField(
            model_name='site',
            name='active',
        ),
        migrations.RemoveField(
            model_name='site',
            name='name',
        ),
        # 4. Pin the survivor onto the fixed id, then enforce it.
        migrations.RunPython(
            _pin_site_pk, migrations.RunPython.noop, elidable=True
        ),
        migrations.AlterField(
            model_name='site',
            name='id',
            field=models.UUIDField(
                default=uuid.UUID('00000000-0000-0000-0000-000000000001'),
                editable=False,
                primary_key=True,
                serialize=False,
            ),
        ),
        migrations.AddConstraint(
            model_name='site',
            constraint=models.CheckConstraint(
                condition=models.Q(('id', SITE_ID)), name='single_site_row'
            ),
        ),
        migrations.RunPython(
            _ensure_site_row, migrations.RunPython.noop, elidable=True
        ),
    ]
