from __future__ import annotations

from datetime import date, datetime, timezone
from datetime import timedelta as td

from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.core import mail
from django.test import RequestFactory
from django.urls import reverse
from django.utils.timezone import now

from hc.accounts.admin import HcUserAdmin, ProfileAdmin
from hc.accounts.models import Credential, Profile, Project
from hc.api.models import Channel, Check
from hc.test import BaseTestCase, TestHttpResponse


class AccountsAdminTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()

        self.alice.is_staff = True
        self.alice.is_superuser = True
        self.alice.save()

    def messages(self, r: TestHttpResponse) -> list[str]:
        return [str(m) for m in get_messages(r.wsgi_request)]

    def test_it_shows_profiles(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        r = self.client.get("/admin/accounts/profile/")
        self.assertContains(r, "alice@example.org")
        self.assertContains(r, "charlie@example.org")

    def test_it_escapes_emails_when_showing_profiles(self) -> None:
        self.charlie.email = "charlie&friends@example.org"
        self.charlie.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get("/admin/accounts/profile/")
        # The amperstand should be escaped
        self.assertNotContains(r, "charlie&friends@example.org")

    def test_it_shows_projects(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        r = self.client.get("/admin/accounts/project/")
        self.assertContains(r, "Alices Project")
        self.assertContains(r, "Default Project for charlie@example.org")

    def test_it_escapes_emails_when_showing_projects(self) -> None:
        self.charlie.email = "charlie&friends@example.org"
        self.charlie.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get("/admin/accounts/project/")
        # The amperstand should be escaped
        self.assertNotContains(r, "charlie&friends@example.org")

    def test_it_highlights_check_count_above_one(self) -> None:
        Check.objects.create(project=self.project)
        Check.objects.create(project=self.project)
        Check.objects.create(project=self.charlies_project)

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(reverse("admin:accounts_profile_changelist"))
        self.assertContains(r, '<td class="field-checks"><b>2</b></td>', html=True)
        self.assertContains(r, '<td class="field-checks">1</td>', html=True)

    def test_it_filters_profiles_by_check_count(self) -> None:
        Check.objects.bulk_create([Check(project=self.project) for _ in range(11)])
        Check.objects.bulk_create([Check(project=self.charlies_project) for _ in range(10)])

        self.client.login(username="alice@example.org", password="password")
        url = reverse("admin:accounts_profile_changelist")
        r = self.client.get(url, {"num_checks": "10"})
        self.assertEqual(list(r.context["cl"].result_list), [self.profile])

        r = self.client.get(url)
        self.assertEqual(len(r.context["cl"].result_list), 2)

    def test_profile_date_columns_show_dates(self) -> None:
        self.profile.last_active_date = datetime(2020, 1, 2, 3, tzinfo=timezone.utc)

        profile_admin = ProfileAdmin(Profile, admin.site)
        self.assertEqual(profile_admin.last_active(self.profile), date(2020, 1, 2))

    def test_profile_date_columns_handle_missing_dates(self) -> None:
        profile_admin = ProfileAdmin(Profile, admin.site)
        self.assertIsNone(profile_admin.last_active(self.charlies_profile))

    def test_it_has_no_login_as_action(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        payload = {"action": "login", "_selected_action": [self.charlies_profile.id]}
        r = self.client.post(reverse("admin:accounts_profile_changelist"), payload)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.messages(r), ["No action selected."])
        self.assertEqual(self.client.session["_auth_user_id"], str(self.alice.id))

    def test_send_report_action_sends_report(self) -> None:
        Check.objects.create(project=self.project, name="Foo", status="up", last_ping=now())

        self.client.login(username="alice@example.org", password="password")
        payload = {"action": "send_report", "_selected_action": [self.profile.id]}
        r = self.client.post(reverse("admin:accounts_profile_changelist"), payload)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.messages(r), ["1 email(s) sent"])

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["alice@example.org"])
        self.assertEqual(mail.outbox[0].subject, "Monthly Report")
        self.assertEmailContains("Foo")

    def test_send_nag_action_sends_nag(self) -> None:
        self.profile.nag_period = td(hours=1)
        self.profile.save()
        Check.objects.create(project=self.project, name="Foo", status="down", last_ping=now())

        self.client.login(username="alice@example.org", password="password")
        payload = {"action": "send_nag", "_selected_action": [self.profile.id]}
        r = self.client.post(reverse("admin:accounts_profile_changelist"), payload)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.messages(r), ["1 email(s) sent"])

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["alice@example.org"])
        self.assertEqual(mail.outbox[0].subject, "Reminder: 1 check still down")

    def test_remove_totp_action_clears_totp(self) -> None:
        self.charlies_profile.totp = "0" * 32
        self.charlies_profile.totp_created = now()
        self.charlies_profile.save()

        self.client.login(username="alice@example.org", password="password")
        payload = {"action": "remove_totp", "_selected_action": [self.charlies_profile.id]}
        r = self.client.post(reverse("admin:accounts_profile_changelist"), payload)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.messages(r), ["Removed TOTP for 1 profile(s)"])

        self.charlies_profile.refresh_from_db()
        self.assertIsNone(self.charlies_profile.totp)
        self.assertIsNone(self.charlies_profile.totp_created)

    def test_it_shows_project_usage(self) -> None:
        Check.objects.create(project=self.project)
        Channel.objects.create(project=self.project, kind="webhook")
        for _ in range(2):
            Check.objects.create(project=self.charlies_project)
            Channel.objects.create(project=self.charlies_project, kind="webhook")
        Project.objects.create(owner=self.alice, name="Empty Project")

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(reverse("admin:accounts_project_changelist"))
        self.assertContains(r, '<td class="field-usage">1 check, 1 channel</td>', html=True)
        self.assertContains(
            r,
            '<td class="field-usage"><strong>2 checks</strong>, <strong>2 channels</strong></td>',
            html=True,
        )
        self.assertContains(r, '<td class="field-usage">0 checks, 0 channels</td>', html=True)

    def test_it_shows_users(self) -> None:
        Check.objects.create(project=self.project)
        Check.objects.create(project=self.project)
        Channel.objects.create(project=self.project, kind="webhook")

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(reverse("admin:auth_user_changelist"))
        self.assertEqual(len(r.context["cl"].result_list), 2)
        self.assertContains(r, '<td class="field-usage"><strong>2 checks</strong>, 1 channel</td>', html=True)
        self.assertContains(r, '<td class="field-usage">0 checks, 0 channels</td>', html=True, count=1)

    def test_it_does_not_add_users(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(reverse("admin:auth_user_changelist"))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, reverse("admin:auth_user_add"))

        r = self.client.get(reverse("admin:auth_user_add"))
        self.assertEqual(r.status_code, 403)

        payload = {"username": "eve", "password1": "Correct-Horse-9", "password2": "Correct-Horse-9"}
        r = self.client.post(reverse("admin:auth_user_add"), payload)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(User.objects.count(), 2)

    def test_user_list_shows_last_active_date(self) -> None:
        last_active = datetime(2020, 1, 2, 3, tzinfo=timezone.utc)
        self.profile.last_active_date = last_active
        self.profile.save()

        request = RequestFactory().get("/")
        request.user = self.alice
        user_admin = HcUserAdmin(User, admin.site)
        users = {u.id: u for u in user_admin.get_queryset(request)}

        self.assertEqual(user_admin.last_active(users[self.alice.id]), last_active)
        self.assertIsNone(user_admin.last_active(users[self.charlie.id]))

    def test_it_offers_no_activate_or_deactivate_action(self) -> None:
        # Deactivating the one user would lock the instance: createsuperuser refuses
        # while a user exists
        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(reverse("admin:auth_user_changelist"))
        self.assertNotContains(r, 'value="deactivate"', status_code=200)
        self.assertNotContains(r, 'value="activate"')

    def test_it_keeps_the_user_able_to_log_in(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        url = reverse("admin:auth_user_change", args=[self.alice.id])
        r = self.client.get(url)
        for field in ("email", "is_active", "is_staff", "is_superuser"):
            self.assertNotContains(r, f'name="{field}"', status_code=200)

        # A save with a blank email and the boxes left out, as unticked checkboxes are,
        # keeps all four
        payload = {
            "username": "alice",
            "email": "",
            "date_joined_0": "2020-01-01",
            "date_joined_1": "00:00:00",
        }
        r = self.client.post(url, payload)
        self.assertRedirects(r, reverse("admin:auth_user_changelist"))
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.email, "alice@example.org")
        self.assertTrue(self.alice.is_active)
        self.assertTrue(self.alice.is_staff)
        self.assertTrue(self.alice.is_superuser)

    def test_it_keeps_password_log_in_on(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        url = reverse("admin:auth_user_password_change", args=[self.alice.id])
        r = self.client.get(url)
        self.assertNotContains(r, 'name="usable_password"', status_code=200)

        r = self.client.post(url, {"usable_password": "false", "unset-password": "1"})
        self.assertEqual(r.status_code, 200)
        self.alice.refresh_from_db()
        self.assertTrue(self.alice.check_password("password"))

    def test_it_changes_the_password(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        url = reverse("admin:auth_user_password_change", args=[self.alice.id])
        payload = {"password1": "Correct-Horse-9", "password2": "Correct-Horse-9"}
        r = self.client.post(url, payload)
        self.assertEqual(r.status_code, 302)
        self.alice.refresh_from_db()
        self.assertTrue(self.alice.check_password("Correct-Horse-9"))

    def test_it_runs_the_password_validators(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        url = reverse("admin:auth_user_password_change", args=[self.alice.id])
        payload = {"password1": "1qaz2wsx3edc", "password2": "1qaz2wsx3edc"}
        r = self.client.post(url, payload)
        self.assertContains(r, "This password is too common.")
        self.alice.refresh_from_db()
        self.assertTrue(self.alice.check_password("password"))

    def test_it_shows_credentials(self) -> None:
        Credential.objects.create(user=self.charlie, name="Charlies Yubikey", data=b"")

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(reverse("admin:accounts_credential_changelist"))
        self.assertContains(r, '<td class="field-name">Charlies Yubikey</td>', html=True)
        self.assertContains(r, '<td class="field-email">charlie@example.org</td>', html=True)
