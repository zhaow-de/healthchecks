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

A check alerts only through the integrations enabled for it. A check created in the
web interface starts with every integration of its project enabled, and a newly added
integration is enabled for every existing check in its project. You can switch an
integration on or off for a single check in two places:

* **The Checks page.** The "Integrations" column shows one icon per integration in
the project, in the same order on every row. An icon in full color is on for that
check, a greyed-out icon is off; hover over an icon to see the integration's name.
Click an icon to switch it. A project with more than ten integrations shows a count
such as "3 of 12" in that column instead of the icons; use the details page there.
* **A check's details page.** The "Notification Methods" section lists every
integration in the project, each row starting with an "ON" or "OFF" label (Group
integrations are listed separately, under "Notification Groups"). Click a row to
switch that integration for this check.

Both switches take effect at once, with no Save button. To set one integration for
many checks at a time, click the "N of M" count in the "Assigned Checks" column of the
Integrations page: it opens a list of the project's checks with a checkbox each, saved
with "Save Changes". Through the [Management API](../api/), a check's `channels` field
sets the same assignment.

## Repeated Notifications

If you want to receive repeated notifications for as long as a particular check is
down, SITE_NAME can send **hourly or daily email reminders** if any check is down
in any of your projects.
Set them up in [Account Settings › Email Reports](../../accounts/profile/notifications/):
under "Ongoing reminders if any checks are down", pick "Remind me daily" or
"Remind me hourly", and click "Save Changes".

## Daily, Weekly and Monthly Reports

SITE_NAME sends periodic email reports, either monthly at the start of each month,
weekly every Monday, or daily. Use them to ensure all checks have their expected state
and nothing has "fallen through the cracks."

The reports list checks from all your projects, grouped by project.
For each check, they show:

* the check's current status
* the number of downtimes in each of the last two report periods (months, weeks
or days)
* the total downtime duration in each of the last two report periods

You can opt-out from receiving the reports in the
[Account Settings › Email Reports](../../accounts/profile/notifications/) page
or by clicking the "Unsubscribe" link in the email report's footer.
