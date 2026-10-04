import time_machine

from hc.test import BaseTestCase


@time_machine.travel("2020-01-01 00:00+00:00")
class OnCalendarPreviewTestCase(BaseTestCase):
    url = "/checks/oncalendar_preview/"

    def test_it_works(self) -> None:
        payload = {"schedule": "*:*", "tz": "UTC"}
        self.client.login(username="alice@example.org", password="password")
        r = self.client.post(self.url, payload)
        self.assertContains(r, "oncalendar-preview-title", status_code=200)
        self.assertContains(r, "2020-01-01 00:01:00 UTC")

    def test_it_handles_single_result(self) -> None:
        payload = {"schedule": "2020-02-01", "tz": "UTC"}
        self.client.login(username="alice@example.org", password="password")
        r = self.client.post(self.url, payload)
        self.assertContains(r, "oncalendar-preview-title", status_code=200)
        self.assertContains(r, "2020-02-01 00:00:00 UTC")

    def test_it_handles_invalid_timezone(self) -> None:
        payload = {"schedule": "*:*", "tz": "Surprise/Nowhere"}
        self.client.login(username="alice@example.org", password="password")
        r = self.client.post(self.url, payload)
        self.assertContains(r, "Invalid timezone.", status_code=200)
        self.assertNotContains(r, "oncalendar-preview-title")

    def test_it_handles_invalid_schedule(self) -> None:
        payload = {"schedule": "not a schedule", "tz": "UTC"}
        self.client.login(username="alice@example.org", password="password")
        r = self.client.post(self.url, payload)
        self.assertContains(r, "Invalid OnCalendar expression.", status_code=200)

    def test_it_handles_schedule_without_future_dates(self) -> None:
        # A valid expression whose only match is in the past
        payload = {"schedule": "2019-01-01", "tz": "UTC"}
        self.client.login(username="alice@example.org", password="password")
        r = self.client.post(self.url, payload)
        self.assertContains(r, "Invalid OnCalendar expression.", status_code=200)

    def test_it_shows_utc_rows_for_non_utc_timezone(self) -> None:
        payload = {"schedule": "12:00", "tz": "Europe/Riga"}
        self.client.login(username="alice@example.org", password="password")
        r = self.client.post(self.url, payload)
        self.assertContains(r, "oncalendar-preview-title", status_code=200)
        self.assertContains(r, "2020-01-01 12:00:00 EET")
        self.assertContains(r, "2020-01-01 10:00:00 UTC")
        # Non-UTC previews are limited to 4 dates
        self.assertContains(r, 'class="in-utc"', count=4)
