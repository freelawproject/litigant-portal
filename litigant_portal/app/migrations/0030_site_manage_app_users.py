from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0029_variable_is_private"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="site",
            options={
                "permissions": [
                    ("manage_site", "Can manage the site"),
                    ("manage_developers", "Can manage developer access"),
                    ("manage_app_users", "Can manage the app users' accounts"),
                ]
            },
        ),
    ]
