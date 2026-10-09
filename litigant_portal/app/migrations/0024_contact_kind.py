from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0023_site_branding"),
    ]

    operations = [
        migrations.AddField(
            model_name="contact",
            name="kind",
            field=models.CharField(
                blank=True,
                choices=[
                    ("clerk", "Clerk"),
                    ("self_help", "Self Help"),
                    ("legal_aid", "Legal Aid"),
                    ("referral", "Referral"),
                ],
                max_length=16,
            ),
        ),
    ]
