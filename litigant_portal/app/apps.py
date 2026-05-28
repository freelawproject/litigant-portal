from django.apps import AppConfig as DjangoAppConfig


class AppConfig(DjangoAppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "litigant_portal.app"

    def ready(self):
        import litigant_portal.app.checks  # noqa: F401
        import litigant_portal.app.signals  # noqa: F401
        import litigant_portal.app.topic_flow.checks  # noqa: F401
