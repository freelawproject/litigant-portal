import click

from .manage import manage


@click.group()
def cli():
    """Litigant Portal CLI."""
    pass


cli.add_command(manage)
