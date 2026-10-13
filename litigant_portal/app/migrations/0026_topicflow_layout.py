from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0025_form_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="topicflow",
            name="layout",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
