import os
import tempfile
from unittest import mock

from django.test import TestCase

from config.settings import _read_secret


class ReadSecretTests(TestCase):
    """Tests for the _read_secret() helper."""

    def test_plain_env_var(self):
        """Falls back to plain env var when no _FILE is set."""
        with mock.patch.dict(
            os.environ, {"MY_SECRET": "plain-value"}, clear=False
        ):
            self.assertEqual(_read_secret("MY_SECRET"), "plain-value")

    def test_file_based(self):
        """Reads secret from file when _FILE is set."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as f:
            f.write("file-secret\n")
            f.flush()
            try:
                with mock.patch.dict(
                    os.environ,
                    {"MY_SECRET_FILE": f.name},
                    clear=False,
                ):
                    self.assertEqual(_read_secret("MY_SECRET"), "file-secret")
            finally:
                os.unlink(f.name)

    def test_file_takes_precedence_over_env_var(self):
        """When both _FILE and plain var exist, file wins."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as f:
            f.write("from-file")
            f.flush()
            try:
                with mock.patch.dict(
                    os.environ,
                    {
                        "MY_SECRET_FILE": f.name,
                        "MY_SECRET": "from-env",
                    },
                    clear=False,
                ):
                    self.assertEqual(_read_secret("MY_SECRET"), "from-file")
            finally:
                os.unlink(f.name)

    def test_nonexistent_file_falls_back_to_env_var(self):
        """Missing file falls back to env var."""
        with mock.patch.dict(
            os.environ,
            {
                "MY_SECRET_FILE": "/nonexistent/path.txt",
                "MY_SECRET": "fallback",
            },
            clear=False,
        ):
            self.assertEqual(_read_secret("MY_SECRET"), "fallback")

    def test_neither_set_returns_none(self):
        """Returns None when neither _FILE nor plain var is set."""
        env = os.environ.copy()
        env.pop("MY_SECRET", None)
        env.pop("MY_SECRET_FILE", None)
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertIsNone(_read_secret("MY_SECRET"))
