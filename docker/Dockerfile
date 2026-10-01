FROM python:3.14.7-slim-trixie AS builder

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# The uv version must satisfy "required-version" in pyproject.toml
COPY --from=ghcr.io/astral-sh/uv:0.12.19@sha256:04d046b13e60d6bcec73cbc5e1cad25d680dea90c8573340950a0ac2d1aef424 /uv /bin/uv

# build-essential is required to build uwsgi, psycopg[c], mysqlclient
# libpq-dev is required to build psycopg[c]
# libmariadb-dev is required to build mysqlclient
# pkg-config is required to build mysqlclient
RUN \
    apt-get update && \
    apt-get install -y build-essential libpq-dev libmariadb-dev pkg-config

# Use the Python interpreter of the base image, never download one
ENV UV_PYTHON_DOWNLOADS=never
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV UV_COMPILE_BYTECODE=1
ENV UV_NO_CACHE=1

WORKDIR /opt/healthchecks
RUN --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --locked --no-dev --all-extras

FROM python:3.14.7-slim-trixie

RUN useradd --system hc
ENV PYTHONUNBUFFERED=1
WORKDIR /opt/healthchecks

RUN \
    apt-get update && \
    apt-get install -y libpq5 libmariadb3 && \
    rm -rf /var/apt/cache && \
    rm -rf /var/lib/apt/lists

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# See .dockerignore for the files that are left out of the image
COPY . /opt/healthchecks/
COPY docker/fetchstatus.py /opt/healthchecks/

RUN \
    DEBUG=False SECRET_KEY=build-key ./manage.py collectstatic --noinput && \
    DEBUG=False SECRET_KEY=build-key ./manage.py compress

RUN mkdir /data && chown hc /data

USER hc

ENV USE_GZIP_MIDDLEWARE=True
HEALTHCHECK --start-period=20s --start-interval=5s --interval=60s --retries=1 CMD ./fetchstatus.py
CMD [ "uwsgi", "/opt/healthchecks/docker/uwsgi.ini"]
