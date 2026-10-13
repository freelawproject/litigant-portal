from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0024_contact_kind"),
    ]

    operations = [
        migrations.AddField(
            model_name="form",
            name="url",
            field=models.URLField(blank=True, max_length=500),
        ),
    ]
