from datetime import timedelta as td

from django.test.utils import override_settings
from django.utils.timezone import now

from hc.api.models import Check
from hc.test import BaseTestCase


class MyChecksTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.check = Check(project=self.project, name="Alice Was Here")
        self.check.slug = "alice-was-here"
        self.check.save()

        self.url = f"/projects/{self.project.code}/checks/"

    def test_it_works(self) -> None:
        self.profile.tz = "Europe/Riga"
        self.profile.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertContains(r, "favicon.svg", status_code=200)
        self.assertContains(r, "Alice Was Here")
        self.assertContains(r, str(self.check.code))
        self.assertContains(r, 'data-profile-tz="Europe/Riga"')
        # The pause button:
        self.assertContains(r, "btn pause")
        # The Add Check button:
        self.assertContains(r, 'data-bs-target="#add-check-modal"')
        # The ping URL style switcher:
        self.assertContains(r, 'id="url-style-switcher"')
        # The cells that checks.js and update-timeout-modal.js make editable:
        self.assertContains(r, 'class="my-checks-name ')
        self.assertContains(r, 'class="integrations ic"')
        self.assertContains(r, 'class="timeout-grace"')
        # The schedule dialog's Save buttons are enabled
        html = r.content.decode()
        self.assertRegex(html, r'id="update-cron-submit"')
        self.assertNotRegex(html, r'id="update-cron-submit"[^>]*disabled')
        self.assertRegex(html, r'id="update-oncalendar-submit"')
        self.assertNotRegex(html, r'id="update-oncalendar-submit"[^>]*disabled')

        # last_active_date should have been set
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.last_active_date)

    def test_it_bumps_last_active_date(self) -> None:
        self.profile.last_active_date = now() - td(days=10)
        self.profile.save()

        self.client.login(username="alice@example.org", password="password")
        self.client.get(self.url)

        # last_active_date should have been bumped
        self.profile.refresh_from_db()
        duration = now() - self.profile.last_active_date
        self.assertTrue(duration.total_seconds() < 1)

    def test_it_updates_session(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

        self.assertEqual(self.client.session["last_project_id"], self.project.id)

    def test_it_checks_access(self) -> None:
        self.client.login(username="charlie@example.org", password="password")
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 404)

    def test_it_shows_add_check_button_on_empty_project(self) -> None:
        self.check.delete()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        # Enabled: no attribute after its modal target
        self.assertRegex(
            r.content.decode(),
            r'<button\s+class="btn btn-primary"\s+data-bs-toggle="modal"\s+data-bs-target="#add-check-modal">\s+Add Check',
        )

    def test_it_shows_green_check(self) -> None:
        self.check.last_ping = now()
        self.check.status = "up"
        self.check.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertContains(r, "ic-up")

    @override_settings(SITE_NAME="Mychecks")
    def test_it_shows_red_check(self) -> None:
        self.check.last_ping = now() - td(days=3)
        self.check.status = "up"
        self.check.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertContains(r, "ic-down")

        self.assertContains(r, "favicon_down.svg")
        self.assertContains(r, "1 down – Mychecks")

    def test_it_shows_amber_check(self) -> None:
        self.check.last_ping = now() - td(days=1, minutes=30)
        self.check.status = "up"
        self.check.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertContains(r, "ic-grace")

    def test_it_saves_sort_field(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        self.client.get(self.url + "?sort=name")

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.sort, "name")

    def test_it_includes_filters_in_sort_urls(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url + "?tag=foo&search=bar")
        self.assertContains(r, "?tag=foo&search=bar&sort=name")
        self.assertContains(r, "?tag=foo&search=bar&sort=last_ping")

    def test_it_ignores_bad_sort_value(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        self.client.get(self.url + "?sort=invalid")

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.sort, "created")

    def test_it_shows_started_but_down_badge(self) -> None:
        self.check.last_start = now()
        self.check.tags = "foo"
        self.check.status = "down"
        self.check.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertContains(r, """<div data-tooltip="1 of 1 down" class="btn btn-sm down ">foo</div>""")

    def test_it_shows_grace_badge(self) -> None:
        self.check.last_ping = now() - td(days=1, minutes=10)
        self.check.tags = "foo"
        self.check.status = "up"
        self.check.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertContains(r, """<div data-tooltip="1 up" class="btn btn-sm grace ">foo</div>""")

    def test_it_shows_grace_started_badge(self) -> None:
        self.check.last_start = now()
        self.check.last_ping = now() - td(days=1, minutes=10)
        self.check.tags = "foo"
        self.check.status = "up"
        self.check.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertContains(r, """<div data-tooltip="1 up" class="btn btn-sm grace ">foo</div>""")

    def test_it_shows_slugs(self) -> None:
        self.project.show_slugs = True
        self.project.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertContains(r, "alice-was-here")
        self.assertNotContains(r, "(not unique)")

    def test_it_shows_not_unique_note(self) -> None:
        self.project.show_slugs = True
        self.project.save()

        dupe = Check(project=self.project, name="Alice Was Here")
        dupe.slug = "alice-was-here"
        dupe.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertContains(r, "alice-was-here")
        self.assertContains(r, "(not unique)")

    def test_it_saves_url_format_preference(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        self.client.get(self.url + "?urls=slug")

        self.project.refresh_from_db()
        self.assertTrue(self.project.show_slugs)

    def test_it_outputs_period_grace_as_integers(self) -> None:
        self.check.timeout = td(seconds=123)
        self.check.grace = td(seconds=456)
        self.check.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)

        self.assertContains(r, 'data-timeout="123"')
        self.assertContains(r, 'data-grace="456"')

    def test_it_denies_a_superuser_outsider(self) -> None:
        self.charlie.is_superuser = True
        self.charlie.save()

        self.client.login(username="charlie@example.org", password="password")
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 404)

    def test_it_filters_by_status(self) -> None:
        self.check.last_ping = now()
        self.check.status = "up"
        self.check.save()

        down = Check.objects.create(project=self.project, name="Down Check", status="down")

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url + "?status=down")
        self.assertContains(r, f'<tr id="{down.code}" class="checks-row" >', status_code=200)
        self.assertContains(r, f'<tr id="{self.check.code}" class="checks-row" style="display: none">')

    def test_status_filter_matches_started_checks(self) -> None:
        self.check.last_ping = now()
        self.check.last_start = now()
        self.check.status = "up"
        self.check.save()

        idle = Check.objects.create(project=self.project, name="Idle Check", status="up", last_ping=now())

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url + "?status=started")
        self.assertContains(r, f'<tr id="{self.check.code}" class="checks-row" >', status_code=200)
        self.assertContains(r, f'<tr id="{idle.code}" class="checks-row" style="display: none">')

    def test_it_shows_last_duration_header(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertNotContains(r, "Last Duration", status_code=200)

        self.check.last_duration = td(seconds=75)
        self.check.save()

        r = self.client.get(self.url)
        self.assertContains(r, "Last Duration", status_code=200)
