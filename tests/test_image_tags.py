"""The tag and summary steps of `.github/workflows/image.yml`, run in bash as a Linux runner runs them."""

import os
import subprocess
from pathlib import Path

import pytest
import yaml

IMAGE_YML = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "image.yml"
JOB = "build-push"
TAG_STEP, BUILD_STEP, SUMMARY_STEP = "Choose the tags", "Build and push", "Write image digest to the job summary"
SHA = "0123abcd" * 5


def _workflow() -> dict:
    return yaml.safe_load(IMAGE_YML.read_text(encoding="utf-8"))


def _step(workflow: dict, name: str) -> dict:
    found = [s for s in workflow["jobs"][JOB]["steps"] if s.get("name") == name]
    assert len(found) == 1, f"{JOB} has {len(found)} steps named {name!r}"
    return found[0]


def _bash(workflow: dict, step: dict) -> list[str]:
    """The command a Linux runner runs a `run:` step's script with when no shell is named."""
    for scope in (step, workflow["jobs"][JOB], workflow):
        named = scope.get("shell") or ((scope.get("defaults") or {}).get("run") or {}).get("shell")
        assert named is None, f"a shell is named ({named!r}), which this test does not run"
    return ["bash", "-e", "-c"]


def _outputs(text: str) -> dict[str, str]:
    """$GITHUB_OUTPUT as the runner reads it: `name=value` lines and `name<<DELIMITER` blocks."""
    lines, values = text.splitlines(), {}
    while lines:
        line = lines.pop(0)
        if "<<" in line:
            name, delimiter = line.split("<<", 1)
            end = lines.index(delimiter)
            values[name], lines = "\n".join(lines[:end]), lines[end + 1 :]
        else:
            name, _, value = line.partition("=")
            values[name] = value
    return values


def test_the_build_pushes_the_tags_the_tag_step_chooses_and_the_summary_reads_them():
    workflow = _workflow()
    tag_step = _step(workflow, TAG_STEP)
    assert tag_step.get("id") == "tags"
    assert _step(workflow, BUILD_STEP)["with"]["tags"] == "${{ steps.tags.outputs.refs }}"
    assert _step(workflow, SUMMARY_STEP)["env"]["REFS"] == "${{ steps.tags.outputs.refs }}"


@pytest.mark.parametrize(
    ("event", "ref", "ref_name", "tags"),
    [
        ("push", "refs/heads/develop", "develop", [SHA]),
        ("push", "refs/heads/main", "main", [SHA, "latest"]),
        ("push", "refs/tags/v4.6.0", "v4.6.0", [SHA, "latest", "v4.6.0"]),
        ("workflow_dispatch", "refs/heads/main", "main", [SHA, "latest"]),
        ("workflow_dispatch", "refs/heads/develop", "develop", [SHA]),
        ("workflow_dispatch", "refs/heads/feat/x", "feat/x", [SHA]),
        ("workflow_dispatch", "refs/tags/v4.6.0", "v4.6.0", [SHA]),
    ],
)
def test_the_sha_always_latest_for_main_alone_and_the_release_tag_on_a_tag_push(tmp_path, event, ref, ref_name, tags):
    workflow = _workflow()
    image = workflow["env"]["IMAGE"]
    files = {"GITHUB_OUTPUT": tmp_path / "output", "GITHUB_STEP_SUMMARY": tmp_path / "summary"}
    env = {
        "PATH": os.environ["PATH"],
        "IMAGE": image,
        "GITHUB_SHA": SHA,
        "GITHUB_EVENT_NAME": event,
        "GITHUB_REF": ref,
        "GITHUB_REF_NAME": ref_name,
        **{name: str(path) for name, path in files.items()},
    }
    tag_step = _step(workflow, TAG_STEP)
    subprocess.run([*_bash(workflow, tag_step), tag_step["run"]], env=env, check=True)
    refs = _outputs(files["GITHUB_OUTPUT"].read_text())["refs"]
    assert refs.split("\n") == [f"{image}:{tag}" for tag in tags]

    summary = _step(workflow, SUMMARY_STEP)
    subprocess.run([*_bash(workflow, summary), summary["run"]], env={**env, "DIGEST": "sha256:feed", "REFS": refs}, check=True)
    listed = [line for line in files["GITHUB_STEP_SUMMARY"].read_text().splitlines() if line.startswith("- Tags: ")]
    assert listed == ["- Tags: " + ", ".join(f"`{tag}`" for tag in tags)]
