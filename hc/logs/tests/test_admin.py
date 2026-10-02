from __future__ import annotations

import logging
from datetime import datetime, timezone

from django.urls import reverse

from hc.logs.models import Record
from hc.test import BaseTestCase

TRACEBACK = """Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
ValueError: boom"""


class RecordsAdminTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()

        self.alice.is_staff = True
        self.alice.is_superuser = True
        self.alice.save()

    def test_it_shows_records(self) -> None:
        Record.objects.create(
            created=datetime(2020, 1, 2, 3, 4, tzinfo=timezone.utc),
            host="web-1",
            name="hc.api",
            level=logging.ERROR,
            message="Something <failed>",
            traceback=TRACEBACK,
        )
        Record.objects.create(name="hc.front", level=logging.WARNING, message="All good", traceback="")

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(reverse("admin:logs_record_changelist"))
        self.assertContains(r, "Jan 2, 03:04")
        self.assertContains(r, "web-1")
        self.assertContains(r, '<span class="E">E</span> hc.api')
        self.assertContains(r, '<span class="W">W</span> hc.front')
        # The message and the traceback are both escaped
        self.assertContains(r, "Something &lt;failed&gt;<details><summary>Show traceback</summary><pre>")
        self.assertContains(r, "File &quot;&lt;stdin&gt;&quot;, line 1, in &lt;module&gt;\nValueError: boom</pre></details>")
        # A record without a traceback shows the bare message
        self.assertContains(r, '<td class="field-message_traceback">All good</td>', html=True)

    def test_records_are_read_only(self) -> None:
        record = Record.objects.create(name="hc.api", level=logging.ERROR, message="Oops", traceback="")

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(reverse("admin:logs_record_add"))
        self.assertEqual(r.status_code, 403)

        # The change page opens as a read-only view: no save button
        r = self.client.get(reverse("admin:logs_record_change", args=[record.id]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Oops")
        self.assertNotContains(r, 'name="_save"')
