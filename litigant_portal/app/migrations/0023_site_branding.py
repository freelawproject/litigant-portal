from django.db import migrations, models

import litigant_portal.app.models.site


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0022_municipal_jurisdiction_level"),
    ]

    operations = [
        migrations.AddField(
            model_name="site",
            name="branding_name",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="site",
            name="logo",
            field=models.FileField(
                blank=True,
                storage=litigant_portal.app.models.site._public_storage,
                upload_to="branding/",
            ),
        ),
        migrations.AddField(
            model_name="site",
            name="name_image",
            field=models.FileField(
                blank=True,
                storage=litigant_portal.app.models.site._public_storage,
                upload_to="branding/",
            ),
        ),
    ]
