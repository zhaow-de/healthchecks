# Self-Hosted Healthchecks

Healthchecks is open-source. The code from the original Healthchecks project is
licensed under the BSD 3-clause license, and this fork's changes under the MIT license.

You have the option to host a Healthchecks instance yourself.

The building blocks are:

* Python 3.14
* Django 6.1
* SQLite (the default) or PostgreSQL

## Setting Up for Development

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
    `createsuperuser` refuses to run once a user exists.

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

## Accessing Administration Panel

Healthchecks comes with Django's administration panel where you can perform
administrative tasks: change the user's password, inspect contents of
database tables.

To access the administration panel, log into the site as the superuser.
`createsuperuser` in the setup steps above prompts for its credentials; you can
also provide them via parameters, bypassing the interactive prompt:

    $ ./manage.py createsuperuser --email user@example.com --password changeme123

Once logged in, click on the "Account" dropdown in top navigation, and select
"Site Administration".

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

## Sending Status Notifications

The `sendalerts` management command continuously polls the database for any checks
changing state, and sends out notifications as needed.
When `sendalerts` is not running, the Healthchecks instance will not send out any
alerts.

Within an activated virtualenv, run the `sendalerts` command like so:

    $ ./manage.py sendalerts


In a production setup, make sure the `sendalerts` command can survive
server restarts.

## Database Cleanup {: #database-cleanup }

Healthchecks deletes old entries from `api_ping`, `api_flip`, and `api_notification`
tables automatically. By default, Healthchecks keeps the 100 most recent
pings for every check. You can set the limit higher to keep a longer history:
go to the Administration Panel, look up user's **Profile** and modify its
"Ping log limit" field.

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

## Next Steps

Get the [source code](https://github.com/zhaow-de/healthchecks).

See [Configuration](../self_hosted_configuration/) for a list of configuration options.
