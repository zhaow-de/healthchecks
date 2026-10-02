from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from urllib.parse import urlsplit

from django.apps import AppConfig
from django.conf import settings
from django.core.checks import Error, Warning, register
from django.http.request import split_domain_port, validate_host


class ApiConfig(AppConfig):
    name = "hc.api"


@register()  # W001, W002, W005, E002, E003
def settings_check(
    app_configs: Sequence[AppConfig] | None,
    databases: Sequence[str] | None,
    **kwargs: dict[str, Any],
) -> list[Error | Warning]:
    items: list[Error | Warning] = []

    site_root_parts = urlsplit(settings.SITE_ROOT)
    if not site_root_parts.scheme:
        items.append(
            Warning(
                "Invalid settings.SITE_ROOT value",
                hint="SITE_ROOT should start with either http:// or https://",
                id="hc.api.W001",
            )
        )

    host, _ = split_domain_port(site_root_parts.netloc)
    if site_root_parts.scheme and not validate_host(host, settings.ALLOWED_HOSTS):
        items.append(
            Error(
                "The hostname in settings.SITE_ROOT is not found in settings.ALLOWED_HOSTS",
                hint=f"Add '{host}' to settings.ALLOWED_HOSTS",
                id="hc.api.E002",
            )
        )

    if not settings.MAILERS:
        items.append(
            Warning(
                "No SMTP configuration, cannot send email",
                hint="See https://github.com/zhaow-de/healthchecks#sending-emails",
                id="hc.api.W002",
            )
        )

    v = settings.SECURE_PROXY_SSL_HEADER
    if v is not None and (not isinstance(v, tuple) or len(v) != 2):
        items.append(
            Warning(
                "settings.SECURE_PROXY_SSL_HEADER is not 2-element tuple",
                hint="See https://zcrypto-hc.zhaow.me/docs/self_hosted_configuration/#SECURE_PROXY_SSL_HEADER",
                id="hc.api.W005",
            )
        )

    if settings.TIME_ZONE != "UTC":
        items.append(
            Error(
                "settings.TIME_ZONE is not 'UTC'",
                hint="Healthchecks is designed to use UTC internally, changing this setting will break things",
                id="hc.api.E003",
            )
        )

    return items
