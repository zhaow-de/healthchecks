from django.test.utils import override_settings

from hc.api.models import Check
from hc.test import BaseTestCase


@override_settings(METRICS_KEY="foo")
class CollectionRoutesTestCase(BaseTestCase):
    def test_each_collection_answers_with_and_without_its_slash(self) -> None:
        check = Check.objects.create(project=self.project)
        cases = [
            ("GET", "checks", 200),
            ("POST", "checks", 201),
            ("OPTIONS", "checks", 204),
            ("PUT", "checks", 405),
            ("GET", f"checks/{check.code}/pings", 200),
            ("GET", f"checks/{check.code}/flips", 200),
            ("GET", f"checks/{check.unique_key}/flips", 200),
            ("GET", "channels", 200),
            ("GET", "metrics", 200),
            ("GET", "status", 200),
            ("POST", "bounces", 200),
        ]
        for method, path, status in cases:
            for url in (f"/api/v3/{path}/", f"/api/v3/{path}"):
                with self.subTest(method=method, url=url):
                    r = self.client.generic(
                        method,
                        url,
                        "{}",
                        content_type="application/json",
                        HTTP_X_API_KEY=self.api_key,
                        HTTP_X_METRICS_KEY="foo",
                    )
                    self.assertEqual(r.status_code, status)

    @override_settings(DEBUG=True)
    def test_a_post_without_the_slash_creates_a_check_with_debug_on(self) -> None:
        r = self.client.post("/api/v3/checks", {"name": "Foo"}, content_type="application/json", HTTP_X_API_KEY=self.api_key)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Check.objects.get(name="Foo").project, self.project)
