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
[Reverse Proxy and TLS](#tls-termination)); [Example: Debian 13 on a VPS](#debian-vps)
puts the pieces together, with Caddy in front.

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
* sets `DEBUG=False`, and does not start without a strong `SECRET_KEY` (see
  [Getting Started](#getting-started));
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
    * `SECRET_KEY` – secures HTTP sessions, set to a random value of at least 50
    characters, with at least 5 different ones, that does not start with
    `django-insecure-`.
    The sample's `---` does not pass: with it, or any weaker key, the container does
    not start. Generate one with
    `python3 -c 'import secrets; print(secrets.token_urlsafe(50))'`. Set it before
    you create the first API key and keep it: changing it later invalidates the
    API keys and more (see [SECRET_KEY](../self_hosted_configuration/#SECRET_KEY)).
    * `SITE_ROOT` – The base public URL of your Healthchecks instance. Example:
    `SITE_ROOT=https://hc.example.org`. With an `https://` URL, the console's
    cookies are marked Secure, so you log in over HTTPS only.
    * `ALLOWED_HOSTS` – the sample sets `localhost`. Set it to the host of
    `SITE_ROOT`, or delete the line to derive it from `SITE_ROOT`: when the host of
    `SITE_ROOT` is not in it, the container does not start.
    * `PING_ENDPOINT` – the base of ping URLs. The sample sets it to
    `http://localhost:8000/ping/`, so set it to your `SITE_ROOT` followed by
    `/ping/`, or delete the line to derive it from `SITE_ROOT`.

    The image sets `DEBUG=False`, as does the sample; keep it so. Leave out `DB`
    and `DB_NAME`: the image's SQLite path is the default (see
    [SQLite and the /data Volume](#sqlite)).

    For email (see [Sending Emails](../self_hosted/#sending-emails), and
    [Example: Amazon SES](../self_hosted/#ses)), also set:

    * `DEFAULT_FROM_EMAIL` – the "From:" address for outbound emails.
    * `EMAIL_HOST` – the SMTP server.
    * `EMAIL_HOST_PASSWORD` – the SMTP password.
    * `EMAIL_HOST_USER` – the SMTP username.
    * For implicit TLS on port 465, `EMAIL_PORT=465`, `EMAIL_USE_SSL=True` (the
    sample has no such line, so add it) and `EMAIL_USE_TLS=False`.

* Create and start the container in the background:

        $ docker compose up -d

    Wait until `docker compose ps` shows the `web` container as healthy: by then
    the database file exists and the migrations have run. A container that keeps
    restarting instead, which `docker compose up -d --wait` reports as unhealthy,
    refused to start: `docker compose logs web` shows why, such as `hc.api.E004`
    for a weak `SECRET_KEY`, or `hc.api.E002` for a `SITE_ROOT` host missing from
    `ALLOWED_HOSTS`.

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
  it: a client that reaches port 8000 directly, a process on the Docker host
  included, chooses its own `X-Forwarded-For` (see
  [TRUSTED_PROXY_HOPS](#trusted-proxy-hops)).
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

The database runs in SQLite's WAL mode: while it is in use, `hc.sqlite-wal` and
`hc.sqlite-shm` sit beside `hc.sqlite` in `/data`, and the latest commits are in the
`-wal` file until a checkpoint copies them into `hc.sqlite`. So:

* `/data` must be a local file system, used by the containers of one host: WAL mode
  does not work over a network file system.
* Never copy `hc.sqlite` alone while the container runs: the copy misses what the
  `-wal` file holds, and a restore of it is inconsistent. Back up with `VACUUM INTO`
  (see [Backups and Restore](#backups)).
* A clean stop (`docker compose stop` or `down`) checkpoints the `-wal` file and
  removes both files. A killed container (`docker kill`, out of memory, a host
  crash) leaves them, and the next start applies the `-wal` file to `hc.sqlite`.
* The first write after a checkpoint cuts the `-wal` file back to 16 MiB, but under
  sustained concurrent writes it grows past that between checkpoints: keep about
  50 MiB of disk free for it beside the database.

Commits use `synchronous = NORMAL`: a crash of the container loses no committed ping,
but a power loss or a crash of the host's operating system can lose the last ones.

## PostgreSQL {: #postgresql }

To run on PostgreSQL 18 instead, layer `docker-compose.postgres.yml` over
`docker-compose.yml`. It adds a `db` service that runs `postgres:18` with its data in
the `db-data` volume, makes `web` wait until `db` is healthy, and points `web` at it.

* Copy `docker-compose.postgres.yml` beside `docker-compose.yml`.
* In `.env`, set `DB_PASSWORD`, the PostgreSQL password: both services refuse to
  start without it. The `db` container applies it only when it first creates its
  data volume, so changing it later breaks the connection. `DB_SSLMODE` and
  `DB_TARGET_SESSION_ATTRS` tune the connection; leave `DB`, `DB_HOST`, `DB_NAME`
  and `DB_USER` to the override. With
  [DB_CONN_MAX_AGE](../self_hosted_configuration/#DB_CONN_MAX_AGE) at its default,
  600 seconds, each uWSGI worker keeps its connection open between requests, so
  PostgreSQL holds a connection per worker beside those of the daemons.
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
  checks; when either fails, uWSGI exits before it starts any worker, and the
  compose file's restart policy starts the container again, in a loop, until the
  cause is fixed;
* loads the web application and serves it on port 8000;
* starts `./manage.py sendalerts` and `./manage.py sendreports --loop` as daemons,
  and starts either again when it exits;
* schedules `./manage.py prune` every day at 03:17 UTC (see
  [Housekeeping](#housekeeping)).

The start of the container's log shows each of them, among uWSGI's other lines:

```text
running "exec:./manage.py migrate" (asap)...
  No migrations to apply.
*** Starting uWSGI 2.0.31 (64bit) on [Sun Oct  4 20:05:03 2026] ***
[uwsgi-cron] command "./manage.py prune --skip-checks" registered as cron task
spawned uWSGI worker 1 (pid: 8, cores: 1)
spawned uWSGI worker 2 (pid: 9, cores: 1)
spawned uWSGI worker 3 (pid: 10, cores: 1)
spawned uWSGI worker 4 (pid: 11, cores: 1)
[uwsgi-daemons] spawning "./manage.py sendalerts --skip-checks" (uid: 100 gid: 101)
[uwsgi-daemons] spawning "./manage.py sendreports --loop --skip-checks" (uid: 100 gid: 101)
2026-10-04 20:05:06,036 INFO hc sendreports is now running
2026-10-04 20:05:06,156 INFO hc sendalerts is now running
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
* uWSGI refuses a request whose body is larger than 2,621,440 bytes (2.5 MiB)
  before it reads the body, and closes the connection without an HTTP response
  (`limit-post`; curl reports "Empty reply from server", exit code 52).
  `UWSGI_LIMIT_POST` replaces that limit: with a
  [PING_BODY_LIMIT](../self_hosted_configuration/#PING_BODY_LIMIT) above 2,621,440,
  set it to the same value.
* uWSGI treats a request with `X-Forwarded-Proto: https` as HTTPS, as Healthchecks
  does by default (see
  [SECURE_PROXY_SSL_HEADER](../self_hosted_configuration/#SECURE_PROXY_SSL_HEADER)).
* The image sets `DEBUG=False` and `USE_GZIP_MIDDLEWARE=True`.
* The image's Docker `HEALTHCHECK` runs `fetchstatus.py`, which requests
  `/api/v3/status/` on port 8000, over plain HTTP, under `SITE_ROOT`'s path, with
  `SITE_ROOT`'s host as the `Host` header; it works with an `https://` `SITE_ROOT`
  too. A `SITE_ROOT` host missing from `ALLOWED_HOSTS` stops the container before
  that, with `hc.api.E002`.

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
Deleted api_ping 833, api_notification 0, api_flip 0, api_tokenbucket 0, django_session 0, django_admin_log 0; freed 90 SQLite pages, 0 left free; checkpointed 841 of 841 WAL frames
[uwsgi-cron] command "./manage.py prune --skip-checks" running with pid 14 exited after 3 second(s)
```

On SQLite, the run ends with a checkpoint, which moves the `-wal` file's frames into
`hc.sqlite`, so the file shrinks by the pages the run freed; "checkpointed N of M"
with N below M means another connection still needed some frames, and a later
checkpoint moves them. On PostgreSQL the summary line ends after `django_admin_log`.

uWSGI does not log the exit status: a run that fails prints a Python traceback in
place of the summary line. A summary that ends with "reached the 900 s time limit"
means the run left work for the next one.

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

Back up while the container runs: `VACUUM INTO` writes a consistent copy, the
commits still in `hc.sqlite-wal` included, and only reads the live database.

```sh
$ docker compose exec web python -c "import sqlite3; sqlite3.connect('/data/hc.sqlite').execute(\"VACUUM INTO '/tmp/hc-backup.sqlite'\")"
$ docker compose cp web:/tmp/hc-backup.sqlite ./hc-backup.sqlite
```

`VACUUM INTO` refuses an existing target: for a second backup from the same
container, remove `/tmp/hc-backup.sqlite` first. The copy keeps the database's
auto-vacuum mode, and is a single file in SQLite's rollback-journal mode; the first
connection after a restore switches it back to WAL mode.

To restore, stop `web`, remove the `-wal` and `-shm` files, write the backup into
the volume as the `hc` user, and start `web` again:

    $ docker compose stop web
    $ docker compose run --rm --no-deps -T web sh -c 'rm -f /data/hc.sqlite-wal /data/hc.sqlite-shm /data/hc.sqlite-journal && cat > /data/hc.sqlite.restore && mv /data/hc.sqlite.restore /data/hc.sqlite' < hc-backup.sqlite
    $ docker compose start web

**Important:** the `rm -f` is part of the restore. A killed container leaves its
`-wal` and `-shm` files, and the next start applies that old `-wal` file to the
restored `hc.sqlite`: the result is a corrupt database, and nothing reports it.

**Important:** `docker compose cp ./hc-backup.sqlite web:/data/hc.sqlite` alone
leaves the `-wal` and `-shm` files in place, and the file owned by your host user. The
container then starts, reports healthy and shows the restored data, but cannot write
the file: every ping fails with 500 and the log shows "attempt to write a readonly
database". After a `docker compose cp`, remove the two files and give the database
to `hc` before you start `web`:

    $ docker compose run --rm --no-deps --user root web sh -c 'rm -f /data/hc.sqlite-wal /data/hc.sqlite-shm /data/hc.sqlite-journal && chown hc:hc /data/hc.sqlite'

Before `docker compose start web`, `docker compose run --rm --no-deps web ls -ln /data`
should show `hc.sqlite` alone, with `100` and `101` as its owner and group.

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

## Reverse Proxy and TLS {: #tls-termination }

The container serves plain HTTP on `127.0.0.1:8000`. Expose Healthchecks to the
internet only through a reverse proxy that terminates TLS and that:

* passes the `Host` header unchanged: Healthchecks answers 400 to a host that is not
  in [ALLOWED_HOSTS](../self_hosted_configuration/#ALLOWED_HOSTS);
* sets `X-Forwarded-Proto` to the scheme the client used, replacing any value the
  client sent: Healthchecks trusts it to tell an HTTPS request (see
  [SECURE_PROXY_SSL_HEADER](../self_hosted_configuration/#SECURE_PROXY_SSL_HEADER)),
  for the scheme it records with each ping, for HSTS, and for Django's CSRF checks;
* sets or appends to `X-Forwarded-For` the client's address: Healthchecks takes the
  client's address from it, as [TRUSTED_PROXY_HOPS](#trusted-proxy-hops) describes.

Caddy does all three by default.

### Caddy {: #caddy }

On Debian 13, install Caddy from Debian's own repository. The package runs Caddy
under systemd as the `caddy` user, and keeps the certificates in that user's home,
`/var/lib/caddy`:

    $ sudo apt install caddy

Replace the package's `/etc/caddy/Caddyfile`, which serves a placeholder page on port
80, with one site block that names your `SITE_ROOT` host and forwards to the
container:

```text
hc.example.org {
	reverse_proxy 127.0.0.1:8000
}
```

Check the file, and reload Caddy:

    $ sudo caddy validate --config /etc/caddy/Caddyfile
    $ sudo systemctl reload caddy

With this, Caddy:

* listens on TCP ports 80 and 443 on every IPv4 and IPv6 address of the host, and on
  UDP port 443 for HTTP/3;
* gets a public certificate for the name, which needs the name's `A` and `AAAA` DNS
  records to point at the host, and ports 80 and 443 to be reachable: keep port 80
  open beside 443, for the certificate authority's challenge and for the redirect;
* answers every plain-HTTP request with a 308 redirect to HTTPS, ping URLs included
  (see [Pings over Plain HTTP](#http-pings));
* passes `Host` unchanged, and replaces `X-Forwarded-For`, `X-Forwarded-Proto` and
  `X-Forwarded-Host` with what it saw: one address, the client's, IPv4 or IPv6, and
  `https`. A client that forges these headers changes nothing Healthchecks records,
  and [TRUSTED_PROXY_HOPS](#trusted-proxy-hops) stays at its default, `1`;
* adds no `Strict-Transport-Security` header (see [HSTS](#hsts)).

### Pings over Plain HTTP {: #http-pings }

Behind Caddy, give your jobs `https://` ping URLs. With an `https://` `SITE_ROOT`,
`PING_ENDPOINT`, and so every ping URL Healthchecks shows, is one already. An
`http://` ping URL gets Caddy's 308 redirect, which `curl -fsS` takes for success: it
exits with 0, prints nothing, and the ping is not recorded, `--retry` or not. With
`-L`, curl follows the redirect, keeps the method and the body, and the ping is
recorded.

Healthchecks itself never redirects to HTTPS: `SECURE_SSL_REDIRECT` stays off, so
pings and the image's health check work over plain HTTP wherever the proxy lets them
through. The redirect to HTTPS belongs at the proxy, and is for the console: if you
have jobs that ping over plain HTTP and that you cannot change, keep `/ping/` out of
it. In Caddy, add this block to the Caddyfile, which forwards `/ping/` over plain
HTTP and redirects every other path:

```text
http://hc.example.org {
	handle /ping/* {
		reverse_proxy 127.0.0.1:8000
	}
	handle {
		redir https://{host}{uri} 308
	}
}
```

Such pings are recorded with the scheme `http`; Caddy still replaces a forged
`X-Forwarded-Proto: https`. With a path in `SITE_ROOT`, the ping path is
`/<path>/ping/*`.

### TRUSTED_PROXY_HOPS {: #trusted-proxy-hops }

Healthchecks records each ping's client address, and limits login attempts per
client address (see [Login Lockout](../self_hosted/#login-lockout)). It reads the
address from `X-Forwarded-For` as
[TRUSTED_PROXY_HOPS](../self_hosted_configuration/#TRUSTED_PROXY_HOPS) describes;
the default, `1`, fits one proxy such as Caddy or NGINX, which may append to the
header as well as replace it. Behind a second proxy, such as a CDN, Caddy replaces
the header, and so does not append, unless the outer proxy's addresses are in its
`trusted_proxies` option.

Whatever reaches port 8000 without passing the proxy chooses its own address: with
the compose file's `127.0.0.1` binding, that is any process on the Docker host.

### NGINX {: #nginx }

NGINX needs the three headers set in the `location` that forwards to the container:

```text
proxy_pass http://127.0.0.1:8000;
proxy_set_header Host $host;
proxy_set_header X-Forwarded-For $remote_addr;
proxy_set_header X-Forwarded-Proto $scheme;
```

`$proxy_add_x_forwarded_for`, which appends, works with `TRUSTED_PROXY_HOPS=1` too.
On port 80, forward `location /ping/` the same way, and answer every other path with
`return 308 https://$host$request_uri;`.

In HAProxy:

```text
http-request set-header X-Forwarded-For %[src]
http-request set-header X-Forwarded-Proto https if { ssl_fc }
http-request set-header X-Forwarded-Proto http unless { ssl_fc }
```

### HSTS and the Content Security Policy {: #hsts }

HSTS, the `Strict-Transport-Security` response header, makes a browser use only HTTPS
for the host. Neither Caddy nor Healthchecks sends it by default; once HTTPS works,
turn it on with
[SECURE_HSTS_SECONDS](../self_hosted_configuration/#SECURE_HSTS_SECONDS). It changes
nothing for your jobs' pings: curl keeps no HSTS list unless it runs with `--hsts`,
and a client that keeps one only moves its pings to HTTPS.

Every response carries an enforced `Content-Security-Policy`, so the proxy needs to
add none. If you customise a template, an inline `<script>` or `<style>` element
needs `{% csp_nonce_attr %}` in its tag, and a `style` attribute or an inline event
handler such as `onclick` has to move to a static file: the browser blocks them
otherwise.

## Example: Debian 13 on a VPS {: #debian-vps }

One host, such as a Linode node with Debian 13, runs the image on SQLite under Docker
Compose; Caddy, from Debian's package, terminates TLS on port 443 over IPv4 and IPv6
and forwards to the container on `127.0.0.1:8000`; email goes out through Amazon SES.
The host steps marked *(not tested here)* were not verified with this setup: follow
their own documentation where it differs.

* **DNS** *(not tested here)*: point the `A` and `AAAA` records of the name, here
  `hc.example.org`, at the host's IPv4 and IPv6 addresses. Caddy needs them for the
  certificate.
* **Firewall** *(not tested here)*: allow inbound TCP 80 and 443, and UDP 443 for
  HTTP/3, over IPv4 and IPv6, besides SSH. Port 8000 needs no rule: the compose file
  publishes it on `127.0.0.1` only.
* **Docker** *(not tested here)*: install Docker Engine and its Compose plugin from
  Docker's own apt repository, as
  [Docker's guide for Debian](https://docs.docker.com/engine/install/debian/)
  describes.
* **Healthchecks**: in a directory such as `/srv/healthchecks`, put
  `docker-compose.yml` and `.env.example` from the repository's `docker/` directory,
  copy `.env.example` to `.env`, and set in it:

        HC_IMAGE=ghcr.io/zhaow-de/healthchecks:vX.Y.Z
        SECRET_KEY=<the output of: python3 -c 'import secrets; print(secrets.token_urlsafe(50))'>
        SITE_ROOT=https://hc.example.org

    Delete the `ALLOWED_HOSTS` and `PING_ENDPOINT` lines, so that both follow
    `SITE_ROOT`, and set the email settings of
    [Example: Amazon SES](../self_hosted/#ses). `TRUSTED_PROXY_HOPS=1` and the default
    `SECURE_PROXY_SSL_HEADER` fit Caddy. Start the container, which waits until it is
    healthy, and create the superuser:

        $ docker compose up -d --wait
        $ docker compose exec web ./manage.py createsuperuser

* **Caddy**: install it, put the site block of [Caddy](#caddy) with your name in
  `/etc/caddy/Caddyfile`, check it, and reload (*systemd's reload not tested here*):

        $ sudo apt install caddy
        $ sudo caddy validate --config /etc/caddy/Caddyfile
        $ sudo systemctl reload caddy

* **Check** *(the public certificate not tested here)*: open
  `https://hc.example.org`, log in, and ping "My First Check" with the URL its
  details page shows:

        $ curl -fsS https://hc.example.org/ping/<uuid>
        OK

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
