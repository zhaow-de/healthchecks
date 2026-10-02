from __future__ import annotations

from django.utils.timezone import now

from hc.api.models import Channel, Check, Flip, Notification
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
