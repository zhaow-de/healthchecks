from __future__ import annotations

from unittest import TestCase
from unittest.mock import call, patch

from django.test.utils import override_settings
from statsd.client.udp import StatsClient

from hc.lib.statsd import NoopClient, get_client


class StatsdTestCase(TestCase):
    @override_settings(STATSD_HOST="localhost")
    def test_it_initializes_udp_client(self) -> None:
        client = get_client()
        self.assertTrue(isinstance(client, StatsClient))
        self.assertEqual(client._addr, ("127.0.0.1", 8125))
        client.close()

    @override_settings(STATSD_HOST="localhost:1234")
    def test_it_parses_port(self) -> None:
        client = get_client()
        self.assertTrue(isinstance(client, StatsClient))
        self.assertEqual(client._addr, ("127.0.0.1", 1234))
        client.close()

    @override_settings(STATSD_HOST=None)
    def test_it_initializes_noop_client(self) -> None:
        client = get_client()
        self.assertTrue(isinstance(client, NoopClient))
        client.close()

    def test_noop_client_discards_metrics(self) -> None:
        client = NoopClient()
        with patch.object(client, "_send", wraps=client._send) as send:
            self.assertIsNone(client.incr("hc.test.counter"))
            self.assertIsNone(client.gauge("hc.test.gauge", 5))

        # The base class formats each metric and hands it to _send, which drops it
        self.assertEqual(
            send.call_args_list,
            [call("hc.test.counter:1|c"), call("hc.test.gauge:5|g")],
        )

    def test_noop_client_has_no_pipeline(self) -> None:
        self.assertIsNone(NoopClient().pipeline())
