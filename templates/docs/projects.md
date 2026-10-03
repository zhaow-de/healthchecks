# Projects

Use Projects to organize checks in your SITE_NAME account. Your account initially
has a single default project. You can create additional projects and transfer
your checks between them as your usage grows.

The project menu at the top left of every project page (it shows the current
project's name) switches between projects. Its "All Projects" item opens a page
that lists every project with its overall status and its numbers of checks and
integrations, and its "New Project…" item creates a project.

Checks and integrations are project-scoped: each check and each configured
integration always belongs to a particular project.

## Transferring Checks Between Projects {: #transferring-checks }

You can transfer a check between projects, **and keep its ping address**. To transfer
a check, go to its details page, and look for the "Transfer to Another Project&hellip;"
button.
In the dialog, pick the **Target Project** and click **Transfer**. The check's
integrations get reset: it loses its current notification channels and is assigned
all notification channels of the target project.

## Monthly / Weekly / Daily Email Reports

SITE_NAME can optionally send periodic email reports with a summary of checks
from all your projects. For each check, the reports show the check's current status
and its downtime statistics.

You can configure the frequency of the reports (monthly, on the 1st of every month,
or weekly, on Mondays, or daily) or turn them off altogether in
[Account Settings › Email Reports](../../accounts/profile/notifications/).
