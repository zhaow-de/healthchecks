from __future__ import annotations

from django.urls import include, path, register_converter

from hc.api import views


class SHA1Converter:
    regex = "[A-z0-9]{40}"

    def to_python(self, value: str) -> str:
        return value

    def to_url(self, value: str) -> str:
        return value


register_converter(SHA1Converter, "sha1")

uuid_urls = [
    path("", views.ping),
    path("fail", views.ping, {"action": "fail"}),
    path("start", views.ping, {"action": "start"}),
    path("log", views.ping, {"action": "log"}),
    path("<int:exitstatus>", views.ping),
]

slug_urls = [
    path("fail", views.ping_by_slug, {"action": "fail"}),
    path("start", views.ping_by_slug, {"action": "start"}),
    path("log", views.ping_by_slug, {"action": "log"}),
    path("<int:exitstatus>", views.ping_by_slug),
]

api_urls = [
    path("checks/", views.checks, name="hc-api-checks"),
    path("checks/<uuid:code>", views.single, name="hc-api-single"),
    path("checks/<sha1:unique_key>", views.get_check_by_unique_key),
    path("checks/<uuid:code>/pause", views.pause, name="hc-api-pause"),
    path("checks/<uuid:code>/resume", views.resume, name="hc-api-resume"),
    path("checks/<uuid:code>/pings/", views.pings, name="hc-api-pings"),
    path(
        "checks/<uuid:code>/pings/<int:n>/body",
        views.ping_body,
        name="hc-api-ping-body",
    ),
    path("checks/<uuid:code>/flips/", views.flips_by_uuid, name="hc-api-flips"),
    path("checks/<sha1:unique_key>/flips/", views.flips_by_unique_key),
    path("channels/", views.channels),
    path("metrics/", views.metrics),
    path("status/", views.status),
    path("bounces/", views.bounces),
]

urlpatterns = [
    path("ping/<uuid:code>", views.ping),
    path("ping/<uuid:code>/", include(uuid_urls)),
    path("ping/<slug:ping_key>/<slug:slug>", views.ping_by_slug),
    path("ping/<slug:ping_key>/<slug:slug>/", include(slug_urls)),
    path("api/v3/", include(api_urls)),
]
