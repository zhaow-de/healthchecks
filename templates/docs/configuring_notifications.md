# Configuring Notifications

You can set up multiple ways to receive notifications when checks in your account
change state. Doing so is helpful for several reasons:

* **Redundancy in case of notification failures.** Set up notifications using two
different notification channels (for example, email and Slack). If one transport
fails (e.g., an email message goes to spam), you still receive a notification over the
other channel.
* **Use different notification methods depending on urgency**. For example, if a
low-priority housekeeping script fails, post a message in chat. If a vital service fails,
post in chat, send an email, and call a webhook.
* Route notifications to the right people.

Each notification method ("integration") belongs to a project:
if you want to use a notification method in multiple projects, you must
set it up in each project separately.

## When Alerts Are Sent {: #when-alerts-are-sent }

An integration sends an alert when a check goes **down**, and when it comes back
**up** from down. Nothing is sent when a new or paused check receives its first
success signal, when you pause or resume a check, or when a schedule change made in
the web interface marks a check down (see
[Schedule Changes](../configuring_checks/#schedule-changes)). How a ping changes a
check's status is in [How SITE_NAME Interprets a Ping](../http_api/#interpreting-pings).

## Adding an Integration {: #adding-an-integration }

Open the project's "Integrations" page from the top navigation. Under "Add More",
click "Add Integration" next to one of these:

* **Email**: an address, and under "Notify When", whether to send an alert when a
check goes down, up, or both. An address other than the account's own stays
"Unconfirmed" and receives no alerts until someone clicks the confirmation link
SITE_NAME emails to it, unless the server sets
[`EMAIL_USE_VERIFICATION`](../self_hosted_configuration/#EMAIL_USE_VERIFICATION)
to `False`. On a server that cannot send email, only the account's own address
can be added while that setting is on.
* **Webhook**: an optional name, and for "down" events and for "up" events each a
URL, a method (GET, POST or PUT), a request body (sent with POST and PUT only) and
request headers (`Header-Name: value`, one per line). Leave one URL empty to skip
that event; at least one is required. The URL, the body and the header values accept
placeholders, listed in the form's "(available placeholders)" dialog: `$CODE`,
`$NAME`, `$NAME_JSON`, `$SLUG`, `$NOW`, `$STATUS`, `$TAGS`, `$TAG1`, `$TAG2`, …,
`$BODY` and `$BODY_JSON` (the body of the most recent ping; in the request body
only), `$EXITSTATUS` (the exit status of the most recent ping, `-1` when it has none)
and `$JSON` (the check as the [Management API](../api/#check-object) returns it). A
call that gets no complete response within 30 seconds, or a status code other than
200, 201, 202 or 204, counts as failed and is retried twice.
* **Slack**: the URL of a Slack incoming webhook, which receives an alert when a
check goes down and when it comes back up. When the server has a Slack app
configured ([`SLACK_CLIENT_ID`](../self_hosted_configuration/#SLACK_CLIENT_ID)),
the page shows an "Add to Slack" button instead, which lets you pick the channel in
Slack.
* **Group**: a Label, and a selection of the project's other integrations (groups
cannot contain groups). An alert to the group goes to each selected integration.

The server can switch off the Webhook and Slack integrations
([`WEBHOOKS_ENABLED`](../self_hosted_configuration/#WEBHOOKS_ENABLED),
[`SLACK_ENABLED`](../self_hosted_configuration/#SLACK_ENABLED)), and then the page
does not offer them. Prometheus, also listed there, is a metrics export and sends no
alerts; see [Configuring Prometheus](../configuring_prometheus/).

Each integration is a row on the Integrations page. Click its name to rename it.
"Edit" (email, webhook and group integrations; a Slack integration cannot be edited)
opens its form again. "Test!" sends a test alert for a dummy check named "TEST": a
"down" alert, or an "up" alert to an integration that sends only those; it is not
retried. The "Status" column shows "Ready to deliver", "Unconfirmed" or "Disabled",
and "Last Notification" shows "Delivered" or "Failed" with the time of the latest
attempt (hover over "Failed" for the error), or "Never".

## Assigning Integrations to Checks {: #assigning-integrations }

A check alerts only through the integrations enabled for it. A check created in the
web interface starts with every integration of its project enabled, and a newly added
integration is enabled for every existing check in its project. A check created
through the Management API gets only the integrations its
[`channels`](../api/#field-channels) field names; a check
[transferred](../projects/#transferring-checks) to another project gets all of the
target project's integrations. You can switch an integration on or off for a single
check in two places:

* **The Checks page.** The "Integrations" column shows one icon per integration in
the project, in the same order on every row. An icon in full color is on for that
check, a greyed-out icon is off; hover over an icon to see the integration's name.
Click an icon to switch it. A project with more than ten integrations shows a count
such as "3 of 12" in that column instead of the icons; use the details page there.
* **A check's details page.** The "Notification Methods" section lists every
integration in the project, each row starting with an "ON" or "OFF" label (Group
integrations are listed separately, under "Notification Groups", above "Notification
Methods"; that section appears only when the project has a group). Click a row to
switch that integration for this check.

Both switches take effect at once, with no Save button. To set one integration for
many checks at a time, click the "N of M" count in the "Assigned Checks" column of the
Integrations page: it opens a list of the project's checks with a checkbox each, saved
with "Save Changes". Through the [Management API](../api/), a check's `channels` field
sets the same assignment.

When a Group is on for a check, each of its members is notified, even a member that
is off for that check, and even a disabled one. A member that is also on for the
check gets the alert twice. Since a new check gets every integration, groups and
their members alike, switch the members off for checks that should alert only
through the group.

## Disabled Integrations {: #disabled-integrations }

SITE_NAME disables an integration that cannot deliver:

* An email integration, when an alert to it bounces permanently (when the mail
service reports bounces; see [Receive Email Bounces](../api/#bounces)), or when the
recipient clicks the "Unsubscribe" link in an alert.
* A Slack integration, when Slack answers an alert with 404, or with 400 and
`invalid_token`.

A disabled integration shows "Disabled" in the "Status" column and sends nothing on
its own; a group that contains it still delivers to it. To re-enable an email
integration, click "Fix…" on its row and save the form (an address other than the
account's own has to be confirmed again). A Slack integration cannot be edited:
remove it and add it again.

## Repeated Notifications {: #repeated-notifications }

If you want to receive repeated notifications for as long as a particular check is
down, SITE_NAME can send **hourly or daily email reminders** if any check is down
in any of your projects.
Set them up in [Account Settings › Email Reports](../../accounts/profile/notifications/):
under "Ongoing reminders if any checks are down", pick "Remind me daily" or
"Remind me hourly", and click "Save Changes".

Reminders go to the account's own email address, not to the email integrations.
Each one lists only the checks that are down at that moment, and reminders stop once
no check is down.

## Daily, Weekly and Monthly Reports {: #reports }

SITE_NAME sends periodic email reports, either monthly at the start of each month,
weekly every Monday, or daily. Use them to ensure all checks have their expected state
and nothing has "fallen through the cracks." Reports go to the account's email
address, between 9:00 and 11:00 in the account's preferred time zone (set under
[Account Settings › Account](../../accounts/profile/), "Preferred Time Zone").
No report and no reminder is sent while no check in any project has received a
ping in the last 180 days.

The reports list checks from all your projects, grouped by project.
For each check, they show:

* the check's current status
* the number of downtimes in each of the last two report periods (months, weeks
or days)
* the total downtime duration in each of the last two report periods

You can opt out of receiving the reports in the
[Account Settings › Email Reports](../../accounts/profile/notifications/) page
or by clicking the "Unsubscribe" link in the email report's footer. The
"Unsubscribe" link in a report or a reminder turns off both the reports and the
reminders.
