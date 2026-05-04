import os
import subprocess
from pathlib import Path

import click

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
INSTALL_SCRIPT = PROJECT_ROOT / "docker" / "django" / "install-tailwind.sh"
APP_STATIC = PROJECT_ROOT / "litigant_portal" / "app" / "static"
INPUT_CSS = APP_STATIC / "css" / "main.css"
OUTPUT_CSS = APP_STATIC / "css" / "main.built.css"


@click.command()
@click.option(
    "--dev",
    is_flag=True,
    help="Run the watcher for development. Without it, build once and minify.",
)
def tailwind(dev):
    """Build the Tailwind CSS bundle."""
    dest = Path(
        os.getenv("TAILWIND_DEST", str(PROJECT_ROOT / "tailwindcss"))
    ).resolve()

    if not dest.exists():
        click.echo(f"Tailwind binary not found at {dest}, installing...")
        env = os.environ.copy()
        env["TAILWIND_DEST"] = str(dest)
        subprocess.run(["bash", str(INSTALL_SCRIPT)], env=env, check=True)

    cmd = [str(dest), "-i", str(INPUT_CSS), "-o", str(OUTPUT_CSS)]
    cmd.append("--watch") if dev else cmd.append("--minify")

    subprocess.run(cmd, check=True)
