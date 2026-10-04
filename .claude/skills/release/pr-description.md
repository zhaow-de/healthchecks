# Release PR Description Template

Use this template when creating the release PR (fill in `{version}`, and paste the notes step 8 wrote under the last heading):

```markdown
## Release v{version}

This PR promotes `develop` to `main` for release **v{version}**. It contains:
- Everything merged into `develop` since the previous release
- The version bump to {version} (`.cz.toml`, `pyproject.toml`, `uv.lock`)

**Merge with a merge commit (do not squash)** so the tagged bump commit is preserved on `main`.

### Post-merge actions
After this PR is merged, the `release` skill:
1. Pushes the `v{version}` tag, which builds and pushes the release image `ghcr.io/zhaow-de/healthchecks:v{version}`.
2. Creates the GitHub Release `v{version}` in `zhaow-de/healthchecks` with the notes below as its description; this repository keeps no changelog file.
3. Back-merges `main` into `develop` to keep the two in step.

### Release notes

{the notes of step 8}
```
