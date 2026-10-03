"""The device cookie: a browser that completed a login gets its own login buckets.

Adapted from django-device-cookies 0.5.0 (https://github.com/knyghty/django-device-cookies),
Copyright (c) 2024 Tom Carrick, under the MIT License; the notice is in LICENSE.

A login that went through every step it requires sets a signed cookie holding
the user's id and a random nonce. The login form takes the nonce into its
TokenBucket keys when the cookie verifies and was issued to the user whose
email was submitted, so the shared per-email buckets an attacker can drain do
not apply to that browser.
"""

from __future__ import annotations

import secrets
from datetime import timedelta as td

from django.conf import settings
from django.contrib.auth.models import User
from django.core import signing
from django.http import HttpRequest, HttpResponse

COOKIE_NAME = "hc-device"
SALT = "hc.accounts.device"
MAX_AGE = td(days=365)
NONCE_LENGTH = 32


def _payload(user: User, nonce: str) -> dict[str, object]:
    return {"u": user.id, "n": nonce}


def nonce(request: HttpRequest, user: User | None) -> str:
    """Return the nonce of the request's device cookie, or "" if untrusted."""
    if user is None:
        return ""

    cookie = request.COOKIES.get(COOKIE_NAME, "")
    try:
        payload = signing.loads(cookie, salt=SALT, max_age=MAX_AGE)
    except signing.BadSignature:
        return ""

    n = payload.get("n") if isinstance(payload, dict) else None
    if not isinstance(n, str) or len(n) != NONCE_LENGTH:
        return ""

    return n if payload == _payload(user, n) else ""


def issue(request: HttpRequest, response: HttpResponse, user: User) -> None:
    # A browser that already holds a valid cookie for this user keeps its
    # nonce, and so its buckets.
    n = nonce(request, user) or secrets.token_hex(NONCE_LENGTH // 2)
    response.set_cookie(
        COOKIE_NAME,
        signing.dumps(_payload(user, n), salt=SALT),
        max_age=MAX_AGE,
        httponly=True,
        samesite="Lax",
        secure=bool(settings.SESSION_COOKIE_SECURE),
    )
