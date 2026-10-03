# Server Configuration

Healthchecks prepares its configuration in `hc/settings.py`. It reads configuration
from environment variables. Below is a list of environment variables it reads and uses.

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
<li><a href="#EMAIL_PORT">EMAIL_PORT</a></li>
<li><a href="#EMAIL_USE_TLS">EMAIL_USE_TLS</a></li>
<li><a href="#EMAIL_USE_SSL">EMAIL_USE_SSL</a></li>
<li><a href="#EMAIL_USE_VERIFICATION">EMAIL_USE_VERIFICATION</a></li>
<li><a href="#http_proxy">http_proxy and https_proxy</a></li>
<li><a href="#INTEGRATIONS_ALLOW_PRIVATE_IPS">INTEGRATIONS_ALLOW_PRIVATE_IPS</a></li>
<li><a href="#MASTER_BADGE_LABEL">MASTER_BADGE_LABEL</a></li>
<li><a href="#PING_BODY_LIMIT">PING_BODY_LIMIT</a></li>
<li><a href="#PING_ENDPOINT">PING_ENDPOINT</a></li>
<li><a href="#PROMETHEUS_ENABLED">PROMETHEUS_ENABLED</a></li>
<li><a href="#RP_ID">RP_ID</a></li>
<li><a href="#SECRET_KEY">SECRET_KEY</a></li>
<li><a href="#SECRET_KEY_FILE">SECRET_KEY_FILE</a></li>
<li><a href="#SECURE_PROXY_SSL_HEADER">SECURE_PROXY_SSL_HEADER</a></li>
<li><a href="#SITE_LOGO_URL">SITE_LOGO_URL</a></li>
<li><a href="#SITE_NAME">SITE_NAME</a></li>
<li><a href="#SITE_ROOT">SITE_ROOT</a></li>
<li><a href="#SLACK_CLIENT_ID">SLACK_CLIENT_ID</a></li>
<li><a href="#SLACK_CLIENT_SECRET">SLACK_CLIENT_SECRET</a></li>
<li><a href="#SLACK_CLIENT_SECRET_FILE">SLACK_CLIENT_SECRET_FILE</a></li>
<li><a href="#SLACK_ENABLED">SLACK_ENABLED</a></li>
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

## `ALLOWED_HOSTS` {: #ALLOWED_HOSTS }

Default: the domain part of `SITE_ROOT`

The host/domain names that this site can serve. Healthchecks populates this setting
automatically with the domain part of [SITE_ROOT](#SITE_ROOT). You do not need
to set it unless you serve Healthchecks on more than one domain.

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

## `DB_CONN_MAX_AGE` {: #DB_CONN_MAX_AGE }

Default: `0`

This is a standard Django setting, read more in
[Django documentation](https://docs.djangoproject.com/en/6.1/ref/settings/#conn-max-age).

## `DB_HOST` {: #DB_HOST }

Default: `""` (empty string)

This is a standard Django setting, read more in
[Django documentation](https://docs.djangoproject.com/en/6.1/ref/settings/#host).

## `DB_NAME` {: #DB_NAME }

Default: `hc` (PostgreSQL) or `/path/to/projectdir/hc.sqlite` (SQLite)

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

This is a standard Django setting, read more in
[Django documentation](https://docs.djangoproject.com/en/6.1/ref/settings/#debug).

## `DEFAULT_FROM_EMAIL` {: #DEFAULT_FROM_EMAIL }

Default: `healthchecks@example.org`

This is a standard Django setting, read more in
[Django documentation](https://docs.djangoproject.com/en/6.1/ref/settings/#default-from-email).

## `EMAIL_HOST` {: #EMAIL_HOST }

Default: `""` (empty string)

The hostname of a SMTP server to use for sending email. If this environment variable
is not set, Healthchecks will not be able to send any email.

**On using `local_settings.py`:**
Healthchecks reads SMTP settings from the `EMAIL_*` environment variables,
and uses them to construct the `settings.MAILERS` dictionary (a standard Django setting,
read more in [Django documentation](https://docs.djangoproject.com/en/6.1/ref/settings/#std-setting-MAILERS)).
To configure SMTP server in the `local_settings.py` file, use the
`MAILERS` setting, not the individual `EMAIL_*` settings:

```
MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
        "OPTIONS": {
            "host": "smtp.example.org",
            "username": "example-username",
            "password": "example-password",
        },
    },
}
```

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

## `EMAIL_PORT` {: #EMAIL_PORT }

Default: `587`

Port to use for the SMTP server defined in [EMAIL_HOST](#EMAIL_HOST).

## `EMAIL_USE_TLS` {: #EMAIL_USE_TLS }

Default: `True`

hether to use a TLS (secure) connection when talking to the SMTP server.
This is used for explicit TLS connections, generally on port 587.

## `EMAIL_USE_SSL` {: #EMAIL_USE_SSL}

Default: `False`

Whether to use an implicit TLS (secure) connection when talking to the SMTP server.
It is generally used on port 465.

## `EMAIL_USE_VERIFICATION` {: #EMAIL_USE_VERIFICATION }

Default: `True`

A boolean that turns on/off a verification step when adding an email integration.

If enabled, whenever a user adds an email integration, Healthchecks emails a
verification link to the new address. The new integration becomes active only
after the user clicks the verification link.

If you are setting up a private healthchecks instance where
you trust your users, you can opt to disable the verification step. In that case,
set `EMAIL_USE_VERIFICATION` to `False`.

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
is set to `False` by default, because allowing users to define webhooks that probe
internal addresses is a security risk.

Only enable this setting if you run your Healthchecks instance in a trusted
environment, and need to integrate with services running in your internal network.

This setting affects all integration types that make HTTP requests, not just
webhooks: the Slack integration is subject to it as well.

This setting also affects connections to the proxy server when the `http_proxy` or
`https_proxy` environment variables are set. If your proxy server has a private
IP address, you will need to enable `INTEGRATIONS_ALLOW_PRIVATE_IPS` to use it.

## `MASTER_BADGE_LABEL` {: #MASTER_BADGE_LABEL }

Default: same as `SITE_NAME`

The label for the "Overall Status" status badge.

## `PING_BODY_LIMIT` {: #PING_BODY_LIMIT }

Default: `10000`

The upper size limit in bytes for logged ping request bodies.
The default value is 10000 (10 kilobytes). You can adjust the limit or you can remove
it altogether by setting this value to `None`.

Healthchecks stores each ping body in the database, with its ping. Keep
`PING_BODY_LIMIT`, and the bodies your jobs send, no bigger than the output you
actually need to read.

## `PING_ENDPOINT` {: #PING_ENDPOINT }

Default: `SITE_ROOT` + `/ping/`

The base URL to use for constructing ping URLs for display. Healthchecks constructs ping
URLs by appending either an UUID value or `<ping-key>/<slug>` value to `PING_ENDPOINT`.

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

## `RP_ID` {: #RP_ID }

Default: `None`

The [Relying Party identifier](https://www.w3.org/TR/webauthn-2/#relying-party-identifier),
required by the WebAuthn second-factor authentication feature.

Healthchecks optionally supports two-factor authentication using the WebAuthn
standard. To enable WebAuthn support, set the `RP_ID` setting to a non-null value.
Set its value to your site's domain without scheme and without port. For example,
if your site runs on `https://my-hc.example.org`, set `RP_ID` to `my-hc.example.org`.

## `SECRET_KEY` {: #SECRET_KEY }

Default: `---`

A secret key used for cryptographic signing. Should be set to a unique,
unpredictable value.

This is a standard Django setting, read more in
[Django documentation](https://docs.djangoproject.com/en/6.1/ref/settings/#secret-key).

## `SECRET_KEY_FILE` {: #SECRET_KEY_FILE }

Default: `None`

If set, must contain a filesystem path pointing to a readable file. Healthchecks will
read the contents of the file into the [SECRET_KEY](#SECRET_KEY) setting.
If `SECRET_KEY` and `SECRET_KEY_FILE` are both set, `SECRET_KEY_FILE` takes
precedence.

## `SECURE_PROXY_SSL_HEADER` {: #SECURE_PROXY_SSL_HEADER }

Default: `None`

Comma-separated HTTP header name and value that signifies a request is secure
(made over https://). This information is important for CSRF protection.

If Healthchecks is running behind a proxy, the proxy may be "swallowing" whether the original
request uses HTTPS or not. In this case, you may see HTTP 403 errors when submitting
forms (for example, trying to log in).

If set, the value should contain the name of the header to look for and the required
value, separated with comma. The header name must be specified in upper-case,
with any dashes replaced with underscores, and prefixed with `HTTP_`. Example:

```ini
# environment variable
SECURE_PROXY_SSL_HEADER=HTTP_X_FORWARDED_PROTO,https
```

You should *only* set this environment variable if you control your proxy or have some
other guarantee that it sets/strips this header appropriately.

**Note on using `local_settings.py`:**
When Healthchecks reads settings from environment variables, it expects
`SECURE_PROXY_SSL_HEADER` to contain header name and value, separated with comma.
If you set `SECURE_PROXY_SSL_HEADER` in `local_settings.py`, it should be a tuple
with two elements instead:

```ini
# in local_settings.py
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
```

This environment variable maps to a standard Django setting, read more in
[Django documentation](https://docs.djangoproject.com/en/6.1/ref/settings/#secure-proxy-ssl-header).

## `SITE_LOGO_URL` {: #SITE_LOGO_URL }

Default: `None`

An URL pointing to the image you want to use as the site logo. If not set,
Healthchecks will use a fallback image: `/static/img/logo.png`.

You can place a custom logo in `/static/img/`, run `manage.py collectstatic`, and
point `SITE_LOGO_URL` to it like so:

```ini
SITE_LOGO_URL=/static/img/my-custom-logo.png
```

Or you can serve the logo from another server, and point to it using an absolute URL:

```ini
SITE_LOGO_URL=https://example.org/cdn/my-custom-logo.png
```

Either way, Healthchecks will use the provided `SITE_LOGO_URL` value as-is in HTML
pages, and you should use an URL that **the end user's browser will be able to
access directly**. The logo image can use any image format supported by browsers
(PNG, SVG, JPG are all fine).

**Docker note.** You can build a custom Docker image with your logo "baked in". To
do so, use a Dockerfile with the following contents, and with your logo.png placed next
to it:

```docker
FROM ghcr.io/zhaow-de/healthchecks:vX.Y.Z
COPY logo.png /opt/healthchecks/static-collected/img/
```

This overwrites the default placeholder logo, so, in this case, you do not need to
specify `SITE_LOGO_URL`. Notice that the logo must be placed in `static-collected`, not
`static`. This is because `manage.py collectstatic` has already been run in the base
image's build time, and the web server will not recognize any new files placed in the
`static` directory.

## `SITE_NAME` {: #SITE_NAME }

Default: `Mychecks`

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

**On using `local_settings.py`:** Healthchecks only sets the above additional settings
if you specify `SITE_ROOT` via an environment variable. If you instead specify it in
`local_settings.py`, you will also need to set `ALLOWED_HOSTS`, `LOGIN_URL`, and
`STATIC_URL` there.

## `SLACK_CLIENT_ID` {: #SLACK_CLIENT_ID }

Default: `None`

The Slack Client ID, used by the Healthchecks integration for Slack.

The integration can work with or without the Slack Client ID. If
the Slack Client ID is not set, in the "Integrations - Add Slack" page,
Healthchecks will ask the user to provide a webhook URL for posting notifications.

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

## `WEBHOOKS_ENABLED` {: #WEBHOOKS_ENABLED }

Default: `True`

A boolean that turns on/off the Webhooks integration. Enabled by default.
