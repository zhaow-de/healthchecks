# Configuring Checks

In SITE_NAME, a **Check** represents a single service you want to
monitor. For example, when monitoring cron jobs, you would create a separate check for
each cron job you wish to monitor. You can create checks
in the SITE_NAME web interface or via [Management API](../api/).

## Adding a Check {: #adding-a-check }

On the "Checks" page, click **Add Check**. The "Add Check" dialog has these fields:

* **Name**, **Slug** (with a "Use Suggested" button) and **Tags**, described in the
next section.
* **Schedule**: **Simple**, **Cron** or **OnCalendar**, described below.
* **Period** (Simple only), 1 day by default; or **Cron Expression** (Cron only),
`* * * * *` by default; or **OnCalendar Expression(s)** (OnCalendar only),
`*-*-* *:*:*` by default.
* **Time Zone** (Cron and OnCalendar only), UTC by default.
* **Grace Time**, 1 hour by default.

Click **Save** to create the check. The new check starts in the "New" state and is
assigned every integration of the project. You can add a description afterwards in
the "Name and Tags" dialog. A check created through the Management API gets only the
integrations its [`channels`](../api/#field-channels) field names.

## Name, Tags, Description

Describe each check using an optional name, slug, tags, and description fields.
To edit them, click the check's name on the "Checks" page, or the "(edit…)" link
after the name in the heading of the check's details page; "Add description…" (or
"Edit Description…") in the details page's "Description" section opens the same
dialog. It is the "Name and Tags" dialog, with these four fields:

* **Name**: names are optional, but setting them is a good idea.
Good naming becomes especially important as you add more checks to the
account. SITE_NAME will display check names in the web interface, email reports,
and notifications. A name can be up to 100 characters long.
* **Slug**: URL-friendly identifier used in [slug-based ping URLs](../http_api/#success-slug),
which the checks list shows by default (its "uuid" / "slug" switch shows the UUID-based
ones instead). A slug-based URL also needs the project's ping key, which the project's
**Settings** page generates. The slug should only contain the
following characters: `a-z`, `0-9`, hyphens, and underscores. A check without a slug has
only its UUID-based URL. The "Use Suggested" button
beside the field fills in a slug derived from the name. A slug can be up to 100
characters long.
* **Tags**: a space-separated list of optional labels. Use tags to organize and group
checks within a project. You can tag checks by the environment
(`prod`, `staging`, `dev`, etc.), by role (`www`, `db`, `worker`, etc.), or by using
any other system. The tags together can be up to 500 characters long.
* **Description**: a free-form text field with any related information for your
future self. Describe the cron job's role, who set it up, what to do in
case of failures, and where to look for additional information. It has no length
limit, and email and Slack alerts include it.

## Simple Schedules

SITE_NAME supports three types of schedules: **Simple**, **Cron**, and **OnCalendar**.
Use Simple schedules for monitoring processes that you expect to run at relatively
regular intervals: once an hour, once a day, once a week, etc.

To change a check's schedule, click its entry in the "Period" column of the "Checks"
page, or the "Change Schedule…" button on the check's details page. The "Simple", "Cron"
and "OnCalendar" buttons at the bottom left of the dialog switch between the three
schedule types.

For the simple schedules, you can configure two parameters, Period and Grace Time.
Set each with a number and a unit (minutes, hours, or days), or drag its slider.
Each must be between 1 minute and 365 days, whether typed or set with the slider;
the dialog refuses a larger value with "Must not exceed 365 days".

* **Period** is the expected time between pings.
* **Grace Time** is the additional time to wait before sending an alert when a check
is late. Use this parameter to account for minor, expected deviations in job
execution times.

Note: if you use the "start" signal to [measure job run times](../measuring_script_run_time/),
then Grace Time also specifies the maximum allowed time gap between "start" and
"success" signals. Whenever SITE_NAME receives a "start" signal, it expects a subsequent
"success" signal within Grace Time. If the success signal does not arrive within the
configured Grace Time, SITE_NAME will mark the check as failed and send out alerts.

## Cron Schedules

Use "Cron" for monitoring cron jobs and other processes with more complex schedules.
This monitoring mode ensures that jobs run **at the correct time** and not just at
the correct time intervals.

See [Cron syntax cheatsheet](../cron/) for cron expression syntax examples.
See [crontab(5) man page](https://www.man7.org/linux/man-pages/man5/crontab.5.html)
for complete cron syntax reference.

You will need to specify Cron Expression, Server's Time Zone, and Grace Time.

* **Cron Expression** is the cron expression you specified in the crontab.
* **Server's Time Zone** is the timezone of your server. The cron daemon typically uses
the system's local time. If the machine does not use the UTC timezone, specify its
timezone here.
* **Grace Time**, same as for simple schedules, is how long to wait before sending an
alert for a late check. It has the same limits, 1 minute to 365 days, but no slider.

The cron expression can be up to 100 characters long. As you type, the dialog
describes the cron expression in words and lists the next six dates when SITE_NAME
expects a ping; while the expression or the time zone is invalid, it shows an error
and the Save button stays disabled.

## OnCalendar Schedules

Use "OnCalendar" schedules to monitor systemd timers that use `OnCalendar=` schedules.
Same as with systemd timers, you can specify more than one `OnCalendar` expression
(separated with newlines, one schedule per line), and SITE_NAME will expect a ping
whenever any schedule matches.

See [systemd.time(7) man page](https://www.man7.org/linux/man-pages/man7/systemd.time.7.html#CALENDAR_EVENTS)
for complete OnCalendar syntax reference.

With "OnCalendar" selected, the schedule dialog has the same three fields as with
"Cron": **OnCalendar Expression(s)**, **Server's Time Zone**, and **Grace Time**.
All the expression lines together can be up to 100 characters long. Beside the fields,
the dialog lists the next dates when SITE_NAME expects a ping: the next 6 when the
time zone is UTC, the next 4 otherwise. While an expression is invalid, the Save
button stays disabled.

## Schedule Changes {: #schedule-changes }

A new schedule applies from the check's last "success" or "failure" signal. If the
new schedule makes an "up" check already overdue (past its grace time), saving it
in the web interface marks the check "down" at once and sends no alerts; the check
alerts again when it comes back up. If ongoing reminders are on (see
[Repeated Notifications](../configuring_notifications/#repeated-notifications)),
they start from then.

## Filtering Rules {: #filtering-rules }

In the "Filtering Rules" dialog, you can control several advanced aspects of
how SITE_NAME handles incoming pings for a particular check. Open it with the
"Filtering Rules…" button in the "How To Ping" section of the check's details page.

![Setting filtering rules](IMG_URL/filtering_rules.png)

* **Allowed HTTP Request Methods**. You can require the ping
requests to use HTTP POST. Use the "Only POST" option if you run into issues of
preview bots hitting the ping URLs when you send them in email or post them in chat.
With "Only POST" selected, a ping that uses another method still gets "200 OK", is
recorded as "Ignored" in the event log, and does not change the check's status (see
[How SITE_NAME Interprets a Ping](../http_api/#interpreting-pings)).
The default option, labelled "HEAD, GET, POST, PUT", counts pings sent with any
HTTP method, not only those four.
* **Content Filtering**. You can instruct SITE_NAME to look for specific keywords
in the HTTP request body of HTTP pings.
* **Pinging a Paused Check**. Normally (option "Leave the paused state (default)"),
a "success" ping takes a paused check out of the paused state and into the "up"
state, and a "failure" ping into the "down" state (see
[signaling failures](../signaling_failures/)); a "start" or "log" ping does not
unpause it. You can change this behavior by selecting the "Ignore the ping, stay in
the paused state" option. With this option selected, the paused state becomes
"sticky": SITE_NAME records every incoming ping as "Ignored" until you click
"(Resume Now)" in the "Current Status" section of the check's details page, or call
the Management API's [resume](../api/#resume-check). Resuming puts the check in the
"new" state.

### Content Filtering

If the **Request body of HTTP requests** option is checked, SITE_NAME will classify
the HTTP pings as start, success, or failure signals by looking for keywords in
the first PING_BODY_LIMIT_FORMATTED of the request body.

The keywords decide what every ping counts as, overriding the URL: pings to `/start`,
`/fail`, `/log` and `/<exit-status>` are classified by their body as well. The body
is read as UTF-8, with bytes that are not valid UTF-8 matching no keyword.
See [How SITE_NAME Interprets a Ping](../http_api/#interpreting-pings) for the full
order of rules. Saving the dialog with the option unchecked clears the keyword fields
(unless the check's inert `filter_subject` or `filter_body` flag, described next,
is set).

SITE_NAME does not accept email pings: the email-only fields `filter_subject` and
`filter_body` that the [Management API](../api/) still accepts and returns are inert,
kept for compatibility with the original Healthchecks API v3 only.

You can specify multiple keywords in each of the **Start Keywords**,
**Success Keywords**, and **Failure Keywords** fields by separating them with commas;
each field can be up to 200 characters long.
The keyword matching is case-sensitive (for example, "error" and "ERROR" are different
keywords).

SITE_NAME looks for keywords in a specific order:

* It first looks for **failure keywords**. If any are found, it classifies the ping
  as a failure signal and does not look further.
* It then looks for **success keywords**. If any are found, it classifies the ping
  as a success signal and does not look further.
* It then looks for **start keywords**. If any are found, it classifies the ping
  as a start signal.
* Finally, if no matching keywords are found, SITE_NAME either ignores the ping or
  classifies it as a failure signal, depending on the **If no keywords match**
  configuration option. Ignored pings are shown in the event log with an "Ignored" label,
  but they do not affect check's status as they are neither "success" nor "failure"
  nor "start" signals.

Example use case: consider a backup cron job that sends an HTTP POST request every
time it completes. If the job completes successfully, the HTTP request will contain
text "Backup successful". If the job fails, the request body will contain an
error message. The error messages can vary, and the complete list of all possible error
messages is not known. To handle this scenario, you can use content filtering as
follows:

* Enable the **Request body of HTTP requests** – enables content filtering for
  HTTP pings.
* In the **Success keywords** field enter "Backup successful" – if this string is found
  in the request body of an HTTP ping, SITE_NAME will classify the ping as a success
  signal.
* Select the **If no keywords match: Classify the ping as failure** option – SITE_NAME
  will classify all other HTTP requests as failure signals.

With these settings, SITE_NAME will classify an HTTP ping as a success signal
if and only if the request body contains text "Backup successful". If the request
body does not contain this string (or the request body is absent altogether),
it will classify the ping as a failure signal.
