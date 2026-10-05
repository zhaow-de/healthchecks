import logging

from django.conf import settings

from hc.accounts.models import Profile
from hc.api.models import Flip, Notification
from hc.api.transports import Transport, TransportError, get_ping_body
from hc.lib import emails
from hc.lib.signing import sign_bounce_id

logger = logging.getLogger(__name__)


class Email(Transport):
    def notify(self, flip: Flip, notification: Notification) -> None:
        # Not permanent: a permanent error disables the channel, which would stay
        # disabled after SMTP is configured
        if not settings.MAILERS:
            raise TransportError("No SMTP configuration")

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
        ctx = {
            "flip": flip,
            "check": flip.owner,
            "ping": ping,
            "body": get_ping_body(ping),
            "projects": projects,
            "unsub_link": unsub_link,
            "tz": profile.tz,
        }

        try:
            emails.alert(self.channel.email.value, ctx, headers)
        except OSError as e:
            # OSError covers SMTPException, socket timeouts and ssl errors. Channel.notify()
            # logs the failure at ERROR; the traceback stays below it, at WARNING.
            logger.warning("Exception while sending email", exc_info=True)
            raise TransportError(f"SMTP error: {type(e).__name__}") from e

    def is_noop(self, status: str) -> bool:
        if status == "down":
            return not self.channel.email.notify_down
        return not self.channel.email.notify_up
