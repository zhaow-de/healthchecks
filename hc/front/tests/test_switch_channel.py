from typing import Any
from unittest import skipUnless
from unittest.mock import patch

from django.db import connection
from django.shortcuts import get_object_or_404
from django.test.utils import CaptureQueriesContext

from hc.accounts.models import Project
from hc.api.models import Channel, Check
from hc.test import BaseTestCase


class SwitchChannelTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.check = Check.objects.create(project=self.project)

        self.channel = Channel(project=self.project, kind="email")
        self.channel.value = "alice@example.org"
        self.channel.save()

        self.url = f"/checks/{self.check.code}/channels/{self.channel.code}/enabled"

    def test_it_enables(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        self.client.post(self.url, {"state": "on"})

        self.assertTrue(self.channel in self.check.channel_set.all())

    def test_it_disables(self) -> None:
        self.check.channel_set.add(self.channel)

        self.client.login(username="alice@example.org", password="password")
        self.client.post(self.url, {"state": "off"})

        self.assertFalse(self.channel in self.check.channel_set.all())

    def test_it_checks_ownership(self) -> None:
        self.client.login(username="charlie@example.org", password="password")
        r = self.client.post(self.url, {"state": "on"})
        self.assertEqual(r.status_code, 404)

    def test_it_checks_channels_ownership(self) -> None:
        charlies_project = Project.objects.create(owner=self.charlie)
        cc = Check.objects.create(project=charlies_project)

        # Charlie will try to assign Alice's channel to his check:
        self.url = f"/checks/{cc.code}/channels/{self.channel.code}/enabled"

        self.client.login(username="charlie@example.org", password="password")
        r = self.client.post(self.url, {"state": "on"})
        self.assertEqual(r.status_code, 400)

    def test_it_handles_a_check_deleted_after_it_was_read(self) -> None:
        def get_and_delete(*args: Any, **kwargs: Any) -> Check:
            check = Check.objects.get(id=self.check.id)
            self.check.delete()
            return check

        self.client.login(username="alice@example.org", password="password")
        with patch("hc.front.views._get_check_for_user", get_and_delete):
            r = self.client.post(self.url, {"state": "on"})
        self.assertEqual(r.status_code, 404)
        self.assertFalse(self.channel.checks.exists())

    def test_it_handles_a_channel_deleted_after_it_was_read(self) -> None:
        def get_and_delete(*args: Any, **kwargs: Any) -> Any:
            obj = get_object_or_404(*args, **kwargs)
            if isinstance(obj, Channel):
                Channel.objects.filter(id=obj.id).delete()
            return obj

        self.client.login(username="alice@example.org", password="password")
        with patch("hc.front.views.get_object_or_404", get_and_delete):
            r = self.client.post(self.url, {"state": "on"})
        self.assertEqual(r.status_code, 404)
        self.assertFalse(Channel.checks.through.objects.exists())

    @skipUnless(connection.features.has_select_for_update, "no row locks")
    def test_it_locks_the_channel_for_no_key_update(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        with CaptureQueriesContext(connection) as ctx:
            self.client.post(self.url, {"state": "on"})
        locks = [q["sql"] for q in ctx.captured_queries if 'FROM "api_channel"' in q["sql"] and " FOR " in q["sql"]]
        self.assertEqual(len(locks), 1, locks)
        self.assertIn(" FOR NO KEY UPDATE", locks[0])
