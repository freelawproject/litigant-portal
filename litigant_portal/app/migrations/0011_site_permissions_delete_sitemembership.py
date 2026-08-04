from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0010_remove_actionitemmodel_case_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='site',
            options={'permissions': [('manage_site', 'Can manage the site'), ('manage_developers', 'Can manage developer access')]},
        ),
        migrations.RemoveConstraint(
            model_name='sitemembership',
            name='unique_site_membership',
        ),
        migrations.DeleteModel(
            name='SiteMembership',
        ),
    ]
