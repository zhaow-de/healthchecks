# python:3.14-alpine is left unpinned on purpose: each build takes the newest Python 3.14
# on the newest Alpine
FROM python:3.14-alpine AS builder

SHELL ["/bin/sh", "-o", "pipefail", "-c"]

COPY --from=ghcr.io/astral-sh/uv:0.12.19@sha256:04d046b13e60d6bcec73cbc5e1cad25d680dea90c8573340950a0ac2d1aef424 /uv /bin/uv

# PyPI has no musllinux wheels for pycurl, psycopg-c and uwsgi, so they compile here:
# gcc and musl-dev for all three, curl-dev for pycurl, libpq-dev for psycopg[c],
# linux-headers for uwsgi
RUN apk add --no-cache gcc musl-dev curl-dev libpq-dev linux-headers

# Use the Python interpreter of the base image, never download one
ENV UV_PYTHON_DOWNLOADS=never
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV UV_COMPILE_BYTECODE=1
ENV UV_NO_CACHE=1

WORKDIR /opt/healthchecks
RUN --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --locked --no-dev --all-extras

FROM python:3.14-alpine

RUN addgroup -S hc && adduser -S -D -H -G hc hc
ENV PYTHONUNBUFFERED=1
WORKDIR /opt/healthchecks

# The libraries the packages compiled in the builder link against:
# libcurl for pycurl, libpq for psycopg[c]
RUN apk add --no-cache libcurl libpq

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# See .dockerignore for the files that are left out of the image
COPY . /opt/healthchecks/
COPY docker/fetchstatus.py /opt/healthchecks/

RUN \
    DEBUG=False SECRET_KEY=build-key ./manage.py collectstatic --noinput && \
    DEBUG=False SECRET_KEY=build-key ./manage.py compress

RUN mkdir /data && chown hc /data
# SQLite on the /data volume. With DB=postgres, set DB_NAME as well: left as
# it is, this path names the PostgreSQL database.
ENV DB_NAME=/data/hc.sqlite

USER hc

ENV USE_GZIP_MIDDLEWARE=True
HEALTHCHECK --start-period=20s --start-interval=5s --interval=60s --retries=1 CMD ./fetchstatus.py
CMD [ "uwsgi", "/opt/healthchecks/docker/uwsgi.ini"]
