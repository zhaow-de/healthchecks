"""`docker/docker-compose.yml` runs the image on SQLite in the volume it mounts, and `docker/docker-compose.postgres.yml`
layered over it moves the web service to PostgreSQL."""

import re
from pathlib import Path, PurePosixPath

import yaml

DOCKER = Path(__file__).resolve().parent.parent / "docker"
DOCKERFILE = DOCKER / "Dockerfile"
COMPOSE = DOCKER / "docker-compose.yml"
POSTGRES = DOCKER / "docker-compose.postgres.yml"
ENV_EXAMPLE = DOCKER / ".env.example"


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_the_image_keeps_its_sqlite_database_in_the_directory_compose_mounts_a_volume_on():
    runtime = DOCKERFILE.read_text(encoding="utf-8").split("\nFROM ")[-1]
    (db_name,) = re.findall(r"^ENV DB_NAME=(\S+)$", runtime, re.M)
    (owned,) = re.findall(r"^RUN mkdir (\S+) && chown hc \1$", runtime, re.M)
    assert PurePosixPath(db_name).parent == PurePosixPath(owned)

    compose = _load(COMPOSE)
    mounts = [m.split(":") for m in compose["services"]["web"]["volumes"]]
    assert [name for name, target in mounts if target == owned and name in compose["volumes"]]


def test_the_postgres_override_points_web_at_its_db_service():
    override = _load(POSTGRES)
    web, db = override["services"]["web"], override["services"]["db"]
    env = web["environment"]
    assert env["DB"] == "postgres"
    assert env["DB_HOST"] == "db"
    # Left unset, DB_NAME keeps the image's SQLite path, which PostgreSQL would take for the database name.
    assert env["DB_NAME"] == db["environment"]["POSTGRES_DB"]
    assert env["DB_PASSWORD"] == db["environment"]["POSTGRES_PASSWORD"]
    assert web["depends_on"]["db"]["condition"] == "service_healthy"


def test_the_env_example_leaves_the_database_to_the_image():
    # An env_file line replaces the image's ENV: DB_NAME here would move the SQLite file, DB would switch engines.
    lines = ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
    set_here = {line.partition("=")[0] for line in lines if line and not line.startswith("#")}
    assert not set_here & {"DB", "DB_NAME"}
