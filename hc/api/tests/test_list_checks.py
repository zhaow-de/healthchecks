from datetime import timedelta as td

from django.conf import settings
from django.utils.timezone import now

from hc.api.models import Channel, Check
from hc.test import BaseTestCase, TestHttpResponse


class ListChecksTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()

        self.now = now().replace(microsecond=0)

        self.a1 = Check(project=self.project, name="Alice 1")
        self.a1.slug = "alice-1"
        self.a1.timeout = td(seconds=3600)
        self.a1.grace = td(seconds=900)
        self.a1.n_pings = 0
        self.a1.status = "new"
        self.a1.tags = "a1-tag a1-additional-tag"
        self.a1.desc = "This is description"
        self.a1.save()

        self.a2 = Check(project=self.project, name="Alice 2")
        self.a2.timeout = td(seconds=86400)
        self.a2.grace = td(seconds=3600)
        self.a2.last_ping = self.now
        self.a2.status = "up"
        self.a2.tags = "a2-tag"
        self.a2.save()

        self.c1 = Channel.objects.create(project=self.project)
        self.a1.channel_set.add(self.c1)

    def get(self) -> TestHttpResponse:
        return self.client.get("/api/v3/checks/", HTTP_X_API_KEY=self.api_key)

    def test_it_does_not_serve_api_v1_or_v2(self) -> None:
        for prefix in ("/api/v1/", "/api/v2/"):
            with self.subTest(prefix=prefix):
                r = self.client.get(prefix + "checks/", HTTP_X_API_KEY=self.api_key)
                self.assertEqual(r.status_code, 404)

    def test_it_works(self) -> None:
        # Expect 3 queries:
        # * check API key
        # * retrieve checks
        # * retrieve  channel codes
        with self.assertNumQueries(3):
            r = self.get()

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Access-Control-Allow-Origin"], "*")

        doc = r.json()
        self.assertEqual(len(doc["checks"]), 2)

        by_name = {}
        for check in doc["checks"]:
            by_name[check["name"]] = check

        a1 = by_name["Alice 1"]
        self.assertEqual(a1["uuid"], str(self.a1.code))
        self.assertEqual(a1["timeout"], 3600)
        self.assertEqual(a1["grace"], 900)
        self.assertEqual(a1["ping_url"], settings.PING_ENDPOINT + str(self.a1.code))
        self.assertEqual(a1["last_ping"], None)
        self.assertEqual(a1["n_pings"], 0)
        self.assertEqual(a1["status"], "new")
        self.assertFalse(a1["started"])
        self.assertEqual(a1["channels"], str(self.c1.code))
        self.assertEqual(a1["desc"], "This is description")

        update_url = settings.SITE_ROOT + f"/api/v3/checks/{self.a1.code}"
        self.assertEqual(a1["update_url"], update_url)
        self.assertEqual(a1["pause_url"], update_url + "/pause")
        self.assertEqual(a1["resume_url"], update_url + "/resume")

        self.assertEqual(a1["next_ping"], None)

        a2 = by_name["Alice 2"]
        self.assertEqual(a2["uuid"], str(self.a2.code))
        self.assertEqual(a2["timeout"], 86400)
        self.assertEqual(a2["grace"], 3600)
        self.assertEqual(a2["ping_url"], settings.PING_ENDPOINT + str(self.a2.code))
        self.assertEqual(a2["status"], "up")
        next_ping = self.now + td(seconds=86400)
        self.assertEqual(a2["last_ping"], self.now.isoformat())
        self.assertEqual(a2["next_ping"], next_ping.isoformat())

    def test_it_lists_the_checks_in_creation_order(self) -> None:
        # a2's empty slug sorts before a1's
        doc = self.get().json()
        self.assertEqual([check["name"] for check in doc["checks"]], ["Alice 1", "Alice 2"])

    def test_it_lists_each_checks_channel_codes(self) -> None:
        c2 = Channel.objects.create(project=self.project)
        self.a1.channel_set.add(c2)

        doc = self.get().json()
        by_name = {check["name"]: check for check in doc["checks"]}
        self.assertEqual(by_name["Alice 1"]["channels"], ",".join(sorted([str(self.c1.code), str(c2.code)])))
        self.assertEqual(by_name["Alice 2"]["channels"], "")

    def test_it_handles_options(self) -> None:
        r = self.client.options("/api/v3/checks/")
        self.assertEqual(r.status_code, 204)
        self.assertIn("GET", r["Access-Control-Allow-Methods"])

    def test_it_shows_only_users_checks(self) -> None:
        Check.objects.create(project=self.charlies_project, name="Charlie 1")

        r = self.get()
        data = r.json()
        self.assertEqual(len(data["checks"]), 2)
        for check in data["checks"]:
            self.assertNotEqual(check["name"], "Charlie 1")

    def test_it_works_with_tags_param(self) -> None:
        r = self.client.get("/api/v3/checks/?tag=a2-tag", HTTP_X_API_KEY=self.api_key)
        self.assertEqual(r.status_code, 200)

        doc = r.json()
        self.assertTrue("checks" in doc)
        self.assertEqual(len(doc["checks"]), 1)

        check = doc["checks"][0]

        self.assertEqual(check["name"], "Alice 2")
        self.assertEqual(check["tags"], "a2-tag")

    def test_it_filters_with_multiple_tags_param(self) -> None:
        r = self.client.get("/api/v3/checks/?tag=a1-tag&tag=a1-additional-tag", HTTP_X_API_KEY=self.api_key)
        self.assertEqual(r.status_code, 200)

        doc = r.json()
        self.assertTrue("checks" in doc)
        self.assertEqual(len(doc["checks"]), 1)

        check = doc["checks"][0]

        self.assertEqual(check["name"], "Alice 1")
        self.assertEqual(check["tags"], "a1-tag a1-additional-tag")

    def test_it_does_not_match_tag_partially(self) -> None:
        r = self.client.get("/api/v3/checks/?tag=tag", HTTP_X_API_KEY=self.api_key)
        self.assertEqual(r.status_code, 200)

        doc = r.json()
        self.assertTrue("checks" in doc)
        self.assertEqual(len(doc["checks"]), 0)

    def test_non_existing_tags_filter_returns_empty_result(self) -> None:
        r = self.client.get(
            "/api/v3/checks/?tag=non_existing_tag_with_no_checks",
            HTTP_X_API_KEY=self.api_key,
        )
        self.assertEqual(r.status_code, 200)

        doc = r.json()
        self.assertTrue("checks" in doc)
        self.assertEqual(len(doc["checks"]), 0)

    def test_readonly_key_works(self) -> None:
        ro_key = self.project.set_api_key_readonly()
        self.project.save()

        # Expect a query to check the API key, and a query to retrieve checks
        with self.assertNumQueries(2):
            r = self.client.get("/api/v3/checks/", HTTP_X_API_KEY=ro_key)

        self.assertEqual(r.status_code, 200)

        # When using readonly keys, the ping URLs should not be exposed:
        self.assertNotContains(r, str(self.a1.code))

    def test_it_reports_started_separately(self) -> None:
        self.a1.last_start = now()
        self.a1.save()
        self.a2.delete()

        r = self.get()

        a1 = r.json()["checks"][0]
        self.assertEqual(a1["status"], "new")
        self.assertTrue(a1["started"])

    def test_it_works_with_slug_param(self) -> None:
        r = self.client.get("/api/v3/checks/?slug=alice-1", HTTP_X_API_KEY=self.api_key)
        self.assertEqual(r.status_code, 200)

        doc = r.json()
        self.assertEqual(len(doc["checks"]), 1)
        check = doc["checks"][0]
        self.assertEqual(check["name"], "Alice 1")
