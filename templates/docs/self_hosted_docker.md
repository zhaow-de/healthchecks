# Running with Docker

The way to run Healthchecks in production is the published Docker image,
`ghcr.io/zhaow-de/healthchecks`, under [Docker Compose](https://docs.docker.com/compose/).
The repository's [docker/ directory](https://github.com/zhaow-de/healthchecks/tree/main/docker)
holds the files this page uses:

* `docker-compose.yml`: one `web` service that runs the image, with its SQLite
  database in the `hc-data` volume;
* `docker-compose.postgres.yml`: an override that adds a PostgreSQL 18 `db` service
  and points `web` at it;
* `.env.example`: the settings, to copy to `.env`;
* `Dockerfile` and `uwsgi.ini`: how the image is built, and what it runs.

The container serves plain HTTP on port 8000, published on the Docker host's
loopback address alone. Put a reverse proxy in front of it that terminates TLS (see
[Reverse Proxy, TLS Termination, and CSRF Protection](#tls-termination)).

## The Image {: #image }

The images are published
[on the GitHub Container Registry](https://github.com/zhaow-de/healthchecks/pkgs/container/healthchecks)
as `ghcr.io/zhaow-de/healthchecks`, built from `docker/Dockerfile`, with these tags:

* `vX.Y.Z` for each release: pin one of these in production;
* `latest` for the newest build of `main` or of a release tag;
* the full 40-character commit SHA for each build of the `develop` and `main`
  branches.

The image:

* supports the amd64 architecture only;
* runs as the user `hc` (user ID 100, group ID 101), in `/opt/healthchecks`;
* keeps its SQLite database at `/data/hc.sqlite`: it sets `DB_NAME=/data/hc.sqlite`,
  and `/data` is the one directory `hc` can write to;
* runs uWSGI, which applies the database migrations at every start, serves the web
  application, and runs `sendalerts`, `sendreports` and the daily housekeeping (see
  [What Runs in the Container](#processes));
* serves its static files itself, collected and compressed when the image is built;
* ships the PostgreSQL driver, but no `sqlite3`, `psql`, `pg_dump` or `curl`
  program;
* runs in UTC;
* does *not* handle TLS termination.

## Getting Started {: #getting-started }

* Copy `docker-compose.yml` and `.env.example` from the repository's `docker/`
  directory into a directory on the Docker host, or clone the repository and work
  in its `docker/` directory. Every `docker compose` command on this page runs in
  that directory.
* Copy `.env.example` to `.env` and add your configuration in it. Docker Compose
  passes every line of `.env` to the container, and reads `HC_IMAGE` from it. As a
  minimum, set the following fields:
    * `HC_IMAGE` – the image to run, a release. Example:
    `HC_IMAGE=ghcr.io/zhaow-de/healthchecks:vX.Y.Z`. Without it, the compose file
    runs `latest`.
    * `SECRET_KEY` – secures HTTP sessions, set to a random value. Set it before
    you create the first API key and keep it: changing it later invalidates the
    API keys and more (see [SECRET_KEY](../self_hosted_configuration/#SECRET_KEY)).
    * `SITE_ROOT` – The base public URL of your Healthchecks instance. Example:
    `SITE_ROOT=https://hc.example.org`.
    * `ALLOWED_HOSTS` – the sample sets `localhost`. Set it to the host of
    `SITE_ROOT`, or delete the line to derive it from `SITE_ROOT`: when the host of
    `SITE_ROOT` is not in it, the container does not start.
    * `PING_ENDPOINT` – the base of ping URLs. The sample sets it to
    `http://localhost:8000/ping/`, so set it to your `SITE_ROOT` followed by
    `/ping/`, or delete the line to derive it from `SITE_ROOT`.

    Keep `DEBUG=False` from the sample: the image does not set it, and the default
    is `True`. Leave out `DB` and `DB_NAME`: the image's SQLite path is the default
    (see [SQLite and the /data Volume](#sqlite)).

    For email (see [Sending Emails](../self_hosted/#sending-emails)), also set:

    * `DEFAULT_FROM_EMAIL` – the "From:" address for outbound emails.
    * `EMAIL_HOST` – the SMTP server.
    * `EMAIL_HOST_PASSWORD` – the SMTP password.
    * `EMAIL_HOST_USER` – the SMTP username.
    * For implicit TLS on port 465, `EMAIL_PORT=465`, `EMAIL_USE_SSL=True` (the
    sample has no such line, so add it) and `EMAIL_USE_TLS=False`.

* Create and start the container in the background:

        $ docker compose up -d

    Wait until `docker compose ps` shows the `web` container as healthy: by then
    the database file exists and the migrations have run.

* Create the superuser:

        $ docker compose exec web ./manage.py createsuperuser

    This will trigger an interactive prompt. See
    [Creating the Superuser](../self_hosted/#superuser) for the parameters, what
    `createsuperuser` creates and the password rules.

* Open your `SITE_ROOT` in your browser, through your reverse proxy, and log in
  with the credentials from the previous step. On the Docker host itself,
  [http://localhost:8000](http://localhost:8000) works while `SITE_ROOT` and
  `ALLOWED_HOSTS` keep their `localhost` sample values: with your own domain set, a
  request to `localhost` gets 400 Bad Request.

## The Compose File {: #compose }

`docker-compose.yml` is set up for production:

* `image: ${HC_IMAGE:-ghcr.io/zhaow-de/healthchecks:latest}` runs the image `HC_IMAGE`
  names in `.env`.
* `env_file: .env` passes every line of `.env` to the container.
* `volumes: hc-data:/data` keeps the database in a named volume, so it outlives the
  container. `docker compose down` keeps the volume; `docker compose down -v` deletes
  it, and the database with it.
* `ports: "127.0.0.1:8000:8000"` publishes the port on the Docker host's loopback
  address, for a reverse proxy on the same host. For a proxy on another host,
  publish it on an address that proxy reaches, and keep every other client away from
  it: a client that reaches port 8000 directly chooses its own `X-Forwarded-For`.
* `restart: unless-stopped` starts the container again when it exits and when the
  Docker host restarts, unless you stopped it. Docker does not restart a container
  that is only unhealthy.
* `logging` keeps at most three log files of 10 MB each for the container.

A `<NAME>_FILE` setting (`SECRET_KEY_FILE`, `EMAIL_HOST_PASSWORD_FILE`,
`SLACK_CLIENT_SECRET_FILE`, `DB_PASSWORD_FILE`) reads the value from a file instead,
for example a secret mounted into the container; the file has to be readable by
user ID 100. The image has no `hc/local_settings.py`: to use one, mount it read-only
at `/opt/healthchecks/hc/local_settings.py` in the `web` service's `volumes`.

## SQLite and the /data Volume {: #sqlite }

SQLite is the default. The image sets `DB_NAME=/data/hc.sqlite`, and
`docker-compose.yml` mounts the named volume `hc-data` at `/data`. A `DB_NAME` line
in `.env` would replace the image's path.

The first start creates the database file, owned by `hc`, with SQLite's incremental
auto-vacuum, which lets the daily housekeeping give the space of deleted rows back to
the file system (see [Data Retention](../self_hosted/#database-cleanup)).

A new named volume takes its owner from the image's `/data`, so the `hc` user can
write to it; a host directory mounted there instead must be writable by user ID 100.

## PostgreSQL {: #postgresql }

To run on PostgreSQL 18 instead, layer `docker-compose.postgres.yml` over
`docker-compose.yml`. It adds a `db` service that runs `postgres:18` with its data in
the `db-data` volume, makes `web` wait until `db` is healthy, and points `web` at it.

* Copy `docker-compose.postgres.yml` beside `docker-compose.yml`.
* In `.env`, set `DB_PASSWORD`, the PostgreSQL password: both services refuse to
  start without it. The `db` container applies it only when it first creates its
  data volume, so changing it later breaks the connection. `DB_CONN_MAX_AGE`,
  `DB_SSLMODE` and `DB_TARGET_SESSION_ATTRS` tune the connection; leave `DB`,
  `DB_HOST`, `DB_NAME` and `DB_USER` to the override.
* Name both files in every `docker compose` command:

        $ docker compose -f docker-compose.yml -f docker-compose.postgres.yml up -d

The other commands on this page are written for SQLite. With PostgreSQL, put
`-f docker-compose.yml -f docker-compose.postgres.yml` after `docker compose` in each
of them: without the override, Docker Compose knows no `db` service and no PostgreSQL
settings.

## Running Management Commands {: #management-commands }

Run a management command in the running `web` container:

    $ docker compose exec web ./manage.py <command>

It runs as `hc`, in `/opt/healthchecks`, with the container's settings, and prints
to your terminal, not to the container's log. Add `-T` to pipe input into it, for
example a script for `manage.py shell`:

    $ docker compose exec -T web ./manage.py shell < script.py

While `web` is stopped, run the command in a one-off container instead:

    $ docker compose run --rm --no-deps web ./manage.py <command>

Without `--skip-checks`, a command prints the system checks' warnings first, such as
the two SMTP warnings while `EMAIL_HOST` is unset. `manage.py dbshell` fails, since
the image has no `sqlite3` or `psql` program: use Python's `sqlite3` module for
SQLite, and `psql` in the `db` container for PostgreSQL.

## What Runs in the Container {: #processes }

The container's main process is uWSGI, configured by `docker/uwsgi.ini`. At every
start it:

* runs `./manage.py migrate`, which applies new migrations and runs the system
  checks; when either fails, the container does not start;
* loads the web application and serves it on port 8000;
* starts `./manage.py sendalerts` and `./manage.py sendreports --loop` as daemons,
  and starts either again when it exits;
* schedules `./manage.py prune` every day at 03:17 UTC (see
  [Housekeeping](#housekeeping)).

The start of the container's log shows each of them:

```text
[uwsgi-cron] command "./manage.py prune --skip-checks" registered as cron task
running "exec:./manage.py migrate" (pre app)...
  No migrations to apply.
[uwsgi-daemons] spawning "./manage.py sendalerts --skip-checks" (uid: 100 gid: 101)
[uwsgi-daemons] spawning "./manage.py sendreports --loop --skip-checks" (uid: 100 gid: 101)
2026-10-04 13:51:53,391 INFO hc sendreports is now running
2026-10-04 13:51:53,525 INFO hc sendalerts is now running
```

`docker compose logs -f web` follows the log (see [Logs](../self_hosted/#logs)).

### uWSGI Configuration {: #uwsgi }

You can configure uWSGI by setting `UWSGI_...` environment variables in `.env`. For
example, to adjust the number of uWSGI processes (to save memory, say), set:

    UWSGI_PROCESSES=2

Read more about configuring uWSGI in [uWSGI documentation](https://uwsgi-docs.readthedocs.io/en/latest/Configuration.html#environment-variables).

What `docker/uwsgi.ini` and the Dockerfile set:

* Without `UWSGI_PROCESSES`, uWSGI runs 4 worker processes.
* uWSGI listens on `:8000` (IPv4). When `LISTEN_IPV6` is set, to any value, even
  `False`, it listens on `[::]:8000` instead.
* uWSGI kills a worker whose request runs longer than 10 seconds
  (`harakiri = 10`), and a `prune` run that runs longer than 1800 seconds.
* The image sets `USE_GZIP_MIDDLEWARE=True`.
* The image's Docker `HEALTHCHECK` runs `fetchstatus.py`, which requests
  `/api/v3/status/` on port 8000, under `SITE_ROOT`'s path, with `SITE_ROOT`'s host
  as the `Host` header. `SITE_ROOT`'s host must therefore be in `ALLOWED_HOSTS`, or
  the container reports unhealthy (and the `web` container never shows as healthy
  in `docker compose ps`).

## Housekeeping {: #housekeeping }

uWSGI runs `./manage.py prune` every day at 03:17 UTC, in the same container. It
deletes what each table keeps past its retention (see
[Data Retention](../self_hosted/#database-cleanup)) and, on SQLite, gives the freed
pages back to the file system. A run is skipped while the previous one is still
going; a run stops by itself after 900 seconds and leaves the rest to the next day.
A run missed while the container was down is not made up.

To check that it ran, look for its three lines in the container's log:

    $ docker compose logs --timestamps web

A run logs the time it started, one summary line, and how long it took, for example:

```text
Sun Oct  4 13:54:42 2026 - [uwsgi-cron] running "./manage.py prune --skip-checks" (pid 14)
Deleted api_ping 1400, api_notification 250, api_flip 300, api_tokenbucket 2500, django_session 1234, django_admin_log 0; freed 1522 SQLite pages, 0 left free
[uwsgi-cron] command "./manage.py prune --skip-checks" running with pid 14 exited after 3 second(s)
```

On PostgreSQL the summary line ends after `django_admin_log`. uWSGI does not log the
exit status: a run that fails prints a Python traceback in place of the summary
line. A summary that ends with "reached the 900 s time limit" means the run left
work for the next one.

To run it now, by hand:

    $ docker compose exec web ./manage.py prune --skip-checks

To watch the schedule itself work without waiting for 03:17, add this line to `.env`
and run `docker compose up -d`:

    UWSGI_CRON2="minute=-1,unique=1 ./manage.py prune --skip-checks"

The job then runs a few seconds after the start and every minute after that. Remove
the line and run `docker compose up -d` again.

## Backups and Restore {: #backups }

Keep the backups off the Docker host, and try a restore once.

### SQLite

Back up while the container runs: `VACUUM INTO` writes a consistent copy, and only
reads the live file.

```sh
$ docker compose exec web python -c "import sqlite3; sqlite3.connect('/data/hc.sqlite').execute(\"VACUUM INTO '/tmp/hc-backup.sqlite'\")"
$ docker compose cp web:/tmp/hc-backup.sqlite ./hc-backup.sqlite
```

`VACUUM INTO` refuses an existing target: for a second backup from the same
container, remove `/tmp/hc-backup.sqlite` first. The copy keeps the database's
auto-vacuum mode.

To restore, stop `web`, write the backup into the volume as the `hc` user, and start
`web` again:

    $ docker compose stop web
    $ docker compose run --rm --no-deps -T web sh -c 'cat > /data/hc.sqlite.restore && mv /data/hc.sqlite.restore /data/hc.sqlite' < hc-backup.sqlite
    $ docker compose start web

**Important:** `docker compose cp ./hc-backup.sqlite web:/data/hc.sqlite` alone
leaves the file owned by your host user. The container then starts, reports healthy
and shows the restored data, but cannot write the file: every ping fails with 500
and the log shows "attempt to write a readonly database". After a `docker compose cp`,
give the file to `hc` before you start `web`:

    $ docker compose run --rm --no-deps --user root web chown hc:hc /data/hc.sqlite

Before `docker compose start web`, `docker compose run --rm --no-deps web ls -ln /data`
should show `100` and `101` as the file's owner and group.

### PostgreSQL

Back up with `pg_dump` in the `db` container:

    $ docker compose -f docker-compose.yml -f docker-compose.postgres.yml exec -T db pg_dump -U postgres -Fc hc > hc.dump

To restore, stop `web`, restore into the `hc` database, and start `web` again:

    $ docker compose -f docker-compose.yml -f docker-compose.postgres.yml stop web
    $ docker compose -f docker-compose.yml -f docker-compose.postgres.yml exec -T db pg_restore -U postgres -d hc --clean --if-exists --single-transaction < hc.dump
    $ docker compose -f docker-compose.yml -f docker-compose.postgres.yml start web

## Upgrading {: #upgrading }

A new release is a new image; the database stays in its volume.

* Read the release notes.
* Take a backup (see [Backups and Restore](#backups)).
* Set `HC_IMAGE` in `.env` to the new release, then pull it and recreate the
  container:

        $ docker compose pull
        $ docker compose up -d

* Wait until `docker compose ps` shows `web` as healthy: `migrate` applies the new
  release's migrations at the start.

There is no way back across a migration other than restoring the backup taken
before the upgrade, with the old image.

## Upgrading PostgreSQL {: #upgrading-postgresql }

When you move the `db` service to a new PostgreSQL major version in
`docker-compose.postgres.yml` (for example, from `postgres:16` to `postgres:18`), you
will also need to upgrade your postgres data directory. One way to do this is using
the [pgautoupgrade](https://hub.docker.com/r/pgautoupgrade/pgautoupgrade) container.

Steps:

* As the very first step, **take a full backup of your database**, for example:
  `docker compose -f docker-compose.yml -f docker-compose.postgres.yml exec -T db pg_dumpall -U postgres > healthchecks-backup.sql`
* Stop the `db` and `web` containers:
  `docker compose -f docker-compose.yml -f docker-compose.postgres.yml stop`
* Look up the name of the postgres data volume using `docker volume ls`
* Run `pgautoupgrade` like so (with the old `/var/lib/postgresql/data` mount target
  it exits without upgrading anything):

```
docker run --rm --name pgauto -it \
   --mount type=volume,source=<pg-volume-name-here>,target=/var/lib/postgresql \
   -e POSTGRES_PASSWORD=password \
   -e PGAUTO_ONESHOT=yes \
   pgautoupgrade/pgautoupgrade:18-trixie
```

* Update the `db` service in `docker-compose.postgres.yml` to the new image. From
  `postgres:18` on, the data volume is mounted at `/var/lib/postgresql`, as the file
  does (with the old mount target, `/var/lib/postgresql/data`, `postgres:18` exits
  with an error that starts
  `Error: in 18+, these Docker images are configured to store database data`):

```yaml
services:
  db:
    image: postgres:18
    volumes:
      - db-data:/var/lib/postgresql
```

* Start containers:
  `docker compose -f docker-compose.yml -f docker-compose.postgres.yml up -d`
* If the `db` container logs a warning that a database `has a collation version mismatch`,
  the database was created by a `postgres` image built on an older Debian release
  (such as bookworm). `pgautoupgrade` has already reindexed every database, so record
  the new collation version:

```
echo "SELECT format('ALTER DATABASE %I REFRESH COLLATION VERSION', datname) FROM pg_database WHERE datallowconn \gexec" | docker compose -f docker-compose.yml -f docker-compose.postgres.yml exec -T db psql -U postgres
```

## Reverse Proxy, TLS Termination, and CSRF Protection {: #tls-termination }

If you plan to expose your Healthchecks instance to the public internet, make sure you
put a TLS-terminating reverse proxy or a load balancer in front of it.

**Important:** configure the reverse proxy to replace the `X-Forwarded-For` request
header with the client's address. Healthchecks trusts it to determine the client's
IP address, and takes the first address in it, so appending to a value the client
sent is not enough. In NGINX:

```text
proxy_set_header X-Forwarded-For $remote_addr;
```

(not `$proxy_add_x_forwarded_for`, which appends). In HAProxy:

```text
http-request set-header X-Forwarded-For %[src]
```

Otherwise a client can choose the IP address Healthchecks records for its pings, and
the address its login attempts count against: the per-IP limit of a new browser,
20 attempts per hour on the password and the login link forms together (see
[Login Lockout](../self_hosted/#login-lockout)). A proxy that sets no
`X-Forwarded-For` at all makes every client share the proxy's address, and so one
limit.

**Important:** This Dockerfile uses uWSGI, which relies on the [X-Forwarded-Proto](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Forwarded-Proto)
header to determine if a request is secure or not. Without this information you
may run into HTTP 403 "CSRF verification failed." errors when using your Healthchecks
instance. See [this issue comment](https://github.com/healthchecks/healthchecks/discussions/851#discussioncomment-6293396)
for more information.

Make sure your TLS-terminating reverse proxy:

* Discards the `X-Forwarded-Proto` header sent by the end user.
* Sets the `X-Forwarded-Proto` header value to match the protocol of the original request
  ("http" or "https").

For example, in NGINX you can use the `$scheme` variable like so:

```text
proxy_set_header X-Forwarded-Proto $scheme;
```

If you are using haproxy, you can do the same like so:

```text
http-request set-header X-Forwarded-Proto https if { ssl_fc }
http-request set-header X-Forwarded-Proto http unless { ssl_fc }
```

## Making Healthchecks Trust Your Self-signed TLS Certificate

If you configure Healthchecks to deliver notifications to a server that uses
a self-signed TLS certificate, you may see a "TLS handshake failed" error
when sending a notification.

Healthchecks uses libcurl for making outbound HTTP(S) requests. curl and libcurl
validates certificates and refuses to continue if a certificate cannot be validated.
It is possible to turn off certificate validation, but doing so is
[strongly discouraged in curl docs](https://curl.se/docs/sslcerts.html).

To make curl accept a self-hosted certificate, add your self-signed certificate to
the Healthchecks container's trust store.

First, mount the certificate inside the container running the healthchecks
web application. In `docker-compose.yml`, add it to the `web` service's `volumes`:

```yaml
    volumes:
      - hc-data:/data
      - /path/to/cert.pem:/usr/local/share/ca-certificates/my-selfsigned-cert.crt:ro
```

Note: `/path/to/cert.pem` must be **an absolute path** in the host system pointing
to the certificate.

Then recreate the container with the certificate mounted, and run `update-ca-certificates`
inside it as the root user:

```sh
docker compose up -d
docker compose exec -u root web update-ca-certificates
```

The updated trust store lives in the container, not in a volume, so run the
`exec` command again after every recreate of the `web` container: after a change
to `.env` or `docker-compose.yml`, an image update, or `docker compose down`.

If the server's address is private (127.0.0.1, 192.168.x.x, ...), also set
[INTEGRATIONS_ALLOW_PRIVATE_IPS](../self_hosted_configuration/#INTEGRATIONS_ALLOW_PRIVATE_IPS)
to `True`; otherwise the request is refused before the certificate is checked.

## Building the Image Yourself {: #building }

To run an image of your own checkout, build it from the root of the checkout:

    $ docker build -t hc:local -f docker/Dockerfile .

Then set `HC_IMAGE=hc:local` in `.env` and run `docker compose up -d`. The build
compiles uWSGI, pycurl and the PostgreSQL driver, so the first one takes a while.

Alternatively, replace `image:` in `docker-compose.yml` with the `build:` section its
comment shows, and run `docker compose up -d --build` after each change to the
checkout.
