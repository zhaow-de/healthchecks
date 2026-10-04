from django.contrib.auth.models import User
from django.core import mail
from django.urls import reverse
from django.utils.timezone import now

from hc.accounts.models import Credential
from hc.test import BaseTestCase


class AccountsAdminTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()

        self.alice.is_staff = True
        self.alice.is_superuser = True
        self.alice.save()

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
        self.assertContains(r, '<td class="field-owner nowrap">charlie</td>', html=True)

    def test_it_escapes_emails_when_showing_projects(self) -> None:
        self.charlie.email = "charlie&friends@example.org"
        self.charlie.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get("/admin/accounts/project/")
        # The amperstand should be escaped
        self.assertNotContains(r, "charlie&friends@example.org")

    def test_it_offers_no_profile_actions(self) -> None:
        self.profile.totp = "0" * 32
        self.profile.totp_created = now()
        self.profile.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(reverse("admin:accounts_profile_changelist"))
        self.assertNotContains(r, 'name="action"', status_code=200)

        # Neither a log-in-as nor a TOTP removal, nor a report sent from here
        for action in ("login", "remove_totp", "send_report", "send_nag"):
            payload = {"action": action, "_selected_action": [self.profile.id]}
            self.client.post(reverse("admin:accounts_profile_changelist"), payload)

        self.assertEqual(self.client.session["_auth_user_id"], str(self.alice.id))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.totp, "0" * 32)
        self.assertEqual(len(mail.outbox), 0)

    def test_it_does_not_show_totp_fields(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(reverse("admin:accounts_profile_change", args=[self.profile.id]))
        self.assertContains(r, 'name="tz"')
        self.assertNotContains(r, 'name="totp"')
        self.assertNotContains(r, 'name="totp_created"')

    def test_it_does_not_add_profiles(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(reverse("admin:accounts_profile_add"))
        self.assertEqual(r.status_code, 403)

    def test_it_does_not_delete_profiles(self) -> None:
        self.profile.totp = "0" * 32
        self.profile.totp_created = now()
        self.profile.save()

        self.client.login(username="alice@example.org", password="password")
        r = self.client.post(reverse("admin:accounts_profile_delete", args=[self.profile.id]), {"post": "yes"})
        self.assertEqual(r.status_code, 403)

        r = self.client.get(reverse("admin:accounts_profile_changelist"))
        self.assertNotContains(r, 'value="delete_selected"', status_code=200)

        payload = {"action": "delete_selected", "_selected_action": [self.profile.id], "post": "yes"}
        self.client.post(reverse("admin:accounts_profile_changelist"), payload)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.totp, "0" * 32)

    def test_it_shows_users(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(reverse("admin:auth_user_changelist"))
        self.assertEqual(len(r.context["cl"].result_list), 2)
        self.assertContains(r, "charlie@example.org")

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
        self.set_sudo_flag()
        url = reverse("admin:auth_user_password_change", args=[self.alice.id])
        r = self.client.get(url)
        self.assertContains(r, 'name="password1"')
        self.assertNotContains(r, 'name="usable_password"')

        r = self.client.post(url, {"usable_password": "false", "unset-password": "1"})
        self.assertEqual(r.status_code, 200)
        self.alice.refresh_from_db()
        self.assertTrue(self.alice.check_password("password"))

    def test_password_page_requires_sudo_mode(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        url = reverse("admin:auth_user_password_change", args=[self.alice.id])
        r = self.client.get(url)
        self.assertTemplateUsed(r, "accounts/sudo.html")
        self.assertContains(r, "We have sent a confirmation code")
        self.assertEqual(len(mail.outbox), 1)

        payload = {"password1": "Correct-Horse-9", "password2": "Correct-Horse-9"}
        r = self.client.post(url, payload)
        self.assertTemplateUsed(r, "accounts/sudo.html")
        self.alice.refresh_from_db()
        self.assertTrue(self.alice.check_password("password"))

    def test_it_changes_the_password(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        self.set_sudo_flag()
        url = reverse("admin:auth_user_password_change", args=[self.alice.id])
        payload = {"password1": "Correct-Horse-9", "password2": "Correct-Horse-9"}
        r = self.client.post(url, payload)
        self.assertEqual(r.status_code, 302)
        self.alice.refresh_from_db()
        self.assertTrue(self.alice.check_password("Correct-Horse-9"))

    def test_it_runs_the_password_validators(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        self.set_sudo_flag()
        url = reverse("admin:auth_user_password_change", args=[self.alice.id])
        payload = {"password1": "1qaz2wsx3edc", "password2": "1qaz2wsx3edc"}
        r = self.client.post(url, payload)
        self.assertContains(r, "This password is too common.")
        self.alice.refresh_from_db()
        self.assertTrue(self.alice.check_password("password"))

    def test_own_password_page_requires_sudo_mode(self) -> None:
        url = reverse("admin:password_change")
        r = self.client.get(url)
        self.assertRedirects(r, f"/admin/login/?next={url}", fetch_redirect_response=False)

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(url)
        self.assertTemplateUsed(r, "accounts/sudo.html")

        payload = {
            "old_password": "password",
            "new_password1": "Correct-Horse-9",
            "new_password2": "Correct-Horse-9",
        }
        r = self.client.post(url, payload)
        self.assertTemplateUsed(r, "accounts/sudo.html")
        self.alice.refresh_from_db()
        self.assertTrue(self.alice.check_password("password"))

        self.set_sudo_flag()
        r = self.client.post(url, payload)
        self.assertRedirects(r, reverse("admin:password_change_done"))
        self.alice.refresh_from_db()
        self.assertTrue(self.alice.check_password("Correct-Horse-9"))

    def test_password_pages_hide_post_data_on_the_sudo_page(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        urls = (
            reverse("admin:auth_user_password_change", args=[self.alice.id]),
            reverse("admin:password_change"),
        )
        for url in urls:
            r = self.client.post(url, {"old_password": "password", "sudo_code": "123456"})
            self.assertTemplateUsed(r, "accounts/sudo.html")
            self.assertEqual(r.wsgi_request.sensitive_post_parameters, "__ALL__")

    def test_it_shows_credentials(self) -> None:
        Credential.objects.create(user=self.charlie, name="Charlies Yubikey", data=b"")

        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(reverse("admin:accounts_credential_changelist"))
        self.assertContains(r, '<td class="field-name">Charlies Yubikey</td>', html=True)
        self.assertContains(r, '<td class="field-user nowrap">charlie</td>', html=True)

    def test_it_does_not_add_credentials(self) -> None:
        self.client.login(username="alice@example.org", password="password")
        r = self.client.get(reverse("admin:accounts_credential_changelist"))
        self.assertNotContains(r, reverse("admin:accounts_credential_add"), status_code=200)

        r = self.client.get(reverse("admin:accounts_credential_add"))
        self.assertEqual(r.status_code, 403)

        payload = {"name": "Eve's Key", "code": "00000000-0000-0000-0000-000000000000"}
        r = self.client.post(reverse("admin:accounts_credential_add"), payload)
        self.assertEqual(r.status_code, 403)

    def test_it_does_not_delete_credentials(self) -> None:
        c = Credential.objects.create(user=self.alice, name="Alices Yubikey", data=b"")

        self.client.login(username="alice@example.org", password="password")
        r = self.client.post(reverse("admin:accounts_credential_delete", args=[c.id]), {"post": "yes"})
        self.assertEqual(r.status_code, 403)

        r = self.client.get(reverse("admin:accounts_credential_changelist"))
        self.assertNotContains(r, 'value="delete_selected"', status_code=200)

        payload = {"action": "delete_selected", "_selected_action": [c.id], "post": "yes"}
        self.client.post(reverse("admin:accounts_credential_changelist"), payload)
        self.assertTrue(Credential.objects.filter(id=c.id).exists())
