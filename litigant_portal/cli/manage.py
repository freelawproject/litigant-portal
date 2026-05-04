import click
from django.core.management import execute_from_command_line

from litigant_portal.utils import init_django


@click.command(context_settings={"ignore_unknown_options": True})
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def manage(args):
    """Run Django management commands.

    Examples:

        > litigant-portal manage runserver\n
        > litigant-portal manage makemigrations\n
        > litigant-portal manage migrate\n
    """
    init_django()
    execute_from_command_line(["manage.py", *args])
