![Version](https://img.shields.io/badge/version-v4.5.0-blue)
![License](https://img.shields.io/badge/license-MIT%20%2B%20BSD--3--Clause-blue)
![Python Version from PEP 621 TOML](https://img.shields.io/python/required-version-toml?tomlFilePath=https://raw.githubusercontent.com/zhaow-de/healthchecks/develop/pyproject.toml)
![coverage](https://img.shields.io/coverallsCoverage/github/zhaow-de/healthchecks)

# Healthchecks

This project is a hard fork of
[healthchecks/healthchecks](https://github.com/healthchecks/healthchecks):

* It changes the tooling and harness strategy from zero-AI to AI-first. The
  original project accepts no AI-generated or AI-assisted contributions; this
  one is developed with AI agents, guided by [CLAUDE.md](CLAUDE.md) and the
  rules, skills and workflows under [.claude/](.claude/).
* It removes the features that the
  [zcrypto-kraken](https://github.com/zhaow-de/zcrypto-kraken) project does not
  need.
* It has one user, the superuser that `manage.py createsuperuser` creates: there
  is no sign-up and there are no teams, and `createsuperuser` refuses to run once
  a user exists.
* It introduces the MIT license on top of the original BSD 3-clause license:
  this repository's changes are under MIT, and the code from the original
  project stays under its BSD 3-clause license. Both are in [LICENSE](LICENSE).
* It stays 100% compatible with the original project's
  [API v3](templates/docs/api.md). It takes no email pings, so the email-only
  fields `filter_subject` and `filter_body` it still accepts and returns are
  inert, as api.md describes.

Healthchecks is a cron job monitoring service. It listens for HTTP requests
("pings") from your cron jobs and scheduled tasks ("checks").
When a ping does not arrive on time, Healthchecks sends out alerts.

Healthchecks comes with a web dashboard, API, integrations for
delivering notifications (email, webhooks, Slack, groups), a Prometheus
metrics endpoint, monthly email reports, WebAuthn 2FA support, and projects
to group checks, each with its own read-write and read-only API keys.

The building blocks are:

* Python 3.14
* Django 6.1
* SQLite (the default) or PostgreSQL

This fork's own instance runs at
[https://zcrypto-hc.zhaow.me/](https://zcrypto-hc.zhaow.me/).

A [Dockerfile](docker/)
and [pre-built Docker images](https://github.com/zhaow-de/healthchecks/pkgs/container/healthchecks) are
available.

## Setting Up for Development

If you are planning to develop Healthchecks, please read
[CONTRIBUTING.md](CONTRIBUTING.md).

To set up Healthchecks development environment:

* Install [uv](https://docs.astral.sh/uv/getting-started/installation/).
  Healthchecks uses uv to manage the Python interpreter, the virtual environment
  and the dependencies.

* Check out project code. Feel free to use a different location:

  ```sh
  mkdir -p ~/webapps
  cd ~/webapps
  git clone https://github.com/zhaow-de/healthchecks.git
  cd healthchecks
  ```

* Install requirements (Django, ...):

  ```sh
  uv sync
  ```

  This creates a virtual environment in `.venv` and installs the exact package
  versions listed in `uv.lock`. If you do not have Python 3.14, uv downloads it.

  Most dependencies are installed from pre-built wheels. On platforms where a
  dependency has no pre-built wheel (for example, `cryptography` on Intel Macs),
  uv compiles it from source, and you will need a C compiler and a Rust toolchain.

* Create database tables and the superuser account:

  ```sh
  uv run ./manage.py migrate
  uv run ./manage.py createsuperuser
  ```

  With the default configuration, Healthchecks stores data in a SQLite file
  `hc.sqlite` in the checkout directory (`~/webapps/healthchecks`).

* Run tests:

  ```sh
  uv run pytest hc -n auto
  ```

  pytest drives the Django test suite under `hc/` through pytest-django, and
  `-n auto` (pytest-xdist) spreads it over every CPU core. Add `--cov` for a
  coverage report; `uv run ./manage.py test` runs the same tests serially.

  The tests of the commit and review tooling under `tests/` run with
  `uv run pytest -n auto`. CI runs both on every pull request, the Django suite
  on SQLite and PostgreSQL.

* Run development server:

  ```sh
  uv run ./manage.py runserver
  ```

The site should now be running at `http://localhost:8000`.
To access Django administration site, log in as the superuser, then
visit `http://localhost:8000/admin/`

`uv run` runs a command in the project's virtual environment. Alternatively,
activate the virtual environment with `source .venv/bin/activate`, and then
run `./manage.py` directly. The `./manage.py` examples in the rest of this document
assume an activated virtual environment.

## Configuration

Healthchecks reads configuration from environment variables. See the
[full list of configuration parameters](https://zcrypto-hc.zhaow.me/docs/self_hosted_configuration/)
you can set via environment variables.

In addition, Healthchecks reads settings from the `hc/local_settings.py` file if it
exists. You can set or override any [standard Django setting](https://docs.djangoproject.com/en/6.1/ref/settings/)
in this file, except `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT` and the other
email backend settings Django 6.1 deprecates: Healthchecks always defines `MAILERS`,
and Django refuses them alongside it, so configure SMTP in this file through `MAILERS`
(see [EMAIL_HOST](https://zcrypto-hc.zhaow.me/docs/self_hosted_configuration/#EMAIL_HOST)).
You can copy the provided `hc/local_settings.py.example` as
`hc/local_settings.py` and use it as a starting point.

If a setting is specified both as environment variable and in `hc/local_settings.py`,
the latter takes precedence.

## Accessing Administration Panel

Healthchecks comes with Django's administration panel where you can perform
administrative tasks: change the user's password, inspect contents of
database tables.

To access the administration panel,

 * log into the site using the superuser credentials
 * in the top navigation, "Account" dropdown, select "Site Administration"


## Sending Emails

Healthchecks must be able to send email messages, so it can send out login
links and alerts to users. Specify your SMTP credentials using the following
environment variables:

- Implicit TLS (*recommended*):
    ```ini
    DEFAULT_FROM_EMAIL=valid-sender-address@example.org
    EMAIL_HOST=smtp.example.org
    EMAIL_PORT=465
    EMAIL_HOST_USER=example-username
    EMAIL_HOST_PASSWORD=example-password
    EMAIL_USE_TLS=False
    EMAIL_USE_SSL=True
    ```

    Port 465 should be the preferred method according to [RFC8314 Section 3.3: Implicit
    TLS for SMTP Submission](https://tools.ietf.org/html/rfc8314#section-3.3). Be sure
    to use a TLS certificate and not an SSL one.

- Explicit TLS:
    ```ini
    DEFAULT_FROM_EMAIL=valid-sender-address@example.org
    EMAIL_HOST=smtp.example.org
    EMAIL_PORT=587
    EMAIL_HOST_USER=example-username
    EMAIL_HOST_PASSWORD=example-password
    EMAIL_USE_TLS=True
    ```

Healthchecks uses these environment variables to construct the `settings.MAILERS`
dictionary (a standard Django setting, [docs](https://docs.djangoproject.com/en/6.1/ref/settings/#std-setting-MAILERS)).

## Sending Alerts and Reports

Healthchecks comes with a `sendalerts` management command, which continuously
polls database for any checks changing state, and sends out notifications as
needed. Within an activated virtualenv, you can manually run
the `sendalerts` command like so:

```sh
./manage.py sendalerts
```

In a production setup, you will want to run this command from a process
manager like systemd or [supervisor](http://supervisord.org/).

Healthchecks also comes with a `sendreports` management command which
sends out monthly reports, weekly reports, and the daily or hourly reminders.

Run `sendreports` without arguments to run any due reports and reminders
and then exit:

```sh
./manage.py sendreports
```

Run it with the `--loop` argument to make it run continuously:

```sh
./manage.py sendreports --loop
```

## Database Cleanup

Healthchecks deletes old entries from `api_ping`, `api_flip`, and `api_notification`
tables automatically. By default, Healthchecks keeps the 100 most recent
pings for every check. You can set the limit higher to keep a longer history:
go to the Administration Panel, look up user's **Profile** and modify its
"Ping log limit" field.

Healthchecks also provides a management command for cleaning up the
`api_tokenbucket` (rate limiting records) table. The TokenBucket model is used
for rate-limiting login attempts and similar operations. Any records older than
one day can be safely removed.

```sh
./manage.py prunetokenbucket
```

When you first try this command on your data, it is a good idea to
test it on a copy of your database, not on the live database right away.
In a production setup, you should also have regular, automated database
backups set up.

## Two-factor Authentication

Healthchecks optionally supports two-factor authentication using the WebAuthn
standard. To enable WebAuthn support, set the `RP_ID` (relying party identifier )
setting to a non-null value. Set its value to your site's domain without scheme
and without port. For example, if your site runs on `https://my-hc.example.org`,
set `RP_ID` to `my-hc.example.org`.

## Integrations

### Slack

Healthchecks supports two Slack integration setup flows: legacy and app-based.

The legacy flow does not require additional configuration and is used by default.
In this flow the user creates an incoming webhook URL on the Slack side, and
pastes the webhook URL in a form on the Healthchecks side.

In the app-based flow the user clicks an "Add to Slack" button in Healthchecks,
and gets transferred to a Slack-hosted dialog where they select the channel to
post notifications to. This flow uses OAuth2 behind the scenes. To enable this
flow, you will need to set up a Slack OAuth2 app:

* Create a new Slack app on https://api.slack.com/apps/
* Add at least one scope in the permissions section to be able to deploy the app in
  your workspace (By example `incoming-webhook` for the `Bot Token Scopes`).
* Add a _redirect url_ in the format `SITE_ROOT/integrations/add_slack_btn/`.
  For example, if your SITE_ROOT is `https://my-hc.example.org` then the redirect URL
  would be `https://my-hc.example.org/integrations/add_slack_btn/`.
* Look up your Slack app for the Client ID and Client Secret. Put them
  in `SLACK_CLIENT_ID` and `SLACK_CLIENT_SECRET` environment
  variables. Once these variables are set, Healthchecks will switch from using
  the legacy flow to using the app-based flow.

The legacy and app-based flows only affect the user experience during the initial
setup of Slack integrations. The contents of notifications posted to Slack are the same
regardless of the setup flow used.

## Running in Production

Here is a non-exhaustive list of pointers and things to check before launching a
Healthchecks instance in production.

* Environment variables, settings.py and local_settings.py.
  * [DEBUG](https://docs.djangoproject.com/en/6.1/ref/settings/#debug). Make sure it is
    set to `False`.
  * [ALLOWED_HOSTS](https://docs.djangoproject.com/en/6.1/ref/settings/#allowed-hosts).
    Make sure it contains the correct domain name you want to use.
  * Server Errors. When DEBUG=False, Django will not show detailed error pages;
    exception tracebacks go to the log on the console (see
    [LOG_FORMAT](https://zcrypto-hc.zhaow.me/docs/self_hosted_configuration/#LOG_FORMAT)).
    To receive exception tracebacks in email, review and edit the
    [ADMINS](https://docs.djangoproject.com/en/6.1/ref/settings/#admins) and
    [SERVER_EMAIL](https://docs.djangoproject.com/en/6.1/ref/settings/#server-email)
    settings. Consider setting up exception logging with [Sentry](https://sentry.io/for/django/).
* Use a reverse proxy. Do not expose the Healthchecks instance directly to the public
  internet, put a reverse proxy such as nginx, HAProxy, or Caddy in front of it.

  **Important:** configure the reverse proxy to set the `X-Forwarded-For` request
  header. Healthchecks trusts it to determine the client's IP address. If the proxy
  does not set the `X-Forwarded-For` header, the clients can pass their own value and
  circumvent, among other things, the IP-based rate limiting in the login form.
* Management commands that need to be run during each version upgrade.
  * `manage.py compress` – creates combined JS and CSS bundles and
     places them in the `static-collected` directory.
  * `manage.py collectstatic` – collects static files in the `static-collected`
     directory.
  * `manage.py migrate` – applies any pending database schema changes
     and data migrations.
* Processes that need to be running constantly.
  * `manage.py runserver` is intended for development only.
     **Do not use it in production**, use
     [uWSGI](https://uwsgi-docs.readthedocs.io/en/latest/) instead, as the Docker
     image does with [docker/uwsgi.ini](docker/uwsgi.ini). A minimal setup installs
     uWSGI with `uv sync --no-dev --extra uwsgi` (plus any other extras you use) and
     runs `uv run --no-sync uwsgi --http :8000 --module hc.wsgi --disable-logging`
     from the project's root directory.
  *  `manage.py sendalerts` is the process that monitors checks and sends out
     monitoring alerts. It must be always running, it must be started on reboot, and it
     must be restarted if it itself crashes. On modern linux systems, a good option is
     to [define a systemd service](https://github.com/healthchecks/healthchecks/issues/273#issuecomment-520560304)
     for it.
  * `manage.py sendreports --loop` is the command that sends periodic email reports and
     the email reminders when any checks are down. If you need this functionality, make
     sure `manage.py sendreports --loop` is started on reboot and is always running,
     same as `manage.py sendalerts`.
* Static files. Healthchecks serves static files on its own, no configuration
  required. It uses the [Whitenoise library](http://whitenoise.evans.io/en/stable/index.html)
  for this.
* General
  * Make sure the database is secured well and is getting backed up regularly
  * Make sure the TLS certificates are secured well and are getting refreshed regularly
  * Have monitoring in place to be sure the Healthchecks instance itself is operational
    (is accepting pings, is sending out alerts, is not running out of resources).

## Docker Image

Healthchecks provides a reference Dockerfile. It lives in the [/docker/](docker/)
directory and builds images for the amd64 architecture only. This repository
publishes the images it builds from that Dockerfile
[on the GitHub Container Registry](https://github.com/zhaow-de/healthchecks/pkgs/container/healthchecks)
as `ghcr.io/zhaow-de/healthchecks`: a release as `vX.Y.Z`, every build of the
`develop` and `main` branches as its commit sha, and the newest build of `main` as `latest`.

The Docker images:

* Use uWSGI as the web server. uWSGI is configured to perform database migrations
  on startup, and to run `sendalerts` and `sendreports` in the background.
  You do not need to run them separately.
* Ship with the PostgreSQL database driver.
* Serve static files using the whitenoise library.
* Do *not* handle TLS termination. In a production setup, you will want to put
  the Healthchecks container behind a reverse proxy or load balancer that handles TLS
  termination.
