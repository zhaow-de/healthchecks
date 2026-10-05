import re
from ipaddress import IPv6Address, ip_address

from django.conf import settings
from django.http import HttpRequest

# "[IPv6]" or "[IPv6]:port", and "IPv4:port": an IPv6 address alone has two colons or more
_WITH_PORT = re.compile(r"\[(?P<bracketed>[^\]]*)\](?::\d+)?|(?P<ipv4>[\d.]+):\d+", re.ASCII)


def parse_ip(value: str) -> str | None:
    """Return the address in `value` without its port, or None if it holds none.

    An IPv4-mapped IPv6 address comes back in its IPv4 form, and an IPv6 zone is
    dropped, which PostgreSQL's inet column would refuse.
    """
    value = value.strip()
    if m := _WITH_PORT.fullmatch(value):
        value = m["bracketed"] if m["bracketed"] is not None else m["ipv4"]

    try:
        addr = ip_address(value)
    except ValueError:
        return None

    if isinstance(addr, IPv6Address):
        if addr.ipv4_mapped:
            return str(addr.ipv4_mapped)
        addr = IPv6Address(int(addr))

    return str(addr)


def client_ip(request: HttpRequest) -> str | None:
    """Return the client's address, or None if what names it is not an address.

    With TRUSTED_PROXY_HOPS = N, the N-th X-Forwarded-For entry from the right is the
    address the outermost trusted proxy saw, whatever the client sent before it. A
    request whose header has fewer entries did not come through every proxy, and its
    REMOTE_ADDR is the peer. With 0, the header is not read.
    """
    hops = settings.TRUSTED_PROXY_HOPS
    value = request.META.get("REMOTE_ADDR", "")
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if hops and forwarded.strip():
        entries = forwarded.split(",")
        if len(entries) >= hops:
            value = entries[-hops]

    return parse_ip(value)
