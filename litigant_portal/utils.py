import os

import django


def init_django():
    """Initializes Django."""
    os.environ["DJANGO_SETTINGS_MODULE"] = "litigant_portal.settings"
    django.setup()
