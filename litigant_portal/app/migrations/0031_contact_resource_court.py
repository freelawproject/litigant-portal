from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0030_site_manage_app_users"),
    ]

    operations = [
        migrations.AddField(
            model_name="contact",
            name="court",
            field=models.SlugField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="resource",
            name="court",
            field=models.SlugField(blank=True, default="", max_length=64),
        ),
    ]
