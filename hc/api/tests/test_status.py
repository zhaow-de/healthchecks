from hc.test import BaseTestCase


class StatusTestCase(BaseTestCase):
    url = "/api/v3/status/"

    def test_it_works(self) -> None:
        with self.assertNumQueries(1):
            r = self.client.get(self.url)

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, b"OK")

    def test_it_forbids_caching(self) -> None:
        r = self.client.get(self.url)
        self.assertIn("no-store", r["Cache-Control"])
