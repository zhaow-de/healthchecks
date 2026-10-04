# Server Configuration

Healthchecks prepares its configuration in `hc/settings.py`. It reads configuration
from environment variables. Below is a list of environment variables it reads and uses.
With Docker, set them in `.env` beside `docker-compose.yml` (see
[Running with Docker](../self_hosted_docker/#getting-started)); from source, in the
environment of every process (see [Running from Source](../self_hosted_source/#production)).

How the values are read:

* A boolean setting accepts exactly `True` or `False` (case-sensitive). An empty
  value counts as `False`, not as the default. Any other value stops startup with
  `ImproperlyConfigured: Unexpected value NAME=..., use 'True' or 'False'`.
* An integer setting accepts a whole number or `None`. Anything else, an empty
  value included, stops startup with a `ValueError`.
* A string setting set to an empty value is the empty string, not the default. For
  `ADMINS`, `ALLOWED_HOSTS`, `EMAIL_HOST`, `METRICS_KEY`, `RP_ID`, `SLACK_CLIENT_ID`
  and `SUPPORT_EMAIL` that is the same as unset; for the others, `SITE_ROOT`,
  `SITE_NAME`, `PING_ENDPOINT` and `SERVER_EMAIL` among them, delete the line to get
  the default. An empty `SECURE_PROXY_SSL_HEADER` turns that setting off, while
  unset it has its default.
* A `<NAME>_FILE` variable with a non-empty value names a file whose content is used
  instead of `<NAME>`; an empty one counts as unset, and `<NAME>` is read. A
  non-empty value that does not name an existing regular file stops startup with
  `ImproperlyConfigured: Error reading <NAME>_FILE (<path>)`, and a file the process
  may not read stops it with a `PermissionError`. Healthchecks strips whitespace
  from both ends of the file's content.
* Settings in `hc/local_settings.py`, when that file exists, override the
  environment.

<ul class="self-hosted-configuration-toc">
<li><a href="#ADMINS">ADMINS</a></li>
<li><a href="#ALLOWED_HOSTS">ALLOWED_HOSTS</a></li>
<li><a href="#DB">DB</a></li>
<li><a href="#DB_CONN_MAX_AGE">DB_CONN_MAX_AGE</a></li>
<li><a href="#DB_HOST">DB_HOST</a></li>
<li><a href="#DB_NAME">DB_NAME</a></li>
<li><a href="#DB_PASSWORD">DB_PASSWORD</a></li>
<li><a href="#DB_PASSWORD_FILE">DB_PASSWORD_FILE</a></li>
<li><a href="#DB_PORT">DB_PORT</a></li>
<li><a href="#DB_SSLMODE">DB_SSLMODE</a></li>
<li><a href="#DB_TARGET_SESSION_ATTRS">DB_TARGET_SESSION_ATTRS</a></li>
<li><a href="#DB_USER">DB_USER</a></li>
<li><a href="#DEBUG">DEBUG</a></li>
<li><a href="#DEFAULT_FROM_EMAIL">DEFAULT_FROM_EMAIL</a></li>
<li><a href="#EMAIL_HOST">EMAIL_HOST</a></li>
<li><a href="#EMAIL_HOST_PASSWORD">EMAIL_HOST_PASSWORD</a></li>
<li><a href="#EMAIL_HOST_PASSWORD_FILE">EMAIL_HOST_PASSWORD_FILE</a></li>
<li><a href="#EMAIL_HOST_USER">EMAIL_HOST_USER</a></li>
<li><a href="#EMAIL_MAIL_FROM_TMPL">EMAIL_MAIL_FROM_TMPL</a></li>
<li><a href="#EMAIL_PORT">EMAIL_PORT</a></li>
<li><a href="#EMAIL_USE_TLS">EMAIL_USE_TLS</a></li>
<li><a href="#EMAIL_USE_SSL">EMAIL_USE_SSL</a></li>
<li><a href="#EMAIL_USE_VERIFICATION">EMAIL_USE_VERIFICATION</a></li>
<li><a href="#http_proxy">http_proxy and https_proxy</a></li>
<li><a href="#INTEGRATIONS_ALLOW_PRIVATE_IPS">INTEGRATIONS_ALLOW_PRIVATE_IPS</a></li>
<li><a href="#LOG_FORMAT">LOG_FORMAT</a></li>
<li><a href="#METRICS_KEY">METRICS_KEY</a></li>
<li><a href="#PING_BODY_LIMIT">PING_BODY_LIMIT</a></li>
<li><a href="#PING_ENDPOINT">PING_ENDPOINT</a></li>
<li><a href="#PROMETHEUS_ENABLED">PROMETHEUS_ENABLED</a></li>
<li><a href="#RP_ID">RP_ID</a></li>
<li><a href="#SECRET_KEY">SECRET_KEY</a></li>
<li><a href="#SECRET_KEY_FILE">SECRET_KEY_FILE</a></li>
<li><a href="#SECURE_HSTS_SECONDS">SECURE_HSTS_SECONDS</a></li>
<li><a href="#SECURE_PROXY_SSL_HEADER">SECURE_PROXY_SSL_HEADER</a></li>
<li><a href="#SERVER_EMAIL">SERVER_EMAIL</a></li>
<li><a href="#SITE_NAME">SITE_NAME</a></li>
<li><a href="#SITE_ROOT">SITE_ROOT</a></li>
<li><a href="#SLACK_CLIENT_ID">SLACK_CLIENT_ID</a></li>
<li><a href="#SLACK_CLIENT_SECRET">SLACK_CLIENT_SECRET</a></li>
<li><a href="#SLACK_CLIENT_SECRET_FILE">SLACK_CLIENT_SECRET_FILE</a></li>
<li><a href="#SLACK_ENABLED">SLACK_ENABLED</a></li>
<li><a href="#SUPPORT_EMAIL">SUPPORT_EMAIL</a></li>
<li><a href="#TRUSTED_PROXY_HOPS">TRUSTED_PROXY_HOPS</a></li>
<li><a href="#USE_GZIP_MIDDLEWARE">USE_GZIP_MIDDLEWARE</a></li>
<li><a href="#WEBHOOKS_ENABLED">WEBHOOKS_ENABLED</a></li>
</ul>

## `ADMINS` {: #ADMINS }

Default: `""` (empty string)

A comma-separated list of email addresses to send code error notifications to.
When `DEBUG=False`, Healthchecks will send the details of exceptions raised in the
request/response cycle to the listed addresses. Example:

```ini
ADMINS=alice@example.org,bob@example.org
```

Note: for error notifications to work, make sure you have also specified working
SMTP credentials in the `EMAIL_...` environment variables.

Django sends these emails with the subject prefix "[Django] " and from
[SERVER_EMAIL](#SERVER_EMAIL), which defaults to
[DEFAULT_FROM_EMAIL](#DEFAULT_FROM_EMAIL). Healthchecks' own warnings and errors are
not emailed: they go to the console only (see [Logs](../self_hosted/#logs)).

## `ALLOWED_HOSTS` {: #ALLOWED_HOSTS }

Default: the domain part of `SITE_ROOT`

The host/domain names that this site can serve. Healthchecks populates this setting
automatically with the domain part of [SITE_ROOT](#SITE_ROOT). You do not need
to set it unless you serve Healthchecks on more than one domain.

When set, the list must include the host of `SITE_ROOT`. Otherwise the system check
`hc.api.E002` fails, and every `manage.py` command that runs the system checks,
`migrate` included (so also the Docker container's startup), stops with "The
hostname in settings.SITE_ROOT is not found in settings.ALLOWED_HOSTS". A request
whose `Host` header is not in the list gets 400 Bad Request.

If you do serve the same Healthchecks instance on more than one domain, specify
them all in `ALLOWED_HOSTS`, separated by commas:

```ini
ALLOWED_HOSTS=first.example.org,second.example.org
```

Aside from the comma-separated syntax, this is a standard Django setting.
Read more about it in the
[Django documentation](https://docs.djangoproject.com/en/6.1/ref/settings/#allowed-hosts).

## `DB` {: #DB }

Default: `sqlite`

The database engine to use. Possible values: `sqlite`, `postgres`.

Only the exact value `postgres` selects PostgreSQL; any other value, or none, means
SQLite. `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD` (or `DB_PASSWORD_FILE`),
`DB_SSLMODE` and `DB_TARGET_SESSION_ATTRS` are read only when `DB=postgres`. With
SQLite, only [DB_NAME](#DB_NAME), a file path, and
[DB_CONN_MAX_AGE](#DB_CONN_MAX_AGE) apply.

## `DB_CONN_MAX_AGE` {: #DB_CONN_MAX_AGE }

Default: `600`

The lifetime of a database connection, in seconds: an integer, `0` to close each
connection at the end of its request, or `None` for unlimited persistent
connections. It applies to SQLite and PostgreSQL alike. With the default, each web
server process, and each of `sendalerts` and `sendreports`, keeps its connection for
up to 10 minutes. Before a request reuses a connection, Django checks that it still
works (`CONN_HEALTH_CHECKS`, on), and replaces one that a PostgreSQL restart closed
without failing the request; on SQLite the check does nothing.

This is a standard Django setting, read more in
[Django documentation](https://docs.djangoproject.com/en/6.1/ref/settings/#conn-max-age).

## `DB_HOST` {: #DB_HOST }

Default: `""` (empty string)

This is a standard Django setting, read more in
[Django documentation](https://docs.djangoproject.com/en/6.1/ref/settings/#host).

## `DB_NAME` {: #DB_NAME }

Default: `hc` (PostgreSQL) or `/path/to/projectdir/hc.sqlite` (SQLite); the Docker
image sets `/data/hc.sqlite`

The PostgreSQL database name, or the path of the SQLite database file. With
`DB=postgres`, set `DB_NAME` as well, as `docker-compose.postgres.yml` does: left as
it is, the image's path names the PostgreSQL database.

This is a standard Django setting, read more in
[Django documentation](https://docs.djangoproject.com/en/6.1/ref/settings/#name).

## `DB_PASSWORD` {: #DB_PASSWORD }

Default: `""` (empty string)

This is a standard Django setting, read more in
[Django documentation](https://docs.djangoproject.com/en/6.1/ref/settings/#password).

## `DB_PASSWORD_FILE` {: #DB_PASSWORD_FILE }

Default: `None`

If set, must contain a filesystem path pointing to a readable file. Healthchecks will
read the contents of the file into the [DB_PASSWORD](#DB_PASSWORD) setting.
If `DB_PASSWORD` and `DB_PASSWORD_FILE` are both set, `DB_PASSWORD_FILE` takes
precedence.

## `DB_PORT` {: #DB_PORT }

Default: `""` (empty string)

This is a standard Django setting, read more in
[Django documentation](https://docs.djangoproject.com/en/6.1/ref/settings/#port).

## `DB_SSLMODE` {: #DB_SSLMODE }

Default: `prefer`

PostgreSQL-specific, [details](https://www.postgresql.org/docs/18/libpq-connect.html#LIBPQ-CONNECT-SSLMODE)

## `DB_TARGET_SESSION_ATTRS` {: #DB_TARGET_SESSION_ATTRS }

Default: `read-write`

PostgreSQL-specific, [details](https://www.postgresql.org/docs/18/libpq-connect.html#LIBPQ-CONNECT-TARGET-SESSION-ATTRS)

## `DB_USER` {: #DB_USER }

Default: `postgres`

This is a standard Django setting, read more in
[Django documentation](https://docs.djangoproject.com/en/6.1/ref/settings/#user).

## `DEBUG` {: #DEBUG }

Default: `True`

A boolean that turns on/off debug mode.

_Never run a Healthchecks instance in production with the debug mode turned on!_

The Docker image sets `DEBUG=False`; from source, set it yourself. With
`DEBUG=False`, a weak [SECRET_KEY](#SECRET_KEY) stops startup.

This is a standard Django setting, read more in
[Django documentation](https://docs.djangoproject.com/en/6.1/ref/settings/#debug).

## `DEFAULT_FROM_EMAIL` {: #DEFAULT_FROM_EMAIL }

Default: `healthchecks@example.org`

The `From:` address of every email Healthchecks sends, and its envelope sender (the
SMTP `MAIL FROM` address) unless [EMAIL_MAIL_FROM_TMPL](#EMAIL_MAIL_FROM_TMPL) is set.
It is also the sender of the `ADMINS` error emails unless
[SERVER_EMAIL](#SERVER_EMAIL) is set. With an SMTP service that sends only from
verified addresses, such as Amazon SES, make it one of those (see
[Example: Amazon SES](../self_hosted/#ses)).

This is a standard Django setting, read more in
[Django documentation](https://docs.djangoproject.com/en/6.1/ref/settings/#default-from-email).

## `EMAIL_HOST` {: #EMAIL_HOST }

Default: `""` (empty string)

The hostname of an SMTP server to use for sending email. If this environment variable
is not set, Healthchecks will not be able to send any email, and
[`EMAIL_PORT`](#EMAIL_PORT), [`EMAIL_USE_TLS`](#EMAIL_USE_TLS),
[`EMAIL_USE_SSL`](#EMAIL_USE_SSL), [`EMAIL_HOST_USER`](#EMAIL_HOST_USER) and
[`EMAIL_HOST_PASSWORD`](#EMAIL_HOST_PASSWORD) are ignored. Without email, there is
no login by link, no sudo mode (so Set Password, Change Email, Close Account, the
two-factor changes and the password change in the administration panel show an
"Email Needed" page; use `manage.py changepassword` instead), no email alerts,
reports or `ADMINS` mail, and `manage.py` commands print the warnings
`hc.api.W002` and `mail.W001`. See [Sending Emails](../self_hosted/#sending-emails),
and [Example: Amazon SES](../self_hosted/#ses).

**On using `local_settings.py`:**
Healthchecks reads SMTP settings from the `EMAIL_*` environment variables,
and uses them to construct the `settings.MAILERS` dictionary (a standard Django setting,
read more in [Django documentation](https://docs.djangoproject.com/en/6.1/ref/settings/#std-setting-MAILERS)).
To configure SMTP server in the `local_settings.py` file, use the
`MAILERS` setting, not the individual `EMAIL_*` settings. A `MAILERS` defined there
replaces the one built from the environment entirely, defaults included: without
`port` and `use_tls`, Django connects in plain text on port 25, and without
`timeout` it waits for the server indefinitely (the environment-built one uses 30
seconds). For explicit TLS on port 587:

```
MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
        "OPTIONS": {
            "host": "smtp.example.org",
            "port": 587,
            "use_tls": True,
            "username": "example-username",
            "password": "example-password",
            "timeout": 30,
        },
    },
}
```

For implicit TLS, use `"port": 465, "use_ssl": True` instead of the `port` and
`use_tls` lines.

## `EMAIL_HOST_PASSWORD` {: #EMAIL_HOST_PASSWORD }

Default: `""` (empty string)

Password to use for the SMTP server defined in [EMAIL_HOST](#EMAIL_HOST).

## `EMAIL_HOST_PASSWORD_FILE` {: #EMAIL_HOST_PASSWORD_FILE }

Default: `None`

If set, must contain a filesystem path pointing to a readable file. Healthchecks will
read the contents of the file into the [EMAIL_HOST_PASSWORD](#EMAIL_HOST_PASSWORD)
setting. If `EMAIL_HOST_PASSWORD` and `EMAIL_HOST_PASSWORD_FILE`
are both set, `EMAIL_HOST_PASSWORD_FILE` takes precedence.

## `EMAIL_HOST_USER` {: #EMAIL_HOST_USER }

Default: `""` (empty string)

Username to use for the SMTP server defined in [EMAIL_HOST](#EMAIL_HOST).

## `EMAIL_MAIL_FROM_TMPL` {: #EMAIL_MAIL_FROM_TMPL }

Default: `""` (empty string)

A template for the envelope sender (the SMTP `MAIL FROM` address) of outgoing
email, with one `%s`. Example:

```ini
EMAIL_MAIL_FROM_TMPL=%s@bounces.example.org
```

Healthchecks fills `%s` with a signed bounce ID for alert and report emails, and
with `bounces` for other emails. The `From:` header stays
[DEFAULT_FROM_EMAIL](#DEFAULT_FROM_EMAIL). When the setting is empty, the envelope
sender is `DEFAULT_FROM_EMAIL` too.

To act on bounces, have the mail service that receives mail for those addresses
POST each bounce message, as a raw MIME message, to `/api/v3/bounces/` (see
[Receive Email Bounces](../api/#bounces)); Healthchecks reads the bounce ID from the
local part of the bounce's `To:` header. Only bounces that arrive within 48 hours
of the email are acted on:

* a permanent failure of an alert disables that email integration;
* a permanent failure of a report or reminder email turns reports off, whatever
  their period (daily, weekly or monthly), and turns reminders off.

## `EMAIL_PORT` {: #EMAIL_PORT }

Default: `587`

Port to use for the SMTP server defined in [EMAIL_HOST](#EMAIL_HOST).

## `EMAIL_USE_TLS` {: #EMAIL_USE_TLS }

Default: `True`

Whether to use a TLS (secure) connection when talking to the SMTP server.
This is used for explicit TLS connections, generally on port 587.
Set it to `False` when you set [EMAIL_USE_SSL](#EMAIL_USE_SSL) to `True`: with
both `True`, every email fails with Django's `InvalidMailer` error, and nothing
reports it at startup.

## `EMAIL_USE_SSL` {: #EMAIL_USE_SSL}

Default: `False`

Whether to use an implicit TLS (secure) connection when talking to the SMTP server.
It is generally used on port 465. Set [EMAIL_USE_TLS](#EMAIL_USE_TLS), which
defaults to `True`, to `False` with it.

## `EMAIL_USE_VERIFICATION` {: #EMAIL_USE_VERIFICATION }

Default: `True`

A boolean that turns on/off a verification step when adding an email integration.

If enabled, adding an email integration, changing its address, or saving a disabled
one emails a verification link to the address. The integration stays "Unconfirmed",
and receives no alerts, until someone clicks the link. The account's own email
address is never verified this way: it is confirmed at once.

Verification needs email: with verification on and no [EMAIL_HOST](#EMAIL_HOST),
the form refuses a new or changed address, or a disabled integration, unless the
address is the account's own, so that no address receives alerts without having
been confirmed.

Set `EMAIL_USE_VERIFICATION` to `False` to confirm each address as it is saved.
The setting does not change integrations already unconfirmed; to confirm one,
change its address and back, or delete it and add it again.

## `http_proxy` and `https_proxy` {: #http_proxy}

Default: `""` (empty string)

Specifies the proxy server to use for outgoing HTTP and HTTPS requests.
Supports different proxy server types. Examples:

```ini
https_proxy=http://example.org:1234
https_proxy=https://example.org:1234
https_proxy=socks4://example.org:1234
https_proxy=socks5://example.org:1234
```

Healthchecks uses libcurl as the HTTP client library for making HTTP(S) requests.
For more information about the proxy functionality, please see
[libcurl documentation](https://curl.se/libcurl/c/CURLOPT_PROXY.html).

Note: If your proxy server has a private IP address, you will also need to
set the `INTEGRATIONS_ALLOW_PRIVATE_IPS` setting to `True` to use it.

## `INTEGRATIONS_ALLOW_PRIVATE_IPS` {: #INTEGRATIONS_ALLOW_PRIVATE_IPS }

Default: `False`

A boolean that controls whether the integrations are allowed to make
HTTP(S) requests to private IP addresses (127.0.0.1, 192.168.x.x, ...). This setting
is set to `False` by default, because a webhook could then make the server probe
internal addresses: its URL is typed in the web UI, but placeholders in it, such as
`$NAME`, take values that a read-write API key can set.

An address is blocked when Python's `ipaddress` module marks it private. That
covers 127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 169.254.0.0/16,
0.0.0.0, the documentation and benchmarking ranges (192.0.2.0/24, 198.18.0.0/15,
198.51.100.0/24, 203.0.113.0/24), 240.0.0.0/4, `::1`, `fc00::/7` and `fe80::/10`;
100.64.0.0/10 (carrier-grade NAT) is not blocked. The check runs on the address of
every connection, after DNS resolution and after each redirect, so a public
hostname that resolves to a private address is blocked as well. A blocked request
fails with the integration error "Connections to private IP addresses are not
allowed".

Only enable this setting if you run your Healthchecks instance in a trusted
environment, and need to integrate with services running in your internal network.

This setting affects all integration types that make HTTP requests, not just
webhooks: the Slack integration is subject to it as well.

This setting also affects connections to the proxy server when the `http_proxy` or
`https_proxy` environment variables are set. If your proxy server has a private
IP address, you will need to enable `INTEGRATIONS_ALLOW_PRIVATE_IPS` to use it.

## `LOG_FORMAT` {: #LOG_FORMAT }

Default: `text`

The format of the log records Healthchecks writes to the console (in Docker, the
container's output), including the output of the `sendalerts` and `sendreports`
management commands.

With `text`, a record starts with a line holding the time, the level, the logger
name and the message; a multi-line message or a traceback continues on the lines
after it. With `json`, each record is one JSON object on one line, with the keys
`time` (ISO 8601, in UTC), `level`, `logger`, `message`, and `exception` (the
formatted traceback) when the record carries one.

Any value other than `json` (case-insensitive) means `text`. Text timestamps are in
the process's local time (UTC in the Docker image).

Neither `manage.py runserver` nor the Docker image's uWSGI writes a line per HTTP
request. A uWSGI you run yourself does unless it is started with `--disable-logging`.

## `METRICS_KEY` {: #METRICS_KEY }

Default: `None`

The secret that the [Read Service Metrics](../api/#metrics) endpoint,
`/api/v3/metrics/`, expects in its `X-Metrics-Key` request header. While it is
unset, that endpoint answers 403 to every request.

## `PING_BODY_LIMIT` {: #PING_BODY_LIMIT }

Default: `10000`

The upper size limit in bytes for logged ping request bodies.
The default value is 10000 (10 kilobytes). Healthchecks stores the first
`PING_BODY_LIMIT` bytes of each ping's body and drops the rest without an error,
and sends the value in the `Ping-Body-Limit` response header. With `None`, the body
is stored whole and the header is omitted.

Independently, a request whose body is larger than 2,621,440 bytes (2.5 MiB) is
refused and not recorded, and `None` does not lift that cap: the Docker image's
uWSGI closes the connection without an HTTP response, and under a server without
that limit Django answers 400. Only a limit above 2,621,440 raises the cap, to the
limit itself; in the Docker image, set `UWSGI_LIMIT_POST` to the same value too (see
[uWSGI Configuration](../self_hosted_docker/#uwsgi)). See
[Request Body](../http_api/#request-body).

Healthchecks stores each ping body in the database, with its ping. Keep
`PING_BODY_LIMIT`, and the bodies your jobs send, no bigger than the output you
actually need to read.

## `PING_ENDPOINT` {: #PING_ENDPOINT }

Default: `SITE_ROOT` + `/ping/`

The base URL to use for constructing ping URLs for display. Healthchecks constructs ping
URLs by appending either a UUID value or `<ping-key>/<slug>` value to `PING_ENDPOINT`.

Notes:

* Make sure the `PING_ENDPOINT` value ends with a trailing slash. If a trailing slash
  is missing, Healthchecks will *not* add it implicitly.
* Healthchecks uses `PING_ENDPOINT` for formatting ping URLs for display.
  The `PING_ENDPOINT` value does not influence the routing of incoming HTTP requests.
  If you change the `PING_ENDPOINT` value, you will likely also need to add matching
  URL rewriting rules in your reverse proxy configuration.

Example:

```ini
PING_ENDPOINT=https://ping.my-hc.example.org/
```

With this setting, Healthchecks will generate ping URLs similar to:

```
https://ping.my-hc.example.org/3f1a7317-8e96-437c-a17d-b0d550b51e86
https://ping.my-hc.example.org/1fj9XWM6Ns8vLGTmnPGk9g/dummy-slug
```

## `PROMETHEUS_ENABLED` {: #PROMETHEUS_ENABLED }

Default: `True`

A boolean that turns on/off the Prometheus integration. Enabled by default.

With `False`, Prometheus is hidden from the Integrations page, its page there
answers 404, and so do the metrics endpoints (`/projects/<uuid>/metrics/` and
`/projects/<uuid>/metrics/<key>`), so Prometheus scrapes fail. See
[Configuring Prometheus](../configuring_prometheus/).

## `RP_ID` {: #RP_ID }

Default: `None`

The [Relying Party identifier](https://www.w3.org/TR/webauthn-2/#relying-party-identifier),
required by the WebAuthn second-factor authentication feature.

Healthchecks optionally supports two-factor authentication using the WebAuthn
standard. To enable WebAuthn support, set the `RP_ID` setting to a non-null value.
Set its value to your site's domain without scheme and without port. For example,
if your site runs on `https://my-hc.example.org`, set `RP_ID` to `my-hc.example.org`.

`RP_ID` turns on security keys (WebAuthn) only: the authenticator app (TOTP) second
factor is available with or without it. An empty value counts as unset. Browsers
allow WebAuthn only over HTTPS, or on `localhost`.

## `SECRET_KEY` {: #SECRET_KEY }

Default: `---`

A secret key used for cryptographic signing. Set it to a unique, unpredictable value
of at least 50 characters, with at least 5 different ones, that does not start with
`django-insecure-`, for example the output of:

```sh
python3 -c 'import secrets; print(secrets.token_urlsafe(50))'
```

With `DEBUG=False`, a key that breaks this rule, the default `---` included, fails
the system check `hc.api.E004`, which stops every `manage.py` command that runs the
system checks, `migrate` included, and so the Docker container's start.

Set it once, before first use, and keep it. Changing it later:

* stops every Management API key (read-write and read-only) from working, because
  the database stores only an HMAC of each key made with `SECRET_KEY`; Prometheus
  scrapes with a read-only key stop too. Create new keys in the **API Access**
  section of each project's Settings page (see [Authentication](../api/#authentication)).
* invalidates every session, login link, device cookie, pending sudo code, email
  verification link and unsubscribe link in emails already sent.
* resets the per-email [login rate limits](../self_hosted/#login-lockout).

This is a standard Django setting, read more in
[Django documentation](https://docs.djangoproject.com/en/6.1/ref/settings/#secret-key).

## `SECRET_KEY_FILE` {: #SECRET_KEY_FILE }

Default: `None`

If set, must contain a filesystem path pointing to a readable file. Healthchecks will
read the contents of the file into the [SECRET_KEY](#SECRET_KEY) setting.
If `SECRET_KEY` and `SECRET_KEY_FILE` are both set, `SECRET_KEY_FILE` takes
precedence.

## `SECURE_HSTS_SECONDS` {: #SECURE_HSTS_SECONDS }

Default: `0`

The `max-age`, in seconds, of the `Strict-Transport-Security` (HSTS) header that
Healthchecks sends on every response to a request it sees as HTTPS (see
[SECURE_PROXY_SSL_HEADER](#SECURE_PROXY_SSL_HEADER)); `0` sends no header. A browser
that has seen the header uses only HTTPS for the host until the `max-age` runs out,
even if you go back to plain HTTP: turn it on once HTTPS works, with a small value
first, such as `3600`, then `31536000` (a year). The header carries neither
`includeSubDomains` nor `preload`. See
[HSTS and the Content Security Policy](../self_hosted_docker/#hsts).

`manage.py check --deploy` reports the warning `security.W004` while it is `0`.

This is a standard Django setting, read more in
[Django documentation](https://docs.djangoproject.com/en/6.1/ref/settings/#secure-hsts-seconds).

## `SECURE_PROXY_SSL_HEADER` {: #SECURE_PROXY_SSL_HEADER }

Default: `HTTP_X_FORWARDED_PROTO,https`

The request header, and its value, that mark a request as made over HTTPS: the header
name and the value, separated with a comma. With the default, Healthchecks treats a
request as HTTPS when the first comma-separated item of its `X-Forwarded-Proto`
header is exactly `https`. That decides the scheme Healthchecks records with each
ping, whether it sends [HSTS](#SECURE_HSTS_SECONDS), and which of Django's CSRF checks
a form gets.

The default fits a reverse proxy that sets `X-Forwarded-Proto` itself, replacing
what the client sent, as Caddy does, and NGINX with
`proxy_set_header X-Forwarded-Proto $scheme` (see
[Reverse Proxy and TLS](../self_hosted_docker/#tls-termination)). If nothing in front
of Healthchecks replaces that header, a client could claim HTTPS: set the variable to
an empty value, `SECURE_PROXY_SSL_HEADER=`, to turn the setting off. In the Docker
image, uWSGI then still treats a request with exactly `X-Forwarded-Proto: https` as
HTTPS.

The header name is written in upper case, with any dashes replaced with underscores,
and prefixed with `HTTP_`. Example:

```ini
# environment variable
SECURE_PROXY_SSL_HEADER=HTTP_X_FORWARDED_PROTO,https
```

**Note on using `local_settings.py`:**
When Healthchecks reads settings from environment variables, it expects
`SECURE_PROXY_SSL_HEADER` to contain header name and value, separated with comma.
If you set `SECURE_PROXY_SSL_HEADER` in `local_settings.py`, it should be a tuple
with two elements instead, or `None` to turn it off:

```ini
# in local_settings.py
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
```

This environment variable maps to a standard Django setting, read more in
[Django documentation](https://docs.djangoproject.com/en/6.1/ref/settings/#secure-proxy-ssl-header).

## `SERVER_EMAIL` {: #SERVER_EMAIL }

Default: the value of [DEFAULT_FROM_EMAIL](#DEFAULT_FROM_EMAIL)

The sender of the error emails Django sends to [ADMINS](#ADMINS). Leave it unset to
send them from `DEFAULT_FROM_EMAIL`. Django's own default, `root@localhost`, is a
sender that an SMTP service sending only from verified addresses, such as Amazon SES,
refuses.

This is a standard Django setting, read more in
[Django documentation](https://docs.djangoproject.com/en/6.1/ref/settings/#server-email).

## `SITE_NAME` {: #SITE_NAME }

Default: `Healthchecks`

The display name of this Healthchecks instance. Healthchecks uses it throughout
its web UI and documentation.

## `SITE_ROOT` {: #SITE_ROOT }

Default: `http://localhost:8000`

The base URL of this Healthchecks instance. Healthchecks uses `SITE_ROOT` whenever
it needs to construct absolute URLs. Healthchecks also uses `SITE_ROOT` to set
several other settings, detailed below.

If the [ALLOWED_HOSTS](#ALLOWED_HOSTS) setting is not set, Healthchecks
automatically populates it with the domain part of `SITE_ROOT`. Under typical scenarios
you can use the automatically populated value and do not need to set
`ALLOWED_HOSTS` yourself.

With an `https://` `SITE_ROOT`, the session, CSRF, messages, device and auto-login
cookies are marked `Secure`, so a browser sends them over HTTPS only: log in through
the HTTPS URL. `SITE_ROOT`'s origin is also trusted for CSRF
(`CSRF_TRUSTED_ORIGINS`), so a form posted from it passes Django's origin check even
when the proxy does not mark the request as HTTPS.

If the SITE_ROOT contains a path (for example, <code>http://localhost:8000<b>/prefix</b></code>),
then Healthchecks automatically sets the following additional Django settings:

* <code>LOGIN_URL=<b>/prefix</b>/accounts/login/</code>. Required
for correct redirection to a log-in page when an unauthenticated user requests a
page that requires authentication. `LOGIN_URL` is a standard Django setting, read more
about it in
[Django documentation](https://docs.djangoproject.com/en/6.1/ref/settings/#login-url).
* <code>STATIC_URL=<b>/prefix</b>/static/</code>. Required for correct
URL generation to static files (JS, CSS, images). `STATIC_URL` is a standard Django
setting, read more about it in
[Django documentation](https://docs.djangoproject.com/en/6.1/ref/settings/#static-url).

With a path, Healthchecks also serves every route under it (`/prefix/accounts/login/`,
`/prefix/ping/<uuid>`, `/prefix/api/v3/...`), so the reverse proxy must forward the
path unchanged, without stripping the prefix.

A trailing slash is removed. A value that does not start with `http://` or
`https://` triggers the warning `hc.api.W001`.

**On using `local_settings.py`:** the settings above, the route prefix and the default
of [PING_ENDPOINT](#PING_ENDPOINT) follow `SITE_ROOT` wherever it is set, in the
environment or in `local_settings.py`, and its trailing slash is removed either way.
One of those settings that `local_settings.py` sets itself keeps that value.

## `SLACK_CLIENT_ID` {: #SLACK_CLIENT_ID }

Default: `None`

The Slack Client ID, used by the Healthchecks integration for Slack.

The integration can work with or without the Slack Client ID. If the Slack Client
ID is not set, the Slack row's "Add Integration" button on the Integrations page opens
a form that asks for a "Webhook URL" (a Slack incoming-webhook URL). If it is set,
the same button opens a page with an "Add to Slack" button instead.

If the Slack Client ID _is_ set, Healthchecks will use the OAuth2 flow
to get the webhook URL from Slack. The OAuth2 flow is more user-friendly.
To set it up, go to [https://api.slack.com/apps/](https://api.slack.com/apps/)
and create a _Slack app_. When setting up the Slack app, make sure to:

* Add the [incoming-webhook](https://api.slack.com/scopes/incoming-webhook)
  scope to the Bot Token Scopes.
* Add a _Redirect URL_ in the format `SITE_ROOT/integrations/add_slack_btn/`.
  For example, if your `SITE_ROOT` is `https://my-hc.example.org` then the
  Redirect URL would be `https://my-hc.example.org/integrations/add_slack_btn/`.

## `SLACK_CLIENT_SECRET` {: #SLACK_CLIENT_SECRET }

Default: `None`

The Slack Client Secret. Required if `SLACK_CLIENT_ID` is set.
Look it up at [https://api.slack.com/apps/](https://api.slack.com/apps/).

## `SLACK_CLIENT_SECRET_FILE` {: #SLACK_CLIENT_SECRET_FILE }

Default: `None`

If set, must contain a filesystem path pointing to a readable file. Healthchecks will
read the contents of the file into the [SLACK_CLIENT_SECRET](#SLACK_CLIENT_SECRET)
setting. If `SLACK_CLIENT_SECRET` and `SLACK_CLIENT_SECRET_FILE` are both set,
`SLACK_CLIENT_SECRET_FILE` takes precedence.

## `SLACK_ENABLED` {: #SLACK_ENABLED }

Default: `True`

A boolean that turns on/off the Healthchecks integration for Slack. Enabled by default.

With `False`, Slack is hidden from the Integrations page and its add pages answer
404. Existing Slack integrations stay listed, but each notification through them
fails with the error "Slack notifications are not enabled."

## `SUPPORT_EMAIL` {: #SUPPORT_EMAIL }

Default: `None`

An email address to contact for help. When it is set, the login page's "Lost your
password?" dialog shows it, and so does the email that
[`sendflappingnotices`](../self_hosted/#sending-notifications) sends.

## `TRUSTED_PROXY_HOPS` {: #TRUSTED_PROXY_HOPS }

Default: `1`

The number of reverse proxies in front of Healthchecks that write the
`X-Forwarded-For` request header. Healthchecks records the client's address with each
ping, and limits login attempts per client address. It takes that address from the
`TRUSTED_PROXY_HOPS`-th entry of `X-Forwarded-For` from the right, the one the
outermost of those proxies wrote, whatever the client put to the left of it:

* `0`: clients connect to Healthchecks directly. The header is ignored, and the
  address of the connection is used.
* `1`: one proxy, such as Caddy or NGINX in front of the Docker container.
* `2` or more: a chain of that many proxies that each append to the header, such as a
  CDN or a load balancer in front of your proxy.

For a request with fewer entries than that, or no header, the address of the
connection is used. An entry that is not an IP address gives none: the ping's
`remote_addr` is `null`, and such login attempts share one limit.

A value below `0`, or `None`, fails the system check `hc.api.E005`, which stops every
`manage.py` command that runs the system checks, the Docker container's start
included. See [TRUSTED_PROXY_HOPS](../self_hosted_docker/#trusted-proxy-hops) on the
Docker page.

## `USE_GZIP_MIDDLEWARE` {: #USE_GZIP_MIDDLEWARE }

Default: `False` (the Docker image sets `True`)

A boolean that adds Django's `GZipMiddleware`, which compresses responses for
clients that accept gzip.

## `WEBHOOKS_ENABLED` {: #WEBHOOKS_ENABLED }

Default: `True`

A boolean that turns on/off the Webhooks integration. Enabled by default.

With `False`, Webhook is hidden from the Integrations page, and its add and edit
pages answer 404. Existing webhook integrations stay listed, but each notification
through them fails with the error "Webhook notifications are not enabled."
