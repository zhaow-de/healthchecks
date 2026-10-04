# Running with Docker

This is a sample configuration for running Healthchecks with
[Docker](https://www.docker.com) and [Docker Compose](https://docs.docker.com/compose/).

Note: For the sake of simplicity, the sample configuration starts a single database
node and a single web server node, both on the same host. It does not handle TLS
termination.

## Getting Started

* Copy `/docker/.env.example` to `/docker/.env` and add your configuration in it.
  As a minimum, set the following fields:
    * `ALLOWED_HOSTS` – the domain name of your Healthchecks instance.
    Example: `ALLOWED_HOSTS=hc.example.org`.
    * `DEFAULT_FROM_EMAIL` – the "From:" address for outbound emails.
    * `EMAIL_HOST` – the SMTP server.
    * `EMAIL_HOST_PASSWORD` – the SMTP password.
    * `EMAIL_HOST_USER` – the SMTP username.
    * `SECRET_KEY` – secures HTTP sessions, set to a random value.
    * `SITE_ROOT` – The base public URL of your Healthchecks instance. Example:
    `SITE_ROOT=https://hc.example.org`.

* Create and start containers:

  ```sh
  docker compose up
  ```

* Create a superuser:

  ```sh
  docker compose run web /opt/healthchecks/manage.py createsuperuser
  ```

* Open [http://localhost:8000](http://localhost:8000) in your browser and log in with
  the credentials from the previous step.

## Running `manage.py` Commands

* `collectstatic`, `compress` – when running with Docker, you do
  not need to manually run these. These are run while building the container image,
  and their results are baked in the image (you can find them listed in the [Dockerfile](Dockerfile)).
* `migrate`, `sendalerts`, `sendreports` – when running with Docker, you
  also do  not need to manually run these. They are run automatically on
  container startup (you can find them listed in [uwsgi.ini](uwsgi.ini)).
* `createsuperuser`, `prunetokenbucket` – you need to run them
  **inside the container**, not on the host system. Do it like so:

  ```sh
  docker compose run web /opt/healthchecks/manage.py <command>
  ```

  After a login lockout, `prunetokenbucket --all` clears every rate limit
  record and lets you log in again; `changepassword` sets a new password.

## uWSGI Configuration

The reference Dockerfile uses [uWSGI](https://uwsgi-docs.readthedocs.io/en/latest/)
as the WSGI server. You can configure uWSGI by setting `UWSGI_...` environment
variables in `docker/.env`. For example, to adjust the number of uWSGI processes
(to save memory, say), set:

    UWSGI_PROCESSES=2

Read more about configuring uWSGI in [uWSGI documentation](https://uwsgi-docs.readthedocs.io/en/latest/Configuration.html#environment-variables).

## IPv6

uWSGI is configured to listen on IPv4 only by default. To also listen on IPv6, set
the LISTEN_IPV6 environment variable:

    LISTEN_IPV6=1

Unfortunately this cannot be enabled by default because on an IPv4-only system
uWSGI would crash while trying to open an IPv6 socket
(see [issue #1207](https://github.com/healthchecks/healthchecks/issues/1207)).

## TLS Termination and CSRF Protection

If you plan to expose your Healthchecks instance to the public internet, make sure you
put a TLS-terminating reverse proxy or load balancer in front of it.

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

```
proxy_set_header X-Forwarded-Proto $scheme;
```

If you are using haproxy, you can do the same like so:

```
http-request set-header X-Forwarded-Proto https if { ssl_fc }
http-request set-header X-Forwarded-Proto http unless { ssl_fc }
```

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

* Start containers: `docker compose up`
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
as `ghcr.io/zhaow-de/healthchecks`. This repository publishes them from the Dockerfile
in this directory: every release as `vX.Y.Z`, every build of the `develop` and `main`
branches as its commit sha, and the newest build of `main` as `latest`.

The Docker images built from the Dockerfile in this directory:

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

To upgrade to a newer Healthchecks version, edit `docker-compose.yml` and update the
version number in the container image name (the "X.Y.Z" part) and run
`docker compose up`.
