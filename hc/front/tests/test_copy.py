from datetime import timedelta as td
from typing import Any
from unittest import skipUnless
from unittest.mock import patch

from django.db import connection
from django.test.utils import CaptureQueriesContext

from hc.accounts.models import Project
from hc.api.models import Channel, Check
from hc.test import BaseTestCase


class CopyCheckTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.check = Check(project=self.project)
        self.check.name = "Foo"
        self.check.slug = "custom-slug"
        self.check.tags = "tag1 tag2"
        self.check.desc = "Description goes here"
        self.check.kind = "cron"
        self.check.timeout = td(minutes=10)
        self.check.grace = td(minutes=5)
        self.check.schedule = "0 0 * * *"
        self.check.tz = "Europe/Riga"
        self.check.filter_subject = True
        self.check.filter_body = True
        self.check.filter_http_body = True
        self.check.filter_default_fail = True
        self.check.start_kw = "start-keyword"
        self.check.success_kw = "success-keyword"
        self.check.failure_kw = "failure-keyword"
        self.check.methods = "POST"
        self.check.manual_resume = True
        self.check.save()

        self.copy_url = f"/checks/{self.check.code}/copy/"

    def test_it_works(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        r = self.client.post(self.copy_url, follow=True)
        self.assertContains(r, "This is a brand-new check")

        copy = Check.objects.get(name="Foo (copy)")
        self.assertEqual(copy.slug, "custom-slug-copy")
        self.assertEqual(copy.tags, "tag1 tag2")
        self.assertEqual(copy.desc, "Description goes here")
        self.assertEqual(copy.kind, "cron")
        self.assertEqual(copy.timeout, td(minutes=10))
        self.assertEqual(copy.grace, td(minutes=5))
        self.assertEqual(copy.schedule, "0 0 * * *")
        self.assertEqual(copy.tz, "Europe/Riga")
        self.assertTrue(copy.filter_subject)
        self.assertTrue(copy.filter_body)
        self.assertTrue(copy.filter_http_body)
        self.assertTrue(copy.filter_default_fail)
        self.assertEqual(copy.start_kw, "start-keyword")
        self.assertEqual(copy.success_kw, "success-keyword")
        self.assertEqual(copy.failure_kw, "failure-keyword")
        self.assertEqual(copy.methods, "POST")
        self.assertTrue(copy.manual_resume)

    def test_it_copies_channels(self) -> None:
        channel = Channel.objects.create(project=self.project, kind="email")
        self.check.channel_set.add(channel)

        self.client.login(username="alice@example.org", password="password")
        self.client.post(self.copy_url)

        copy = Check.objects.get(name="Foo (copy)")
        self.assertEqual(copy.channel_set.get(), channel)

    def test_it_has_no_check_limit(self) -> None:
        Check.objects.bulk_create([Check(project=self.project) for _ in range(25)])

        self.client.login(username="alice@example.org", password="password")
        r = self.client.post(self.copy_url)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Check.objects.count(), 27)

    def test_it_checks_ownership(self) -> None:
        self.client.login(username="charlie@example.org", password="password")
        r = self.client.post(self.copy_url)
        self.assertEqual(r.status_code, 404)
        self.assertEqual(Check.objects.count(), 1)

    def test_it_handles_long_check_name(self) -> None:
        self.check.name = "A" * 100
        self.check.save()

        self.client.login(username="alice@example.org", password="password")
        self.client.post(self.copy_url)

        q = Check.objects.filter(name="A" * 90 + "... (copy)")
        self.assertTrue(q.exists())

    def test_it_clears_too_long_slug(self) -> None:
        self.check.slug = "a" * 100
        self.check.save()

        self.client.login(username="alice@example.org", password="password")
        self.client.post(self.copy_url)

        copy = Check.objects.get(name="Foo (copy)")
        self.assertEqual(copy.slug, "")

    def test_it_keeps_empty_slug_empty(self) -> None:
        self.check.slug = ""
        self.check.save()

        self.client.login(username="alice@example.org", password="password")
        self.client.post(self.copy_url)

        copy = Check.objects.get(name="Foo (copy)")
        self.assertEqual(copy.slug, "")

    def test_it_handles_a_project_deleted_after_it_was_read(self) -> None:
        def get_and_delete(*args: Any, **kwargs: Any) -> Check:
            check = Check.objects.select_related("project").get(id=self.check.id)
            Project.objects.filter(id=self.project.id).delete()
            return check

        self.client.login(username="alice@example.org", password="password")
        with patch("hc.front.views._get_check_for_user", get_and_delete):
            r = self.client.post(self.copy_url)
        self.assertEqual(r.status_code, 404)
        self.assertFalse(Check.objects.exists())

    def test_it_copies_into_the_project_a_transfer_moved_the_check_to(self) -> None:
        self.check.channel_set.add(Channel.objects.create(project=self.project, kind="email"))
        other_project = Project.objects.create(owner=self.alice)
        other_channel = Channel.objects.create(project=other_project, kind="email")

        def get_and_transfer(*args: Any, **kwargs: Any) -> Check:
            check = Check.objects.select_related("project").get(id=self.check.id)
            # As the transfer view does: the new project, then all of its channels
            Check.objects.filter(id=self.check.id).update(project=other_project)
            self.check.channel_set.set([other_channel])
            return check

        self.client.login(username="alice@example.org", password="password")
        with patch("hc.front.views._get_check_for_user", get_and_transfer):
            r = self.client.post(self.copy_url)
        self.assertEqual(r.status_code, 302)

        copy = Check.objects.get(name="Foo (copy)")
        self.assertEqual(copy.project, other_project)
        self.assertEqual(list(copy.channel_set.all()), [other_channel])

    @skipUnless(connection.features.has_select_for_update, "no row locks")
    def test_it_locks_the_channels_for_no_key_update_in_id_order(self) -> None:
        self.check.channel_set.add(Channel.objects.create(project=self.project, kind="email"))
        self.client.login(username="alice@example.org", password="password")
        with CaptureQueriesContext(connection) as ctx:
            self.client.post(self.copy_url)
        locks = [q["sql"] for q in ctx.captured_queries if 'FROM "api_channel"' in q["sql"] and " FOR " in q["sql"]]
        self.assertEqual(len(locks), 1, locks)
        self.assertIn(' ORDER BY "api_channel"."id" ASC FOR NO KEY UPDATE', locks[0])
