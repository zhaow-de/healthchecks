"""A required status check names a job that reports on every pull request into the branch requiring it.

`.github/settings.yml` requires the `name:` of the aggregate job in `.github/workflows/tests.yml` on `develop`
and `main`, with `enforce_admins: true` on both: a required context that no job reports blocks every pull request
into that branch, the owner's included, until the protection is edited by hand outside the repository.
"""

from __future__ import annotations

import itertools
import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SETTINGS = ROOT / ".github" / "settings.yml"
WORKFLOWS = ROOT / ".github" / "workflows"
SUITE = WORKFLOWS / "tests.yml"
AGGREGATE = "suite"  # the job id of the aggregate job in tests.yml
PROTECTED = ("develop", "main")
RESULTS = ("success", "failure", "cancelled", "skipped")  # what `needs.<job>.result` can be
NEEDS_RESULT = re.compile(r"\$\{\{\s*needs\.([A-Za-z0-9_-]+)\.result\s*\}\}")


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _required_contexts(branch: str) -> list[str]:
    """The contexts `branch` requires, [] when settings.yml gives it no required status checks."""
    for entry in _load(SETTINGS).get("branches") or []:
        if entry["name"] == branch:
            checks = (entry.get("protection") or {}).get("required_status_checks")
            return [] if checks is None else list(checks.get("contexts") or [])
    return []


def _aggregate_name() -> str:
    job = _load(SUITE)["jobs"][AGGREGATE]
    return job.get("name") or AGGREGATE


def _conditional_trigger_reason(pr: object, branch: str) -> str | None:
    """Why a `pull_request` trigger might NOT fire for some pull request into `branch`, or None if it always does."""
    if not isinstance(pr, dict):
        return None  # a bare `pull_request:` has no filters and fires for everything
    if (targets := pr.get("branches")) is not None and branch not in targets:
        return f"its `branches` is {targets!r}, which excludes {branch!r}"
    if (excluded := pr.get("branches-ignore")) is not None and branch in excluded:
        return f"its `branches-ignore` {excluded!r} excludes {branch!r}"
    for key in ("paths", "paths-ignore"):
        if pr.get(key) is not None:
            return f"it has a `{key}` filter {pr[key]!r}, so a pull request touching none of those files gets no run"
    if (types := pr.get("types")) is not None and not {"opened", "synchronize"} <= set(types):
        return f"its `types` is {types!r}, which does not cover both `opened` and `synchronize`"
    return None


def _runs_always(condition: object) -> bool:
    """`always()`, bare or in `${{ }}`: the one job-level condition that cannot skip the job."""
    text = str(condition).strip()
    if text.startswith("${{") and text.endswith("}}"):
        text = text[3:-2].strip()
    return text == "always()"


def _job_disqualifier(job: dict) -> str | None:
    """Why a job may not report a check-run named exactly its `name:` on every run, or None if it does."""
    if job.get("strategy") is not None:
        return "it has a `strategy:`, so GitHub appends the matrix values to the reported name"
    if job.get("uses") is not None:
        return "it delegates with `uses:`, so GitHub reports it as `caller / callee`"
    if job.get("if") is not None and not _runs_always(job["if"]):
        return "it has a job-level `if:`, so it can report `skipped`, which satisfies a required check without running"
    if job.get("needs") is not None and job.get("if") is None:
        return "it has `needs:` and no `if: always()`, so a failed job it needs skips it, which satisfies a required check"
    return None


def _check_names_reported_on_prs_into(branch: str) -> tuple[dict[str, Path], list[str]]:
    """The check-run names that always report for a pull request into `branch`, and why any workflow or job was left out."""
    names: dict[str, Path] = {}
    skipped: list[str] = []
    for path in sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml")):
        wf = _load(path)
        # PyYAML reads the bare key `on:` as the boolean True (YAML 1.1), not as the string.
        triggers = wf.get("on", wf.get(True)) or {}
        # `on: pull_request` and `on: [push, pull_request]` carry no filters, so they always fire.
        if isinstance(triggers, str):
            triggers = {triggers: None}
        elif isinstance(triggers, list):
            triggers = dict.fromkeys(triggers)
        if not isinstance(triggers, dict) or "pull_request" not in triggers:
            continue
        if (reason := _conditional_trigger_reason(triggers["pull_request"], branch)) is not None:
            skipped.append(f"{path.name}: {reason}")
            continue
        for job_id, job in (wf.get("jobs") or {}).items():
            job = job or {}
            if (reason := _job_disqualifier(job)) is not None:
                skipped.append(f"{path.name} job {job_id!r}: {reason}")
                continue
            names[job.get("name") or job_id] = path
    return names, skipped


def _needs(job: dict) -> list[str]:
    needs = job.get("needs") or []
    return [needs] if isinstance(needs, str) else list(needs)


def _shell(workflow: dict, job: dict, step: dict) -> list[str]:
    """The command a Linux runner runs a `run:` step's script with."""
    shell = step.get("shell")
    for scope in (job, workflow):
        shell = shell or ((scope.get("defaults") or {}).get("run") or {}).get("shell")
    if shell is None:
        return ["bash", "-e", "-c"]
    assert shell == "bash", f"a step of the aggregate runs under {shell!r}, which this test does not run"
    return ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c"]


def _aggregate_passes(tmp_path: Path, results: dict[str, str]) -> bool:
    """Whether the aggregate job succeeds when the jobs it needs ended with `results`, by running its steps."""
    workflow = _load(SUITE)
    job = workflow["jobs"][AGGREGATE]

    def render(text: object) -> str:
        # GitHub renders the result of a job `needs` does not name as an empty string.
        rendered = NEEDS_RESULT.sub(lambda m: results.get(m[1], ""), str(text))
        assert "${{" not in rendered, f"the aggregate reads an expression this test cannot render: {text!r}"
        return rendered

    files = {name: str(tmp_path / name.lower()) for name in ("GITHUB_ENV", "GITHUB_OUTPUT", "GITHUB_STEP_SUMMARY")}
    for step in job["steps"]:
        declared = {**(workflow.get("env") or {}), **(job.get("env") or {}), **(step.get("env") or {})}
        env = {"PATH": os.environ["PATH"], **files, **{name: render(value) for name, value in declared.items()}}
        done = subprocess.run([*_shell(workflow, job, step), render(step["run"])], env=env, capture_output=True)
        if done.returncode != 0:
            return False
    return True


@pytest.mark.parametrize("branch", PROTECTED)
def test_each_protected_branch_requires_the_aggregate_job_s_name(branch):
    assert SETTINGS.is_file(), f"{SETTINGS} is missing: the branch protection is managed by this file"
    assert _aggregate_name() in _required_contexts(branch), (
        f"{branch} requires {_required_contexts(branch)}, not {_aggregate_name()!r}, the `name:` of job "
        f"{AGGREGATE!r} in {SUITE.name}"
    )


@pytest.mark.parametrize("branch", PROTECTED)
def test_every_required_context_of_a_branch_is_the_aggregate_job_s_name(branch):
    """`main` is read as well as `develop`: it gates the release pull request, which is rarer than a develop merge
    and so has fewer chances to show a context that never reports."""
    for context in _required_contexts(branch):
        assert context == _aggregate_name(), f"{branch} requires {context!r}; {SUITE.name} reports {_aggregate_name()!r}"


@pytest.mark.parametrize(
    ("branch", "context"),
    [(branch, context) for branch in PROTECTED for context in _required_contexts(branch)],
)
def test_every_required_context_is_a_job_that_reports_on_every_pr_into_its_branch(branch, context):
    reported, skipped = _check_names_reported_on_prs_into(branch)
    assert context in reported, (
        f"required context {context!r} is not reported unconditionally by a workflow that runs on pull requests "
        f"into {branch}, so some pull request would wait for it forever (enforce_admins is true: the owner cannot "
        f"override). Names always reported: {sorted(reported)}. Left out: {skipped or 'none'}"
    )


def test_the_aggregate_job_needs_every_other_job_of_the_suite():
    jobs = _load(SUITE)["jobs"]
    assert sorted(_needs(jobs[AGGREGATE])) == sorted(set(jobs) - {AGGREGATE})


def test_the_aggregate_job_fails_unless_every_job_it_needs_succeeded(tmp_path):
    """A step that can be skipped, or whose failure is ignored, lets a failed job through whatever its script says."""
    job = _load(SUITE)["jobs"][AGGREGATE]
    assert not job.get("continue-on-error"), "the aggregate job has `continue-on-error`"
    for step in job["steps"]:
        assert "run" in step, f"the aggregate has a step that runs no script of its own: {step}"
        assert "if" not in step and not step.get("continue-on-error"), f"the aggregate has a conditional step: {step}"
    needs = _needs(job)
    wrong = [
        results
        for results in (dict(zip(needs, combo, strict=True)) for combo in itertools.product(RESULTS, repeat=len(needs)))
        if _aggregate_passes(tmp_path, results) != all(result == "success" for result in results.values())
    ]
    assert not wrong, f"the aggregate's verdict is wrong when the jobs it needs end with {wrong}"


@pytest.mark.parametrize(
    ("job", "reason"),
    [
        ({"needs": ["a"], "if": "always()"}, None),
        ({"needs": ["a"], "if": "${{ always() }}"}, None),
        ({"needs": ["a"], "if": "${{ !cancelled() }}"}, "job-level `if:`"),
        ({"needs": ["a"]}, "`needs:` and no `if: always()`"),
        ({"if": "github.event_name == 'pull_request'"}, "job-level `if:`"),
        ({"strategy": {"matrix": {"db": ["sqlite"]}}}, "`strategy:`"),
        ({"uses": "./.github/workflows/x.yml"}, "`uses:`"),
        ({}, None),
    ],
)
def test_only_always_exempts_a_job_level_condition(job, reason):
    found = _job_disqualifier(job)
    assert (found is None) if reason is None else (found is not None and reason in found), found
