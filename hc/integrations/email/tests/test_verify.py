from typing import Any
from unittest.mock import patch

from hc.api.models import Channel
from hc.test import BaseTestCase


class VerifyEmailTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.channel = Channel(project=self.project, kind="email")
        self.channel.value = "alice@example.org"
        self.channel.save()

    def test_it_works(self) -> None:
        token = self.channel.make_token()
        url = f"/integrations/{self.channel.code}/verify/{token}/"

        r = self.client.get(url)
        assert r.status_code == 200, r.status_code

        channel = Channel.objects.get(code=self.channel.code)
        assert channel.email_verified

    def test_it_handles_bad_token(self) -> None:
        url = f"/integrations/{self.channel.code}/verify/bad-token/"

        r = self.client.get(url)
        assert r.status_code == 200, r.status_code

        channel = Channel.objects.get(code=self.channel.code)
        assert not channel.email_verified

    def test_missing_channel(self) -> None:
        # Valid UUID, and even valid token but there is no channel for it:
        code = "6837d6ec-fc08-4da5-a67f-08a9ed1ccf62"
        token = self.channel.make_token()
        url = f"/integrations/{code}/verify/{token}/"

        r = self.client.get(url)
        assert r.status_code == 404

    def test_make_token_depends_on_email(self) -> None:
        token = self.channel.make_token()
        self.channel.value = "bob@example.org"
        self.assertNotEqual(self.channel.make_token(), token)

    def test_it_handles_a_channel_deleted_after_it_was_read(self) -> None:
        def get_and_delete(*args: Any, **kwargs: Any) -> Channel:
            channel = Channel.objects.get(id=self.channel.id)
            Channel.objects.filter(id=self.channel.id).delete()
            return channel

        token = self.channel.make_token()
        url = f"/integrations/{self.channel.code}/verify/{token}/"
        with patch("hc.integrations.email.views.get_object_or_404", get_and_delete):
            r = self.client.get(url)
        self.assertEqual(r.status_code, 404)
