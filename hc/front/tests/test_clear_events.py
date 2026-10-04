from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch

from django.db import DatabaseError
from django.db.models import QuerySet

from hc.api.models import Check, Ping
from hc.test import BaseTestCase


class ClearEventsTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.check = Check.objects.create(project=self.project)
        self.check.status = "up"
        self.check.last_start = datetime(2020, 1, 1, tzinfo=UTC)
        self.check.last_ping = datetime(2020, 1, 1, tzinfo=UTC)
        self.check.alert_after = datetime(2020, 1, 1, 1, tzinfo=UTC)
        self.check.last_duration = timedelta(minutes=1)
        self.check.has_confirmation_link = True
        self.check.n_pings = 1
        self.check.save()

        Ping.objects.create(owner=self.check, n=1)

        self.clear_url = f"/checks/{self.check.code}/clear_events/"
        self.redirect_url = f"/checks/{self.check.code}/details/"

    def test_it_works(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        r = self.client.post(self.clear_url)
        self.assertRedirects(r, self.redirect_url)

        self.check.refresh_from_db()
        self.assertEqual(self.check.status, "new")
        self.assertIsNone(self.check.last_start)
        self.assertIsNone(self.check.last_ping)
        self.assertIsNone(self.check.last_duration)
        self.assertIsNone(self.check.alert_after)
        self.assertFalse(self.check.has_confirmation_link)
        self.assertFalse(self.check.ping_set.exists())

    def test_it_handles_bad_uuid(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        r = self.client.post("/checks/not-uuid/clear_events/")
        self.assertEqual(r.status_code, 404)

    def test_it_checks_owner(self) -> None:
        self.client.login(username="charlie@example.org", password="password")
        r = self.client.post(self.clear_url)
        self.assertEqual(r.status_code, 404)

    def test_it_handles_missing_uuid(self) -> None:
        # Valid UUID but there is no check for it:
        url = "/checks/6837d6ec-fc08-4da5-a67f-08a9ed1ccf62/clear_events/"

        self.client.login(username="alice@example.org", password="password")
        r = self.client.post(url)
        self.assertEqual(r.status_code, 404)

    def test_it_rejects_get(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.clear_url)
        self.assertEqual(r.status_code, 405)

    def test_it_clears_in_one_transaction(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        with (
            patch.object(QuerySet, "delete", side_effect=DatabaseError("boom")),
            self.assertRaises(DatabaseError),
        ):
            self.client.post(self.clear_url)

        # The failed delete of the pings left the check as it was
        self.check.refresh_from_db()
        self.assertEqual(self.check.status, "up")
        self.assertIsNotNone(self.check.last_ping)
        self.assertTrue(self.check.ping_set.exists())

    def test_it_handles_a_check_deleted_after_it_was_read(self) -> None:
        def get_and_delete(*args: Any, **kwargs: Any) -> Check:
            check = Check.objects.get(id=self.check.id)
            self.check.delete()
            return check

        self.client.login(username="alice@example.org", password="password")
        with patch("hc.front.views._get_check_for_user", get_and_delete):
            r = self.client.post(self.clear_url)
        self.assertEqual(r.status_code, 404)
