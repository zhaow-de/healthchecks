from ipaddress import ip_address

from django.http import HttpRequest


def client_ip(request: HttpRequest) -> str:
    """Return the client's address: the first of X-Forwarded-For, else REMOTE_ADDR."""
    headers = request.META
    remote_addr = headers.get("HTTP_X_FORWARDED_FOR", headers["REMOTE_ADDR"])
    remote_addr = remote_addr.split(",")[0]

    # If remote_addr does not validate but appears to be in ipv4:port form
    # (like Azure App Service reports), then remove the port
    try:
        ip_address(remote_addr)
    except ValueError:
        parts = remote_addr.split(".")
        if len(parts) == 4 and ":" in parts[-1]:
            remote_addr = remote_addr.split(":")[0]

    return remote_addr
