from unittest.mock import patch

from django.db import connection
from django.test.utils import CaptureQueriesContext

from hc.accounts.models import Project
from hc.api.models import Channel, Check
from hc.lib.string import is_valid_uuid_string
from hc.test import BaseTestCase


class UpdateChannelTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.check = Check.objects.create(project=self.project)
        self.channel = Channel.objects.create(project=self.project, kind="email")

    def test_it_works(self) -> None:
        payload = {"channel": self.channel.code, f"check-{self.check.code}": True}

        self.client.login(username="alice@example.org", password="password")
        r = self.client.post(self.channels_url, data=payload)
        self.assertRedirects(r, self.channels_url)

        channel = Channel.objects.get(code=self.channel.code)
        checks = channel.checks.all()
        assert len(checks) == 1
        assert checks[0].code == self.check.code

    def test_it_checks_channel_user(self) -> None:
        charlies_project = Project.objects.create(owner=self.charlie)
        url = f"/projects/{charlies_project.code}/integrations/"

        payload = {"channel": self.channel.code}
        self.client.login(username="charlie@example.org", password="password")
        r = self.client.post(url, data=payload)

        # self.channel does not belong to charlie, this should fail--
        self.assertEqual(r.status_code, 403)

    def test_it_checks_check_owner(self) -> None:
        charlies_project = Project.objects.create(owner=self.charlie)
        url = f"/projects/{charlies_project.code}/integrations/"

        charlies_channel = Channel(project=charlies_project, kind="email")
        charlies_channel.value = "charlie@example.org"
        charlies_channel.save()

        payload = {"channel": charlies_channel.code, f"check-{self.check.code}": True}
        self.client.login(username="charlie@example.org", password="password")
        r = self.client.post(url, data=payload)

        # charlies_channel belongs to charlie but self.check does not--
        self.assertEqual(r.status_code, 403)

    def test_it_handles_empty_payload(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        r = self.client.post(self.channels_url, data={})
        self.assertEqual(r.status_code, 400)

    def test_it_handles_missing_channel(self) -> None:
        # Correct UUID but there is no channel for it:
        payload = {"channel": "6837d6ec-fc08-4da5-a67f-08a9ed1ccf62"}

        self.client.login(username="alice@example.org", password="password")
        r = self.client.post(self.channels_url, data=payload)
        self.assertEqual(r.status_code, 403)

    def test_it_handles_missing_check(self) -> None:
        # check- key has a correct UUID but there's no check object for it
        payload = {
            "channel": self.channel.code,
            "check-6837d6ec-fc08-4da5-a67f-08a9ed1ccf62": True,
        }

        self.client.login(username="alice@example.org", password="password")
        r = self.client.post(self.channels_url, data=payload)
        self.assertEqual(r.status_code, 403)

    def test_it_handles_invalid_check_uuid(self) -> None:
        payload = {
            "channel": self.channel.code,
            "check-surprise": True,
        }

        self.client.login(username="alice@example.org", password="password")
        r = self.client.post(self.channels_url, data=payload)
        self.assertEqual(r.status_code, 400)

    def test_it_handles_a_channel_deleted_after_it_was_read(self) -> None:
        # The view validates the check codes after it read the channel
        def validate_and_delete(s: str) -> bool:
            if s == str(self.check.code):
                Channel.objects.filter(id=self.channel.id).delete()
            return is_valid_uuid_string(s)

        payload = {"channel": self.channel.code, f"check-{self.check.code}": True}
        self.client.login(username="alice@example.org", password="password")
        with patch("hc.front.views.is_valid_uuid_string", validate_and_delete):
            r = self.client.post(self.channels_url, data=payload)
        self.assertEqual(r.status_code, 404)
        self.assertFalse(Channel.checks.through.objects.exists())

    def test_it_handles_a_check_deleted_after_it_was_read(self) -> None:
        other = Check.objects.create(project=self.project)

        # The view validates each check code after it read the previous check
        def validate_and_delete(s: str) -> bool:
            if s == str(other.code):
                Check.objects.filter(id=self.check.id).delete()
            return is_valid_uuid_string(s)

        payload = {
            "channel": self.channel.code,
            f"check-{self.check.code}": True,
            f"check-{other.code}": True,
        }
        self.client.login(username="alice@example.org", password="password")
        with patch("hc.front.views.is_valid_uuid_string", validate_and_delete):
            r = self.client.post(self.channels_url, data=payload)
        self.assertEqual(r.status_code, 404)
        self.assertFalse(Channel.checks.through.objects.exists())

    def test_it_handles_a_check_transferred_after_it_was_read(self) -> None:
        other = Check.objects.create(project=self.project)
        other_project = Project.objects.create(owner=self.alice)

        def validate_and_transfer(s: str) -> bool:
            if s == str(other.code):
                Check.objects.filter(id=self.check.id).update(project=other_project)
            return is_valid_uuid_string(s)

        payload = {
            "channel": self.channel.code,
            f"check-{self.check.code}": True,
            f"check-{other.code}": True,
        }
        self.client.login(username="alice@example.org", password="password")
        with patch("hc.front.views.is_valid_uuid_string", validate_and_transfer):
            r = self.client.post(self.channels_url, data=payload)
        self.assertEqual(r.status_code, 403)
        self.assertFalse(Channel.checks.through.objects.exists())

    def test_it_locks_the_checks_before_the_channel(self) -> None:
        payload = {"channel": self.channel.code, f"check-{self.check.code}": True}

        self.client.login(username="alice@example.org", password="password")
        with CaptureQueriesContext(connection) as ctx:
            self.client.post(self.channels_url, data=payload)

        sqls = [q["sql"] for q in ctx.captured_queries]
        # The view's transaction, a savepoint inside the test's own
        locked = sqls[next(i for i, sql in enumerate(sqls) if sql.startswith("SAVEPOINT")) :]
        check_read = next(i for i, sql in enumerate(locked) if sql.startswith("SELECT") and 'FROM "api_check"' in sql)
        channel_read = next(i for i, sql in enumerate(locked) if sql.startswith("SELECT") and 'FROM "api_channel"' in sql)
        self.assertLess(check_read, channel_read)
        if connection.vendor == "postgresql":
            # values_list("id") orders by the position of the id it selects, column 1
            sql = r'^SELECT "api_check"\."id" AS "id" FROM .* ORDER BY 1 ASC FOR NO KEY UPDATE$'
            self.assertRegex(locked[check_read], sql)
            self.assertIn("FOR NO KEY UPDATE", locked[channel_read])
