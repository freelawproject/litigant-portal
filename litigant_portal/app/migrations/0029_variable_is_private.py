from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0028_contact_address_hours"),
    ]

    operations = [
        migrations.AddField(
            model_name="variable",
            name="is_private",
            field=models.BooleanField(default=False),
        ),
    ]
