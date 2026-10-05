from typing import Any
from unittest.mock import patch

from django.utils.timezone import now

from hc.accounts.models import Project
from hc.api.models import Check
from hc.test import BaseTestCase


class DeleteCheckTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.check = Check.objects.create(project=self.project)
        self.url = f"/api/v3/checks/{self.check.code}"

    def test_it_works(self) -> None:
        r = self.client.delete(self.url, HTTP_X_API_KEY=self.api_key)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Access-Control-Allow-Origin"], "*")

        # It should be gone--
        self.assertFalse(Check.objects.filter(code=self.check.code).exists())

    def test_it_handles_missing_check(self) -> None:
        self.check.delete()
        r = self.client.delete(self.url, HTTP_X_API_KEY=self.api_key)
        self.assertEqual(r.status_code, 404)

    def test_it_handles_a_check_deleted_after_it_was_read(self) -> None:
        def get_and_delete(*args: Any, **kwargs: Any) -> Check:
            check = Check.objects.get(id=self.check.id)
            self.check.delete()
            return check

        with patch("hc.api.views.get_object_or_404", get_and_delete):
            r = self.client.delete(self.url, HTTP_X_API_KEY=self.api_key)

        self.assertEqual(r.status_code, 404)
        self.assertEqual(r["Access-Control-Allow-Origin"], "*")

    def test_it_handles_a_check_transferred_after_it_was_read(self) -> None:
        other_project = Project.objects.create(owner=self.alice)

        def get_and_transfer(*args: Any, **kwargs: Any) -> Check:
            check = Check.objects.get(id=self.check.id)
            Check.objects.filter(id=self.check.id).update(project=other_project)
            return check

        with patch("hc.api.views.get_object_or_404", get_and_transfer):
            r = self.client.delete(self.url, HTTP_X_API_KEY=self.api_key)

        self.assertEqual(r.status_code, 403)
        self.assertEqual(r["Access-Control-Allow-Origin"], "*")
        self.assertTrue(Check.objects.filter(code=self.check.code, project=other_project).exists())

    def test_it_handles_options(self) -> None:
        r = self.client.options(self.url)
        self.assertEqual(r.status_code, 204)
        self.assertIn("DELETE", r["Access-Control-Allow-Methods"])

    def test_it_handles_missing_api_key(self) -> None:
        r = self.client.delete(self.url)
        self.assertContains(r, "missing api key", status_code=401)

    def test_it_reports_started_separately(self) -> None:
        self.check.last_start = now()
        self.check.save()

        r = self.client.delete(self.url, HTTP_X_API_KEY=self.api_key)
        doc = r.json()
        self.assertEqual(doc["status"], "new")
        self.assertTrue(doc["started"])

    def test_it_rejects_check_from_another_project(self) -> None:
        charlies_check = Check.objects.create(project=self.charlies_project)

        url = f"/api/v3/checks/{charlies_check.code}"
        r = self.client.delete(url, HTTP_X_API_KEY=self.api_key)
        self.assertEqual(r.status_code, 403)

        # The check should still exist
        self.assertTrue(Check.objects.filter(id=charlies_check.id).exists())
