from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth.hashers import get_hasher
from django.http import HttpRequest

from hc.accounts.backends import BasicBackend, EmailBackend, ProfileBackend
from hc.test import BaseTestCase


class BasicBackendTestCase(BaseTestCase):
    def test_get_user_works(self) -> None:
        user = BasicBackend().get_user(self.alice.id)
        assert user
        self.assertEqual(user.email, "alice@example.org")

    def test_get_user_handles_missing_user(self) -> None:
        self.assertIsNone(BasicBackend().get_user(self.alice.id + 1000))


class ProfileBackendTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.request = HttpRequest()
        self.token = self.profile.prepare_token()

    def test_it_works(self) -> None:
        user = ProfileBackend().authenticate(self.request, "alice", self.token)
        self.assertEqual(user, self.alice)

    def test_it_requires_token(self) -> None:
        with self.assertNumQueries(0):
            self.assertIsNone(ProfileBackend().authenticate(self.request, "alice", None))
            self.assertIsNone(ProfileBackend().authenticate(self.request, "alice", ""))

    def test_it_handles_unknown_username(self) -> None:
        self.assertIsNone(ProfileBackend().authenticate(self.request, "eve", self.token))

    def test_it_rejects_token_of_another_user(self) -> None:
        self.charlies_profile.prepare_token()
        self.assertIsNone(ProfileBackend().authenticate(self.request, "charlie", self.token))


class EmailBackendTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.request = HttpRequest()

    def test_it_works(self) -> None:
        user = EmailBackend().authenticate(self.request, "alice@example.org", "password")
        self.assertEqual(user, self.alice)

    def test_it_requires_password(self) -> None:
        # The user's password check would reject these too; the backend
        # rejects them before looking the user up
        with self.assertNumQueries(0):
            self.assertIsNone(EmailBackend().authenticate(self.request, "alice@example.org", None))
            self.assertIsNone(EmailBackend().authenticate(self.request, "alice@example.org", ""))

    def test_it_handles_unknown_email(self) -> None:
        hasher = get_hasher()
        with patch.object(hasher, "encode", wraps=hasher.encode) as encode:
            self.assertIsNone(EmailBackend().authenticate(self.request, "eve@example.org", "password"))

        encode.assert_called_once()
        self.assertEqual(encode.call_args.args[0], "password")

    def test_it_rejects_wrong_password(self) -> None:
        self.assertIsNone(EmailBackend().authenticate(self.request, "alice@example.org", "hunter2"))
