"""The postgres leg of `.github/workflows/tests.yml` tests the PostgreSQL image `docker/docker-compose.postgres.yml` deploys."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SUITE = ROOT / ".github" / "workflows" / "tests.yml"
COMPOSE = ROOT / "docker" / "docker-compose.postgres.yml"


def test_the_postgres_leg_runs_the_image_compose_deploys():
    service = yaml.safe_load(SUITE.read_text(encoding="utf-8"))["jobs"]["django"]["services"]["postgres"]
    # The service's `image` is an expression that names the image for the postgres leg and '' for the sqlite leg.
    (tested,) = re.findall(r"'(postgres:[^']*)'", service["image"])
    deployed = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))["services"]["db"]["image"]
    assert tested == deployed
