"""
Django settings for healthchecks project.

For the full list of settings and their values, see
https://docs.djangoproject.com/en/6.1/ref/settings/
"""

import os
import sys
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any, overload
from urllib.parse import urlparse

import django_stubs_ext
from django.core.exceptions import ImproperlyConfigured
from django.http.request import split_domain_port

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
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL")
if admins := os.getenv("ADMINS"):
    ADMINS = admins.split(",")

if v := os.getenv("SECURE_PROXY_SSL_HEADER"):
    SECURE_PROXY_SSL_HEADER = tuple(v.split(",", maxsplit=1))


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
    "hc.logs",
    "hc.integrations.email",
    "hc.integrations.group",
    "hc.integrations.prometheus",
    "hc.integrations.slack",
    "hc.integrations.webhook",
)


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "hc.accounts.middleware.ProfileMiddleware",
]

if envbool("USE_GZIP_MIDDLEWARE", "False"):
    MIDDLEWARE.append("django.middleware.gzip.GZipMiddleware")

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
        "json": {"()": "hc.logs.JsonFormatter"},
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": "json" if LOG_FORMAT == "json" else "text",
        },
        "db": {
            "level": "WARNING",
            "class": "hc.logs.Handler",
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
            "handlers": ["console", "db", "mail_admins"],
            "propagate": False,
        },
        # Without a handler, its 4xx and 5xx lines would reach logging.lastResort
        "django.server": {"handlers": ["null"], "propagate": False},
        "hc": {"level": "INFO", "handlers": ["console", "db"], "propagate": False},
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
        "OPTIONS": {
            "init_command": "PRAGMA busy_timeout = 5000;",
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
            "CONN_MAX_AGE": envint("DB_CONN_MAX_AGE", "0"),
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

SITE_ROOT = os.getenv("SITE_ROOT", "http://localhost:8000").removesuffix("/")
SITE_NAME = os.getenv("SITE_NAME", "Healthchecks")
PING_ENDPOINT = os.getenv("PING_ENDPOINT", SITE_ROOT + "/ping/")
PING_BODY_LIMIT = envint("PING_BODY_LIMIT", "10000")
# If PING_BODY_LIMIT is higher than the default value for DATA_UPLOAD_MAX_MEMORY_SIZE,
# then we need to bump up DATA_UPLOAD_MAX_MEMORY_SIZE too:
if PING_BODY_LIMIT and PING_BODY_LIMIT > 2621440:
    DATA_UPLOAD_MAX_MEMORY_SIZE = PING_BODY_LIMIT
_site_root_parts = urlparse(SITE_ROOT)
LOGIN_URL = f"{_site_root_parts.path}/accounts/login/"
STATIC_URL = f"{_site_root_parts.path}/static/"
if v := os.getenv("ALLOWED_HOSTS"):
    # If ALLOWED_HOSTS is set in environment, use it
    ALLOWED_HOSTS = v.split(",")
else:
    # Otherwise, populate it with the domain from SITE_ROOT
    domain, _ = split_domain_port(_site_root_parts.netloc)
    ALLOWED_HOSTS = [domain]

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
if (BASE_DIR / "hc/local_settings.py").exists():
    from .local_settings import *  # noqa: F403

# Overrides for testing
if sys.argv[1:2] == ["test"] or "pytest" in sys.modules:
    # For speed:
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
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
