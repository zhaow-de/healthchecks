from __future__ import annotations

from io import StringIO
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.core.management import CommandError, call_command
from django.test import TestCase

from hc.accounts.management.commands.changepassword import Command


# Not BaseTestCase: its two users would leave a bare run without a user to pick
@patch.object(Command, "_get_pass", Mock(return_value="Correct-Horse-9"))
class ChangePasswordTestCase(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user = User.objects.create_user("0f8b3c1e-uuid", "one@example.org", "old")

    def test_it_changes_the_one_users_password(self) -> None:
        call_command("changepassword", stdout=StringIO())

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Correct-Horse-9"))

    def test_it_finds_the_user_by_email(self) -> None:
        call_command("changepassword", "one@example.org", stdout=StringIO())

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Correct-Horse-9"))

    def test_it_still_takes_a_username(self) -> None:
        call_command("changepassword", "0f8b3c1e-uuid", stdout=StringIO())

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Correct-Horse-9"))

    def test_it_refuses_an_unknown_email(self) -> None:
        with self.assertRaisesMessage(CommandError, "user 'nobody@example.org' does not exist"):
            call_command("changepassword", "nobody@example.org", stdout=StringIO())
