# Hand-written. Aligns the flow models with the reviewed shape on main
# (PR #786): TopicFlow gains an admin-orderable ``order``; TopicFlowField
# gains a denormalized ``flow`` FK (backfilled from its group) so field
# names can be unique per flow, and loses the per-group order constraint —
# order is a display hint the move services renumber, not an invariant.

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import OuterRef, Subquery


def backfill_field_flow(apps, schema_editor):
    """Point every field at its group's flow."""
    field_model = apps.get_model("app", "TopicFlowField")
    group_model = apps.get_model("app", "TopicFlowFieldGroup")
    field_model.objects.update(
        flow_id=Subquery(
            group_model.objects.filter(pk=OuterRef("group_id")).values(
                "flow_id"
            )[:1]
        )
    )


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0012_simulateduser"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="topicflow",
            options={"ordering": ["order", "created_at"]},
        ),
        migrations.AddField(
            model_name="topicflow",
            name="order",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="topicflowfield",
            name="flow",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="fields",
                to="app.topicflow",
            ),
        ),
        migrations.RunPython(
            backfill_field_flow, migrations.RunPython.noop
        ),
        migrations.AlterField(
            model_name="topicflowfield",
            name="flow",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="fields",
                to="app.topicflow",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="topicflowfield",
            name="unique_group_field_order",
        ),
        migrations.AddConstraint(
            model_name="topicflowfield",
            constraint=models.UniqueConstraint(
                fields=("flow", "name"), name="unique_topic_flow_field_name"
            ),
        ),
    ]
