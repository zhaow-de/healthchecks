# SITE_NAME Documentation

SITE_NAME is a service for monitoring cron jobs ([see guide](SITE_ROOT/docs/monitoring_cron_jobs/))
and similar periodic processes:

* SITE_NAME **listens for HTTP requests ("pings")** from your cron jobs and scheduled
  tasks.
* It **keeps silent** as long as pings arrive on time.
* It **raises an alert** as soon as a ping does not arrive on time.

SITE_NAME works as a [dead man's switch](https://en.wikipedia.org/wiki/Dead_man%27s_switch) for processes that need to
run continuously or on a regular, known schedule. Some examples of jobs that would
benefit from SITE_NAME monitoring:

* filesystem backups, database backups
* task queues
* database replication monitoring scripts
* report generation scripts
* periodic data import and sync jobs
* periodic antivirus scans
* DDNS updater scripts
* SSL renewal scripts

SITE_NAME is *not* the right tool for:

* monitoring website uptime by probing it with HTTP requests
* collecting application performance metrics
* log aggregation

## Concepts

A **Check** represents a single service you want to monitor. For example, when
[monitoring cron jobs](SITE_ROOT/docs/monitoring_cron_jobs/), you would create a separate check for
each cron job to be monitored. Each check has a unique ping URL, schedule,
and associated integrations. For the available configuration options, see
[Configuring checks](SITE_ROOT/docs/configuring_checks/).

Each check is always in one of the following states, depicted by a status icon:

<span class="status ic-new"></span>
:   **New**. No success or failure signal has arrived yet. Each new check you create
    starts in this state, and stays in it after "start" and "log" signals. Resuming
    a paused check also returns it to this state.

<span class="status ic-up"></span>
:   **Up**. All is well. The last "success" signal has arrived on time.

<span class="status ic-grace"></span>
:   **Late**. The "success" signal is due but has not arrived yet.
    It is not yet late by more than the check's configured **Grace Time**.

<span class="status ic-down"></span>
:   **Down**. The "success" signal is overdue by more than the Grace Time, or a
    "failure" signal arrived, or a run opened by a "start" signal did not finish
    within the Grace Time. When a check transitions into the "Down"
    state, SITE_NAME sends alert messages via the configured integrations; it sends
    them again when the check comes back "Up".

<span class="status ic-paused"></span>
:   **Paused**. You can manually pause the monitoring of specific checks. For example,
    if a frequently running cron job has a known problem, and a fix is in the works
    but not yet ready, you can pause monitoring the corresponding check temporarily to
    avoid unwanted alerts about a known issue.
    To pause a check, click "Pause" in the "Current Status" section of its details
    page, or click the pause button on its row of the "Checks" page twice (the first
    click asks for confirmation). Pausing ends an open run, and while paused the check
    sends no alerts. A "success" or "failure" signal takes the check out of the paused
    state, to "Up" or "Down", unless its [filtering rules](SITE_ROOT/docs/configuring_checks/#filtering-rules)
    say to ignore pings while paused; then only the "(Resume Now)" link on its
    details page or the Management API's [resume](SITE_ROOT/docs/api/#resume-check)
    call ends the pause, and the check returns to "New". A "start" or "log" signal
    does not unpause it, but a "start" signal opens a run: if no "success" or
    "failure" signal follows within the Grace Time, the check leaves the paused
    state for "Down" and alerts are sent.

<span class="status ic-up"></span><div class="spinner started"></div>
:   Additionally, while a run is open (a "start" signal arrived and no "success" or
    "failure" signal has ended it yet), three animated dots appear under the check's
    status icon. A "log" signal or an ignored ping after the start does not remove
    them. See [Run IDs](SITE_ROOT/docs/http_api/#run-ids) for how a run ends.

---

**Ping URL**. Each check has a unique **Ping URL**. Clients (cron jobs, background
workers, batch scripts, scheduled tasks, web services) make HTTP requests to the
ping URL to signal a start of the execution, a success, or a failure.

SITE_NAME supports two ping URL formats:

* `PING_ENDPOINT<uuid>`<br>
The check is identified by its UUID. Check UUIDs are assigned
automatically by SITE_NAME, and are guaranteed to be unique.
* `PING_ENDPOINT<project-ping-key>/<name-slug>`<br>
The check is identified by project's **Ping key** and check's
**slug** (user-chosen, URL-friendly identifier). A slug URL works only after you
create the project's ping key on the project's **Settings** page; a new project has
none.

You can append `/start`, `/fail`, `/log` or `/<exitcode>` to the base ping URL to send
"start", "failure" and "log" signals, or to report an exit code; a "log" signal records
a message and does not change the check's status. See
[What to Call](SITE_ROOT/docs/http_api/#task-index) for every option.
The "start" and "failure" signals are optional.
You don't have to use them, but you can gain additional monitoring insights
if you do use them. See [Measuring script run time](SITE_ROOT/docs/measuring_script_run_time/) and
[Signaling failures](SITE_ROOT/docs/signaling_failures/) for details.

You should treat check UUIDs and project Ping keys as secrets. If you make them public,
anybody can send telemetry signals to your checks and mess with your monitoring.

Read more about Ping URLs in [Pinging API](SITE_ROOT/docs/http_api/).

---

**Grace Time** is one of the configuration parameters you can set for each check.
It is the additional time to wait before sending an alert when a check
is late. Use this parameter to account for minor, expected deviations in job
execution times.

When a check is considered *late* depends on whether the check uses a simple
or cron schedule, and whether or not you are
[tracking job durations](SITE_ROOT/docs/measuring_script_run_time/) using the "start" events.

For **simple schedules**, the check is late when the check's configured period has passed
since the last "success" or "failure" signal.
For example, consider a periodic task that should run every hour, and the gaps between
runs should not deviate by more than 5 minutes (Period = 1 hour,
Grace Time = 5 minutes). And let's say the last successful ping arrived at 12:00.

* At 13:00 the check will be declared late (because 1 hour will have passed
  since the last ping).
* At 13:05 the check will be declared down and the alerts will go out (because
  1 hour + 5 minutes will have passed since the last ping).

For **cron and OnCalendar schedules**, the check enters the late state at the exact
moment when the current wall clock time matches the schedule. Let's consider a cron
job with the schedule `10 * * * *` (10 minutes past every hour) and grace time of 5 minutes.
And let's say the last successful ping arrived at 12:30.

* At 13:10 the check will be declared late (because 13:10 is the next scheduled time
  the cron job is expected to send a ping according to the cron schedule).
* At 13:15 the check will be declared down and the alerts will go out (because 5
  minutes will have passed since the time the cron job was expected to check in).

If you use "start" signals to [measure job execution time](SITE_ROOT/docs/measuring_script_run_time/),
Grace Time also sets the maximum allowed time gap between "start" and "success" signals.
If a job sends a "start" signal but does not send a "success" signal within grace time,
SITE_NAME will assume failure and send out alerts.

---

An **Integration** is a specific method for delivering monitoring alerts when a check
changes state. SITE_NAME supports email, webhook, Slack and group integrations; the
server can switch off webhook and Slack integrations
([`WEBHOOKS_ENABLED`](SITE_ROOT/docs/self_hosted_configuration/#WEBHOOKS_ENABLED),
[`SLACK_ENABLED`](SITE_ROOT/docs/self_hosted_configuration/#SLACK_ENABLED)), and then
the Integrations page does not offer them. Prometheus also appears on the Integrations
page unless the server switches it off
([`PROMETHEUS_ENABLED`](SITE_ROOT/docs/self_hosted_configuration/#PROMETHEUS_ENABLED)),
but it is a metrics export and sends no alerts (see
[Configuring Prometheus](SITE_ROOT/docs/configuring_prometheus/)).
You can set up multiple integrations.
For each check, you can specify which integrations it should use.

For more information on integrations, see
[Configuring notifications](SITE_ROOT/docs/configuring_notifications/).

---

**Project**. To keep things organized, you can group checks and integrations in **Projects**.
Your account starts with a single default project, but you can create
additional projects as needed. The default project has no name, so it is shown under
the account's email address until you rename it; it holds a check named
"My First Check" (slug `my-first-check`) and an email integration to the account's
address.

You can transfer a check to another project. Its UUID ping URL, schedule, filtering
rules and event log stay the same. Its slug URL changes to the target project's ping
key, and its integrations are replaced by all of the target project's integrations
(see [Projects](SITE_ROOT/docs/projects/#transferring-checks)).

Each project has its own name, API keys (read-write and read-only) and ping key, all
set on the project's **Settings** page.

For more information on projects, see [Projects](SITE_ROOT/docs/projects/).
