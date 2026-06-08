import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def create_identities_and_link(apps, schema_editor):
    """Populate UserIdentity rows and set identity FK on all existing rows."""
    UserIdentity = apps.get_model("app", "UserIdentity")
    ChatSession = apps.get_model("app", "ChatSession")
    CaseInfo = apps.get_model("app", "CaseInfo")

    identity_cache: dict = {}

    def get_identity(user_id, session_key):
        if user_id:
            key = ("user", user_id)
            if key not in identity_cache:
                identity, _ = UserIdentity.objects.get_or_create(user_id=user_id)
                identity_cache[key] = identity
        elif session_key:
            key = ("session", session_key)
            if key not in identity_cache:
                identity, _ = UserIdentity.objects.get_or_create(
                    user=None, session_key=session_key
                )
                identity_cache[key] = identity
        else:
            identity = UserIdentity.objects.create()
            key = ("orphan", identity.pk)
            identity_cache[key] = identity
        return identity_cache[key]

    for session in ChatSession.objects.all():
        session.identity = get_identity(session.user_id, session.session_key)
        session.save(update_fields=["identity"])

    for case in CaseInfo.objects.all():
        case.identity = get_identity(case.user_id, case.session_key)
        case.save(update_fields=["identity"])


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Create UserIdentity table
        migrations.CreateModel(
            name="UserIdentity",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "session_key",
                    models.CharField(blank=True, db_index=True, max_length=40),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="identity",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "User Identity",
                "verbose_name_plural": "User Identities",
            },
        ),
        # 2. Add nullable identity FK to ChatSession
        migrations.AddField(
            model_name="chatsession",
            name="identity",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="chat_sessions",
                to="app.useridentity",
            ),
        ),
        # 3. Add nullable identity FK to CaseInfo
        migrations.AddField(
            model_name="caseinfo",
            name="identity",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="case_infos",
                to="app.useridentity",
            ),
        ),
        # 4. Populate UserIdentity rows and link existing records
        migrations.RunPython(
            create_identities_and_link,
            reverse_code=migrations.RunPython.noop,
        ),
        # 5. Make identity non-nullable on ChatSession
        migrations.AlterField(
            model_name="chatsession",
            name="identity",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="chat_sessions",
                to="app.useridentity",
            ),
        ),
        # 6. Make identity non-nullable on CaseInfo
        migrations.AlterField(
            model_name="caseinfo",
            name="identity",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="case_infos",
                to="app.useridentity",
            ),
        ),
        # 7. Remove old indexes from ChatSession
        migrations.RemoveIndex(
            model_name="chatsession",
            name="app_chatses_user_id_13e404_idx",
        ),
        migrations.RemoveIndex(
            model_name="chatsession",
            name="app_chatses_session_cc7acd_idx",
        ),
        # 8. Remove old fields from ChatSession
        migrations.RemoveField(model_name="chatsession", name="user"),
        migrations.RemoveField(model_name="chatsession", name="session_key"),
        # 9. Remove old indexes from CaseInfo
        migrations.RemoveIndex(
            model_name="caseinfo",
            name="app_caseinf_user_id_2c1330_idx",
        ),
        migrations.RemoveIndex(
            model_name="caseinfo",
            name="app_caseinf_session_421804_idx",
        ),
        # 10. Remove old fields from CaseInfo
        migrations.RemoveField(model_name="caseinfo", name="user"),
        migrations.RemoveField(model_name="caseinfo", name="session_key"),
    ]
