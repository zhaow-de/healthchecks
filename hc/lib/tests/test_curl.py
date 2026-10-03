from __future__ import annotations

from typing import Any
from unittest.mock import Mock, patch

import pycurl
from django.test import SimpleTestCase
from django.test.utils import override_settings

from hc.lib.curl import CurlError, Response, post, request


class FakeCurl:
    def __init__(self, ip: str = "1.2.3.4") -> None:
        self.opts: dict[int, Any] = {}
        self.ip = ip

    def setopt(self, k: int, v: Any) -> None:
        self.opts[k] = v

    def perform(self) -> None:
        if pycurl.OPENSOCKETFUNCTION in self.opts:
            # Simulate what libcurl would be doing here:
            # - if OPENSOCKETFUNCTION is defined, call it and pass it the ip address
            # - if the function returns pycurl.SOCKET_BAD, raise an error
            #
            # This is needed for test cases that exercise the
            # INTEGRATIONS_ALLOW_PRIVATE_IPS setting.
            callback = self.opts[pycurl.OPENSOCKETFUNCTION]
            address = (self.ip, 80)
            with patch("hc.lib.curl.socket"):
                sock = callback(pycurl.SOCKTYPE_IPCXN, (None, None, None, address))
                if sock == pycurl.SOCKET_BAD:
                    raise pycurl.error(pycurl.E_COULDNT_CONNECT)

        if pycurl.WRITEDATA in self.opts:
            self.opts[pycurl.WRITEDATA].write(b"hello world")

    def getinfo(self, _: int) -> int:
        return 200

    def close(self) -> None:
        pass


class CurlTestCase(SimpleTestCase):
    @patch("hc.lib.curl.pycurl.Curl")
    def test_get_works(self, mock: Mock) -> None:
        mock.return_value = obj = FakeCurl()
        response = request("get", "http://example.org")

        # URL should have been encoded to bytes
        self.assertEqual(obj.opts[pycurl.URL], b"http://example.org")

        # Default user agent
        self.assertEqual(obj.opts[pycurl.HTTPHEADER], [b"User-Agent:zcrypto-hc.zhaow.me"])

        # It should allow redirects
        self.assertEqual(obj.opts[pycurl.FOLLOWLOCATION], True)
        self.assertEqual(obj.opts[pycurl.MAXREDIRS], 3)

        self.assertEqual(response.text, "hello world")

    @patch("hc.lib.curl.pycurl.Curl")
    def test_it_allows_custom_ua(self, mock: Mock) -> None:
        mock.return_value = obj = FakeCurl()
        request("get", "http://example.org", headers={"User-Agent": "my-ua"})
        # The custom UA should override the default one
        self.assertEqual(obj.opts[pycurl.HTTPHEADER], [b"User-Agent:my-ua"])

    @patch("hc.lib.curl.pycurl.Curl")
    def test_it_encodes_header_values_to_latin1(self, mock: Mock) -> None:
        mock.return_value = obj = FakeCurl()
        request("get", "http://example.org", headers={"User-Agent": "À"})
        self.assertEqual(obj.opts[pycurl.HTTPHEADER], [b"User-Agent:\xc0"])

    @patch("hc.lib.curl.pycurl.Curl")
    def test_it_sets_timeout(self, mock: Mock) -> None:
        mock.return_value = obj = FakeCurl()
        request("get", "http://example.org", timeout=15)
        self.assertEqual(obj.opts[pycurl.TIMEOUT], 15)

    @patch("hc.lib.curl.pycurl.Curl")
    def test_it_posts_form(self, mock: Mock) -> None:
        mock.return_value = obj = FakeCurl()
        request("post", "http://example.org", data={"a": "b", "c": "d"})
        self.assertEqual(obj.opts[pycurl.CUSTOMREQUEST], "POST")
        self.assertEqual(obj.opts[pycurl.POSTFIELDS], "a=b&c=d")

    @patch("hc.lib.curl.pycurl.Curl")
    def test_it_posts_str(self, mock: Mock) -> None:
        mock.return_value = obj = FakeCurl()
        request("post", "http://example.org", data="hello")
        self.assertEqual(obj.opts[pycurl.CUSTOMREQUEST], "POST")
        self.assertEqual(obj.opts[pycurl.READDATA].getvalue(), b"hello")
        self.assertEqual(obj.opts[pycurl.INFILESIZE], 5)

    @patch("hc.lib.curl.pycurl.Curl")
    def test_it_posts_bytes(self, mock: Mock) -> None:
        mock.return_value = obj = FakeCurl()
        request("post", "http://example.org", data=b"hello")
        self.assertEqual(obj.opts[pycurl.CUSTOMREQUEST], "POST")
        self.assertEqual(obj.opts[pycurl.READDATA].getvalue(), b"hello")
        self.assertEqual(obj.opts[pycurl.INFILESIZE], 5)

    @patch("hc.lib.curl.pycurl.Curl")
    def test_it_posts_json(self, mock: Mock) -> None:
        mock.return_value = obj = FakeCurl()
        request("post", "http://example.org", json=[1, 2, 3])
        self.assertEqual(obj.opts[pycurl.CUSTOMREQUEST], "POST")
        self.assertEqual(obj.opts[pycurl.READDATA].getvalue(), b"[1, 2, 3]")
        self.assertEqual(obj.opts[pycurl.INFILESIZE], 9)

    @patch("hc.lib.curl.pycurl.Curl")
    def test_it_puts_form(self, mock: Mock) -> None:
        mock.return_value = obj = FakeCurl()
        request("put", "http://example.org", data={"a": "b", "c": "d"})
        self.assertEqual(obj.opts[pycurl.CUSTOMREQUEST], "PUT")
        self.assertEqual(obj.opts[pycurl.POSTFIELDS], "a=b&c=d")

    @patch("hc.lib.curl.pycurl.Curl")
    def test_it_puts_str(self, mock: Mock) -> None:
        mock.return_value = obj = FakeCurl()
        request("put", "http://example.org", data="hello")
        self.assertEqual(obj.opts[pycurl.CUSTOMREQUEST], "PUT")
        self.assertEqual(obj.opts[pycurl.READDATA].getvalue(), b"hello")
        self.assertEqual(obj.opts[pycurl.INFILESIZE], 5)

    @patch("hc.lib.curl.pycurl.Curl")
    def test_it_puts_bytes(self, mock: Mock) -> None:
        mock.return_value = obj = FakeCurl()
        request("put", "http://example.org", data=b"hello")
        self.assertEqual(obj.opts[pycurl.CUSTOMREQUEST], "PUT")
        self.assertEqual(obj.opts[pycurl.READDATA].getvalue(), b"hello")
        self.assertEqual(obj.opts[pycurl.INFILESIZE], 5)

    @patch("hc.lib.curl.pycurl.Curl")
    def test_it_puts_json(self, mock: Mock) -> None:
        mock.return_value = obj = FakeCurl()
        request("put", "http://example.org", json=[1, 2, 3])
        self.assertEqual(obj.opts[pycurl.CUSTOMREQUEST], "PUT")
        self.assertEqual(obj.opts[pycurl.READDATA].getvalue(), b"[1, 2, 3]")
        self.assertEqual(obj.opts[pycurl.INFILESIZE], 9)

    @override_settings(INTEGRATIONS_ALLOW_PRIVATE_IPS=False)
    @patch("hc.lib.curl.pycurl.Curl")
    def test_it_rejects_private_ip(self, mock: Mock) -> None:
        mock.return_value = FakeCurl(ip="127.0.0.1")
        with self.assertRaises(CurlError) as cm:
            request("get", "http://example.org")
        self.assertEqual(
            cm.exception.message,
            "Connections to private IP addresses are not allowed",
        )

    @override_settings(INTEGRATIONS_ALLOW_PRIVATE_IPS=True)
    @patch("hc.lib.curl.pycurl.Curl")
    def test_it_accepts_private_ip(self, mock: Mock) -> None:
        mock.return_value = FakeCurl(ip="127.0.0.1")
        request("get", "http://example.org")

    @patch("hc.lib.curl.pycurl.Curl")
    def test_it_maps_pycurl_errors_to_messages(self, mock: Mock) -> None:
        samples = [
            (pycurl.E_OPERATION_TIMEDOUT, "Connection timed out"),
            (pycurl.E_COULDNT_RESOLVE_HOST, "Could not resolve host"),
            (pycurl.E_COULDNT_CONNECT, "Connection failed"),
            (pycurl.E_TOO_MANY_REDIRECTS, "Too many redirects"),
            (pycurl.E_SSL_CONNECT_ERROR, "TLS handshake failed"),
            (pycurl.E_PEER_FAILED_VERIFICATION, "TLS handshake failed"),
            (pycurl.E_RECV_ERROR, f"HTTP request failed, code: {pycurl.E_RECV_ERROR}"),
        ]

        for errcode, message in samples:
            with self.subTest(errcode=errcode):
                mock.return_value.perform.side_effect = pycurl.error(errcode, "")
                with self.assertRaises(CurlError) as cm:
                    request("get", "http://example.org")
                self.assertEqual(cm.exception.message, message)

    @patch("hc.lib.curl.pycurl.Curl")
    def test_post_wrapper_passes_arguments(self, mock: Mock) -> None:
        mock.return_value = obj = FakeCurl()
        post("http://example.org", json={"foo": 1}, timeout=7)

        self.assertEqual(obj.opts[pycurl.CUSTOMREQUEST], "POST")
        self.assertEqual(obj.opts[pycurl.URL], b"http://example.org")
        self.assertEqual(obj.opts[pycurl.READDATA].getvalue(), b'{"foo": 1}')
        self.assertIn(b"Content-Type:application/json", obj.opts[pycurl.HTTPHEADER])
        self.assertEqual(obj.opts[pycurl.TIMEOUT], 7)

    @patch("hc.lib.curl.pycurl.Curl")
    def test_post_wrapper_sends_form_data(self, mock: Mock) -> None:
        mock.return_value = obj = FakeCurl()
        post("http://example.org", {"a": "b"})

        self.assertEqual(obj.opts[pycurl.CUSTOMREQUEST], "POST")
        self.assertEqual(obj.opts[pycurl.POSTFIELDS], "a=b")


class ResponseTestCase(SimpleTestCase):
    def test_json_decodes_content(self) -> None:
        response = Response(200, b'{"ok": true, "items": [1, 2]}')
        self.assertEqual(response.json(), {"ok": True, "items": [1, 2]})

    def test_json_raises_on_invalid_content(self) -> None:
        response = Response(200, b"not json")
        with self.assertRaises(ValueError):
            response.json()
