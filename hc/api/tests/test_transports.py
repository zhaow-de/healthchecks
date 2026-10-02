from __future__ import annotations

from unittest.mock import patch

from django.utils.timezone import now

from hc.api.models import Channel, Check, Flip, Notification
from hc.api.transports import RemovedTransport, Transport
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

    def test_removed_transport_is_noop(self) -> None:
        transport = RemovedTransport(self.channel)
        self.assertTrue(transport.is_noop("down"))
        self.assertTrue(transport.is_noop("up"))

    def test_channel_with_removed_transport_sends_nothing(self) -> None:
        self.channel.kind = "retired"
        self.channel.save()

        with patch.dict("hc.api.models.TRANSPORTS", {"retired": ("Retired", RemovedTransport)}):
            self.assertIsInstance(self.channel.transport, RemovedTransport)
            self.assertEqual(self.channel.notify(self.flip), "no-op")

        self.assertFalse(Notification.objects.exists())
