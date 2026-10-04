# Running with Docker

In the Healthchecks source code, [/docker/ directory](https://github.com/zhaow-de/healthchecks/tree/main/docker),
you can find a sample configuration for running the project with
[Docker](https://www.docker.com) and [Docker Compose](https://docs.docker.com/compose/).

Note: For the sake of simplicity, the sample configuration starts a single database
node and a single web server node, both on the same host. It does not handle TLS
termination.

## Getting Started

* Grab the Healthchecks source code
  [from the GitHub repository](https://github.com/zhaow-de/healthchecks).
* Copy `docker/.env.example` to `docker/.env` and add your configuration in it.
  As a minimum, set the following fields:
    * `ALLOWED_HOSTS` – the domain name of your Healthchecks instance.
    Example: `ALLOWED_HOSTS=hc.example.org`.
    * `DB_PASSWORD` – the PostgreSQL password. The `db` container applies it only
    when it first creates its data volume, so changing it later breaks the
    connection. Keep `DB_USER=postgres`: `docker-compose.yml` does not set
    `POSTGRES_USER`.
    * `PING_ENDPOINT` – the base of ping URLs. The sample sets it to
    `http://localhost:8000/ping/`, so set it to your `SITE_ROOT` followed by
    `/ping/`, or delete the line to derive it from `SITE_ROOT`.
    * `SECRET_KEY` – secures HTTP sessions, set to a random value. Set it before
    you create the first API key and keep it: changing it later invalidates the
    API keys and more (see [SECRET_KEY](../self_hosted_configuration/#SECRET_KEY)).
    * `SITE_ROOT` – The base public URL of your Healthchecks instance. Example:
    `SITE_ROOT=https://hc.example.org`.

    For email (see [Sending Emails](../self_hosted/#sending-emails)), also set:

    * `DEFAULT_FROM_EMAIL` – the "From:" address for outbound emails.
    * `EMAIL_HOST` – the SMTP server.
    * `EMAIL_HOST_PASSWORD` – the SMTP password.
    * `EMAIL_HOST_USER` – the SMTP username.
    * For implicit TLS on port 465, `EMAIL_PORT=465`, `EMAIL_USE_SSL=True` (the
    sample has no such line, so add it) and `EMAIL_USE_TLS=False`.

* Create and start containers in the background:

        $ cd docker
        $ docker compose up -d

    Wait until `docker compose ps` shows the `web` container as healthy: by then
    the database migrations have run.

* Create a superuser:

        $ docker compose exec web /opt/healthchecks/manage.py createsuperuser

    This will trigger an interactive prompt.

    You can also provide credentials via parameters, bypassing the interactive prompt:

        $ docker compose exec web /opt/healthchecks/manage.py createsuperuser --email user@example.com --password correct-horse-battery-staple

    See [Setting Up for Development](../self_hosted/#setting-up-for-development)
    for what `createsuperuser` creates and the password rules.

* Open your `SITE_ROOT` in your browser, through your reverse proxy, and log in
  with the credentials from the previous step.
  [http://localhost:8000](http://localhost:8000) works only while `SITE_ROOT` and
  `ALLOWED_HOSTS` keep their `localhost` sample values: with your own domain set, a
  request to `localhost` gets 400 Bad Request.

## Login Lockout

A browser that has completed a login gets login rate limits of its own, but a
new browser shares them with everyone else, so a run of wrong passwords for the
account's email, from anywhere, can lock it out ([Login Lockout](../self_hosted/#login-lockout)
lists the limits). To get back in, wait for the limits to refill, use the login
link sent by email if email is set up, or clear every rate limit record, the
recent ones too:

```sh
$ docker compose exec web /opt/healthchecks/manage.py prunetokenbucket --all
```

If you have forgotten the password, set a new one with
`docker compose exec web /opt/healthchecks/manage.py changepassword`.

## uWSGI Configuration

The reference Dockerfile uses [uWSGI](https://uwsgi-docs.readthedocs.io/en/latest/)
as the WSGI server. You can configure uWSGI by setting `UWSGI_...` environment
variables in `docker/.env`. For example, to adjust the number of uWSGI processes
(to save memory, say), set:

    UWSGI_PROCESSES=2

Read more about configuring uWSGI in [uWSGI documentation](https://uwsgi-docs.readthedocs.io/en/latest/Configuration.html#environment-variables).

What `docker/uwsgi.ini` and the Dockerfile set:

* Without `UWSGI_PROCESSES`, uWSGI runs 4 worker processes.
* uWSGI listens on `:8000` (IPv4). When `LISTEN_IPV6` is set, to any value, even
  `False`, it listens on `[::]:8000` instead.
* uWSGI kills a worker whose request runs longer than 10 seconds
  (`harakiri = 10`).
* The image sets `USE_GZIP_MIDDLEWARE=True`.
* The image's Docker `HEALTHCHECK` runs `fetchstatus.py`, which requests
  `/api/v3/status/` on port 8000, under `SITE_ROOT`'s path, with `SITE_ROOT`'s host
  as the `Host` header. `SITE_ROOT`'s host must therefore be in `ALLOWED_HOSTS`, or
  the container reports unhealthy (and the `web` container never shows as healthy
  in `docker compose ps`).

## Running on SQLite {: #sqlite }

The image can also run on SQLite, without the `db` container:

* In `docker/.env`, set `DB=sqlite` (any value other than `postgres` selects
  SQLite, which reads `DB_NAME` alone and ignores the other `DB_*` lines) and
  `DB_NAME=/data/hc.sqlite`.
  `/data` is the one directory in the image that its `hc` user can write to:
  without `DB_NAME`, the database file would go under `/opt/healthchecks`, and the
  migrations fail with "unable to open database file".
* In `docker-compose.yml`, remove the `db` service and the `web` service's
  `depends_on`, and mount a named volume at `/data`, so the database outlives the
  container:

```yaml
volumes:
  hc-data: {}

services:
  web:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    env_file:
      - .env
    ports:
      - "8000:8000"
    volumes:
      - hc-data:/data
```

A new named volume takes its owner from the image's `/data`, so the `hc` user can
write to it; a host directory mounted there instead must be writable by user ID 100.

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

Otherwise a client can choose the IP address Healthchecks records for its pings,
and can dodge the per-IP limit on login link requests from a new browser.
Password attempts are limited per email address, not per IP address.

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
web application. In `docker-compose.yml`, add the following in the `web:` section:

```yaml
volumes:
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

## Upgrading Database

When you upgrade the database version in `docker-compose.yml` (for example,
from `postgres:16` to `postgres:18`), you will also need to upgrade your postgres
data directory. One way to do this is using the
[pgautoupgrade](https://hub.docker.com/r/pgautoupgrade/pgautoupgrade) container.

Steps:

* As the very first step, **take a full backup of your database**, for example:
  `docker compose exec -T db pg_dumpall -U postgres > healthchecks-backup.sql`
* Stop the `db` and `web` containers: `docker compose stop`
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

* Update the `docker-compose.yml` file to use the `postgres:18` image and to mount
  the data volume at `/var/lib/postgresql` (with the old mount target, `postgres:18`
  exits with an error that starts
  `Error: in 18+, these Docker images are configured to store database data`):

```yaml
services:
  db:
    image: postgres:18
    volumes:
      - db-data:/var/lib/postgresql
```

* Start containers: `docker compose up -d`
* If the `db` container logs a warning that a database `has a collation version mismatch`,
  the database was created by a `postgres` image built on an older Debian release
  (such as bookworm). `pgautoupgrade` has already reindexed every database, so record
  the new collation version:

```
echo "SELECT format('ALTER DATABASE %I REFRESH COLLATION VERSION', datname) FROM pg_database WHERE datallowconn \gexec" | docker compose exec -T db psql -U postgres
```

## Pre-built Images

Pre-built Docker images are available
[on the GitHub Container Registry](https://github.com/zhaow-de/healthchecks/pkgs/container/healthchecks)
as `ghcr.io/zhaow-de/healthchecks`. They are published from the Dockerfile in the
`/docker/` directory: every release as `vX.Y.Z`, every build of the `develop` and `main`
branches as its full 40-character commit SHA, and the newest build of `main` as
`latest`. The release and `latest` tags start with the first release after v4.5.0,
which predates the image workflow; until then the registry holds only commit-SHA tags
of `develop` builds, and the `latest` line commented out in `docker-compose.yml`
cannot be pulled.

The Docker images built from the Dockerfile in the `/docker/` directory:

* Support the amd64 architecture only.
* Use uWSGI as the web server. uWSGI is configured to perform database migrations
  on startup, and to run `sendalerts` and `sendreports` in the background.
  You do not need to run them separately.
* Ship with the PostgreSQL database driver.
* Serve static files using the whitenoise library.
* Do *not* handle TLS termination. In a production setup, you will want to put
  the Healthchecks container behind a reverse proxy or load balancer that handles TLS
  termination.


To use a pre-built image for Healthchecks version X.Y.Z, in the `docker-compose.yml` file
replace the "build" section with:

```text
image: ghcr.io/zhaow-de/healthchecks:vX.Y.Z
```

For a build of a commit, use its full commit SHA as the tag:

```text
image: ghcr.io/zhaow-de/healthchecks:<commit-sha>
```
