"""
Static collection must not load the model provider during Django startup.
"""

import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent


def test_collectstatic_does_not_import_litellm(tmp_path):
    source = dedent(
        """
        import importlib.abc
        import sys
        from pathlib import Path

        sys.path.insert(0, sys.argv[1])

        class BlockLiteLLM(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path, target=None):
                if fullname.split(".")[0] == "litellm":
                    raise AssertionError("Static collection imported LiteLLM")

        sys.meta_path.insert(0, BlockLiteLLM())
        import django
        django.setup()

        from django.conf import settings
        from django.core.management import call_command

        settings.STATIC_ROOT = Path(sys.argv[2])
        call_command(
            "collectstatic", interactive=False, clear=True,
            dry_run=True, verbosity=0,
        )
        assert "litellm" not in sys.modules
        """
    )
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            source,
            str(Path(__file__).resolve().parents[3]),
            str(tmp_path / "staticfiles"),
        ],
        cwd=tmp_path,
        env={
            **os.environ,
            "DJANGO_SETTINGS_MODULE": "litigant_portal.settings",
            "DEPLOYMENT_ENV": "qa",
            "DEBUG": "false",
            "USE_S3": "false",
        },
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
