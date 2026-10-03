from __future__ import annotations

from typing import Any

from django.contrib.auth.management.commands import changepassword
from django.contrib.auth.models import User


class Command(changepassword.Command):
    help = """Change the password of the instance's one user.

    createsuperuser gives the user a random username, so with no argument this
    changes the one user's password, and an email address picks the user by email.
    """

    def handle(self, *args: Any, **options: Any) -> str:
        users = User.objects.using(options["database"])
        name = options["username"]
        if not name and users.count() == 1:
            options["username"] = users.get().username
        elif name and "@" in name:
            user = users.filter(email=name).first()
            if user:
                options["username"] = user.username

        return super().handle(*args, **options)
