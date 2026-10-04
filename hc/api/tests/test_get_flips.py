from __future__ import annotations

from datetime import UTC, datetime
from datetime import timedelta as td

from django.utils.timezone import now

from hc.api.models import Check, Flip
from hc.test import BaseTestCase, TestHttpResponse


class GetFlipsTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()

        self.a1 = Check(project=self.project, name="Alice 1")
        self.a1.timeout = td(seconds=3600)
        self.a1.grace = td(seconds=900)
        self.a1.n_pings = 0
        self.a1.status = "new"
        self.a1.tags = "a1-tag a1-additional-tag"
        self.a1.desc = "This is description"
        self.a1.save()

        Flip.objects.create(
            owner=self.a1,
            created=datetime(2020, 6, 1, 12, 24, 32, 123000, tzinfo=UTC),
            old_status="new",
            new_status="up",
        )

        self.url = f"/api/v3/checks/{self.a1.code}/flips/"

    def get(self, api_key: str | None = None, qs: str = "") -> TestHttpResponse:
        return self.client.get(self.url + qs, HTTP_X_API_KEY=self.api_key if api_key is None else api_key)

    def test_it_works(self) -> None:
        r = self.get()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Access-Control-Allow-Origin"], "*")

        doc = r.json()
        self.assertEqual(len(doc["flips"]), 1)

        flip = doc["flips"][0]
        # Microseconds (123000) should be stripped out
        self.assertEqual(flip["timestamp"], "2020-06-01T12:24:32+00:00")
        self.assertEqual(flip["up"], 1)

    def test_it_works_with_unique_key(self) -> None:
        url = f"/api/v3/checks/{self.a1.unique_key}/flips/"
        r = self.client.get(url, HTTP_X_API_KEY=self.api_key)
        self.assertEqual(r.status_code, 200)

        doc = r.json()
        self.assertEqual(len(doc["flips"]), 1)

    def test_readonly_key_is_allowed(self) -> None:
        ro_key = self.project.set_api_key_readonly()
        self.project.save()

        r = self.get(api_key=ro_key)
        self.assertEqual(r.status_code, 200)

    def test_it_rejects_post(self) -> None:
        r = self.csrf_client.post(self.url, HTTP_X_API_KEY=self.api_key)
        self.assertEqual(r.status_code, 405)

    def test_it_rejects_non_integer_start(self) -> None:
        r = self.get(qs="?start=abc")
        self.assertEqual(r.status_code, 400)

    def test_it_rejects_negative_start(self) -> None:
        r = self.get(qs="?start=-123")
        self.assertEqual(r.status_code, 400)

    def test_it_filters_by_start(self) -> None:
        r = self.get(qs="?start=1591014300")  # 2020-06-01 12:25:00
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"flips": []})

    def test_it_filters_by_end(self) -> None:
        r = self.get(qs="?end=1591014180")  # 2020-06-01 12:23:00
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"flips": []})

    def test_it_rejects_huge_start(self) -> None:
        r = self.get(qs="?start=12345678901234567890")
        self.assertEqual(r.status_code, 400)

    def test_it_rejects_negative_seconds(self) -> None:
        r = self.get(qs="?seconds=-123")
        self.assertEqual(r.status_code, 400)

    def test_it_rejects_huge_seconds(self) -> None:
        r = self.get(qs="?seconds=12345678901234567890")
        self.assertEqual(r.status_code, 400)

    def test_it_handles_missing_api_key(self) -> None:
        r = self.client.get(self.url)
        self.assertContains(r, "missing api key", status_code=401)

    def test_it_filters_by_seconds(self) -> None:
        recent = Flip.objects.create(
            owner=self.a1,
            created=now() - td(minutes=5),
            old_status="up",
            new_status="down",
        )

        r = self.get(qs="?seconds=3600")
        self.assertEqual(r.status_code, 200)

        doc = r.json()
        self.assertEqual(len(doc["flips"]), 1)
        self.assertEqual(doc["flips"][0]["timestamp"], recent.created.replace(microsecond=0).isoformat())
        self.assertEqual(doc["flips"][0]["up"], 0)

    def test_it_rejects_check_from_another_project(self) -> None:
        charlies_check = Check.objects.create(project=self.charlies_project)

        url = f"/api/v3/checks/{charlies_check.code}/flips/"
        r = self.client.get(url, HTTP_X_API_KEY=self.api_key)
        self.assertEqual(r.status_code, 403)

    def test_it_handles_missing_unique_key(self) -> None:
        url = f"/api/v3/checks/{'a' * 40}/flips/"
        r = self.client.get(url, HTTP_X_API_KEY=self.api_key)
        self.assertEqual(r.status_code, 404)
