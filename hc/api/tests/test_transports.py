from datetime import timedelta as td

from django.utils.timezone import now

from hc.api.models import Channel, Check, Flip, Notification, Ping
from hc.api.transports import Transport
from hc.test import BaseTestCase


class TransportBaseTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.check = Check.objects.create(project=self.project)
        self.channel = Channel.objects.create(project=self.project, kind="webhook")

        self.flip = Flip(owner=self.check)
        self.flip.created = now()
        self.flip.old_status = "up"
        self.flip.new_status = "down"

    def test_base_notify_is_abstract(self) -> None:
        transport = Transport(self.channel)
        with self.assertRaises(NotImplementedError):
            transport.notify(self.flip, Notification(channel=self.channel))

    def test_base_is_not_noop(self) -> None:
        transport = Transport(self.channel)
        self.assertFalse(transport.is_noop("down"))
        self.assertFalse(transport.is_noop("up"))

    def test_last_ping_is_the_highest_n_before_the_flip(self) -> None:
        # n=2 came after n=1 although the clock had stepped back; n=3 came after the flip
        Ping.objects.create(owner=self.check, n=1, created=self.flip.created - td(minutes=2))
        Ping.objects.create(owner=self.check, n=2, created=self.flip.created - td(minutes=3))
        Ping.objects.create(owner=self.check, n=3, created=self.flip.created + td(minutes=1))

        ping = Transport(self.channel).last_ping(self.flip)
        assert ping
        self.assertEqual(ping.n, 2)

    def test_last_ping_is_none_without_a_ping_before_the_flip(self) -> None:
        Ping.objects.create(owner=self.check, n=1, created=self.flip.created + td(minutes=1))

        self.assertIsNone(Transport(self.channel).last_ping(self.flip))
