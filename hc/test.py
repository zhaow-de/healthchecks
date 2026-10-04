from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.core.mail import EmailMultiAlternatives
from django.core.signing import TimestampSigner
from django.db.models import QuerySet
from django.test import Client, TestCase

from hc.accounts.models import Profile, Project

if TYPE_CHECKING:
    # _MonkeyPatchedWSGIResponse is defined in django-stubs,
    # we import with a "TestHttpResponse" alias.
    # We list it in __all__ so subclasses can import and use it.
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse
else:
    from django.http import HttpResponse as TestHttpResponse

__all__ = ["BaseTestCase", "TestHttpResponse", "updated_concurrently"]


@contextmanager
def updated_concurrently(**fields: Any) -> Iterator[None]:
    """Make QuerySet.first() return its row, then change that row in the database.

    This is what a concurrent process does when it claims the same row
    between our SELECT and our UPDATE.
    """
    first = QuerySet.first

    def first_then_update(qs: QuerySet[Any]) -> Any:
        obj = first(qs)
        if obj is not None:
            qs.model._default_manager.filter(pk=obj.pk).update(**fields)
        return obj

    with patch.object(QuerySet, "first", first_then_update):
        yield


class BaseTestCase(TestCase):
    def setUp(self) -> None:
        super().setUp()

        self.csrf_client = Client(enforce_csrf_checks=True)

        # Alice owns self.project
        self.alice = User(username="alice", email="alice@example.org")
        self.alice.set_password("password")
        self.alice.save()

        self.project = Project(owner=self.alice)
        self.api_key = self.project.set_api_key()
        self.project.name = "Alices Project"
        self.project.ping_key = "p" * 22
        self.project.save()

        self.profile = Profile(user=self.alice)
        self.profile.save()

        # Charlie is an outsider and should have no access to Alice's stuff
        self.charlie = User(username="charlie", email="charlie@example.org")
        self.charlie.set_password("password")
        self.charlie.save()

        self.charlies_project = Project(owner=self.charlie)
        self.charlies_project.save()

        self.charlies_profile = Profile(user=self.charlie)
        self.charlies_profile.save()

        self.channels_url = f"/projects/{self.project.code}/integrations/"

    def set_sudo_flag(self) -> None:
        session = self.client.session
        session["sudo"] = TimestampSigner().sign("active")
        session.save()

    def assertEmailContainsText(self, fragment: str) -> None:
        """Test if fragment appears in email body."""

        self.assertIn(fragment, mail.outbox[0].body)

    def assertEmailContainsHtml(self, fragment: str) -> None:
        """Test if fragment appears in email's HTML content."""

        email = mail.outbox[0]
        assert isinstance(email, EmailMultiAlternatives)
        html_content, _ = email.alternatives[0]
        assert isinstance(html_content, str)
        self.assertIn(fragment, html_content)

    def assertEmailContains(self, fragment: str) -> None:
        """Test if fragment appears in email's plain text *and* HTML content."""

        self.assertEmailContainsText(fragment)
        self.assertEmailContainsHtml(fragment)

    def assertEmailNotContains(self, fragment: str) -> None:
        """Test if fragment is absent from both plain text *and* HTML content."""

        email = mail.outbox[0]
        self.assertNotIn(fragment, email.body)

        assert isinstance(email, EmailMultiAlternatives)
        html_content, _ = email.alternatives[0]
        assert isinstance(html_content, str)
        self.assertNotIn(fragment, html_content)
