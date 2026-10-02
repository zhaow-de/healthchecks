from __future__ import annotations

import io
import uuid
from contextlib import redirect_stdout
from unittest import skipIf
from unittest.mock import Mock, call, patch

from django.test import TestCase
from django.test.utils import override_settings

from hc.lib import s3
from hc.lib.s3 import GetObjectError, enc, get_object, put_object, remove_objects

try:
    from minio import InvalidResponseError, S3Error
    from minio.deleteobjects import DeleteError, DeleteObject
    from urllib3.exceptions import InvalidHeader, ProtocolError, ReadTimeoutError

    have_minio = True
except ImportError:
    have_minio = False


def s3error(code: str) -> S3Error:
    return S3Error(
        code=code,
        message="test-message",
        resource="test-resource",
        request_id="test-request-id",
        host_id="test-host-id",
        response=Mock(),
    )


@skipIf(not have_minio, "minio not installed")
@override_settings(S3_BUCKET="dummy-bucket")
class S3TestCase(TestCase):
    @patch("hc.lib.s3.statsd")
    @patch("hc.lib.s3._client")
    def test_get_object_handles_nosuchkey(self, client: Mock, statsd: Mock) -> None:
        e = S3Error(
            code="NoSuchKey",
            message="test-message",
            resource="test-resource",
            request_id="test-request-id",
            host_id="test-host-id",
            response=Mock(),
        )
        client.get_object.return_value.read = Mock(side_effect=e)
        self.assertIsNone(get_object("dummy-code", 1))
        # Should not increase the error counter for NoSuchKey responses
        self.assertEqual(statsd.incr.mock_calls, [call("hc.lib.s3.getObject")])

    @patch("hc.lib.s3.statsd")
    @patch("hc.lib.s3._client")
    def test_get_object_handles_s3error(self, client: Mock, statsd: Mock) -> None:
        e = S3Error(
            code="DummyError",
            message="test-message",
            resource="test-resource",
            request_id="test-request-id",
            host_id="test-host-id",
            response=Mock(),
        )
        client.get_object.return_value.read = Mock(side_effect=e)
        with self.assertRaises(GetObjectError):
            get_object("dummy-code", 1)
        client.get_object.assert_called_once()
        statsd.incr.assert_called_once()

    @patch("hc.lib.s3.statsd")
    @patch("hc.lib.s3._client")
    def test_get_object_handles_urllib_exceptions(self, client: Mock, statsd: Mock) -> None:
        for e in [ProtocolError, InvalidHeader]:
            client.get_object.reset_mock()
            client.get_object.return_value.read = Mock(side_effect=e)
            with self.assertRaises(GetObjectError):
                get_object("dummy-code", 1)
            client.get_object.assert_called_once()

    @patch("hc.lib.s3.statsd")
    @patch("hc.lib.s3._client")
    def test_get_object_handles_invalidresponseerror(self, client: Mock, statsd: Mock) -> None:
        e = InvalidResponseError(123, "text/plain", None)
        client.get_object.return_value.read = Mock(side_effect=e)
        with self.assertRaises(GetObjectError):
            get_object("dummy-code", 1)
        client.get_object.assert_called_once()
        statsd.incr.assert_called_once()

    @override_settings(S3_BUCKET=None)
    @patch("hc.lib.s3._client")
    def test_get_object_handles_no_s3_configuration(self, client: Mock) -> None:
        self.assertIsNone(get_object("dummy-code", 1))
        client.get_object.assert_not_called()


@skipIf(not have_minio, "minio not installed")
@override_settings(
    S3_BUCKET="dummy-bucket",
    S3_ENDPOINT="s3.example.org",
    S3_ACCESS_KEY="dummy-access-key",
    S3_SECRET_KEY="dummy-secret-key",
    S3_REGION="dummy-region",
    S3_SECURE=True,
    S3_TIMEOUT=15,
)
class ClientTestCase(TestCase):
    @patch("hc.lib.s3.PoolManager")
    @patch("hc.lib.s3.Minio")
    def test_it_creates_and_caches_client(self, minio: Mock, pool_manager: Mock) -> None:
        with patch.object(s3, "_client", None):
            first = s3.client()
            second = s3.client()

        self.assertIs(first, minio.return_value)
        self.assertIs(second, first)
        minio.assert_called_once_with(
            "s3.example.org",
            "dummy-access-key",
            "dummy-secret-key",
            region="dummy-region",
            secure=True,
            http_client=pool_manager.return_value,
        )
        self.assertEqual(pool_manager.call_args.kwargs["timeout"], 15)
        self.assertEqual(pool_manager.call_args.kwargs["retries"].total, 1)

    @override_settings(S3_ENDPOINT=None)
    @patch("hc.lib.s3.Minio")
    def test_it_requires_endpoint(self, minio: Mock) -> None:
        with patch.object(s3, "_client", None):
            with self.assertRaises(AssertionError):
                s3.client()
        minio.assert_not_called()

    @override_settings(S3_BUCKET=None)
    def test_it_requires_bucket(self) -> None:
        with self.assertRaisesMessage(AssertionError, "Object storage is not configured"):
            s3.client()


@skipIf(not have_minio, "minio not installed")
@override_settings(S3_BUCKET="dummy-bucket")
class PutObjectTestCase(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.code = uuid.uuid4()
        self.key = f"{self.code}/{enc(5)}"

    @patch("hc.lib.s3._client")
    def test_it_uploads_data(self, client: Mock) -> None:
        put_object(self.code, 5, b"hello")

        client.put_object.assert_called_once()
        bucket, key, stream, length = client.put_object.call_args.args
        self.assertEqual(bucket, "dummy-bucket")
        self.assertEqual(key, self.key)
        self.assertEqual(stream.read(), b"hello")
        self.assertEqual(length, 5)

    @patch("hc.lib.s3._client")
    def test_it_retries_internal_error(self, client: Mock) -> None:
        client.put_object.side_effect = [s3error("InternalError"), None]

        out = io.StringIO()
        with redirect_stdout(out):
            put_object(self.code, 5, b"hello")

        self.assertEqual(client.put_object.call_count, 2)
        self.assertIn("InternalError, retrying (retries=9)", out.getvalue())

    @patch("hc.lib.s3._client")
    def test_it_gives_up_after_ten_retries(self, client: Mock) -> None:
        client.put_object.side_effect = s3error("InternalError")

        with redirect_stdout(io.StringIO()):
            with self.assertRaises(S3Error):
                put_object(self.code, 5, b"hello")

        # One initial attempt plus ten retries
        self.assertEqual(client.put_object.call_count, 11)

    @patch("hc.lib.s3._client")
    def test_it_does_not_retry_other_errors(self, client: Mock) -> None:
        client.put_object.side_effect = s3error("AccessDenied")

        with self.assertRaises(S3Error) as cm:
            put_object(self.code, 5, b"hello")

        self.assertEqual(cm.exception.code, "AccessDenied")
        self.assertEqual(client.put_object.call_count, 1)

    @override_settings(S3_BUCKET=None)
    @patch("hc.lib.s3._client")
    def test_it_requires_bucket(self, client: Mock) -> None:
        with self.assertRaises(AssertionError):
            put_object(self.code, 5, b"hello")
        client.put_object.assert_not_called()


@skipIf(not have_minio, "minio not installed")
@override_settings(S3_BUCKET="dummy-bucket")
class RemoveObjectsTestCase(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.code = uuid.uuid4()

    def _objects(self, *ns: int) -> list[Mock]:
        return [Mock(object_name=f"{self.code}/{enc(n)}") for n in ns]

    @patch("hc.lib.s3.statsd")
    @patch("hc.lib.s3._client")
    def test_it_removes_objects_up_to_n(self, client: Mock, statsd: Mock) -> None:
        client.list_objects.return_value = self._objects(3, 2, 1)
        client.remove_objects.return_value = []

        remove_objects(str(self.code), 3, wait=True)

        client.list_objects.assert_called_once_with("dummy-bucket", f"{self.code}/", start_after=f"{self.code}/{enc(4)}")
        client.remove_objects.assert_called_once_with(
            "dummy-bucket",
            [DeleteObject(f"{self.code}/{enc(n)}") for n in (3, 2, 1)],
        )
        self.assertNotIn(call("hc.lib.s3.removeObjectsErrors"), statsd.incr.mock_calls)

    @patch("hc.lib.s3._client")
    def test_it_skips_nonpositive_n(self, client: Mock) -> None:
        for n in (0, -1):
            remove_objects(str(self.code), n, wait=True)

        client.list_objects.assert_not_called()
        client.remove_objects.assert_not_called()

    @patch("hc.lib.s3._client")
    def test_it_skips_remove_when_nothing_matches(self, client: Mock) -> None:
        client.list_objects.return_value = []

        remove_objects(str(self.code), 3, wait=True)

        client.list_objects.assert_called_once()
        client.remove_objects.assert_not_called()

    @patch("hc.lib.s3.logger")
    @patch("hc.lib.s3.statsd")
    @patch("hc.lib.s3._client")
    def test_it_logs_delete_errors(self, client: Mock, statsd: Mock, logger: Mock) -> None:
        client.list_objects.return_value = self._objects(2, 1)
        client.remove_objects.return_value = [
            DeleteError("AccessDenied", "Access Denied.", f"{self.code}/{enc(2)}", None),
        ]

        remove_objects(str(self.code), 2, wait=True)

        statsd.incr.assert_called_once_with("hc.lib.s3.removeObjectsErrors")
        logger.error.assert_called_once_with(
            "remove_objects error for %s: [%s] %s",
            f"{self.code}/{enc(3)}",
            "AccessDenied",
            "Access Denied.",
        )

    @patch("hc.lib.s3.logger")
    @patch("hc.lib.s3.statsd")
    @patch("hc.lib.s3._client")
    def test_it_handles_read_timeout(self, client: Mock, statsd: Mock, logger: Mock) -> None:
        client.list_objects.return_value = self._objects(2, 1)
        client.remove_objects.side_effect = ReadTimeoutError(None, None, "Read timed out.")

        remove_objects(str(self.code), 2, wait=True)

        statsd.incr.assert_called_once_with("hc.lib.s3.removeObjectsErrors")
        message = logger.exception.call_args.args[0]
        self.assertEqual(message, f"ReadTimeoutError while removing 2 objects for {self.code}")

    @patch("hc.lib.s3.Thread")
    def test_it_does_not_wait_by_default(self, thread: Mock) -> None:
        remove_objects(str(self.code), 3)

        thread.assert_called_once_with(target=s3._remove_objects, args=(str(self.code), 3))
        thread.return_value.start.assert_called_once()
        thread.return_value.join.assert_not_called()
