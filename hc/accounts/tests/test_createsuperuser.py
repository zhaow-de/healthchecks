from __future__ import annotations

from io import StringIO
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.core.management import call_command

from hc.accounts.management.commands.createsuperuser import Command
from hc.test import BaseTestCase


class CreateSuperuserTestCase(BaseTestCase):
    @patch(Command.__module__ + ".sys.stdin.isatty", Mock(return_value=True))
    @patch(Command.__module__ + ".getpass")
    @patch(Command.__module__ + ".input")
    def test_it_works(self, mock_input: Mock, mock_getpass: Mock) -> None:
        cmd = Command(stdout=Mock())
        mock_input.return_value = "superuser@example.org"
        mock_getpass.return_value = "hunter2"
        cmd.handle(email=None, password=None)

        u = User.objects.get(email="superuser@example.org")
        self.assertTrue(u.is_superuser)

    @patch(Command.__module__ + ".sys.stdin.isatty", Mock(return_value=True))
    @patch(Command.__module__ + ".getpass")
    @patch(Command.__module__ + ".input")
    def test_it_rejects_duplicate_email(self, mock_input: Mock, mock_getpass: Mock) -> None:
        cmd = Command(stdout=Mock(), stderr=Mock())
        mock_input.side_effect = ["alice@example.org", "alice2@example.org"]
        mock_getpass.return_value = "hunter2"
        cmd.handle(email=None, password=None)

        u = User.objects.get(email="alice2@example.org")
        self.assertTrue(u.is_superuser)

    def test_it_accepts_arguments(self) -> None:
        cmd = Command(stdout=Mock())
        cmd.handle(email="superuser@example.org", password="hunter2")

        u = User.objects.get(email="superuser@example.org")
        self.assertTrue(u.is_superuser)

    def test_it_parses_command_line_options(self) -> None:
        stdout = StringIO()
        call_command("createsuperuser", "--email", "Superuser@Example.org", "--pass", "hunter2", stdout=stdout)

        self.assertEqual(stdout.getvalue(), "Superuser created successfully.\n")
        u = User.objects.get(email="superuser@example.org")
        self.assertTrue(u.is_staff)
        self.assertTrue(u.is_superuser)
        self.assertTrue(u.check_password("hunter2"))

    @patch(Command.__module__ + ".sys.stdin.isatty", Mock(return_value=False))
    def test_it_exits_on_invalid_email_without_tty(self) -> None:
        stderr = StringIO()
        cmd = Command(stdout=Mock(), stderr=stderr)
        with self.assertRaises(SystemExit) as cm:
            cmd.handle(email="not-an-email", password="hunter2")

        self.assertEqual(cm.exception.code, 2)
        self.assertEqual(
            stderr.getvalue(),
            "Error: Enter a valid email address.\nMissing or invalid required argument: --email\n",
        )
        self.assertFalse(User.objects.filter(is_superuser=True).exists())

    @patch(Command.__module__ + ".sys.stdin.isatty", Mock(return_value=False))
    def test_it_exits_on_blank_password_without_tty(self) -> None:
        stderr = StringIO()
        cmd = Command(stdout=Mock(), stderr=stderr)
        with self.assertRaises(SystemExit) as cm:
            cmd.handle(email="superuser@example.org", password="   ")

        self.assertEqual(cm.exception.code, 2)
        self.assertEqual(
            stderr.getvalue(),
            "Error: Blank passwords aren't allowed.\nMissing or invalid required argument: --password/--pass\n",
        )
        self.assertFalse(User.objects.filter(email="superuser@example.org").exists())

    @patch(Command.__module__ + ".sys.stdin.isatty", Mock(return_value=True))
    @patch(Command.__module__ + ".getpass")
    def test_it_prompts_again_when_passwords_do_not_match(self, mock_getpass: Mock) -> None:
        stderr = StringIO()
        cmd = Command(stdout=Mock(), stderr=stderr)
        mock_getpass.side_effect = ["hunter2", "hunter3", "hunter2", "hunter2"]
        cmd.handle(email="superuser@example.org", password=None)

        self.assertEqual(stderr.getvalue(), "Error: Your passwords didn't match.\n")
        self.assertEqual(mock_getpass.call_count, 4)
        u = User.objects.get(email="superuser@example.org")
        self.assertTrue(u.check_password("hunter2"))

    @patch(Command.__module__ + ".sys.stdin.isatty", Mock(return_value=True))
    @patch(Command.__module__ + ".getpass")
    def test_it_prompts_again_on_blank_password(self, mock_getpass: Mock) -> None:
        stderr = StringIO()
        cmd = Command(stdout=Mock(), stderr=stderr)
        mock_getpass.side_effect = [" ", " ", "hunter2", "hunter2"]
        cmd.handle(email="superuser@example.org", password=None)

        self.assertEqual(stderr.getvalue(), "Error: Blank passwords aren't allowed.\n")
        u = User.objects.get(email="superuser@example.org")
        self.assertTrue(u.check_password("hunter2"))
