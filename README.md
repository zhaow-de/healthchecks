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

## Running Healthchecks

The way to run an instance in production is the published Docker image,
`ghcr.io/zhaow-de/healthchecks`, with the compose files in [docker/](docker/): SQLite
in a volume by default, or PostgreSQL 18 through `docker-compose.postgres.yml`. In
short, in a copy of `docker/`:

```sh
cp .env.example .env    # then set HC_IMAGE, SECRET_KEY, SITE_ROOT, ALLOWED_HOSTS, PING_ENDPOINT
docker compose up -d
docker compose exec web ./manage.py createsuperuser
```

The operator documentation is in [templates/docs/](templates/docs/), and every
instance serves it under `SITE_ROOT/docs/`:

* [Self-Hosted Healthchecks](https://zcrypto-hc.zhaow.me/docs/self_hosted/):
  what runs, management commands, the administration panel, email, data retention,
  logs, login lockout, and a checklist before going live.
* [Running with Docker](https://zcrypto-hc.zhaow.me/docs/self_hosted_docker/):
  the image, the compose files, PostgreSQL, the daily housekeeping, backups and
  restore, upgrades, the reverse proxy.
* [Configuration](https://zcrypto-hc.zhaow.me/docs/self_hosted_configuration/):
  every environment variable.
* [Running from Source](https://zcrypto-hc.zhaow.me/docs/self_hosted_source/):
  development, and production without Docker, with uWSGI, systemd and a daily
  `prune`.

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
run `./manage.py` directly.

## Configuration

Healthchecks reads configuration from environment variables: with Docker from the
`.env` file beside `docker-compose.yml`, from source from the environment of each
process. See the
[full list of configuration parameters](https://zcrypto-hc.zhaow.me/docs/self_hosted_configuration/).

In addition, Healthchecks reads settings from the `hc/local_settings.py` file if it
exists, and they take precedence over the environment. You can set or override any
[standard Django setting](https://docs.djangoproject.com/en/6.1/ref/settings/)
in this file, except `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT` and the other
email backend settings Django 6.1 deprecates: Healthchecks always defines `MAILERS`,
and Django refuses them alongside it, so configure SMTP in this file through `MAILERS`
(see [EMAIL_HOST](https://zcrypto-hc.zhaow.me/docs/self_hosted_configuration/#EMAIL_HOST)).
You can copy the provided `hc/local_settings.py.example` as
`hc/local_settings.py` and use it as a starting point.

## Sending Emails

Email is optional, but without it there is no login by email link, no email alerts
or reports, and no sudo mode, so the password is set with
`manage.py changepassword`. Set the SMTP server in the `EMAIL_*` variables; see
[Sending Emails](https://zcrypto-hc.zhaow.me/docs/self_hosted/#sending-emails)
for what changes without email and for the settings of implicit and explicit TLS.
