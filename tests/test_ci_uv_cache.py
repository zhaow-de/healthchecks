"""The uv cache that `.github/workflows/uv-cache.yml` seeds on develop is the one the jobs of
`.github/workflows/tests.yml` look up, and a pull request saves its own copy only when it changes uv.lock."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
SUITE = WORKFLOWS / "tests.yml"
WARMER = WORKFLOWS / "uv-cache.yml"
# setup-uv folds the first five into its cache key (`computeKeys` in its src/cache/restore-cache.ts), with the
# runner's OS and its cache-format version; `cache-local-path` decides the path the cache is saved under, which a
# restore must match too, and `working-directory` the directory the glob is read from: one differing input splits
# the workflows onto caches neither ever restores from the other.
KEY_INPUTS = (
    "python-version",
    "cache-dependency-glob",
    "prune-cache",
    "cache-python",
    "cache-suffix",
    "cache-local-path",
    "working-directory",
)
SAVE_WHEN_THE_LOCK_CHANGED = "${{ steps.lock.outputs.changed == 'true' }}"


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _setup_uv(job: dict) -> dict | None:
    found = [s for s in job.get("steps") or [] if str(s.get("uses", "")).startswith("astral-sh/setup-uv@")]
    assert len(found) <= 1, found
    return found[0] if found else None


def _cached_jobs() -> dict[str, dict]:
    """Every job of tests.yml that installs uv, by id: each one restores from the shared key."""
    return {job_id: job for job_id, job in _load(SUITE)["jobs"].items() if _setup_uv(job) is not None}


def _warmer() -> dict:
    (job,) = _load(WARMER)["jobs"].values()
    return job


def _sync(job: dict) -> list[str]:
    return [s["run"].strip() for s in job["steps"] if str(s.get("run", "")).strip().startswith("uv sync")]


def test_the_suite_has_jobs_that_share_the_cache():
    """The cases below are drawn from these jobs, so a renamed action must not leave them with nothing to check."""
    assert {"django", "tooling"} <= set(_cached_jobs())


@pytest.mark.parametrize("job_id", sorted(_cached_jobs()))
def test_the_warmer_and_each_suite_job_compute_the_same_cache_key(job_id):
    job, warmer = _cached_jobs()[job_id], _warmer()
    assert job["runs-on"] == warmer["runs-on"]
    suite, warm = _setup_uv(job), _setup_uv(warmer)
    assert suite["uses"] == warm["uses"]
    assert suite["with"].get("version") == warm["with"].get("version")
    for name in KEY_INPUTS:
        assert suite.get("with", {}).get(name) == warm.get("with", {}).get(name), name
    assert suite["with"]["cache-dependency-glob"] == "uv.lock"


@pytest.mark.parametrize("job_id", sorted(_cached_jobs()))
def test_whichever_run_saves_the_key_holds_what_every_job_installs(job_id):
    """One install set for every job sharing the key, so a run that saves it holds what the others install."""
    assert _sync(_cached_jobs()[job_id]) == _sync(_warmer()) == ["uv sync --locked"]


def _lock_step(job: dict) -> dict:
    (lock,) = [s for s in job["steps"] if s.get("id") == "lock"]
    return lock


def _lock_step_output(tmp_path: Path, job: dict, *, lockfile_changed: bool, has_base: bool = True) -> str:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)

    def git(*args: str) -> None:
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)

    git("init", "-q")
    (repo / "uv.lock").write_text("base\n")
    git("add", "uv.lock")
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "base")
    if has_base:
        git("update-ref", "refs/remotes/origin/develop", "HEAD")
    if lockfile_changed:
        (repo / "uv.lock").write_text("changed\n")
        git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-am", "the pull request")
    output = tmp_path / "github_output"
    subprocess.run(
        ["bash", "-e", "-c", _lock_step(job)["run"]],
        cwd=repo,
        check=True,
        env={**os.environ, "GITHUB_OUTPUT": str(output)},
    )
    return output.read_text()


@pytest.mark.parametrize("job_id", sorted(_cached_jobs()))
def test_a_pull_request_saves_the_cache_only_when_it_changes_the_lockfile(tmp_path, job_id):
    job = _cached_jobs()[job_id]
    step = _setup_uv(job)
    assert step["with"].get("save-cache") == SAVE_WHEN_THE_LOCK_CHANGED
    assert job["steps"].index(_lock_step(job)) < job["steps"].index(step)
    assert _lock_step_output(tmp_path / "same", job, lockfile_changed=False) == "changed=false\n"
    assert _lock_step_output(tmp_path / "moved", job, lockfile_changed=True) == "changed=true\n"
    assert _lock_step_output(tmp_path / "no-base", job, lockfile_changed=False, has_base=False) == "changed=true\n"
