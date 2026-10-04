# GitHub Actions

You can augment your GitHub Actions workflows to report success and
failure to SITE_NAME:

```yaml
name: Hourly Housekeeping
on:
  schedule:
    - cron: '15 * * * *'
jobs:
  Main-Job:
    runs-on: ubuntu-latest
    steps:
      - run: echo "Running housekeeping tasks..."
  Ping-Success:
    runs-on: ubuntu-latest
    needs: [Main-Job]
    steps:
      - run: curl -fsS -m 10 --retry 5 ${{ secrets.ping_url }}
  Ping-Failure:
    runs-on: ubuntu-latest
    if: ${{ failure() }}
    needs: [Main-Job]
    steps:
      - run: curl -fsS -m 10 --retry 5 ${{ secrets.ping_url }}/fail
```

Note how the jobs `Ping-Success` and `Ping-Failure` define `Main-Job` as
their dependency. `Ping-Success` runs only if `Main-Job` completes
successfully, and `Ping-Failure` runs when `Main-Job` fails.

To avoid exposing the ping URL, it is a good idea to define it
as [a secret](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
and access it via the `secrets` context.

The curl calls use `-f`, so a wrong URL (a 404) fails the step and the error shows
in the run; without it, the step succeeds and the ping is silently lost. The
[Shell Scripts](../bash/) page explains the other options.

Give the check a cron schedule equal to the workflow's (`15 * * * *`) with the time
zone UTC, since GitHub evaluates `schedule` in UTC, or a period of 1 hour; you can
[create such a check](../api/#create-check) with the Management API. Give it a grace
time that covers GitHub's start delays: scheduled runs often start minutes late, and
later under load. If `Main-Job` is cancelled, neither ping job runs, and the check
goes down when the grace time ends.

## Using the `workflow_run` Trigger

Alternatively, you can put the pinging logic in a separate workflow,
and configure it to trigger every time your main workflow finishes. The main workflow:

```yaml
name: Hourly Housekeeping
on:
  schedule:
    - cron: '15 * * * *'
jobs:
  Main-Job:
    runs-on: ubuntu-latest
    steps:
      - run: echo "Running housekeeping tasks..."
```

And the monitoring workflow:

```yaml
name: Ping SITE_NAME
on:
  workflow_run:
    workflows: ['Hourly Housekeeping']
    types: [completed]
jobs:
  Ping-Success:
    runs-on: ubuntu-latest
    if: ${{ github.event.workflow_run.conclusion == 'success' }}
    steps:
      - run: curl -fsS -m 10 --retry 5 ${{ secrets.ping_url }}
  Ping-Failure:
    runs-on: ubuntu-latest
    if: ${{ github.event.workflow_run.conclusion == 'failure' }}
    steps:
      - run: curl -fsS -m 10 --retry 5 ${{ secrets.ping_url }}/fail
```
