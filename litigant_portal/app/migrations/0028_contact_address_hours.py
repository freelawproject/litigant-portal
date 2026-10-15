from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0027_topicflow_handoff"),
    ]

    operations = [
        migrations.AddField(
            model_name="contact",
            name="address",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="contact",
            name="hours",
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
