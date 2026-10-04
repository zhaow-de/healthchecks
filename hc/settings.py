"""
Django settings for healthchecks project.

For the full list of settings and their values, see
https://docs.djangoproject.com/en/6.1/ref/settings/
"""

import os
import re
import sys
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any, overload
from urllib.parse import urlparse

import django_stubs_ext
from django.core.exceptions import ImproperlyConfigured
from django.http.request import split_domain_port
from django.utils.csp import CSP

django_stubs_ext.monkeypatch()
BASE_DIR = Path(__file__).resolve().parent.parent


def envbool(s: str, default: str) -> bool:
    v = os.getenv(s, default=default)
    if v not in ("", "True", "False"):
        msg = f"Unexpected value {s}={v}, use 'True' or 'False'"
        raise ImproperlyConfigured(msg)
    return v == "True"


def envint(s: str, default: str) -> int | None:
    v = os.getenv(s, default)
    if v == "None":
        return None

    return int(v)


@overload
def envsecret(s: str) -> str | None: ...


@overload
def envsecret(s: str, default: str) -> str: ...


def envsecret(s: str, default: str | None = None) -> str | None:
    """Load a secret from an environment variable or from the filesystem.

    This function either reads the secret from a file (if s + "_FILE" environment
    variable has a non-empty value), or calls os.getenv().

    """

    if secret_path := os.getenv(s + "_FILE"):
        p = Path(secret_path)
        if not p.is_file():
            # If the _FILE env var has a non-empty value then the value *must*
            # be a path to a readable file. If we cannot access the file then we
            # fail loudly
            raise ImproperlyConfigured(f"Error reading {s}_FILE ({secret_path})")
        return p.read_text().strip()

    return os.getenv(s, default)


SECRET_KEY = envsecret("SECRET_KEY", "---")
METRICS_KEY = os.getenv("METRICS_KEY")
DEBUG = envbool("DEBUG", "True")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "healthchecks@example.org")
# The sender of Django's error mails to ADMINS; Django's own default, root@localhost,
# is one an SMTP service that sends only from verified addresses refuses
SERVER_EMAIL = os.getenv("SERVER_EMAIL", DEFAULT_FROM_EMAIL)
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL")
if admins := os.getenv("ADMINS"):
    ADMINS = admins.split(",")

# On by default: the reverse proxy in front of the app sets X-Forwarded-Proto, replacing
# what the client sent. An empty value turns it off.
if v := os.getenv("SECURE_PROXY_SSL_HEADER", "HTTP_X_FORWARDED_PROTO,https"):
    SECURE_PROXY_SSL_HEADER = tuple(v.split(",", maxsplit=1))

# How many reverse proxies in front of the app write X-Forwarded-For: see hc.lib.ip.client_ip
TRUSTED_PROXY_HOPS = envint("TRUSTED_PROXY_HOPS", "1")


with (BASE_DIR / "pyproject.toml").open("rb") as f:
    VERSION = f"v{tomllib.load(f)['project']['version']}"


INSTALLED_APPS = (
    "hc.accounts",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.humanize",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "compressor",
    "hc.api",
    "hc.front",
    "hc.integrations.email",
    "hc.integrations.group",
    "hc.integrations.prometheus",
    "hc.integrations.slack",
    "hc.integrations.webhook",
)


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    # Outside every middleware below, so it compresses the body they leave. Not above
    # WhiteNoise, which serves the build's .gz files itself: there it would compress
    # every other static file, fonts and images included, on each request.
    *(["django.middleware.gzip.GZipMiddleware"] if envbool("USE_GZIP_MIDDLEWARE", "False") else []),
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "hc.accounts.middleware.ProfileMiddleware",
]

AUTHENTICATION_BACKENDS = [
    "hc.accounts.backends.EmailBackend",
    "hc.accounts.backends.ProfileBackend",
]

ROOT_URLCONF = "hc.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.csp",
                "hc.front.context_processors.branding",
            ]
        },
    }
]

# uWSGI's line per request is off in docker/uwsgi.ini (disable-logging)
LOG_FORMAT = os.getenv("LOG_FORMAT", "text").strip().lower()
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "require_debug_false": {"()": "django.utils.log.RequireDebugFalse"},
    },
    "formatters": {
        "text": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
        "json": {"()": "hc.lib.logs.JsonFormatter"},
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": "json" if LOG_FORMAT == "json" else "text",
        },
        # Django's default handler for ADMINS, which configuring the "django"
        # logger here would otherwise drop
        "mail_admins": {
            "level": "ERROR",
            "filters": ["require_debug_false"],
            "class": "django.utils.log.AdminEmailHandler",
        },
        "null": {"class": "logging.NullHandler"},
    },
    "root": {"level": "WARNING", "handlers": ["console"]},
    # The loggers with the console handler do not propagate, so the root's
    # console handler does not write their records a second time
    "loggers": {
        "django": {"level": "INFO", "handlers": ["console", "mail_admins"], "propagate": False},
        "django.request": {
            "level": "ERROR",
            "handlers": ["console", "mail_admins"],
            "propagate": False,
        },
        # Without a handler, its 4xx and 5xx lines would reach logging.lastResort
        "django.server": {"handlers": ["null"], "propagate": False},
        # A request with a Host outside ALLOWED_HOSTS still gets 400; scanners send them,
        # and each would otherwise log a traceback and email ADMINS
        "django.security.DisallowedHost": {"handlers": ["null"], "propagate": False},
        "hc": {"level": "INFO", "handlers": ["console"], "propagate": False},
    },
}

WSGI_APPLICATION = "hc.wsgi.application"


# Default database engine is SQLite. So one can just check out code,
# run "uv sync" and do manage.py runserver and it works
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
DATABASES: Mapping[str, Any] = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.getenv("DB_NAME", BASE_DIR / "hc.sqlite"),
        "CONN_MAX_AGE": envint("DB_CONN_MAX_AGE", "600"),
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {
            # auto_vacuum and WAL are set by the connection_created receiver in hc/api/apps.py,
            # which runs after init_command; its docstring says why. In WAL mode, synchronous
            # NORMAL can lose the last commits to a power loss or an OS crash, not to a crash
            # of the process.
            "init_command": "PRAGMA busy_timeout = 5000; PRAGMA synchronous = NORMAL; PRAGMA journal_size_limit = 16777216;",
            "transaction_mode": "IMMEDIATE",
        },
    }
}

if os.getenv("DB") == "postgres":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "HOST": os.getenv("DB_HOST", ""),
            "PORT": os.getenv("DB_PORT", ""),
            "NAME": os.getenv("DB_NAME", "hc"),
            "USER": os.getenv("DB_USER", "postgres"),
            "PASSWORD": envsecret("DB_PASSWORD", ""),
            "CONN_MAX_AGE": envint("DB_CONN_MAX_AGE", "600"),
            "CONN_HEALTH_CHECKS": True,
            "TEST": {"CHARSET": "UTF8"},
            "OPTIONS": {
                "application_name": "hc",
                "sslmode": os.getenv("DB_SSLMODE", "prefer"),
                "target_session_attrs": os.getenv("DB_TARGET_SESSION_ATTRS", "read-write"),
            },
        }
    }

USE_TZ = True
TIME_ZONE = "UTC"
USE_I18N = False

PASSWORD_HASHERS = ["django.contrib.auth.hashers.PBKDF2PasswordHasher"]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# A trailing slash is removed after hc/local_settings.py, wherever SITE_ROOT is set
SITE_ROOT = os.getenv("SITE_ROOT", "http://localhost:8000")
SITE_NAME = os.getenv("SITE_NAME", "Healthchecks")
# Unset, it is SITE_ROOT + "/ping/", which site_root_settings() fills in
PING_ENDPOINT = os.getenv("PING_ENDPOINT")
PING_BODY_LIMIT = envint("PING_BODY_LIMIT", "10000")
# If PING_BODY_LIMIT is higher than the default value for DATA_UPLOAD_MAX_MEMORY_SIZE,
# then we need to bump up DATA_UPLOAD_MAX_MEMORY_SIZE too:
if PING_BODY_LIMIT and PING_BODY_LIMIT > 2621440:
    DATA_UPLOAD_MAX_MEMORY_SIZE = PING_BODY_LIMIT
SECURE_HSTS_SECONDS = envint("SECURE_HSTS_SECONDS", "0")


def site_root_settings(site_root: str, ping_endpoint: str | None, allowed_hosts: str | None) -> dict[str, Any]:
    """The settings that follow SITE_ROOT and PING_ENDPOINT.

    It runs after hc/local_settings.py, on the final values of both, so a SITE_ROOT
    set there reaches them too; allowed_hosts is the ALLOWED_HOSTS environment variable.
    """
    site_root_parts = urlparse(site_root)
    if ping_endpoint is None:
        ping_endpoint = site_root + "/ping/"
    ping_endpoint_parts = urlparse(ping_endpoint)
    if allowed_hosts:
        # If ALLOWED_HOSTS is set in environment, use it
        hosts = allowed_hosts.split(",")
    else:
        # Otherwise, populate it with the domain from SITE_ROOT
        domain, _ = split_domain_port(site_root_parts.netloc)
        hosts = [domain]
    # On an https SITE_ROOT the session, messages, hc-device, auto-login and CSRF cookies are Secure
    secure = site_root_parts.scheme == "https"
    url_prefix = re.escape(f"{site_root_parts.path.lstrip('/')}/") if site_root_parts.path else ""

    return {
        "PING_ENDPOINT": ping_endpoint,
        "LOGIN_URL": f"{site_root_parts.path}/accounts/login/",
        "STATIC_URL": f"{site_root_parts.path}/static/",
        "ALLOWED_HOSTS": hosts,
        "SESSION_COOKIE_SECURE": secure,
        "CSRF_COOKIE_SECURE": secure,
        # A form posted from SITE_ROOT passes the CSRF origin check even when the proxy
        # does not tell Django the request came over https
        "CSRF_TRUSTED_ORIGINS": [f"{site_root_parts.scheme}://{site_root_parts.netloc}"],
        # SECURE_SSL_REDIRECT stays off: pings may come over http, and docker/fetchstatus.py
        # does. Turned on in local_settings.py, it leaves these paths alone.
        "SECURE_REDIRECT_EXEMPT": [rf"^{url_prefix}ping/", rf"^{url_prefix}api/v3/status/?$"],
        # An inline <script> or <style> needs {% csp_nonce_attr %}. The data: images are the
        # stylesheets' inline SVG icons and the TOTP QR code. The details page's "Ping Now!"
        # posts to PING_ENDPOINT, which may be on another origin.
        "SECURE_CSP": {
            "default-src": [CSP.SELF],
            "script-src": [CSP.SELF, CSP.NONCE],
            "style-src": [CSP.SELF, CSP.NONCE],
            "img-src": [CSP.SELF, "data:"],
            "connect-src": [CSP.SELF, f"{ping_endpoint_parts.scheme}://{ping_endpoint_parts.netloc}"],
            "object-src": [CSP.NONE],
            "base-uri": [CSP.SELF],
            "form-action": [CSP.SELF],
            "frame-ancestors": [CSP.NONE],
        },
    }


STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "static-collected"
STATICFILES_FINDERS = (
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
    "compressor.finders.CompressorFinder",
)
COMPRESS_OFFLINE = True
COMPRESS_CSS_HASHING_METHOD = "content"
COMPRESS_STORAGE = "compressor.storage.GzipCompressorFileStorage"
# Use CssRelativeFilter instead of CssAbsoluteFilter to fix
# icon font loading when serving Healthchecks from a subdirectory
COMPRESS_FILTERS = {
    "css": [
        "compressor.filters.css_default.CssRelativeFilter",
        "compressor.filters.cssmin.rCSSMinFilter",
    ],
    "js": [],
}


def immutable_file_test(path: Any, url: str) -> bool:
    return "/static/CACHE/" in url or "/static/fonts/" in url


WHITENOISE_IMMUTABLE_FILE_TEST = immutable_file_test
# Served at the site's root, where browsers and crawlers ask for files whatever a page links
WHITENOISE_ROOT = BASE_DIR / "webroot"

# SMTP credentials for sending email
EMAIL_USE_VERIFICATION = envbool("EMAIL_USE_VERIFICATION", "True")
EMAIL_MAIL_FROM_TMPL = os.getenv("EMAIL_MAIL_FROM_TMPL", "")

MAILERS = {}
if os.getenv("EMAIL_HOST"):
    MAILERS = {
        "default": {
            "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
            "OPTIONS": {
                "host": os.getenv("EMAIL_HOST", ""),
                "port": envint("EMAIL_PORT", "587"),
                "use_tls": envbool("EMAIL_USE_TLS", "True"),
                "use_ssl": envbool("EMAIL_USE_SSL", "False"),
                "username": os.getenv("EMAIL_HOST_USER", ""),
                "password": envsecret("EMAIL_HOST_PASSWORD", ""),
                "timeout": 30,
            },
        },
    }


# WebAuthn
RP_ID = os.getenv("RP_ID")

# Integrations

# Prometheus
PROMETHEUS_ENABLED = envbool("PROMETHEUS_ENABLED", "True")


# Slack integration
SLACK_CLIENT_ID = os.getenv("SLACK_CLIENT_ID")
SLACK_CLIENT_SECRET = envsecret("SLACK_CLIENT_SECRET")
SLACK_ENABLED = envbool("SLACK_ENABLED", "True")

# Webhooks
WEBHOOKS_ENABLED = envbool("WEBHOOKS_ENABLED", "True")
INTEGRATIONS_ALLOW_PRIVATE_IPS = envbool("INTEGRATIONS_ALLOW_PRIVATE_IPS", "False")

# Read additional configuration from hc/local_settings.py if it exists. The star import
# is the override: every name it defines replaces the one above.
_local_names: set[str] = set()
if (BASE_DIR / "hc/local_settings.py").exists():
    from . import local_settings as _local_settings
    from .local_settings import *  # noqa: F403

    _local_names = set(vars(_local_settings))

SITE_ROOT = SITE_ROOT.removesuffix("/")
# A setting that hc/local_settings.py sets itself keeps its value
for _name, _value in site_root_settings(SITE_ROOT, PING_ENDPOINT, os.getenv("ALLOWED_HOSTS")).items():
    if _name not in _local_names:
        globals()[_name] = _value

# Overrides for testing
if sys.argv[1:2] == ["test"] or "pytest" in sys.modules:
    # For speed:
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    # The test runner sets DEBUG to False, so hc.api.E004 would refuse a weak key
    SECRET_KEY = "test-only-secret-key-0123456789abcdefghijklmnopqrstuvwxyz"
    # Send emails synchronously
    BLOCKING_EMAILS = True
    # Keep log records out of the test output, assertLogs captures them anyway;
    # other loggers' warnings still reach the output through logging.lastResort
    LOGGING["handlers"]["console"] = {"class": "logging.NullHandler"}
    LOGGING["root"] = {"level": "WARNING", "handlers": []}
    # Make sure MAILERS is set as hc.lib.emails.send() requires it
    MAILERS = {
        "default": {
            "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
            "OPTIONS": {},
        },
    }
