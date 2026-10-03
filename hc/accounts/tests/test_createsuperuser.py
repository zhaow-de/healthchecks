from __future__ import annotations

from io import StringIO
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from hc.accounts.management.commands.createsuperuser import Command
from hc.accounts.models import Profile, Project
from hc.api.models import Channel, Check


# Not BaseTestCase: its users would make the command refuse to run
class CreateSuperuserTestCase(TestCase):
    @patch(Command.__module__ + ".sys.stdin.isatty", Mock(return_value=True))
    @patch(Command.__module__ + ".getpass")
    @patch(Command.__module__ + ".input")
    def test_it_works(self, mock_input: Mock, mock_getpass: Mock) -> None:
        cmd = Command(stdout=Mock())
        mock_input.return_value = "superuser@example.org"
        mock_getpass.return_value = "Correct-Horse-9"
        cmd.handle(email=None, password=None)

        u = User.objects.get(email="superuser@example.org")
        self.assertTrue(u.is_superuser)

    @patch(Command.__module__ + ".sys.stdin.isatty", Mock(return_value=True))
    @patch(Command.__module__ + ".getpass")
    @patch(Command.__module__ + ".input")
    def test_it_prompts_again_on_invalid_email(self, mock_input: Mock, mock_getpass: Mock) -> None:
        stderr = StringIO()
        cmd = Command(stdout=Mock(), stderr=stderr)
        mock_input.side_effect = ["not-an-email", "superuser@example.org"]
        mock_getpass.return_value = "Correct-Horse-9"
        cmd.handle(email=None, password=None)

        self.assertEqual(stderr.getvalue(), "Error: Enter a valid email address.\n")
        self.assertEqual(mock_input.call_count, 2)
        u = User.objects.get(email="superuser@example.org")
        self.assertTrue(u.is_superuser)

    def test_it_accepts_arguments(self) -> None:
        cmd = Command(stdout=Mock())
        cmd.handle(email="superuser@example.org", password="Correct-Horse-9")

        u = User.objects.get()
        self.assertEqual(u.email, "superuser@example.org")
        self.assertTrue(u.is_superuser)
        self.assertTrue(Profile.objects.filter(user=u).exists())

        project = Project.objects.get()
        self.assertEqual(project.owner, u)
        self.assertEqual(project.badge_key, u.username)

        check = Check.objects.get()
        self.assertEqual(check.project, project)
        self.assertEqual(check.name, "My First Check")
        self.assertEqual(check.slug, "my-first-check")

        channel = Channel.objects.get()
        self.assertEqual(channel.project, project)
        self.assertEqual(channel.kind, "email")
        self.assertEqual(channel.value, "superuser@example.org")
        self.assertTrue(channel.email_verified)
        self.assertEqual(list(channel.checks.all()), [check])

    @patch(Command.__module__ + ".sys.stdin.isatty", Mock(return_value=True))
    @patch(Command.__module__ + ".getpass")
    @patch(Command.__module__ + ".input")
    def test_it_refuses_when_a_user_exists(self, mock_input: Mock, mock_getpass: Mock) -> None:
        User.objects.create(username="alice", email="alice@example.org")
        mock_input.return_value = "superuser@example.org"
        mock_getpass.return_value = "Correct-Horse-9"

        stderr = StringIO()
        cmd = Command(stdout=Mock(), stderr=stderr)
        with self.assertRaises(SystemExit) as cm:
            cmd.handle(email=None, password=None)

        self.assertEqual(cm.exception.code, 2)
        self.assertEqual(stderr.getvalue(), "Error: a user already exists, and this instance has only one\n")
        mock_input.assert_not_called()
        mock_getpass.assert_not_called()
        self.assertEqual(list(User.objects.values_list("email", flat=True)), ["alice@example.org"])
        self.assertFalse(Project.objects.exists())

    def test_it_parses_command_line_options(self) -> None:
        stdout = StringIO()
        call_command("createsuperuser", "--email", "Superuser@Example.org", "--pass", "Correct-Horse-9", stdout=stdout)

        self.assertEqual(stdout.getvalue(), "Superuser created successfully.\n")
        u = User.objects.get(email="superuser@example.org")
        self.assertTrue(u.is_staff)
        self.assertTrue(u.is_superuser)
        self.assertTrue(u.check_password("Correct-Horse-9"))

    @patch(Command.__module__ + ".sys.stdin.isatty", Mock(return_value=False))
    def test_it_exits_on_invalid_email_without_tty(self) -> None:
        stderr = StringIO()
        cmd = Command(stdout=Mock(), stderr=stderr)
        with self.assertRaises(SystemExit) as cm:
            cmd.handle(email="not-an-email", password="Correct-Horse-9")

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
        mock_getpass.side_effect = ["Correct-Horse-9", "Correct-Horse-8", "Correct-Horse-9", "Correct-Horse-9"]
        cmd.handle(email="superuser@example.org", password=None)

        self.assertEqual(stderr.getvalue(), "Error: Your passwords didn't match.\n")
        self.assertEqual(mock_getpass.call_count, 4)
        u = User.objects.get(email="superuser@example.org")
        self.assertTrue(u.check_password("Correct-Horse-9"))

    @patch(Command.__module__ + ".sys.stdin.isatty", Mock(return_value=True))
    @patch(Command.__module__ + ".getpass")
    def test_it_prompts_again_on_blank_password(self, mock_getpass: Mock) -> None:
        stderr = StringIO()
        cmd = Command(stdout=Mock(), stderr=stderr)
        mock_getpass.side_effect = [" ", " ", "Correct-Horse-9", "Correct-Horse-9"]
        cmd.handle(email="superuser@example.org", password=None)

        self.assertEqual(stderr.getvalue(), "Error: Blank passwords aren't allowed.\n")
        u = User.objects.get(email="superuser@example.org")
        self.assertTrue(u.check_password("Correct-Horse-9"))

    @patch(Command.__module__ + ".sys.stdin.isatty", Mock(return_value=False))
    def test_it_exits_on_weak_password_without_tty(self) -> None:
        stderr = StringIO()
        cmd = Command(stdout=Mock(), stderr=stderr)
        with self.assertRaises(SystemExit) as cm:
            cmd.handle(email="superuser@example.org", password="12345678")

        self.assertEqual(cm.exception.code, 2)
        self.assertEqual(
            stderr.getvalue(),
            "Error: This password is too short. It must contain at least 12 characters. "
            "This password is too common. This password is entirely numeric.\n"
            "Missing or invalid required argument: --password/--pass\n",
        )
        self.assertFalse(User.objects.exists())

    @patch(Command.__module__ + ".sys.stdin.isatty", Mock(return_value=False))
    def test_it_compares_the_password_with_the_email(self) -> None:
        stderr = StringIO()
        cmd = Command(stdout=Mock(), stderr=stderr)
        with self.assertRaises(SystemExit):
            cmd.handle(email="superuser@example.org", password="superuser@example")

        self.assertIn("The password is too similar to the email address.", stderr.getvalue())
        self.assertFalse(User.objects.exists())

    @patch(Command.__module__ + ".sys.stdin.isatty", Mock(return_value=True))
    @patch(Command.__module__ + ".getpass")
    def test_it_prompts_again_on_weak_password(self, mock_getpass: Mock) -> None:
        stderr = StringIO()
        cmd = Command(stdout=Mock(), stderr=stderr)
        mock_getpass.side_effect = ["1qaz2wsx3edc", "1qaz2wsx3edc", "Correct-Horse-9", "Correct-Horse-9"]
        cmd.handle(email="superuser@example.org", password=None)

        self.assertEqual(stderr.getvalue(), "Error: This password is too common.\n")
        u = User.objects.get(email="superuser@example.org")
        self.assertTrue(u.check_password("Correct-Horse-9"))
