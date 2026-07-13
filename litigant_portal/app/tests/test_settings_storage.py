"""Storage backend selection is gated by USE_S3, not DEBUG directly.

A non-debug deploy without S3 credentials (the self-contained DigitalOcean QA
box) must be able to run on local filesystem storage. These tests pin that
contract and the back-compatible default (S3 whenever DEBUG is off, filesystem
otherwise) by reloading the settings module under a controlled environment.
"""

import importlib
import os
from unittest import mock

FILESYSTEM = "django.core.files.storage.FileSystemStorage"
S3 = "storages.backends.s3.S3Storage"


def _storage_backends(env: dict[str, str]) -> dict:
    """Reload settings with exactly ``env`` set and return the resolved
    USE_S3 flag and the `default`/`public` storage backends. Restores the
    module to the ambient environment afterward so other tests are unaffected.
    """
    import litigant_portal.settings as settings_module

    with mock.patch.dict(os.environ, env, clear=True):
        importlib.reload(settings_module)
        result = {
            "use_s3": settings_module.USE_S3,
            "default": settings_module.STORAGES["default"]["BACKEND"],
            "public": settings_module.STORAGES["public"]["BACKEND"],
        }
    # Reload once more under the real environment to undo the patched reload.
    importlib.reload(settings_module)
    return result


def test_use_s3_false_forces_filesystem_even_when_not_debug():
    """The DO QA case: DEBUG off but USE_S3=false → filesystem, no S3."""
    result = _storage_backends({"DEBUG": "false", "USE_S3": "false"})
    assert result["use_s3"] is False
    assert result["default"] == FILESYSTEM
    assert result["public"] == FILESYSTEM


def test_default_is_s3_when_not_debug_and_flag_unset():
    """AWS/EKS behavior preserved: DEBUG off, USE_S3 unset → S3."""
    result = _storage_backends({"DEBUG": "false"})
    assert result["use_s3"] is True
    assert result["default"] == S3
    assert result["public"] == S3


def test_default_is_filesystem_when_debug_and_flag_unset():
    """Dev behavior preserved: DEBUG on, USE_S3 unset → filesystem."""
    result = _storage_backends({"DEBUG": "true"})
    assert result["use_s3"] is False
    assert result["default"] == FILESYSTEM
    assert result["public"] == FILESYSTEM


def test_use_s3_true_forces_s3_even_when_debug():
    """Explicit opt-in overrides the DEBUG-derived default."""
    result = _storage_backends({"DEBUG": "true", "USE_S3": "true"})
    assert result["use_s3"] is True
    assert result["default"] == S3
    assert result["public"] == S3
