from smtplib import SMTPDataError, SMTPServerDisconnected
from unittest import TestCase
from unittest.mock import Mock, patch

from django.conf import settings
from django.test.utils import override_settings

from hc.lib.emails import EmailThread, send


@patch("hc.lib.emails.time.sleep")
class EmailsTestCase(TestCase):
    def test_it_retries(self, mock_time: Mock) -> None:
        mock_msg = Mock()
        mock_msg.send = Mock(side_effect=[SMTPServerDisconnected, None])

        t = EmailThread(mock_msg)
        t.deliver()

        self.assertEqual(mock_msg.send.call_count, 2)

    def test_it_limits_retries(self, mock_time: Mock) -> None:
        mock_msg = Mock()
        mock_msg.send = Mock(side_effect=SMTPServerDisconnected)

        with self.assertRaises(SMTPServerDisconnected):
            t = EmailThread(mock_msg)
            t.deliver()

        self.assertEqual(mock_msg.send.call_count, 3)

    def test_thread_logs_final_failure(self, mock_time: Mock) -> None:
        mock_msg = Mock()
        mock_msg.send = Mock(side_effect=SMTPServerDisconnected)

        with self.assertLogs("hc.lib.emails", "ERROR") as logs:
            EmailThread(mock_msg).run()

        [record] = logs.records
        self.assertEqual(record.getMessage(), "Failed to send email")
        assert record.exc_info
        self.assertIsInstance(record.exc_info[1], SMTPServerDisconnected)

    def test_it_retries_smtp_data_error(self, mock_time: Mock) -> None:
        mock_msg = Mock()
        mock_msg.send = Mock(side_effect=[SMTPDataError(454, "hello"), None])

        t = EmailThread(mock_msg)
        t.deliver()

        self.assertEqual(mock_msg.send.call_count, 2)

    @override_settings(MAILERS={})
    def test_it_requires_smtp_configuration(self, mock_time: Mock) -> None:
        with self.assertRaises(AssertionError):
            send(Mock())


class SendTestCase(TestCase):
    @patch("hc.lib.emails.EmailThread")
    def test_it_sends_on_thread_outside_tests(self, thread: Mock) -> None:
        message = Mock()
        with override_settings():
            del settings.BLOCKING_EMAILS
            send(message)

        thread.assert_called_once_with(message)
        thread.return_value.start.assert_called_once()
        thread.return_value.deliver.assert_not_called()

    @patch("hc.lib.emails.EmailThread")
    def test_block_flag_sends_synchronously(self, thread: Mock) -> None:
        message = Mock()
        with override_settings():
            del settings.BLOCKING_EMAILS
            send(message, block=True)

        thread.assert_called_once_with(message)
        thread.return_value.deliver.assert_called_once()
        thread.return_value.start.assert_not_called()
