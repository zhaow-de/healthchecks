from unittest import TestCase

from django.test import RequestFactory

from hc.lib.ip import client_ip


class ClientIpTestCase(TestCase):
    def ip(self, remote_addr: str, xff: str | None = None) -> str:
        headers = {"REMOTE_ADDR": remote_addr}
        if xff is not None:
            headers["HTTP_X_FORWARDED_FOR"] = xff
        return client_ip(RequestFactory().get("/", **headers))

    def test_it_reads_remote_addr(self) -> None:
        self.assertEqual(self.ip("1.2.3.4"), "1.2.3.4")

    def test_it_takes_the_first_forwarded_address(self) -> None:
        self.assertEqual(self.ip("127.0.0.1", "1.2.3.4, 5.6.7.8"), "1.2.3.4")

    def test_it_removes_an_ipv4_port(self) -> None:
        self.assertEqual(self.ip("127.0.0.1", "1.2.3.4:5678"), "1.2.3.4")

    def test_it_keeps_an_ipv4_mapped_ipv6_address(self) -> None:
        self.assertEqual(self.ip("127.0.0.1", "::ffff:1.2.3.4"), "::ffff:1.2.3.4")
