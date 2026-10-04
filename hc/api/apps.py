from collections.abc import Sequence
from typing import Any
from urllib.parse import urlsplit

from django.apps import AppConfig
from django.conf import settings
from django.core import checks
from django.db.backends.base.base import BaseDatabaseWrapper
from django.db.backends.signals import connection_created
from django.http.request import split_domain_port, validate_host


def set_incremental_auto_vacuum(sender: object, connection: BaseDatabaseWrapper, **kwargs: Any) -> None:
    """Give a SQLite file with no pages yet auto_vacuum INCREMENTAL, so prune can free pages.

    The mode takes effect only before the first table exists, and setting it on an
    existing file writes the header, so any other file is only read here.
    """
    if connection.vendor != "sqlite":
        return

    with connection.cursor() as cursor:
        cursor.execute("PRAGMA page_count")
        if cursor.fetchone()[0] == 0:
            cursor.execute("PRAGMA auto_vacuum = INCREMENTAL")


class ApiConfig(AppConfig):
    name = "hc.api"

    def ready(self) -> None:
        connection_created.connect(set_incremental_auto_vacuum, dispatch_uid="hc.api.auto_vacuum")


@checks.register()  # W001, W002, W005, E002, E003
def settings_check(
    app_configs: Sequence[AppConfig] | None,
    databases: Sequence[str] | None,
    **kwargs: dict[str, Any],
) -> list[checks.CheckMessage]:
    items: list[checks.CheckMessage] = []

    site_root_parts = urlsplit(settings.SITE_ROOT)
    if not site_root_parts.scheme:
        items.append(
            checks.Warning(
                "Invalid settings.SITE_ROOT value",
                hint="SITE_ROOT should start with either http:// or https://",
                id="hc.api.W001",
            )
        )

    host, _ = split_domain_port(site_root_parts.netloc)
    if site_root_parts.scheme and not validate_host(host, settings.ALLOWED_HOSTS):
        items.append(
            checks.Error(
                "The hostname in settings.SITE_ROOT is not found in settings.ALLOWED_HOSTS",
                hint=f"Add '{host}' to settings.ALLOWED_HOSTS",
                id="hc.api.E002",
            )
        )

    if not settings.MAILERS:
        items.append(
            checks.Warning(
                "No SMTP configuration, cannot send email",
                hint="See https://github.com/zhaow-de/healthchecks#sending-emails",
                id="hc.api.W002",
            )
        )

    v = settings.SECURE_PROXY_SSL_HEADER
    if v is not None and (not isinstance(v, tuple) or len(v) != 2):
        items.append(
            checks.Warning(
                "settings.SECURE_PROXY_SSL_HEADER is not 2-element tuple",
                hint="See https://zcrypto-hc.zhaow.me/docs/self_hosted_configuration/#SECURE_PROXY_SSL_HEADER",
                id="hc.api.W005",
            )
        )

    if settings.TIME_ZONE != "UTC":
        items.append(
            checks.Error(
                "settings.TIME_ZONE is not 'UTC'",
                hint="Healthchecks is designed to use UTC internally, changing this setting will break things",
                id="hc.api.E003",
            )
        )

    return items
