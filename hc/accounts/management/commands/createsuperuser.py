from __future__ import annotations

import sys
from argparse import ArgumentParser
from getpass import getpass
from typing import Any
from uuid import uuid4

from django.contrib.auth import password_validation
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand

from hc.accounts.forms import LowercaseEmailField
from hc.accounts.models import Profile, Project
from hc.api.models import Channel, Check


def _make_user(email: str) -> User:
    username = str(uuid4())[:30]
    user = User(username=username, email=email)
    user.set_unusable_password()
    user.save()

    project = Project(owner=user)
    project.badge_key = user.username
    project.save()

    check = Check(project=project)
    check.name = "My First Check"
    check.slug = "my-first-check"
    check.save()

    channel = Channel(project=project)
    channel.kind = "email"
    channel.value = email
    channel.email_verified = True
    channel.save()

    channel.checks.add(check)

    # Ensure a profile gets created
    Profile.objects.for_user(user)
    return user


class Command(BaseCommand):
    help = """Create the instance's one user, a superuser."""

    def validate_email(self, raw_email: str) -> str | None:
        try:
            email = LowercaseEmailField().clean(raw_email)
        except ValidationError as e:
            self.stderr.write("Error: " + " ".join(e.messages))
            return None

        return email

    def validate_password(self, password: str, email: str) -> str | None:
        if password.strip() == "":
            self.stderr.write("Error: Blank passwords aren't allowed.")
            return None

        try:
            password_validation.validate_password(password, User(email=email))
        except ValidationError as e:
            self.stderr.write("Error: " + " ".join(e.messages))
            return None

        return password

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--email",
            type=str,
            help="Email address of the account. If this isn't provided or the value is invalid, will prompt for the email address.",
        )
        parser.add_argument(
            "--password",
            "--pass",
            type=str,
            help="Password of the account. If this isn't provided or the value is invalid, will prompt for the password.",
        )

    def handle(self, **options: Any) -> str:
        if User.objects.exists():
            self.stderr.write("Error: a user already exists, and this instance has only one")
            sys.exit(2)

        email = options["email"]
        password = options["password"]

        if email is not None:
            email = self.validate_email(email)

        if sys.stdin.isatty():
            while email is None:
                raw = input("Email address:")
                email = self.validate_email(raw)
        elif email is None:
            self.stderr.write("Missing or invalid required argument: --email")
            sys.exit(2)

        # After the email, which the similarity validator compares the password with
        if password is not None:
            password = self.validate_password(password, email)

        if sys.stdin.isatty():
            while password is None:
                p1 = getpass()
                p2 = getpass("Password (again):")

                if p1 != p2:
                    self.stderr.write("Error: Your passwords didn't match.")
                    password = None
                    continue

                password = self.validate_password(p1, email)
        elif password is None:
            self.stderr.write("Missing or invalid required argument: --password/--pass")
            sys.exit(2)

        user = _make_user(email)
        user.set_password(password)
        user.is_staff = True
        user.is_superuser = True
        user.save()

        return "Superuser created successfully."
