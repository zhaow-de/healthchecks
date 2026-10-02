from __future__ import annotations

from datetime import timedelta as td
from io import StringIO
from unittest.mock import Mock

from django.contrib.auth.models import User
from django.utils.timezone import now

from hc.accounts.management.commands.pruneusers import Command
from hc.accounts.models import Project
from hc.api.models import Check
from hc.test import BaseTestCase


class PruneUsersTestCase(BaseTestCase):
    year_ago = now() - td(days=365)

    def test_it_removes_old_never_logged_in_users(self) -> None:
        self.charlie.date_joined = self.year_ago
        self.charlie.save()

        # Charlie has one demo check
        charlies_project = Project.objects.create(owner=self.charlie)
        Check(project=charlies_project).save()

        Command(stdout=Mock()).handle()

        self.assertEqual(User.objects.filter(username="charlie").count(), 0)
        self.assertEqual(Check.objects.count(), 0)

    def test_it_leaves_team_members_alone(self) -> None:
        self.bob.date_joined = self.year_ago
        self.bob.last_login = self.year_ago
        self.bob.save()

        Command(stdout=Mock()).handle()

        # Bob belongs to a team so should not get removed
        self.assertEqual(User.objects.filter(username="bob").count(), 1)

    def test_it_removes_users_inactive_since_deletion_notice(self) -> None:
        self.alice.last_login = now() - td(days=60)
        self.alice.save()
        self.profile.deletion_notice_date = now() - td(days=31)
        self.profile.save()

        stdout = StringIO()
        Command(stdout=stdout).handle()

        self.assertIn("Deleting inactive alice@example.org", stdout.getvalue())
        self.assertFalse(User.objects.filter(username="alice").exists())
        self.assertFalse(Project.objects.filter(id=self.project.id).exists())

    def test_it_keeps_users_who_logged_in_after_deletion_notice(self) -> None:
        self.alice.last_login = now() - td(days=1)
        self.alice.save()
        self.profile.deletion_notice_date = now() - td(days=31)
        self.profile.save()

        stdout = StringIO()
        Command(stdout=stdout).handle()

        self.assertNotIn("Deleting inactive", stdout.getvalue())
        self.assertTrue(User.objects.filter(username="alice").exists())

    def test_it_keeps_users_with_recent_deletion_notice(self) -> None:
        self.profile.deletion_notice_date = now() - td(days=29)
        self.profile.save()

        stdout = StringIO()
        Command(stdout=stdout).handle()

        self.assertNotIn("Deleting inactive", stdout.getvalue())
        self.assertTrue(User.objects.filter(username="alice").exists())
