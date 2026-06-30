from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0003_alter_useridentity_options_useridentity_updated_at_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="chatthread",
            name="state",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
