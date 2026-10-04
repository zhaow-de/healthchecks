import os
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase
from django.test.utils import override_settings

from hc.api.tests.test_database import settings_module
from hc.lib.ip import client_ip, parse_ip


class ParseIpTestCase(SimpleTestCase):
    def test_it_returns_an_address(self) -> None:
        self.assertEqual(parse_ip("1.2.3.4"), "1.2.3.4")
        self.assertEqual(parse_ip(" 2001:DB8::1 "), "2001:db8::1")

    def test_it_removes_a_port(self) -> None:
        self.assertEqual(parse_ip("1.2.3.4:5678"), "1.2.3.4")
        self.assertEqual(parse_ip("[2001:db8::1]:443"), "2001:db8::1")
        self.assertEqual(parse_ip("[2001:db8::1]"), "2001:db8::1")

    def test_it_reads_a_bare_ipv6_address_as_an_address(self) -> None:
        # Its last group could be a port only in brackets
        self.assertEqual(parse_ip("2001:db8::1:443"), "2001:db8::1:443")

    def test_it_returns_an_ipv4_mapped_address_in_ipv4_form(self) -> None:
        self.assertEqual(parse_ip("::ffff:1.2.3.4"), "1.2.3.4")
        self.assertEqual(parse_ip("[::ffff:1.2.3.4]:80"), "1.2.3.4")

    def test_it_drops_an_ipv6_zone(self) -> None:
        self.assertEqual(parse_ip("fe80::1%eth0"), "fe80::1")

    def test_it_returns_none_for_anything_else(self) -> None:
        for value in ("", "unknown", "not-an-ip", "1.2.3.4:http", "1.2.3", "01.2.3.4", "[1.2.3.4", "x" * 60, "1.2.3.4:5:6"):
            with self.subTest(value=value):
                self.assertIsNone(parse_ip(value))


class ClientIpTestCase(SimpleTestCase):
    def ip(self, remote_addr: str, xff: str | None = None) -> str | None:
        headers = {"REMOTE_ADDR": remote_addr}
        if xff is not None:
            headers["HTTP_X_FORWARDED_FOR"] = xff
        return client_ip(RequestFactory().get("/", **headers))

    def test_it_reads_remote_addr(self) -> None:
        self.assertEqual(self.ip("1.2.3.4"), "1.2.3.4")

    def test_it_takes_the_entry_the_one_proxy_wrote(self) -> None:
        # The default: one proxy that replaces the header, as Caddy does, or appends to it
        self.assertEqual(self.ip("172.17.0.1", "1.2.3.4"), "1.2.3.4")
        self.assertEqual(self.ip("172.17.0.1", "2001:db8::1"), "2001:db8::1")
        self.assertEqual(self.ip("172.17.0.1", "6.6.6.6, 1.2.3.4"), "1.2.3.4")

    def test_it_ignores_what_a_client_puts_before_that_entry(self) -> None:
        self.assertEqual(self.ip("172.17.0.1", "unknown, " + "x" * 100 + ", 1.2.3.4"), "1.2.3.4")

    @override_settings(TRUSTED_PROXY_HOPS=2)
    def test_it_takes_the_nth_entry_from_the_right(self) -> None:
        self.assertEqual(self.ip("10.0.0.2", "6.6.6.6, 1.2.3.4, 10.0.0.1"), "1.2.3.4")

    @override_settings(TRUSTED_PROXY_HOPS=2)
    def test_it_reads_remote_addr_when_the_header_is_short(self) -> None:
        self.assertEqual(self.ip("10.0.0.2", "1.2.3.4"), "10.0.0.2")

    def test_it_reads_remote_addr_when_the_header_is_blank(self) -> None:
        self.assertEqual(self.ip("10.0.0.2", " "), "10.0.0.2")

    @override_settings(TRUSTED_PROXY_HOPS=0)
    def test_it_ignores_the_header_at_zero_hops(self) -> None:
        self.assertEqual(self.ip("1.2.3.4", "6.6.6.6"), "1.2.3.4")

    def test_it_normalises_the_entry(self) -> None:
        self.assertEqual(self.ip("172.17.0.1", "1.2.3.4:5678"), "1.2.3.4")
        self.assertEqual(self.ip("172.17.0.1", "::ffff:1.2.3.4"), "1.2.3.4")
        self.assertEqual(self.ip("::ffff:1.2.3.4"), "1.2.3.4")

    def test_it_returns_none_for_an_entry_that_is_no_address(self) -> None:
        self.assertIsNone(self.ip("172.17.0.1", "unknown"))
        self.assertIsNone(self.ip("172.17.0.1", "1.2.3.4, unknown"))
        self.assertIsNone(self.ip(""))


class TrustedProxyHopsSettingTestCase(SimpleTestCase):
    def test_it_defaults_to_one(self) -> None:
        with patch.dict(os.environ):
            os.environ.pop("TRUSTED_PROXY_HOPS", None)
            self.assertEqual(settings_module().TRUSTED_PROXY_HOPS, 1)

    def test_it_reads_the_environment(self) -> None:
        for value, expected in (("0", 0), ("2", 2)):
            with self.subTest(value=value):
                self.assertEqual(settings_module(TRUSTED_PROXY_HOPS=value).TRUSTED_PROXY_HOPS, expected)
