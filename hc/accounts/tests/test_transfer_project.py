from __future__ import annotations

from urllib.parse import quote_plus

from django.core import mail
from django.utils.timezone import now

from hc.accounts.models import Member
from hc.api.models import Check
from hc.test import BaseTestCase


class TransferProjectTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()

        Check.objects.create(project=self.project)

        self.url = f"/projects/{self.project.code}/settings/"

    def test_transfer_project_works(self) -> None:
        self.client.login(username="alice@example.org", password="password")

        form = {"transfer_project": "1", "email": "bob@example.org"}
        r = self.client.post(self.url, form)
        self.assertContains(r, "Transfer initiated!")

        self.bobs_membership.refresh_from_db()
        self.assertIsNotNone(self.bobs_membership.transfer_request_date)

        # Bob should receive an email notification
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        quoted_settings_url = quote_plus(self.url)
        self.assertTrue(f"/?next={quoted_settings_url}" in body)

    def test_it_mangles_project_name_in_transfer_email(self) -> None:
        self.project.name = "https://example.org"
        self.project.save()

        self.client.login(username="alice@example.org", password="password")

        form = {"transfer_project": "1", "email": "bob@example.org"}
        self.client.post(self.url, form)
        self.assertEmailContainsHtml("<span>.</span>")
        self.assertEmailContainsHtml("<span>://</span>")

    def test_transfer_project_checks_ownership(self) -> None:
        self.client.login(username="bob@example.org", password="password")

        form = {"transfer_project": "1", "email": "bob@example.org"}
        r = self.client.post(self.url, form)
        self.assertEqual(r.status_code, 403)

    def test_transfer_project_checks_membership(self) -> None:
        self.client.login(username="alice@example.org", password="password")

        form = {"transfer_project": "1", "email": "charlie@example.org"}
        r = self.client.post(self.url, form)
        self.assertEqual(r.status_code, 400)

    def test_cancel_works(self) -> None:
        self.bobs_membership.transfer_request_date = now()
        self.bobs_membership.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.post(self.url, {"cancel_transfer": "1"})
        self.assertContains(r, "Transfer cancelled!")

        self.bobs_membership.refresh_from_db()
        self.assertIsNone(self.bobs_membership.transfer_request_date)

    def test_cancel_checks_ownership(self) -> None:
        self.bobs_membership.transfer_request_date = now()
        self.bobs_membership.save()

        self.client.login(username="bob@example.org", password="password")
        r = self.client.post(self.url, {"cancel_transfer": "1"})
        self.assertEqual(r.status_code, 403)

        self.bobs_membership.refresh_from_db()
        self.assertIsNotNone(self.bobs_membership.transfer_request_date)

    def test_it_shows_transfer_request(self) -> None:
        self.bobs_membership.transfer_request_date = now()
        self.bobs_membership.save()

        self.client.login(username="bob@example.org", password="password")
        r = self.client.get(self.url)
        self.assertContains(r, "would like to transfer")
        # Enabled: no attribute between its name and its class
        self.assertRegex(r.content.decode(), r'name="accept_transfer"\s+class="btn btn-primary">Accept')

    def test_accept_works(self) -> None:
        self.bobs_membership.transfer_request_date = now()
        self.bobs_membership.save()

        self.client.login(username="bob@example.org", password="password")
        r = self.client.post(self.url, {"accept_transfer": "1"})
        self.assertContains(r, "You are now the owner of this project!")

        self.project.refresh_from_db()
        # Bob should now be the owner
        self.assertEqual(self.project.owner, self.bob)

        # Alice, the previous owner, should now be a member
        m = Member.objects.get(project=self.project, user=self.alice)
        self.assertEqual(m.role, Member.Role.REGULAR)

    def test_accept_requires_a_transfer_request(self) -> None:
        self.client.login(username="bob@example.org", password="password")
        r = self.client.post(self.url, {"accept_transfer": "1"})
        self.assertEqual(r.status_code, 403)

        self.project.refresh_from_db()
        # Alice should still be the owner
        self.assertEqual(self.project.owner, self.alice)

    def test_only_the_proposed_owner_can_accept(self) -> None:
        self.bobs_membership.transfer_request_date = now()
        self.bobs_membership.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.post(self.url, {"accept_transfer": "1"})
        self.assertEqual(r.status_code, 403)

    def test_accept_takes_any_number_of_checks(self) -> None:
        Check.objects.bulk_create([Check(project=self.project) for _ in range(25)])
        Check.objects.bulk_create([Check(project=self.bobs_project) for _ in range(25)])

        self.bobs_membership.transfer_request_date = now()
        self.bobs_membership.save()

        self.client.login(username="bob@example.org", password="password")
        r = self.client.post(self.url, {"accept_transfer": "1"})
        self.assertContains(r, "You are now the owner of this project!")
        # Every check now belongs to a project Bob owns
        self.assertEqual(self.bobs_profile.num_checks_used(), Check.objects.count())

    def test_reject_works(self) -> None:
        self.bobs_membership.transfer_request_date = now()
        self.bobs_membership.save()

        self.client.login(username="bob@example.org", password="password")
        r = self.client.post(self.url, {"reject_transfer": "1"})
        self.assertEqual(r.status_code, 200)

        self.project.refresh_from_db()
        # Alice should still be the owner
        self.assertEqual(self.project.owner, self.alice)

        # The transfer_request_date should be cleared out
        self.bobs_membership.refresh_from_db()
        self.assertIsNone(self.bobs_membership.transfer_request_date)

    def test_only_the_proposed_owner_can_reject(self) -> None:
        self.bobs_membership.transfer_request_date = now()
        self.bobs_membership.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.post(self.url, {"reject_transfer": "1"})
        self.assertEqual(r.status_code, 403)

    def test_readonly_user_can_accept(self) -> None:
        self.bobs_membership.transfer_request_date = now()
        self.bobs_membership.role = "r"
        self.bobs_membership.save()

        self.client.login(username="bob@example.org", password="password")
        self.client.post(self.url, {"accept_transfer": "1"})

        self.project.refresh_from_db()
        # Bob should now be the owner
        self.assertEqual(self.project.owner, self.bob)

        # Alice, the previous owner, should now be a *regular* member
        m = Member.objects.get(user=self.alice, project=self.project)
        self.assertEqual(m.role, "w")
