from __future__ import annotations

import logging
from smtplib import SMTPDataError, SMTPServerDisconnected

from hc.accounts.models import Profile
from hc.api.models import Flip, Notification
from hc.api.transports import Transport, TransportError, get_ping_body_bytes
from hc.lib import emails
from hc.lib.signing import sign_bounce_id

logger = logging.getLogger(__name__)


class Email(Transport):
    def notify(self, flip: Flip, notification: Notification) -> None:
        if not self.channel.email_verified:
            raise TransportError("Email not verified")

        unsub_link = self.channel.get_unsub_link()

        headers = {
            "List-Unsubscribe": f"<{unsub_link}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
            "X-Bounce-ID": sign_bounce_id(f"n.{notification.code}"),
        }

        # If this email address has an associated account,
        # - include a summary of projects the account has access to
        # - use their preferred time zone to format datetimes
        # Otherwise, use the channel owner's preferred time zone.
        try:
            profile = Profile.objects.get(user__email=self.channel.email.value)
            projects = list(profile.projects())
        except Profile.DoesNotExist:
            profile = Profile.objects.for_user(self.channel.project.owner)
            projects = None

        ping = self.last_ping(flip)
        body_bytes = get_ping_body_bytes(ping)

        ctx = {
            "flip": flip,
            "check": flip.owner,
            "ping": ping,
            "body": body_bytes.decode(errors="replace") if body_bytes else None,
            "projects": projects,
            "unsub_link": unsub_link,
            "tz": profile.tz,
        }

        try:
            emails.alert(self.channel.email.value, ctx, headers)
        except SMTPServerDisconnected, SMTPDataError, ConnectionRefusedError:
            logger.exception("Exception while sending email")
            raise TransportError("SMTP connection error")

    def is_noop(self, status: str) -> bool:
        if status == "down":
            return not self.channel.email.notify_down
        else:
            return not self.channel.email.notify_up
