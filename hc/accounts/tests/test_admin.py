from __future__ import annotations

from datetime import date, datetime, timezone
from datetime import timedelta as td

import time_machine
from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.core import mail
from django.test import RequestFactory
from django.urls import reverse
from django.utils.timezone import now

from hc.accounts.admin import HcUserAdmin, ProfileAdmin
from hc.accounts.models import DELETION_GRACE, Credential, Profile
from hc.api.models import Channel, Check
from hc.test import BaseTestCase, TestHttpResponse

CURRENT_TIME = datetime(2020, 1, 15, tzinfo=timezone.utc)


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
        self.assertContains(r, "bob@example.org")

    def test_it_escapes_emails_when_showing_profiles(self) -> None:
        self.bob.email = "bob&friends@example.org"
        self.bob.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get("/admin/accounts/profile/")
        # The amperstand should be escaped
        self.assertNotContains(r, "bob&friends@example.org")

    def test_it_shows_projects(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        r = self.client.get("/admin/accounts/project/")
        self.assertContains(r, "Alices Project")
        self.assertContains(r, "Default Project for bob@example.org")

    def test_it_escapes_emails_when_showing_projects(self) -> None:
        self.bob.email = "bob&friends@example.org"
        self.bob.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get("/admin/accounts/project/")
        # The amperstand should be escaped
        self.assertNotContains(r, "bob&friends@example.org")

    def test_it_highlights_check_count_above_one(self) -> None:
        Check.objects.create(project=self.project)
        Check.objects.create(project=self.project)
        Check.objects.create(project=self.bobs_project)

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(reverse("admin:accounts_profile_changelist"))
        self.assertContains(r, '<td class="field-checks"><b>2</b></td>', html=True)
        self.assertContains(r, '<td class="field-checks">1</td>', html=True)
        self.assertContains(r, '<td class="field-checks">0</td>', html=True)

    def test_it_filters_profiles_by_check_count(self) -> None:
        Check.objects.bulk_create([Check(project=self.project) for _ in range(11)])
        Check.objects.bulk_create([Check(project=self.bobs_project) for _ in range(10)])

        self.client.login(username="alice@example.org", password="password")
        url = reverse("admin:accounts_profile_changelist")
        r = self.client.get(url, {"num_checks": "10"})
        self.assertEqual(list(r.context["cl"].result_list), [self.profile])

        r = self.client.get(url)
        self.assertEqual(len(r.context["cl"].result_list), 3)

    def test_profile_date_columns_show_dates(self) -> None:
        self.profile.last_active_date = datetime(2020, 1, 2, 3, tzinfo=timezone.utc)
        self.profile.deletion_scheduled_date = datetime(2020, 3, 4, 5, tzinfo=timezone.utc)

        profile_admin = ProfileAdmin(Profile, admin.site)
        self.assertEqual(profile_admin.last_active(self.profile), date(2020, 1, 2))
        self.assertEqual(profile_admin.deletion(self.profile), date(2020, 3, 4))

    def test_profile_date_columns_handle_missing_dates(self) -> None:
        profile_admin = ProfileAdmin(Profile, admin.site)
        self.assertIsNone(profile_admin.last_active(self.bobs_profile))
        self.assertIsNone(profile_admin.deletion(self.bobs_profile))

    def test_login_action_logs_in_as_selected_user(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        payload = {"action": "login", "_selected_action": [self.bobs_profile.id]}
        r = self.client.post(reverse("admin:accounts_profile_changelist"), payload)
        self.assertRedirects(r, reverse("hc-index"), fetch_redirect_response=False)
        self.assertEqual(self.client.session["_auth_user_id"], str(self.bob.id))

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
        self.bobs_profile.totp = "0" * 32
        self.bobs_profile.totp_created = now()
        self.bobs_profile.save()

        self.client.login(username="alice@example.org", password="password")
        payload = {"action": "remove_totp", "_selected_action": [self.bobs_profile.id]}
        r = self.client.post(reverse("admin:accounts_profile_changelist"), payload)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.messages(r), ["Removed TOTP for 1 profile(s)"])

        self.bobs_profile.refresh_from_db()
        self.assertIsNone(self.bobs_profile.totp)
        self.assertIsNone(self.bobs_profile.totp_created)

    @time_machine.travel(CURRENT_TIME, tick=False)
    def test_schedule_for_deletion_action_sets_date(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        selected = [self.bobs_profile.id, self.charlies_profile.id]
        payload = {"action": "schedule_for_deletion", "_selected_action": selected}
        r = self.client.post(reverse("admin:accounts_profile_changelist"), payload)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.messages(r), ["2 user(s) scheduled for deletion"])

        for profile in (self.bobs_profile, self.charlies_profile):
            profile.refresh_from_db()
            self.assertEqual(profile.deletion_scheduled_date, CURRENT_TIME + DELETION_GRACE)

        self.profile.refresh_from_db()
        self.assertIsNone(self.profile.deletion_scheduled_date)

    def test_unschedule_for_deletion_action_clears_date(self) -> None:
        for profile in (self.bobs_profile, self.charlies_profile):
            profile.deletion_scheduled_date = now()
            profile.save()

        self.client.login(username="alice@example.org", password="password")
        payload = {"action": "unschedule_for_deletion", "_selected_action": [self.bobs_profile.id]}
        r = self.client.post(reverse("admin:accounts_profile_changelist"), payload)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.messages(r), ["1 user(s) unscheduled for deletion"])

        self.bobs_profile.refresh_from_db()
        self.assertIsNone(self.bobs_profile.deletion_scheduled_date)
        # Charlie was not selected and stays scheduled
        self.charlies_profile.refresh_from_db()
        self.assertIsNotNone(self.charlies_profile.deletion_scheduled_date)

    def test_it_shows_project_usage(self) -> None:
        Check.objects.create(project=self.project)
        Channel.objects.create(project=self.project, kind="webhook")
        for _ in range(2):
            Check.objects.create(project=self.bobs_project)
            Channel.objects.create(project=self.bobs_project, kind="webhook")

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
        self.assertEqual(len(r.context["cl"].result_list), 3)
        self.assertContains(r, '<td class="field-usage"><strong>2 checks</strong>, 1 channel</td>', html=True)
        self.assertContains(r, '<td class="field-usage">0 checks, 0 channels</td>', html=True, count=2)

    def test_user_list_shows_last_active_date(self) -> None:
        last_active = datetime(2020, 1, 2, 3, tzinfo=timezone.utc)
        self.profile.last_active_date = last_active
        self.profile.save()

        request = RequestFactory().get("/")
        request.user = self.alice
        user_admin = HcUserAdmin(User, admin.site)
        users = {u.id: u for u in user_admin.get_queryset(request)}

        self.assertEqual(user_admin.last_active(users[self.alice.id]), last_active)
        self.assertIsNone(user_admin.last_active(users[self.bob.id]))

    def test_activate_action_activates_users(self) -> None:
        self.charlie.is_active = False
        self.charlie.save()

        self.client.login(username="alice@example.org", password="password")
        payload = {"action": "activate", "_selected_action": [self.charlie.id]}
        r = self.client.post(reverse("admin:auth_user_changelist"), payload)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.messages(r), ["1 user(s) activated"])

        self.charlie.refresh_from_db()
        self.assertTrue(self.charlie.is_active)

    def test_deactivate_action_deactivates_users(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        payload = {"action": "deactivate", "_selected_action": [self.bob.id, self.charlie.id]}
        r = self.client.post(reverse("admin:auth_user_changelist"), payload)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.messages(r), ["2 user(s) deactivated"])

        for user in (self.bob, self.charlie):
            user.refresh_from_db()
            self.assertFalse(user.is_active)
            self.assertFalse(user.has_usable_password())

        self.alice.refresh_from_db()
        self.assertTrue(self.alice.is_active)

    def test_it_shows_credentials(self) -> None:
        Credential.objects.create(user=self.bob, name="Bobs Yubikey", data=b"")

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(reverse("admin:accounts_credential_changelist"))
        self.assertContains(r, '<td class="field-name">Bobs Yubikey</td>', html=True)
        self.assertContains(r, '<td class="field-email">bob@example.org</td>', html=True)
