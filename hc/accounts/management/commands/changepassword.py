from __future__ import annotations

from argparse import ArgumentParser
from typing import Any

from django.contrib.auth.management.commands import changepassword
from django.contrib.auth.models import User
from django.db import DEFAULT_DB_ALIAS, connections


class Command(changepassword.Command):
    help = """Change the password of the instance's one user: run it with no
    argument, or with the user's email address, as createsuperuser gives the
    user a random username.
    """

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "username",
            nargs="?",
            help="The user's email address or username; by default, the instance's one user.",
        )
        parser.add_argument(
            "--database",
            default=DEFAULT_DB_ALIAS,
            choices=tuple(connections),
            help='Specifies the database to use. Default is "default".',
        )

    def handle(self, *args: Any, **options: Any) -> str:
        users = User.objects.using(options["database"])
        name = options["username"]
        if not name and users.count() == 1:
            options["username"] = users.get().username
        elif name and "@" in name:
            user = users.filter(email__iexact=name).first()
            if user:
                options["username"] = user.username

        return super().handle(*args, **options)
