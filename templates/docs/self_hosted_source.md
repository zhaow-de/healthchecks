# Running from Source

A checkout of the repository, run with uv, is how you develop Healthchecks, and how you run an instance on a host without Docker. For production, [Running with Docker](../self_hosted_docker/) is simpler: the image starts, restarts and schedules every process by itself, while from source you set up each of them.

## Setting Up for Development {: #setting-up-for-development }

Healthchecks uses [uv](https://docs.astral.sh/uv/) to manage the Python interpreter, the [virtual environment](https://docs.python.org/3/tutorial/venv.html) and the dependencies.

* Install uv by following [its installation instructions](https://docs.astral.sh/uv/getting-started/installation/).
* Check out project code. Feel free to use a different location:

        $ mkdir -p ~/webapps
        $ cd ~/webapps
        $ git clone https://github.com/zhaow-de/healthchecks.git
        $ cd healthchecks

* Install requirements (Django, ...):

        $ uv sync

    This creates a virtual environment in `.venv` and installs the exact package versions listed in `uv.lock`, the development tools included. If you do not have Python 3.14, uv downloads it.

* Create database tables and the superuser account (see [Creating the Superuser](../self_hosted/#superuser)):

        $ uv run ./manage.py migrate
        $ uv run ./manage.py createsuperuser

    With the default configuration, Healthchecks stores data in a SQLite file `hc.sqlite` in the project directory (`~/webapps/healthchecks/`).

* Run tests:

        $ uv run ./manage.py test

* Run development server:

        $ uv run ./manage.py runserver

* From another shell, run the `sendalerts` management command, responsible for sending out notifications:

        $ uv run ./manage.py sendalerts

At this point, the site should now be running at `http://localhost:8000`.

`uv run` runs a command in the project's virtual environment. Alternatively, activate the virtual environment with `source .venv/bin/activate`, and then run `./manage.py` directly.

Outside Docker, nothing reads a `.env` file: Healthchecks reads its settings from the environment of each process, and from `hc/local_settings.py`, which overrides the environment. Copy `hc/local_settings.py.example` to `hc/local_settings.py` for a starting point (see [Configuration](../self_hosted_configuration/)).

## Running in Production {: #production }

`manage.py runserver` is intended for development only. In production, an instance from source needs:

* the dependencies without the development tools, and uWSGI;
* its settings, `DEBUG=False` among them (see [Before Going Live](../self_hosted/#checklist)), in the environment of every process below, or in `hc/local_settings.py`;
* the database migrations and the static files, after every checkout of a new version;
* the web application under uWSGI, behind a reverse proxy that terminates TLS;
* `sendalerts` and `sendreports --loop`, always running;
* `prune`, once a day.

Install the dependencies, from the project's root directory:

    $ uv sync --locked --no-dev --extra uwsgi

For PostgreSQL, the host needs the libpq library, which the driver loads; `--extra psycopg-c` also compiles the driver's C implementation, as the Docker image does.

Apply the migrations, and collect and compress the static files into `static-collected/`, with the production settings in the environment:

    $ uv run --no-sync ./manage.py migrate
    $ uv run --no-sync ./manage.py collectstatic --noinput
    $ uv run --no-sync ./manage.py compress

`compress` builds the combined JS and CSS bundles the pages load. Healthchecks serves the files in `static-collected/` itself.

Run the web application under uWSGI, from the project's root directory:

    $ uv run --no-sync uwsgi --http :8000 --module hc.wsgi --disable-logging

[docker/uwsgi.ini](https://github.com/zhaow-de/healthchecks/blob/main/docker/uwsgi.ini) is the configuration the image runs: worker count, time limits, buffer sizes, the migrations at start, the two daemons and the daily `prune`. A copy of it with `chdir` set to your project directory runs all of that from source too, under `uv run --no-sync uwsgi <your copy>`; its `./manage.py` commands run the first `python` on the `PATH`, which `uv run` makes the virtual environment's. With such a copy, skip the daemons and the schedule below.

Put a reverse proxy in front of uWSGI that terminates TLS and sets `X-Forwarded-For` and `X-Forwarded-Proto` as [Reverse Proxy, TLS Termination, and CSRF Protection](../self_hosted_docker/#tls-termination) describes. If submitting a form then fails with 403 "CSRF verification failed.", see [SECURE_PROXY_SSL_HEADER](../self_hosted_configuration/#SECURE_PROXY_SSL_HEADER).

### Running sendalerts and sendreports {: #daemons }

`sendalerts` and `sendreports --loop` have to be always running: started on boot, and started again when they exit. With systemd, give each a service unit. For example, `/etc/systemd/system/hc-sendalerts.service`, with the checkout in `/home/hc/healthchecks` and the settings in `/home/hc/healthchecks.env` as `NAME=value` lines:

```ini
[Unit]
Description=Healthchecks sendalerts
After=network.target

[Service]
User=hc
WorkingDirectory=/home/hc/healthchecks
EnvironmentFile=/home/hc/healthchecks.env
ExecStart=/home/hc/healthchecks/.venv/bin/python manage.py sendalerts --skip-checks
Restart=always

[Install]
WantedBy=multi-user.target
```

`hc-sendreports.service` is the same with `sendreports --loop --skip-checks`. Enable and start both:

    $ sudo systemctl enable --now hc-sendalerts hc-sendreports

### Scheduling the Daily Cleanup {: #prune }

`manage.py prune` deletes what each table keeps past its retention (see [Data Retention](../self_hosted/#database-cleanup)), and nothing runs it by itself outside Docker. Schedule it once a day, with the same settings as the other processes.

With a systemd timer, `/etc/systemd/system/hc-prune.service`:

```ini
[Unit]
Description=Healthchecks daily cleanup

[Service]
Type=oneshot
User=hc
WorkingDirectory=/home/hc/healthchecks
EnvironmentFile=/home/hc/healthchecks.env
ExecStart=/home/hc/healthchecks/.venv/bin/python manage.py prune --skip-checks
```

and `/etc/systemd/system/hc-prune.timer`:

```ini
[Unit]
Description=Run the Healthchecks cleanup daily

[Timer]
OnCalendar=*-*-* 03:17:00 UTC
Persistent=true

[Install]
WantedBy=timers.target
```

Enable the timer, and check when it runs next and how the last run went:

    $ sudo systemctl enable --now hc-prune.timer
    $ systemctl list-timers hc-prune.timer
    $ journalctl -u hc-prune.service

`Persistent=true` makes up for a run missed while the host was down.

With cron instead, add a line to the crontab of the user that owns the checkout, for example:

```text
17 3 * * * cd /home/hc/healthchecks && .venv/bin/python manage.py prune --skip-checks
```

cron gives the command a minimal environment and the host's time zone: keep the settings in `hc/local_settings.py`, or set them in the crontab, and mind that the times are not UTC unless the host's are.

The run prints one summary line, and exits with status 1 and a traceback when it fails. On SQLite, `prune` frees space only in a database file with incremental auto-vacuum; [Data Retention](../self_hosted/#database-cleanup) shows how to switch an older file.

## Upgrading {: #upgrading }

* Take a backup of the database.
* Check out the new version, for example with `git pull`, or `git checkout vX.Y.Z` for a release.
* Install its dependencies: `uv sync --locked --no-dev --extra uwsgi`.
* Apply the migrations and rebuild the static files: `migrate`, `collectstatic --noinput` and `compress`, as above.
* Restart uWSGI, `sendalerts` and `sendreports`.
