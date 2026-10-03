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

The "Checks" page in the web interface shows a visual overview of which alerting
methods are active for each check. You can click the icons to toggle them on and off:

<video autoplay loop muted playsinline>
  <source src="IMG_URL/checks_integrations.webm" type="video/webm">
</video>

You can also toggle the integrations by clicking the "ON" / "OFF" labels on
each check's details pages:

<video autoplay loop muted playsinline>
  <source src="IMG_URL/details_integrations.webm" type="video/webm">
</video>

## Repeated Notifications

If you want to receive repeated notifications for as long as a particular check is
down, SITE_NAME can send **hourly or daily email reminders** if any check is down
in any of your projects.
Set them up in [Account Settings › Email Reports](../../accounts/profile/notifications/):

![Email reminder options](IMG_URL/email_reports.png)

## Weekly and Monthly Reports

SITE_NAME sends periodic email reports, either monthly at the start of each month
or weekly every Monday. Use them to ensure all checks have their expected state
and nothing has "fallen through the cracks."

The reports list checks from all your projects, grouped by project.
For each check, they show:

* the check's current status
* the number of downtimes by month for the last two months
* the total downtime duration by month for the last two months

![Example monthly report](IMG_URL/monthly_report.png)

You can opt-out from receiving the reports in the
[Account Settings › Email Reports](../../accounts/profile/notifications/) page
or by clicking the "Unsubscribe" link in the email report's footer.
