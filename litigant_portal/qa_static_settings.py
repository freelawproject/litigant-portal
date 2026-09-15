"""
Temporary QA collection settings: preserve all assets without loading app models.
"""

from importlib.util import find_spec
from pathlib import Path

from . import settings as _application_settings
from .settings import *  # noqa: F403

# Keep finder precedence and the application's S3 storage and manifest behavior.
STATICFILES_DIRS = list(_application_settings.STATICFILES_DIRS)
for _app in _application_settings.INSTALLED_APPS:
    _spec = find_spec(_app)
    for _location in _spec.submodule_search_locations or ():
        _directory = Path(_location) / "static"
        if _directory.is_dir():
            STATICFILES_DIRS.append(_directory)

INSTALLED_APPS = ["django.contrib.staticfiles"]
