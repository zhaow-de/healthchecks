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
    * `DEFAULT_FROM_EMAIL` – the "From:" address for outbound emails.
    * `EMAIL_HOST` – the SMTP server.
    * `EMAIL_HOST_PASSWORD` – the SMTP password.
    * `EMAIL_HOST_USER` – the SMTP username.
    * `SECRET_KEY` – secures HTTP sessions, set to a random value.
    * `SITE_ROOT` – The base public URL of your Healthchecks instance. Example:
    `SITE_ROOT=https://hc.example.org`.

* Create and start containers:

        $ cd docker
        $ docker compose up

* Create a superuser:

        $ docker compose run web /opt/healthchecks/manage.py createsuperuser

    This will trigger an interactive prompt.

    You can also provide credentials via parameters, bypassing the interactive prompt:

        $ docker compose run web /opt/healthchecks/manage.py createsuperuser --email user@example.com --password changeme123

* Open [http://localhost:8000](http://localhost:8000) in your browser and log in with
  the credentials from the previous step.

## uWSGI Configuration

The reference Dockerfile uses [uWSGI](https://uwsgi-docs.readthedocs.io/en/latest/)
as the WSGI server. You can configure uWSGI by setting `UWSGI_...` environment
variables in `docker/.env`. For example, to disable HTTP request logging, set:

    UWSGI_DISABLE_LOGGING=1

To adjust the number of uWSGI processes (for example, to save memory), set:

    UWSGI_PROCESSES=2

Read more about configuring uWSGI in [uWSGI documentation](https://uwsgi-docs.readthedocs.io/en/latest/Configuration.html#environment-variables).

## Reverse Proxy, TLS Termination, and CSRF Protection {: #tls-termination }

If you plan to expose your Healthchecks instance to the public internet, make sure you
put a TLS-terminating reverse proxy or a load balancer in front of it.

**Important:** configure the reverse proxy to set the `X-Forwarded-For` request
header. Healthchecks trusts it to determine the client's IP address. If the proxy
does not set the `X-Forwarded-For` header, the clients can pass their own value and
circumvent, among other things, the IP-based rate limiting in the login form.

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

Then reload configuration and run `update-ca-certificates` inside the container
as the root user:

```sh
docker compose up
docker compose exec -u root web update-ca-certificates
```

## Upgrading Database

When you upgrade the database version in `docker-compose.yml` (for example,
from `postgres:16` to `postgres:18`), you will also need to upgrade your postgres
data directory. One way to do this is using the
[pgautoupgrade](https://hub.docker.com/r/pgautoupgrade/pgautoupgrade) container.

Starting with `postgres:18`, the image keeps its data in `/var/lib/postgresql/18/docker`
and expects the data volume to be mounted at `/var/lib/postgresql`, not at
`/var/lib/postgresql/data` as earlier versions did. The upgrade below moves your data
into the new layout, so both the upgrade command and `docker-compose.yml` mount the
volume at `/var/lib/postgresql`.

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
as `ghcr.io/zhaow-de/healthchecks`. They are published from the Dockerfile in the
`/docker/` directory: every release as `vX.Y.Z`, every build of the `develop` and `main`
branches as its commit sha, and the newest build of `main` as `latest`.

The Docker images built from the Dockerfile in the `/docker/` directory:

* Support the amd64 architecture only.
* Use uWSGI as the web server. uWSGI is configured to perform database migrations
  on startup, and to run `sendalerts` and `sendreports` in the background.
  You do not need to run them separately.
* Ship with the PostgreSQL database driver.
* Serve static files using the whitenoise library.
* Have the apprise library preinstalled.
* Do *not* handle TLS termination. In a production setup, you will want to put
  the Healthchecks container behind a reverse proxy or load balancer that handles TLS
  termination.


To use a pre-built image for Healthchecks version X.Y.Z, in the `docker-compose.yml` file
replace the "build" section with:

```text
image: ghcr.io/zhaow-de/healthchecks:vX.Y.Z
```
