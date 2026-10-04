from datetime import UTC, datetime
from datetime import timedelta as td
from typing import Any
from unittest.mock import patch

import time_machine
from django.test.utils import override_settings
from django.utils.timezone import now

from hc.accounts.models import Project
from hc.api.models import Channel, Check, Flip, Ping
from hc.test import BaseTestCase


class DetailsTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()

        self.profile.tz = "Europe/Riga"
        self.profile.save()

        self.check = Check.objects.create(project=self.project, name="Foo")

        ping = Ping.objects.create(owner=self.check)

        # Make sure the ping is older than any notifications we may create later:
        ping.created = "2000-01-01T00:00:00+00:00"
        ping.save()

        self.url = f"/checks/{self.check.code}/details/"

    @override_settings(SITE_NAME="Mychecks")
    def test_it_works(self) -> None:
        self.check.kind = "cron"
        self.check.tz = "Europe/Berlin"
        self.check.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertContains(r, "How To Ping", status_code=200)
        self.assertContains(r, "ping-now")
        # The page should contain timezone strings
        self.assertContains(r, "Europe/Riga")

        self.assertContains(r, "Foo – Mychecks")
        self.assertContains(r, "favicon.svg")

        # It should offer both the profile's tz and the check's tz
        # in the timezone switcher:
        self.assertContains(r, "Europe/Riga")
        self.assertContains(r, "Europe/Berlin")

    def test_it_gives_the_ping_dialog_the_check_s_ping_url(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        # ping_details.js opens a ping from #log and from a #ping-<n> hash with this URL
        self.assertContains(r, f'data-url="/checks/{self.check.code}/pings/0/"')

    @override_settings(PING_ENDPOINT="http://ping.example.org/")
    def test_it_shows_no_ping_email_address(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertContains(r, f"http://ping.example.org/{self.check.code}", status_code=200)
        self.assertNotContains(r, f"{self.check.code}@")
        self.assertNotContains(r, "sending email")
        self.assertNotContains(r, 'href="#email"')

    def test_it_disables_keywords_for_email_filters_alone(self) -> None:
        self.check.filter_subject = True
        self.check.filter_body = True
        self.check.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertNotContains(r, "email messages", status_code=200)
        self.assertNotContains(r, 'name="filter_subject"')
        self.assertNotContains(r, 'name="filter_body"')
        self.assertContains(r, 'name="filter_http_body"')
        # filter_any() ignores the inert email filters, so the keyword inputs
        # stay disabled
        html = r.content.decode()
        for kw in ("start_kw", "success_kw", "failure_kw"):
            tag = html[html.index(f'id="{kw}"') :]
            self.assertIn("disabled", tag[: tag.index("/>")])

        self.check.filter_http_body = True
        self.check.save()
        r = self.client.get(self.url)
        html = r.content.decode()
        tag = html[html.index('id="start_kw"') :]
        self.assertNotIn("disabled", tag[: tag.index("/>")])

    def test_it_suggests_tags_from_other_checks(self) -> None:
        self.check.tags = "foo bar"
        self.check.save()

        Check.objects.create(project=self.project, tags="baz")

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertContains(r, "bar baz foo", status_code=200)

    def test_it_checks_ownership(self) -> None:
        self.client.login(username="charlie@example.org", password="password")
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 404)

    def test_it_shows_copy_button(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertContains(r, "Create a Copy&hellip;")
        self.assertContains(r, 'data-bs-target="#clear-events-modal"')
        self.assertContains(r, 'data-bs-target="#remove-check-modal"')

    def test_it_shows_cron_expression(self) -> None:
        self.check.kind = "cron"
        self.check.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertContains(r, "Cron Expression", status_code=200)

    def test_it_shows_actions_to_the_owner(self) -> None:
        Channel.objects.create(project=self.project, kind="email")

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)

        self.assertContains(r, 'id="edit-name"', status_code=200)
        self.assertContains(r, 'id="edit-desc"')
        self.assertContains(r, 'href="?urls=slug"')
        self.assertContains(r, "Filtering Rules")
        self.assertContains(r, 'id="pause-btn"')
        self.assertContains(r, "Change Schedule")
        self.assertContains(r, "btn btn-sm btn-outline-secondary timeout-grace")
        self.assertContains(r, 'class="details-integrations table table-hover"')
        self.assertContains(r, "Create a Copy&hellip;")
        self.assertContains(r, 'id="transfer-btn"')
        self.assertContains(r, 'data-bs-target="#clear-events-modal"')
        self.assertContains(r, 'data-bs-target="#remove-check-modal"')

        # The schedule dialog's Save buttons are enabled
        html = r.content.decode()
        self.assertRegex(html, r'id="update-cron-submit"')
        self.assertNotRegex(html, r'id="update-cron-submit"[^>]*disabled')
        self.assertRegex(html, r'id="update-oncalendar-submit"')
        self.assertNotRegex(html, r'id="update-oncalendar-submit"[^>]*disabled')

    def test_it_shows_resume_action_to_the_owner(self) -> None:
        self.check.status = "paused"
        self.check.manual_resume = True
        self.check.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)

        self.assertContains(r, 'id="resume-btn"', status_code=200)

    def test_crontab_example_guesses_schedules(self) -> None:
        self.client.login(username="alice@example.org", password="password")

        pairs = [
            (td(minutes=1), "* * * * *"),
            (td(minutes=12), "*/12 * * * *"),
            (td(hours=1), "0 * * * *"),
            (td(hours=6), "0 */6 * * *"),
            (td(days=1), "0 0 * * *"),
        ]

        for timeout, expression in pairs:
            self.check.timeout = timeout
            self.check.save()

            r = self.client.get(self.url)
            self.assertContains(r, f"{expression} /your/command.sh")
            self.assertNotContains(r, 'FIXME: replace "* * * * *"')

    def test_crontab_example_handles_unsupported_timeout_values(self) -> None:
        self.client.login(username="alice@example.org", password="password")

        self.check.timeout = td(minutes=13)
        self.check.save()

        r = self.client.get(self.url)
        self.assertContains(r, "* * * * * /your/command.sh")
        self.assertContains(r, 'FIXME: replace "* * * * *"')

    @time_machine.travel("2020-02-01 00:00+00:00")
    def test_it_calculates_downtime_summary(self) -> None:
        self.check.created = datetime(2019, 1, 1, 0, 0, 0, tzinfo=UTC)
        self.check.save()

        # going down on Jan 15, at 12:00
        f1 = Flip(owner=self.check)
        f1.created = datetime(2020, 1, 15, 12, 0, 0, tzinfo=UTC)
        f1.old_status = "up"
        f1.new_status = "down"
        f1.save()

        # back up on Jan 15, at 13:00
        f2 = Flip(owner=self.check)
        f2.created = datetime(2020, 1, 15, 13, 0, 0, tzinfo=UTC)
        f2.old_status = "down"
        f2.new_status = "up"
        f2.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertContains(r, "Feb. 2020")
        self.assertContains(r, "Jan. 2020")
        self.assertContains(r, "Dec. 2019")

        # The summary for Jan. 2020 should be "1 downtime, 1 hour total"
        self.assertContains(r, "1 downtime, 1 h 0 min total")
        self.assertContains(r, "99.86% uptime")

    @time_machine.travel("2020-02-01 00:00+00:00")
    def test_it_downtime_summary_handles_plural(self) -> None:
        self.check.created = datetime(2019, 1, 1, 0, 0, 0, tzinfo=UTC)
        self.check.save()

        # going down on Jan 15, at 12:00
        f1 = Flip(owner=self.check)
        f1.created = datetime(2020, 1, 15, 12, 0, 0, tzinfo=UTC)
        f1.old_status = "up"
        f1.new_status = "down"
        f1.save()

        # back up 2 hours later
        f2 = Flip(owner=self.check)
        f2.created = datetime(2020, 1, 15, 14, 0, 0, tzinfo=UTC)
        f2.old_status = "down"
        f2.new_status = "up"
        f2.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)

        self.assertContains(r, "1 downtime, 2 h 0 min total")
        self.assertContains(r, "99.73% uptime")

    @time_machine.travel("2020-02-01 00:00+00:00")
    def test_downtime_summary_handles_positive_utc_offset(self) -> None:
        self.profile.tz = "America/New_York"
        self.profile.save()

        self.check.created = datetime(2019, 1, 1, 0, 0, 0, tzinfo=UTC)
        self.check.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        # It is not February yet in America/New_York:
        self.assertNotContains(r, "Feb. 2020")
        self.assertContains(r, "Jan. 2020")
        self.assertContains(r, "Dec. 2019")
        self.assertContains(r, "Nov. 2019")

    @time_machine.travel("2020-01-31 23:00:00+00:00")
    def test_downtime_summary_handles_negative_utc_offset(self) -> None:
        self.profile.tz = "Europe/Riga"
        self.profile.save()

        self.check.created = datetime(2019, 1, 1, 0, 0, 0, tzinfo=UTC)
        self.check.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        # It is February already in Europe/Riga:
        self.assertContains(r, "Feb. 2020")
        self.assertContains(r, "Jan. 2020")
        self.assertContains(r, "Dec. 2019")

    @time_machine.travel("2020-02-01 00:00+00:00")
    def test_it_handles_months_when_check_did_not_exist(self) -> None:
        self.check.created = datetime(2020, 1, 10, 0, 0, 0, tzinfo=UTC)
        self.check.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertContains(r, "Feb. 2020")
        self.assertContains(r, "Jan. 2020")
        self.assertContains(r, "Dec. 2019")

        # The summary for Dec. 2019 should be "–"
        self.assertContains(r, "<td>–</td>", html=True)

    def test_it_handles_no_ping_key(self) -> None:
        self.project.show_slugs = True
        self.project.ping_key = None
        self.project.save()

        self.check.slug = "foo"
        self.check.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertContains(r, "Ping Key Required", status_code=200)
        self.assertContains(r, 'data-bs-target="#no-ping-key-modal"')
        self.assertNotContains(r, "ping-now")
        self.assertContains(r, "The ping key is currently not set")

    def test_it_handles_empty_slug(self) -> None:
        self.project.show_slugs = True
        self.project.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertContains(r, "(unavailable, set slug first)", status_code=200)
        self.assertNotContains(r, "click-to-copy")
        self.assertNotContains(r, "ping-now")
        self.assertNotContains(r, "The ping key is currently not set")

    def test_it_saves_url_format_preference(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        self.client.get(self.url + "?urls=slug")

        self.project.refresh_from_db()
        self.assertTrue(self.project.show_slugs)

    def test_it_handles_a_project_deleted_after_it_was_read(self) -> None:
        def get_and_delete(*args: Any, **kwargs: Any) -> Check:
            check = Check.objects.select_related("project").get(id=self.check.id)
            Project.objects.filter(id=self.project.id).delete()
            return check

        # The failed save marks the test's transaction for rollback, so the session
        # must stay unmodified: its save would fail and answer 400
        self.profile.last_active_date = now()
        self.profile.save()

        self.client.login(username="alice@example.org", password="password")
        with patch("hc.front.views._get_check_for_user", get_and_delete):
            r = self.client.get(self.url + "?urls=slug")
        self.assertEqual(r.status_code, 404)

    def test_it_outputs_period_grace_as_integers(self) -> None:
        self.check.timeout = td(seconds=123)
        self.check.grace = td(seconds=456)
        self.check.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)

        self.assertContains(r, 'data-timeout="123"')
        self.assertContains(r, 'data-grace="456"')

    @override_settings(SITE_NAME="Mychecks")
    def test_it_sets_title_and_favicon(self) -> None:
        self.check.status = "down"
        self.check.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertContains(r, "DOWN – Foo – Mychecks", status_code=200)
        self.assertContains(r, "favicon_down.svg")

    def test_it_lists_group_channels_separately(self) -> None:
        email = Channel.objects.create(project=self.project, kind="email", name="Alice's Inbox")
        group = Channel.objects.create(project=self.project, kind="group", name="On-call Group")
        group.value = str(email.code)
        group.save()
        group.checks.add(self.check)

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertContains(r, "Notification Groups", status_code=200)
        self.assertContains(r, "On-call Group")
        self.assertContains(r, "Alice&#x27;s Inbox")

        # The group channel is listed before the regular channel heading,
        # the regular channel after it
        html = r.content.decode()
        groups_pos = html.index("Notification Groups")
        methods_pos = html.index("Notification Methods")
        self.assertLess(groups_pos, html.index("On-call Group"))
        self.assertLess(html.index("On-call Group"), methods_pos)
        self.assertLess(methods_pos, html.index("Alice&#x27;s Inbox"))

    def test_it_omits_notification_groups_heading_without_groups(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertNotContains(r, "Notification Groups", status_code=200)

    def test_it_denies_a_superuser_outsider(self) -> None:
        self.charlie.is_superuser = True
        self.charlie.save()

        self.client.login(username="charlie@example.org", password="password")
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 404)
