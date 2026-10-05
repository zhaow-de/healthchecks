from typing import Any
from unittest.mock import patch

from hc.api.models import Check
from hc.test import BaseTestCase


class FilteringRulesTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.check = Check.objects.create(project=self.project)

        self.url = f"/checks/{self.check.code}/filtering_rules/"
        self.redirect_url = f"/checks/{self.check.code}/details/"

    def test_it_works(self) -> None:
        payload = {
            "filter_http_body": "on",
            "start_kw": "START",
            "success_kw": "SUCCESS",
            "failure_kw": "ERROR",
            "methods": "POST",
            "manual_resume": "1",
            "filter_default_fail": "1",
        }

        self.client.login(username="alice@example.org", password="password")
        r = self.client.post(self.url, data=payload)
        self.assertRedirects(r, self.redirect_url)

        self.check.refresh_from_db()
        self.assertTrue(self.check.filter_http_body)
        self.assertEqual(self.check.start_kw, "START")
        self.assertEqual(self.check.success_kw, "SUCCESS")
        self.assertEqual(self.check.failure_kw, "ERROR")
        self.assertEqual(self.check.methods, "POST")
        self.assertTrue(self.check.manual_resume)
        self.assertTrue(self.check.filter_default_fail)

    def test_it_rejects_invalid_form(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        r = self.client.post(self.url, data={"filter_http_body": "on", "methods": "PUT"})
        self.assertEqual(r.status_code, 400)

        self.check.refresh_from_db()
        self.assertFalse(self.check.filter_http_body)

    def test_it_clears_methods(self) -> None:
        self.check.methods = "POST"
        self.check.save()

        payload = {"methods": "", "filter_by_subject": "yes"}

        self.client.login(username="alice@example.org", password="password")
        r = self.client.post(self.url, data=payload)
        self.assertRedirects(r, self.redirect_url)

        self.check.refresh_from_db()
        self.assertEqual(self.check.methods, "")

    def test_it_clears_filtering_fields(self) -> None:
        self.check.filter_http_body = True
        self.check.filter_default_fail = True
        self.check.start_kw = "START"
        self.check.success_kw = "SUCCESS"
        self.check.failure_kw = "ERROR"
        self.check.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.post(self.url, data={"methods": ""})
        self.assertRedirects(r, self.redirect_url)

        self.check.refresh_from_db()
        self.assertFalse(self.check.filter_http_body)
        self.assertFalse(self.check.filter_default_fail)
        self.assertEqual(self.check.start_kw, "")
        self.assertEqual(self.check.success_kw, "")
        self.assertEqual(self.check.failure_kw, "")

    def test_it_ignores_email_filter_fields(self) -> None:
        payload = {"filter_subject": "on", "filter_body": "on", "methods": ""}

        self.client.login(username="alice@example.org", password="password")
        r = self.client.post(self.url, data=payload)
        self.assertRedirects(r, self.redirect_url)

        self.check.refresh_from_db()
        self.assertFalse(self.check.filter_subject)
        self.assertFalse(self.check.filter_body)

    def test_it_keeps_keywords_that_the_inert_email_flags_hold(self) -> None:
        # An API client set keywords together with the inert filter_subject flag; the
        # dashboard had HTTP body filtering on, and the user now turns it off
        self.check.filter_subject = True
        self.check.filter_http_body = True
        self.check.start_kw = "START"
        self.check.success_kw = "SUCCESS"
        self.check.failure_kw = "ERROR"
        self.check.filter_default_fail = True
        self.check.save()

        # The dialog submits no keywords while HTTP body filtering is off
        self.client.login(username="alice@example.org", password="password")
        r = self.client.post(self.url, data={"methods": "POST"})
        self.assertRedirects(r, self.redirect_url)

        self.check.refresh_from_db()
        self.assertEqual(self.check.methods, "POST")
        self.assertFalse(self.check.filter_http_body)
        self.assertTrue(self.check.filter_subject)
        self.assertEqual(self.check.start_kw, "START")
        self.assertEqual(self.check.success_kw, "SUCCESS")
        self.assertEqual(self.check.failure_kw, "ERROR")
        self.assertTrue(self.check.filter_default_fail)

    def test_it_keeps_keywords_that_the_inert_filter_body_flag_holds(self) -> None:
        self.check.filter_body = True
        self.check.success_kw = "SUCCESS"
        self.check.failure_kw = "ERROR"
        self.check.filter_default_fail = True
        self.check.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.post(self.url, data={"methods": ""})
        self.assertRedirects(r, self.redirect_url)

        self.check.refresh_from_db()
        self.assertTrue(self.check.filter_body)
        self.assertEqual(self.check.success_kw, "SUCCESS")
        self.assertEqual(self.check.failure_kw, "ERROR")
        self.assertTrue(self.check.filter_default_fail)

    def test_it_replaces_keywords_when_filtering_http_bodies(self) -> None:
        self.check.filter_subject = True
        self.check.success_kw = "OLD"
        self.check.save()

        payload = {"filter_http_body": "on", "success_kw": "NEW", "methods": ""}
        self.client.login(username="alice@example.org", password="password")
        self.client.post(self.url, data=payload)

        self.check.refresh_from_db()
        self.assertTrue(self.check.filter_http_body)
        self.assertEqual(self.check.success_kw, "NEW")

    def test_it_clears_manual_resume_flag(self) -> None:
        self.check.manual_resume = True
        self.check.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.post(self.url, data={"filter_by_subject": "no"})
        self.assertRedirects(r, self.redirect_url)

        self.check.refresh_from_db()
        self.assertFalse(self.check.manual_resume)

    def test_it_checks_ownership(self) -> None:
        payload = {
            "filter_http_body": "on",
            "success_kw": "SUCCESS",
            "failure_kw": "ERROR",
            "methods": "POST",
            "manual_resume": "1",
        }

        self.client.login(username="charlie@example.org", password="password")
        r = self.client.post(self.url, payload)
        self.assertEqual(r.status_code, 404)

        self.check.refresh_from_db()
        self.assertFalse(self.check.filter_http_body)
        self.assertEqual(self.check.success_kw, "")
        self.assertEqual(self.check.methods, "")
        self.assertFalse(self.check.manual_resume)

    def test_it_handles_a_check_deleted_after_it_was_read(self) -> None:
        def get_and_delete(*args: Any, **kwargs: Any) -> Check:
            check = Check.objects.get(id=self.check.id)
            self.check.delete()
            return check

        self.client.login(username="alice@example.org", password="password")
        with patch("hc.front.views._get_check_for_user", get_and_delete):
            r = self.client.post(self.url, data={"methods": ""})
        self.assertEqual(r.status_code, 404)
