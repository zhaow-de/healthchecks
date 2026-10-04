from __future__ import annotations

import logging
import time
from email.utils import make_msgid
from smtplib import SMTPDataError, SMTPServerDisconnected
from threading import Thread
from typing import Any

from django.conf import settings
from django.core.mail import EmailMultiAlternatives as Message
from django.template.loader import render_to_string as render

logger = logging.getLogger(__name__)


class EmailThread(Thread):
    MAX_TRIES = 3

    def __init__(self, message: Message) -> None:
        super().__init__()
        self.message = message

    def run(self) -> None:
        # On the background thread no caller sees the exception, and threading's
        # excepthook would only print it to stderr
        try:
            self.deliver()
        except Exception:
            logger.exception("Failed to send email")

    def deliver(self) -> None:
        for attempt in range(self.MAX_TRIES):
            try:
                self.message.send()
                # No exception--great! Return from the retry loop
                return
            except SMTPServerDisconnected, SMTPDataError:
                if attempt + 1 == self.MAX_TRIES:
                    # This was the last attempt and it failed:
                    # re-raise the exception
                    raise

                # Wait 1s before retrying
                time.sleep(1)


def make_message(
    name: str,
    to: str,
    ctx: dict[str, Any],
    headers: dict[str, str] | None = None,
) -> Message:
    subject = render(f"emails/{name}-subject.html", ctx).strip()
    # xa0 is a non-breaking space, in text emails we want regular spaces
    body = render(f"emails/{name}-body-text.html", ctx).replace("\xa0", " ")
    html = render(f"emails/{name}-body-html.html", ctx)
    if headers is None:
        headers = {}

    domain = settings.DEFAULT_FROM_EMAIL.split("@")[-1].strip(">")
    headers["Message-ID"] = make_msgid(domain=domain)

    # Make sure the From: header contains our display From: address
    if "From" not in headers:
        headers["From"] = settings.DEFAULT_FROM_EMAIL

    # If EMAIL_MAIL_FROM_TMPL is set, prepare a custom MAIL FROM address
    bounce_id = headers.pop("X-Bounce-ID", "bounces")
    from_email = settings.EMAIL_MAIL_FROM_TMPL % bounce_id if settings.EMAIL_MAIL_FROM_TMPL else settings.DEFAULT_FROM_EMAIL

    msg = Message(subject, body, from_email, [to], headers=headers)
    msg.attach_alternative(html, "text/html")
    return msg


def send(message: Message, block: bool = False) -> None:
    assert settings.MAILERS, "No SMTP configuration, see https://github.com/zhaow-de/healthchecks#sending-emails"

    t = EmailThread(message)
    if block or hasattr(settings, "BLOCKING_EMAILS"):
        # In tests, we send emails synchronously
        # so we can inspect the outgoing messages
        t.deliver()
    else:
        # Outside tests, we send emails on thread,
        # so there is no delay for the user.
        t.start()


def login(to: str, ctx: dict[str, Any]) -> None:
    send(make_message("login", to, ctx))


def alert(to: str, ctx: dict[str, Any], headers: dict[str, str]) -> None:
    m = make_message("alert", to, ctx, headers=headers)
    send(m, block=True)


def verify_email(to: str, ctx: dict[str, Any]) -> None:
    send(make_message("verify-email", to, ctx))


def report(to: str, ctx: dict[str, Any], headers: dict[str, str]) -> None:
    m = make_message("report", to, ctx, headers=headers)
    send(m, block=True)


def nag(to: str, ctx: dict[str, Any], headers: dict[str, str]) -> None:
    m = make_message("nag", to, ctx, headers=headers)
    send(m, block=True)


def flapping_notice(to: str, ctx: dict[str, Any]) -> None:
    m = make_message("flapping-notice", to, ctx)
    send(m, block=True)


def sudo_code(to: str, ctx: dict[str, Any]) -> None:
    send(make_message("sudo-code", to, ctx))
