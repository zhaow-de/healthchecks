from __future__ import annotations

from hc.test import BaseTestCase


class ProjectTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()

        self.url = f"/projects/{self.project.code}/settings/"

    def test_it_works(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

        self.assertContains(r, "Change Project Name")
        self.assertContains(r, 'data-bs-target="#set-project-name-modal"')
        self.assertContains(r, 'id="set-project-name-modal"')
        self.assertContains(r, "API Access")
        self.assertContains(r, 'id="create-key-form"')
        self.assertContains(r, 'id="revoke-key-modal"')
        self.assertContains(r, 'data-revoke-key="api_key"')
        self.assertContains(r, 'data-create-key="api_key_readonly"')
        self.assertContains(r, 'data-revoke-key="ping_key"')
        self.assertContains(r, 'data-bs-target="#remove-project-modal"')
        self.assertContains(r, 'id="remove-project-modal"')

    def test_it_checks_access(self) -> None:
        self.client.login(username="charlie@example.org", password="password")
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 404)

    def test_it_denies_a_superuser_outsider(self) -> None:
        self.charlie.is_superuser = True
        self.charlie.is_staff = True
        self.charlie.save()

        self.client.login(username="charlie@example.org", password="password")
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 404)

    def test_it_shows_plaintext_keys(self) -> None:
        self.project.api_key_readonly = "R" * 32
        self.project.ping_key = "P" * 22
        self.project.save()

        self.client.login(username="alice@example.org", password="password")

        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

        self.assertContains(r, "X" * 32)
        self.assertContains(r, "R" * 32)
        self.assertContains(r, "P" * 22)

    def test_it_creates_api_key(self) -> None:
        self.client.login(username="alice@example.org", password="password")

        form = {"create_key": "api_key"}
        r = self.client.post(self.url, form)
        self.assertEqual(r.status_code, 200)

        self.project.refresh_from_db()
        self.assertEqual(len(self.project.api_key), 73)
        self.assertContains(r, "key-created-modal")
        self.assertContains(r, "hcw_" + self.project.api_key[:8])

    def test_it_creates_readonly_key(self) -> None:
        self.client.login(username="alice@example.org", password="password")

        form = {"create_key": "api_key_readonly"}
        r = self.client.post(self.url, form)
        self.assertEqual(r.status_code, 200)

        self.project.refresh_from_db()
        self.assertEqual(len(self.project.api_key_readonly), 73)
        self.assertContains(r, "key-created-modal")
        self.assertContains(r, "hcr_" + self.project.api_key_readonly[:8])

    def test_it_creates_ping_key(self) -> None:
        self.project.ping_key = ""
        self.project.save()

        self.client.login(username="alice@example.org", password="password")

        form = {"create_key": "ping_key"}
        r = self.client.post(self.url, form)
        self.assertEqual(r.status_code, 200)

        self.project.refresh_from_db()
        self.assertEqual(len(self.project.ping_key), 22)
        self.assertEqual(self.project.ping_key, self.project.ping_key.lower())
        self.assertContains(r, "key-created-modal")
        self.assertContains(r, "click on it to reveal it")

    def test_it_checks_access_to_create_key(self) -> None:
        self.client.login(username="charlie@example.org", password="password")
        r = self.client.post(self.url, {"create_key": "api_key_readonly"})
        self.assertEqual(r.status_code, 404)

        self.project.refresh_from_db()
        self.assertEqual(self.project.api_key_readonly, "")

    def test_it_revokes_api_key(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        r = self.client.post(self.url, {"revoke_key": "api_key"})
        self.assertEqual(r.status_code, 200)

        self.project.refresh_from_db()
        self.assertEqual(self.project.api_key, "")

    def test_it_revokes_readonly_key(self) -> None:
        self.project.api_key_readonly = "R" * 32
        self.project.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.post(self.url, {"revoke_key": "api_key_readonly"})
        self.assertEqual(r.status_code, 200)

        self.project.refresh_from_db()
        self.assertEqual(self.project.api_key_readonly, "")
        self.assertEqual(self.project.api_key, "X" * 32)

    def test_it_revokes_ping_key(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        r = self.client.post(self.url, {"revoke_key": "ping_key"})
        self.assertEqual(r.status_code, 200)

        self.project.refresh_from_db()
        self.assertIsNone(self.project.ping_key)
        self.assertEqual(self.project.api_key, "X" * 32)

    def test_it_checks_access_to_revoke_key(self) -> None:
        self.client.login(username="charlie@example.org", password="password")
        r = self.client.post(self.url, {"revoke_key": "api_key"})
        self.assertEqual(r.status_code, 404)

        self.project.refresh_from_db()
        self.assertEqual(self.project.api_key, "X" * 32)

    def test_it_sets_project_name(self) -> None:
        self.client.login(username="alice@example.org", password="password")

        form = {"set_project_name": "1", "name": "Alpha Team"}
        r = self.client.post(self.url, form)
        self.assertEqual(r.status_code, 200)

        self.project.refresh_from_db()
        self.assertEqual(self.project.name, "Alpha Team")

    def test_it_checks_access_to_set_project_name(self) -> None:
        self.client.login(username="charlie@example.org", password="password")
        form = {"set_project_name": "1", "name": "Alpha Team"}
        r = self.client.post(self.url, form)
        self.assertEqual(r.status_code, 404)

        self.project.refresh_from_db()
        self.assertEqual(self.project.name, "Alices Project")
