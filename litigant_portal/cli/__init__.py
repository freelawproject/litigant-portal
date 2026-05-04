import click

from .manage import manage
from .tailwind import tailwind


@click.group()
def cli():
    """Litigant Portal CLI."""
    pass


cli.add_command(manage)
cli.add_command(tailwind)
