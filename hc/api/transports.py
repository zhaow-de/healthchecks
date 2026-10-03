from __future__ import annotations

from typing import TYPE_CHECKING, Any, NoReturn

from hc.lib import curl

if TYPE_CHECKING:
    from hc.api.models import Channel, Flip, Notification, Ping


def get_ping_body_bytes(ping: Ping | None) -> bytes | None:
    """Return ping body as bytes for a given Ping object."""
    return ping.get_body_bytes() if ping else None


def get_ping_body(ping: Ping | None, maxlen: int | None = None) -> str | None:
    """Return ping body for a given Ping object."""
    body = None
    if body_bytes := get_ping_body_bytes(ping):
        body = body_bytes.decode(errors="replace")
        if maxlen and len(body) > maxlen:
            body = body[:maxlen] + "\n[truncated]"

    return body


class TransportError(Exception):
    def __init__(self, message: str, permanent: bool = False) -> None:
        self.message = message
        self.permanent = permanent


class Transport:
    def __init__(self, channel: Channel):
        self.channel = channel

    def notify(self, flip: Flip, notification: Notification) -> None:
        """Send notification about current status of the check.

        This method raises TransportError on error, and returns None
        on success.

        """

        raise NotImplementedError()

    def is_noop(self, status: str) -> bool:
        """Return True if transport will ignore check's current status.

        This method is overridden in Webhook subclass where the user can
        configure webhook urls for "up" and "down" events, and both are
        optional.

        """

        return False

    def last_ping(self, flip: Flip) -> Ping | None:
        """Return the last Ping object received before this flip."""

        if not flip.owner.pk:
            return None

        # Sort by "created". Sorting by "id" can cause postgres to pick api_ping.id
        # index (slow if the api_ping table is big)
        q = flip.owner.ping_set.order_by("created")
        # Make sure we're not selecting pings that occurred after the flip
        q = q.filter(created__lte=flip.created)

        return q.last()


class HttpTransport(Transport):
    @classmethod
    def raise_for_response(cls, response: curl.Response) -> NoReturn:
        # Subclasses can override this method to produce a more specific message.
        raise TransportError(f"Received status code {response.status_code}")

    @classmethod
    def _request(
        cls,
        method: str,
        url: str,
        *,
        data: curl.Data,
        json: Any,
        headers: curl.Headers,
    ) -> None:
        try:
            r = curl.request(
                method,
                url,
                data=data,
                json=json,
                headers=headers,
                timeout=30,
            )
            if r.status_code not in (200, 201, 202, 204):
                cls.raise_for_response(r)
        except curl.CurlError as e:
            raise TransportError(e.message)

    @classmethod
    def request(
        cls,
        method: str,
        url: str,
        *,
        retry: bool,
        data: curl.Data = None,
        json: Any = None,
        headers: curl.Headers = None,
    ) -> None:
        tries_left = 3 if retry else 1
        while True:
            try:
                return cls._request(
                    method,
                    url,
                    data=data,
                    json=json,
                    headers=headers,
                )
            except TransportError as e:
                tries_left = 0 if e.permanent else tries_left - 1
                # If we have no tries left then abort the retry loop by re-raising
                # the exception:
                if tries_left == 0:
                    raise

    # Convenience wrapper around self.request for making "POST" requests
    @classmethod
    def post(cls, url: str, retry: bool = True, *, json: Any = None) -> None:
        cls.request("post", url, retry=retry, json=json)
