import os
from pathlib import Path


def read_secret(env_var: str) -> str | None:
    """Read a secret from a file path or fall back to env var.

    Checks <ENV_VAR>_FILE first (path to a file containing the secret),
    then falls back to <ENV_VAR> directly. This pattern works with:
    - Docker Compose secrets (/run/secrets/...)
    - Kubernetes secrets (mounted as files)
    - Plain env vars (local dev, CI)
    """
    file_path = os.environ.get(f"{env_var}_FILE")
    if file_path:
        path = Path(file_path)
        if path.is_file():
            return path.read_text().strip()
    return os.environ.get(env_var)
