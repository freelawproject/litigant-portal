from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0031_contact_resource_court"),
    ]

    operations = [
        migrations.AddField(
            model_name="topic",
            name="court",
            field=models.SlugField(blank=True, default="", max_length=64),
        ),
    ]
