# Running with Docker

This directory holds the files for running Healthchecks with
[Docker](https://www.docker.com) and [Docker Compose](https://docs.docker.com/compose/):

* `docker-compose.yml`: one `web` service that runs the published image
  `ghcr.io/zhaow-de/healthchecks`, with its SQLite database in the `hc-data` volume;
* `docker-compose.postgres.yml`: an override that adds a PostgreSQL 18 `db` service
  and points `web` at it;
* `.env.example`: the settings, to copy to `.env`;
* `Dockerfile`: the image, built from the repository's root directory;
* `uwsgi.ini`: what the image runs: the migrations at start, the web application,
  `sendalerts`, `sendreports` and the daily `prune`;
* `fetchstatus.py`: the image's health check.

The full guide is [Running with Docker](../templates/docs/self_hosted_docker.md),
also served by every instance at `SITE_ROOT/docs/self_hosted_docker/`.
