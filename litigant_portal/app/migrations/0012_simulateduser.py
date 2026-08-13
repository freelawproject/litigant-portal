import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0011_contact_resource_topicflow_topicflowanswer_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="SimulatedUser",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("story", models.TextField(blank=True)),
                (
                    "identity",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="simulated_user",
                        to="app.useridentity",
                    ),
                ),
            ],
            options={
                "ordering": ["created_at"],
            },
        ),
    ]
