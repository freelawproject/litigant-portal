from django.db import migrations, models


class Migration(migrations.Migration):
    """Add ``municipal`` to the jurisdiction-level roster.

    Scottsdale City Court is a municipal (city) court, and the roster had no
    level that fits one — the nearest options all misstate which government
    the court belongs to. Municipal courts handle the bulk of civil traffic,
    which is the topic that surfaced the gap.

    Choices-only, so no stored value changes and nothing needs backfilling:
    this widens what is accepted rather than narrowing it, unlike 0018.
    """

    dependencies = [
        ("app", "0018_bedrock_model_choices"),
    ]

    operations = [
        migrations.AlterField(
            model_name="site",
            name="jurisdiction_level",
            field=models.CharField(
                blank=True,
                choices=[
                    ("state", "State"),
                    ("county", "County"),
                    ("district", "District"),
                    ("municipal", "Municipal"),
                    ("federal", "Federal"),
                    ("tribal", "Tribal"),
                ],
                max_length=16,
            ),
        ),
    ]
