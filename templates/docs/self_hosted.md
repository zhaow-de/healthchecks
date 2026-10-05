# Self-Hosted Healthchecks

Healthchecks is open-source. The code from the original Healthchecks project is
licensed under the BSD 3-clause license, and this fork's changes under the MIT license.

You have the option to host a Healthchecks instance yourself.

The building blocks are:

* Python 3.14
* Django 6.1
* SQLite (the default) or PostgreSQL

There are two ways to run an instance:

* [Running with Docker](../self_hosted_docker/) is the way to run it in production.
  The published image, `ghcr.io/zhaow-de/healthchecks`, runs everything an instance
  needs in one container, with its SQLite database on a volume, or with PostgreSQL 18
  in a second container.
* [Running from Source](../self_hosted_source/) runs a checkout of the repository
  with uv. It is how you develop Healthchecks, and it runs an instance on a host
  without Docker, where you start, supervise and schedule each process yourself.

Both read their settings from environment variables, listed in
[Configuration](../self_hosted_configuration/). The rest of this page applies to both.

## What Runs {: #what-runs }

An instance is made of:

* the web application: the dashboard, the API and the ping endpoints, served by
  uWSGI (`runserver` in development);
* `manage.py migrate`, before the web application starts: it applies the database
  changes a new version brings;
* `manage.py sendalerts`, always running: it marks late checks down and sends the
  alerts (see [Sending Status Notifications](#sending-notifications));
* `manage.py sendreports --loop`, always running: it sends the reports and reminders;
* `manage.py prune`, once a day: it deletes what each table keeps past its retention
  (see [Data Retention](#database-cleanup)).

In the Docker image, uWSGI runs all of them: `migrate` at every start, `sendalerts`
and `sendreports` as daemons it starts again when they exit, and `prune` every day at
03:17 UTC (see [What Runs in the Container](../self_hosted_docker/#processes)). From
source, you run each of them yourself (see
[Running in Production](../self_hosted_source/#production)).

## Running Management Commands {: #management-commands }

With Docker, run a management command in the `web` container, from the directory
that holds `docker-compose.yml`:

    $ docker compose exec web ./manage.py <command>

From source, run it in the checkout:

    $ uv run ./manage.py <command>

This page names a command as `manage.py <command>`; run it in one of these two ways.
The commands an operator runs by hand:

* `createsuperuser` creates the instance's user (see [Creating the Superuser](#superuser)).
* `changepassword` sets the user's password, and prompts for it twice.
* `prunetokenbucket --all` lifts a [login lockout](#login-lockout).
* `prune` runs the daily cleanup now.
* `sendflappingnotices` emails the owner about flapping checks (see
  [Sending Status Notifications](#sending-notifications)).

## Creating the Superuser {: #superuser }

The superuser is the instance's only user: there is no sign-up. Create it once, after
the first start (from source, after `migrate`):

    $ docker compose exec web ./manage.py createsuperuser

It prompts for the email address and the password. It can also take both as
parameters instead of prompting:

    $ docker compose exec web ./manage.py createsuperuser --email user@example.com --password correct-horse-battery-staple

A password on the command line stays in the shell's history. Without a terminal,
`--email` and `--password` are both required: a missing or invalid one prints an
error and exits with status 2.

Besides the user, `createsuperuser` creates the user's project, a check named
"My First Check" (slug `my-first-check`), and an email integration for the
user's address, already verified and assigned to that check. The password must
pass Django's password validators: at least 12 characters, not too similar to
the email address, not a common password, and not all digits.

`createsuperuser` refuses to run once a user exists: a second run prints
"Error: a user already exists, and this instance has only one" and exits with
status 2.

## Accessing Administration Panel {: #admin-panel }

Healthchecks comes with Django's administration panel where you can perform
administrative tasks: change the user's password, inspect contents of
database tables.

To access the administration panel, log into the site as the superuser, click on the
"Account" dropdown in top navigation, and select "Site Administration". The panel is
at `SITE_ROOT/admin/`.

The panel lists checks, pings, channels (integrations), notifications and flips
(status changes) under "Api"; credentials (security keys), profiles and projects
under "Accounts"; and groups and users under "Authentication and Authorization".
Adding a user, a profile or a security key there is disabled.

Changing the password in the panel goes through sudo mode, which emails a
confirmation code, so it works only with [email set up](#sending-emails). Without
email, the panel shows an "Email Needed" page instead; set the password from the
shell with `manage.py changepassword`, which prompts for the new password twice.

## Sending Emails {: #sending-emails }

Email is optional. Without it, that is while `EMAIL_HOST` is unset:

- the login page offers no "Email Me a Link" login, only the password, and its
  "Lost your password?" dialog points to `./manage.py changepassword`;
- sudo mode, which emails a confirmation code, cannot be entered, so Set Password,
  Change Email, Close Account, adding or removing a two-factor method, and the
  password change in the administration panel all show an "Email Needed" page;
  set the password with `manage.py changepassword` instead;
- email alerts, reports and reminders, and the `ADMINS` error emails are not
  sent; an email integration records each alert it could not send with the error
  "No SMTP configuration";
- while [EMAIL_USE_VERIFICATION](../self_hosted_configuration/#EMAIL_USE_VERIFICATION)
  is on, an email integration can be added only for the account's own address;
- every `manage.py` command that runs the system checks prints the warnings
  `hc.api.W002` ("No SMTP configuration, cannot send email") and Django's
  `mail.W001` ("Your MAILERS setting has no 'default' entry").

Healthchecks reads the SMTP variables below from the process environment. With
Docker, set them in `.env` beside `docker-compose.yml` and run `docker compose up -d`,
which recreates the container with them. From source, nothing loads a `.env` file:
export them in the environment of every process, the web server, `sendalerts`,
`sendreports` and `prune`, or set `MAILERS` in `hc/local_settings.py` (see
[EMAIL_HOST](../self_hosted_configuration/#EMAIL_HOST)). Specify your SMTP
credentials using the following environment variables:

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
`EMAIL_USE_TLS` defaults to `True`, so set it to `False` when you set
`EMAIL_USE_SSL=True`: with both `True`, startup and `manage.py check` report
nothing, but every email fails with Django's `InvalidMailer` error ("The 'use_ssl'
and 'use_tls' OPTIONS are incompatible").

### Example: Amazon SES {: #ses }

Amazon SES takes email over SMTP with STARTTLS on port 587:

```ini
DEFAULT_FROM_EMAIL=healthchecks@example.org
EMAIL_HOST=email-smtp.<region>.amazonaws.com
EMAIL_PORT=587
EMAIL_HOST_USER=<SES SMTP user name>
EMAIL_HOST_PASSWORD=<SES SMTP password>
EMAIL_USE_TLS=True
```

- `EMAIL_HOST` is the SMTP endpoint of the AWS region your SES account sends from,
  such as `email-smtp.eu-central-1.amazonaws.com`.
- `EMAIL_HOST_USER` and `EMAIL_HOST_PASSWORD` are SES SMTP credentials, which the SES
  console creates under its SMTP settings. An IAM access key ID and its secret access
  key are not SMTP credentials, and SES refuses them.
- [DEFAULT_FROM_EMAIL](../self_hosted_configuration/#DEFAULT_FROM_EMAIL) has to be a
  verified identity in SES, the address itself or its domain: SES refuses a message
  from any sender it has not verified. Leave
  [SERVER_EMAIL](../self_hosted_configuration/#SERVER_EMAIL) and
  [EMAIL_MAIL_FROM_TMPL](../self_hosted_configuration/#EMAIL_MAIL_FROM_TMPL) unset,
  or point them at verified addresses too.
- While the SES account is in the sandbox, SES delivers only to verified addresses
  as well: verify the user's own email address, each `ADMINS` address and the address
  of each email integration, or ask AWS for production access.

## Sending Status Notifications {: #sending-notifications }

The `sendalerts` management command continuously polls the database for any checks
changing state, and sends out notifications as needed.
When `sendalerts` is not running, the Healthchecks instance will not send out any
alerts.

`sendalerts` takes `--num-workers N` (default 1), the number of notifications it
sends at the same time. Several `sendalerts` processes can run at once: each check
going down and each status change is handled by exactly one of them.

The `sendreports` management command sends the monthly (or weekly or daily)
reports and, while any check is down, the hourly or daily reminders, as each
profile's notification settings choose. With `--loop` it looks for due reports and
reminders every 60 seconds; without it, it sends what is due once and exits.

Both have to keep running and survive restarts. The Docker image runs
`sendalerts` and `sendreports --loop` under uWSGI, and the compose file's restart
policy starts the container again after a reboot. From source, run them as services
(see [Running from Source](../self_hosted_source/#daemons)).

One more command is for occasional use; nothing runs it by itself:

* `manage.py sendflappingnotices` emails the owner about each check that changed
  status more than 200 times in the last 24 hours.

## Data Retention {: #database-cleanup }

Every table that grows by itself has a bound. Two mechanisms delete the old rows:

* each check prunes its own pings, notifications and flips on every 100th ping it
  receives;
* `manage.py prune` prunes every check the same way, and then the other tables. The
  Docker image runs it every day at 03:17 UTC (see
  [Housekeeping](../self_hosted_docker/#housekeeping)); from source, schedule it
  yourself (see [Scheduling the Daily Cleanup](../self_hosted_source/#prune)).

What each table keeps:

* `api_ping`: each check's pings, up to 99 over the "Ping log limit", 100 by
  default. Each ping stores at most
  [PING_BODY_LIMIT](../self_hosted_configuration/#PING_BODY_LIMIT) bytes of its body.
* `api_notification`: each check's notifications no older than its oldest kept ping.
  The notifications of the integrations' Test button belong to no check, and are
  kept for 30 days.
* `api_flip` (status changes): a check's flips are deleted only when they are older
  than both its oldest kept ping and 93 days, because the downtime statistics need
  about three months of them. A flip `sendalerts` has not handled yet is never
  deleted.
* `api_tokenbucket` (rate limiting records): a day after a record was last used.
  Every limit refills within a day, so this lifts no limit early.
* `django_session` (logins): a session until it expires.
* `django_admin_log` (the administration panel's history of changes): 365 days.

The other tables hold what you create: checks, integrations, projects, API keys and
the user.

To keep a longer or a shorter history of pings, go to the Administration Panel,
open the user's **Profile**, and change its "Ping log limit" field, a number from 1
to 1000. Lowering the limit hides the older pings at once, in the web UI and in the
API, but deletes them only at the check's next prune: its next 100th ping, or the
next daily run. Raising the limit does not bring back pings that were already
deleted.

On SQLite, deleted rows leave free pages in the database file. A database file
that Healthchecks creates uses SQLite's incremental auto-vacuum, and `prune` gives
the free pages back to the file system after it deletes, so the file shrinks to
the data it holds. A file created without it, by an older version for example,
keeps its mode: `prune` then frees no pages and says so in its summary line
("SQLite auto_vacuum is 0, not 2 (INCREMENTAL): no pages freed"). To switch such a
file, stop every process that uses it and run once, in the directory that holds it:

```sh
$ python3 -c "import sqlite3; c = sqlite3.connect('hc.sqlite'); c.execute('PRAGMA auto_vacuum = INCREMENTAL'); c.execute('VACUUM')"
```

`VACUUM` rewrites the whole file: plan for free disk space of twice the size of the
data it holds.

On PostgreSQL, `prune` deletes the same rows and leaves their space to autovacuum,
which makes it reusable within each table.

Back the database up regularly (see [Backups and Restore](../self_hosted_docker/#backups)).

## Logs {: #logs }

Healthchecks writes its log to the console, the standard output of each process,
and nowhere else. With Docker, that is the container's log:

    $ docker compose logs -f web

It shows uWSGI's lines, `migrate`'s output, the messages of `sendalerts` and
`sendreports`, the daily `prune` summary, and the warnings and errors of the web
application. Neither the image's uWSGI nor `runserver` writes a line per HTTP
request. The compose file keeps at most three log files of 10 MB each. With
[LOG_FORMAT](../self_hosted_configuration/#LOG_FORMAT) set to `json`, each record of
Python's logging is a JSON object on one line; uWSGI's own lines, `migrate`'s output
and `prune`'s summary stay plain text in the same stream.

With email set up and `DEBUG=False`, the [ADMINS](../self_hosted_configuration/#ADMINS)
addresses also get an email for each error Django logs, such as a server error (5xx)
while handling a request.

## Login Lockout {: #login-lockout }

Logging in is rate limited:

* password attempts: 20 per 24 hours per email address, refilling at one attempt
  every 72 minutes;
* login link requests: 10 per hour per email address;
* from a browser that has not logged in before, both forms together: 20 attempts
  per hour per client IP address, refilling at one attempt every 3 minutes. IPv6
  clients share the limit of their /64 network.

A browser that has completed a login keeps a device cookie for 365 days. For the
account's email it gets per-email limits of its own and skips the per-IP one. A new
browser shares the per-email limits with everyone else, so a run of wrong passwords
for the account's email, from anywhere, can lock it out; and 20 attempts from one
address, on either form, lock out every new browser behind that address until the
limit refills. The client address is the one your reverse proxy puts in
`X-Forwarded-For`, as [TRUSTED_PROXY_HOPS](../self_hosted_configuration/#TRUSTED_PROXY_HOPS)
selects it; attempts whose address is not an IP address share one limit (see
[Reverse Proxy and TLS](../self_hosted_docker/#tls-termination)).

To get back in, wait for the limits to refill, log in from a browser that has
logged in before, use the login link sent by email if email is set up, or clear
every rate limit record, the recent ones too:

```sh
$ docker compose exec web ./manage.py prunetokenbucket --all
```

From source, that is `uv run ./manage.py prunetokenbucket --all`.

Changing [SECRET_KEY](../self_hosted_configuration/#SECRET_KEY) also resets the
per-email limits, but not the per-IP one, and has other effects, listed there.

## Before Going Live {: #checklist }

* `DEBUG=False`. The Docker image sets it; from source, the default is `True`.
* [SECRET_KEY](../self_hosted_configuration/#SECRET_KEY) set to a random value of at
  least 50 characters before the first API key is created, and kept. With
  `DEBUG=False`, a weak key stops the start.
* [SITE_ROOT](../self_hosted_configuration/#SITE_ROOT) set to the public `https://`
  URL, which marks the console's cookies Secure, and `ALLOWED_HOSTS` unset or listing
  its host.
* A reverse proxy in front that terminates TLS, passes `Host`, and sets
  `X-Forwarded-For` and `X-Forwarded-Proto`, with
  [TRUSTED_PROXY_HOPS](../self_hosted_configuration/#TRUSTED_PROXY_HOPS) matching the
  number of proxies (see [Reverse Proxy and TLS](../self_hosted_docker/#tls-termination)).
* Ping URLs over HTTPS, or the proxy's redirect to HTTPS kept off `/ping/` (see
  [Pings over Plain HTTP](../self_hosted_docker/#http-pings)).
* [SECURE_HSTS_SECONDS](../self_hosted_configuration/#SECURE_HSTS_SECONDS) raised once
  HTTPS works, if you want browsers to use HTTPS only.
* Email set up, if you want email alerts, and
  [ADMINS](../self_hosted_configuration/#ADMINS) set to receive the error emails.
* Backups, and a restore tried once.
* Monitoring of the instance itself from outside it:
  [Check Database Connectivity](../api/#status) (`/api/v3/status/`) for an uptime
  monitor, and [Read Service Metrics](../api/#metrics) (`/api/v3/metrics/`, with
  [METRICS_KEY](../self_hosted_configuration/#METRICS_KEY)), whose
  `num_unprocessed_flips` grows while `sendalerts` is not running.

## Next Steps

* [Running with Docker](../self_hosted_docker/): install, operate and upgrade an
  instance from the published image.
* [Configuration](../self_hosted_configuration/): every setting.
* [Running from Source](../self_hosted_source/): develop Healthchecks, or run it
  without Docker.
