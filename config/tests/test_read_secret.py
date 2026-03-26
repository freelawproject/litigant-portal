"""Tests for the _read_secret() helper in config/settings.py."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from config.settings import _read_secret


class ReadSecretTests(unittest.TestCase):
    """Verify _read_secret() precedence and edge cases."""

    def test_plain_env_var(self):
        """Falls back to the plain env var when no _FILE is set."""
        with mock.patch.dict(os.environ, {"MY_VAR": "from-env"}, clear=False):
            os.environ.pop("MY_VAR_FILE", None)
            self.assertEqual(_read_secret("MY_VAR"), "from-env")

    def test_file_based(self):
        """Reads the secret from a file when _FILE is set."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("  secret-from-file\n")
            f.flush()
            try:
                with mock.patch.dict(
                    os.environ, {"MY_VAR_FILE": f.name}, clear=False
                ):
                    os.environ.pop("MY_VAR", None)
                    self.assertEqual(_read_secret("MY_VAR"), "secret-from-file")
            finally:
                os.unlink(f.name)

    def test_file_takes_precedence_over_env_var(self):
        """When both _FILE and plain env var are set, file wins."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("file-value\n")
            f.flush()
            try:
                with mock.patch.dict(
                    os.environ,
                    {"MY_VAR_FILE": f.name, "MY_VAR": "env-value"},
                    clear=False,
                ):
                    self.assertEqual(_read_secret("MY_VAR"), "file-value")
            finally:
                os.unlink(f.name)

    def test_nonexistent_file_falls_back_to_env_var(self):
        """When _FILE points to a missing file, falls back to env var."""
        with mock.patch.dict(
            os.environ,
            {"MY_VAR_FILE": "/nonexistent/path.txt", "MY_VAR": "fallback"},
            clear=False,
        ):
            self.assertEqual(_read_secret("MY_VAR"), "fallback")

    def test_neither_set_returns_none(self):
        """Returns None when neither _FILE nor env var is set."""
        env = os.environ.copy()
        env.pop("MY_VAR", None)
        env.pop("MY_VAR_FILE", None)
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertIsNone(_read_secret("MY_VAR"))
