# Self-Hosted Healthchecks

Healthchecks is open-source. The code from the original Healthchecks project is
licensed under the BSD 3-clause license, and this fork's changes under the MIT license.

You have the option to host a Healthchecks instance yourself.

The building blocks are:

* Python 3.14
* Django 6.1
* SQLite (the default) or PostgreSQL

## Setting Up for Development {: #setting-up-for-development }

You can set up a development environment on your local system to develop a new
feature, write a new integration or test a bugfix. Healthchecks uses
[uv](https://docs.astral.sh/uv/) to manage the Python interpreter,
the [virtual environment](https://docs.python.org/3/tutorial/venv.html)
and the dependencies.

* Install uv by following
  [its installation instructions](https://docs.astral.sh/uv/getting-started/installation/).

* Check out project code. Feel free to use a different location:

        $ mkdir -p ~/webapps
        $ cd ~/webapps
        $ git clone https://github.com/zhaow-de/healthchecks.git
        $ cd healthchecks

* Install requirements (Django, ...):

        $ uv sync

    This creates a virtual environment in `.venv` and installs the exact package
    versions listed in `uv.lock`. If you do not have Python 3.14, uv downloads it.

* Create database tables and the superuser account:

        $ uv run ./manage.py migrate
        $ uv run ./manage.py createsuperuser

    The superuser is the instance's only user: there is no sign-up, and
    `createsuperuser` refuses to run once a user exists: a second run prints
    "Error: a user already exists, and this instance has only one" and exits with
    status 2.

    Besides the user, `createsuperuser` creates the user's project, a check named
    "My First Check" (slug `my-first-check`), and an email integration for the
    user's address, already verified and assigned to that check. The password must
    pass Django's password validators: at least 12 characters, not too similar to
    the email address, not a common password, and not all digits. Without a
    terminal, `--email` and `--password` (see
    [Accessing Administration Panel](#admin-panel)) are both required: a missing
    or invalid one prints an error and exits with status 2.

    With the default configuration, Healthchecks stores data in a SQLite file
    `hc.sqlite` in the project directory (`~/webapps/healthchecks/`).

* Run tests:

        $ uv run ./manage.py test

* Run development server:

        $ uv run ./manage.py runserver

* From another shell, run the `sendalerts` management command, responsible for
  sending out notifications:

        $ uv run ./manage.py sendalerts

At this point, the site should now be running at `http://localhost:8000`.

`uv run` runs a command in the project's virtual environment. Alternatively,
activate the virtual environment with `source .venv/bin/activate`, and then
run `./manage.py` directly. The `./manage.py` examples in the rest of this document
assume an activated virtual environment.

## Accessing Administration Panel {: #admin-panel }

Healthchecks comes with Django's administration panel where you can perform
administrative tasks: change the user's password, inspect contents of
database tables.

To access the administration panel, log into the site as the superuser. In the
setup steps above, `createsuperuser` can take its credentials as parameters
instead of prompting:

    $ ./manage.py createsuperuser --email user@example.com --password correct-horse-battery-staple

Once logged in, click on the "Account" dropdown in top navigation, and select
"Site Administration". The panel is at `SITE_ROOT/admin/`.

The panel lists checks, pings, channels (integrations), notifications and flips
(status changes) under "Api"; credentials (security keys), profiles and projects
under "Accounts"; log records under "Logs"; and groups and users under
"Authentication and Authorization". Adding a user, a security key or a log record
there is disabled.

Changing the password in the panel goes through sudo mode, which emails a
confirmation code, so it works only with [email set up](#sending-emails). Without
email, the panel shows an "Email Needed" page instead; set the password from the
shell with `./manage.py changepassword`, which prompts for the new password twice.

## Sending Emails {: #sending-emails }

Email is optional. Without it, that is while `EMAIL_HOST` is unset:

- the login page offers no "Email Me a Link" login, only the password;
- sudo mode, which emails a confirmation code, cannot be entered, so Set Password,
  Change Email, Close Account, adding or removing a two-factor method, and the
  password change in the administration panel all show an "Email Needed" page;
  set the password with `./manage.py changepassword` instead;
- email alerts, reports and reminders, and the `ADMINS` error emails are not
  sent;
- every `manage.py` command that runs the system checks prints the warnings
  `hc.api.W002` ("No SMTP configuration, cannot send email") and Django's
  `mail.W001` ("Your MAILERS setting has no 'default' entry").

Healthchecks reads the SMTP variables below from the process environment, and
outside Docker nothing loads a `.env` file for it: export them in the shell, or the
service definition, that runs `runserver` (or your WSGI server), `sendalerts` and
`sendreports`, or set `MAILERS` in `hc/local_settings.py` (see
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

## Sending Status Notifications {: #sending-notifications }

The `sendalerts` management command continuously polls the database for any checks
changing state, and sends out notifications as needed.
When `sendalerts` is not running, the Healthchecks instance will not send out any
alerts.

Within an activated virtualenv, run the `sendalerts` command like so:

    $ ./manage.py sendalerts

`sendalerts` takes `--num-workers N` (default 1), the number of notifications it
sends at the same time. Several `sendalerts` processes can run at once: each check
going down and each status change is handled by exactly one of them.

The `sendreports` management command sends the monthly (or weekly or daily)
reports and, while any check is down, the hourly or daily reminders, as each
profile's notification settings choose. Run it as a second long-running process:

    $ ./manage.py sendreports --loop

With `--loop` it looks for due reports and reminders every 60 seconds; without
it, it sends what is due once and exits.

In a production setup, make sure the `sendalerts` and `sendreports --loop`
commands can survive server restarts. The Docker image runs both under uWSGI
(see [Running with Docker](../self_hosted_docker/)).

Two more commands are for occasional use, from cron for example; nothing runs them
by itself:

* `./manage.py sendlogs` emails the `ADMINS` addresses the number of log records
  written in the last 24 hours, with a link to them, and sends nothing when there
  are none.
* `./manage.py sendflappingnotices` emails the owner about each check that changed
  status more than 200 times in the last 24 hours.

## Database Cleanup {: #database-cleanup }

Healthchecks deletes old entries from the `api_ping`, `api_flip`, and
`api_notification` tables automatically. Each check prunes its own entries on every
100th ping it receives:

* pings older than the newest "Ping log limit" pings are deleted (100 by default);
* notifications older than the oldest kept ping are deleted;
* status changes (flips) are deleted only when they are older than both the oldest
  kept ping and 93 days, because the downtime statistics need about three months
  of them.

To keep a longer or a shorter history, go to the Administration Panel, open the
user's **Profile**, and change "Ping log limit" under "Limits". Lowering the limit
hides the older pings at once, in the web UI and in the API, but deletes them only
at the check's next prune. To prune every check now, run:

```sh
$ ./manage.py prunepingsslow
```

It prunes, one by one, every check that has received more than 100 pings. Raising
the limit does not bring back pings that were already deleted. Whatever the limit,
the API returns at most 1000 pings (see [List check's logged pings](../api/#list-pings)).

Log records (Site Administration › Logs › Records) are never pruned
automatically; delete old ones in the Administration Panel.

Healthchecks provides a management command for cleaning up the `api_tokenbucket`
(rate limiting records) table. The TokenBucket model is used for rate-limiting
login attempts and similar operations. Any records older than one day can be
safely removed.

```sh
$ ./manage.py prunetokenbucket
```

When you first try this command on your data, it is a good idea to
test it on a copy of your database, not on the live database right away.
In a production setup, you will want to run this command regularly, as well as
have regular, automatic database backups set up.

## Login Lockout {: #login-lockout }

Logging in is rate limited per email address:

* password attempts: 20 per 24 hours, refilling at one attempt every 72 minutes;
* login link requests: 10 per hour, plus, from a browser that has not logged in
  before, 20 per client IP address per hour.

A browser that has completed a login keeps a device cookie for 365 days and gets
login rate limits of its own, but a new browser shares them with everyone else, so
a run of wrong passwords for the account's email, from anywhere, can lock it out.
To get back in, wait for the limits to refill, use the login link sent by email if
email is set up, or clear every rate limit record, the recent ones too:

```sh
$ ./manage.py prunetokenbucket --all
```

Changing [SECRET_KEY](../self_hosted_configuration/#SECRET_KEY) also resets the
per-email limits, but not the per-IP one, and has other effects, listed there.

If you have forgotten the password, set a new one with `./manage.py changepassword`.

## Next Steps

Get the [source code](https://github.com/zhaow-de/healthchecks).

See [Configuration](../self_hosted_configuration/) for a list of configuration options.
