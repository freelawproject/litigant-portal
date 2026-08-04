from django.apps import AppConfig as DjangoAppConfig
from django.db.models.signals import post_migrate


class AppConfig(DjangoAppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "litigant_portal.app"

    def ready(self):
        import litigant_portal.app.checks  # noqa: F401
        import litigant_portal.app.topic_flow.checks  # noqa: F401
        from litigant_portal.app import signals

        post_migrate.connect(signals.ensure_permission_groups, sender=self)
