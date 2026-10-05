import json
from unittest.mock import Mock, patch

from hc.api.decorators import API_BODY_LIMIT
from hc.api.models import Check
from hc.test import BaseTestCase, TestHttpResponse


class AuthTestCase(BaseTestCase):
    def get(self, key: str) -> TestHttpResponse:
        return self.client.get("/api/v3/checks/", HTTP_X_API_KEY=key)

    def post(self, key: str) -> TestHttpResponse:
        return self.client.post(
            "/api/v3/checks/",
            {"name": "Foo"},
            content_type="application/json",
            HTTP_X_API_KEY=key,
        )

    def test_it_refuses_a_plain_text_key(self) -> None:
        self.project.api_key = "X" * 32
        self.project.save()

        r = self.get(key="X" * 32)
        self.assertEqual(r.status_code, 401)

    def test_it_refuses_a_plain_text_readonly_key(self) -> None:
        self.project.api_key_readonly = "R" * 32
        self.project.save()

        r = self.get(key="R" * 32)
        self.assertEqual(r.status_code, 401)

    def test_it_rejects_wrong_key(self) -> None:
        r = self.get(key="W" * 32)
        self.assertEqual(r.status_code, 401)

    def test_ro_endpoint_accepts_hashed_api_key(self) -> None:
        r = self.get(key=self.api_key)
        self.assertEqual(r.status_code, 200)

    def test_ro_endpoint_accepts_hashed_readonly_key(self) -> None:
        key = self.project.set_api_key_readonly()
        self.project.save()

        r = self.get(key=key)
        self.assertEqual(r.status_code, 200)

    def test_rw_endpoint_accepts_hashed_api_key(self) -> None:
        r = self.post(key=self.api_key)
        self.assertEqual(r.status_code, 201)

    def test_rw_endpoint_rejects_hashed_readonly_key(self) -> None:
        key = self.project.set_api_key_readonly()
        self.project.save()

        r = self.post(key=key)
        self.assertEqual(r.status_code, 401)

    @patch("hc.accounts.models.hmac.compare_digest")
    def test_it_does_not_compare_digest_to_a_stored_value_without_a_hash(self, mock_compare: Mock) -> None:
        # A stored value with no "." holds no digest to compare with
        self.project.api_key = "X" * 32
        self.project.save()

        self.post(key="hcw_" + "X" * 28)
        self.assertFalse(mock_compare.called)

    def test_it_checks_a_header_key_before_parsing_the_body(self) -> None:
        r = self.client.post(
            "/api/v3/checks/",
            "this is not json",
            content_type="application/json",
            HTTP_X_API_KEY="hcw_" + "W" * 28,
        )
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()["error"], "wrong api key")

    def test_it_refuses_deeply_nested_json(self) -> None:
        r = self.client.post("/api/v3/checks/", "[" * 50_000, content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"], "could not parse request body")

    def test_it_refuses_a_body_over_the_limit_before_the_key_lookup(self) -> None:
        body = json.dumps({"name": "Foo", "desc": "a" * API_BODY_LIMIT})
        with self.assertNumQueries(0):
            r = self.client.post("/api/v3/checks/", body, content_type="application/json", HTTP_X_API_KEY=self.api_key)

        self.assertEqual(r.status_code, 413)
        self.assertEqual(r.json()["error"], "request body too large")
        self.assertEqual(r["Access-Control-Allow-Origin"], "*")
        self.assertFalse(Check.objects.exists())

    def test_it_accepts_a_body_at_the_limit(self) -> None:
        doc = {"name": "Foo", "padding": ""}
        doc["padding"] = "a" * (API_BODY_LIMIT - len(json.dumps(doc)))
        body = json.dumps(doc)
        self.assertEqual(len(body), API_BODY_LIMIT)

        r = self.client.post("/api/v3/checks/", body, content_type="application/json", HTTP_X_API_KEY=self.api_key)
        self.assertEqual(r.status_code, 201)
