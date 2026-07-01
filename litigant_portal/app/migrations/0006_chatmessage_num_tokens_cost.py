from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0005_chatmessage_hidden"),
    ]

    operations = [
        migrations.AddField(
            model_name="chatmessage",
            name="num_tokens",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="chatmessage",
            name="cost",
            field=models.FloatField(default=0.0),
        ),
    ]
