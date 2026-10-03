from __future__ import annotations

from urllib.parse import urlparse

from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.views.decorators.debug import sensitive_post_parameters

from hc.accounts import views as accounts_views
from hc.accounts.decorators import require_sudo_mode

prefix = ""
if _path := urlparse(settings.SITE_ROOT).path.lstrip("/"):
    prefix = f"{_path}/"

urlpatterns = [
    path(f"{prefix}admin/login/", accounts_views.login),
    # Ahead of admin.site.urls, which serves the same path without sudo mode and
    # takes unlimited guesses at the old password
    path(
        f"{prefix}admin/password_change/",
        admin.site.admin_view(sensitive_post_parameters()(require_sudo_mode(admin.site.password_change))),
    ),
    path(f"{prefix}admin/", admin.site.urls),
    path(prefix, include("hc.accounts.urls")),
    path(prefix, include("hc.api.urls")),
    path(prefix, include("hc.front.urls")),
    path(prefix, include("hc.integrations.email.urls")),
    path(prefix, include("hc.integrations.group.urls")),
    path(prefix, include("hc.integrations.prometheus.urls")),
    path(prefix, include("hc.integrations.slack.urls")),
    path(prefix, include("hc.integrations.webhook.urls")),
]
