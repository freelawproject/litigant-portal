from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0033_site_judge_model"),
    ]

    operations = [
        migrations.AddField(
            model_name="topicflowinterviewpage",
            name="on_page",
            field=models.BooleanField(default=False),
        ),
    ]
