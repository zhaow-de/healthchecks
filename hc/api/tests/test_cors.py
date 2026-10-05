from uuid import uuid4

from hc.api.models import Check
from hc.test import BaseTestCase


class CorsTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.check = Check.objects.create(project=self.project)
        self.single_url = f"/api/v3/checks/{self.check.code}"

    def test_it_allows_the_content_type_header(self) -> None:
        r = self.client.options(
            "/api/v3/checks/",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="content-type,x-api-key",
        )
        self.assertEqual(r.status_code, 204)
        self.assertEqual(r["Access-Control-Allow-Headers"], "X-Api-Key, Content-Type")

    def test_it_lists_the_methods_in_a_fixed_order(self) -> None:
        cases = {
            "/api/v3/checks/": "GET, POST, OPTIONS",
            self.single_url: "GET, POST, DELETE, OPTIONS",
            self.single_url + "/pause": "POST, OPTIONS",
            self.single_url + "/pings/": "GET, OPTIONS",
        }
        for url, methods in cases.items():
            with self.subTest(url=url):
                r = self.client.options(url)
                self.assertEqual(r["Access-Control-Allow-Methods"], methods)

    def test_it_names_the_allowed_methods_on_405(self) -> None:
        r = self.client.put("/api/v3/checks/", HTTP_X_API_KEY=self.api_key)
        self.assertEqual(r.status_code, 405)
        self.assertEqual(r["Allow"], "GET, POST, OPTIONS")
        self.assertEqual(r["Access-Control-Allow-Origin"], "*")

    def test_it_puts_the_headers_on_a_404(self) -> None:
        missing = f"/api/v3/checks/{uuid4()}"
        cases = [
            ("GET", missing),
            ("POST", missing),
            ("DELETE", missing),
            ("POST", missing + "/pause"),
            ("POST", missing + "/resume"),
            ("GET", missing + "/pings/"),
            ("GET", missing + "/flips/"),
            ("GET", self.single_url + "/pings/1/body"),
        ]
        for method, url in cases:
            with self.subTest(method=method, url=url):
                r = self.client.generic(method, url, HTTP_X_API_KEY=self.api_key)
                self.assertEqual(r.status_code, 404)
                self.assertEqual(r["Access-Control-Allow-Origin"], "*")
                self.assertEqual(r.content, b"")

    def test_it_forbids_caching(self) -> None:
        cases = [
            ("GET", "/api/v3/checks/", self.api_key),
            ("GET", "/api/v3/checks/", ""),
            ("OPTIONS", "/api/v3/checks/", ""),
            ("PUT", "/api/v3/checks/", self.api_key),
            ("GET", self.single_url, self.api_key),
            ("GET", f"/api/v3/checks/{uuid4()}", self.api_key),
            ("GET", "/api/v3/channels/", self.api_key),
        ]
        for method, url, key in cases:
            with self.subTest(method=method, url=url, key=bool(key)):
                r = self.client.generic(method, url, HTTP_X_API_KEY=key)
                self.assertIn("no-store", r["Cache-Control"])
