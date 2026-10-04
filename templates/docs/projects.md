# Projects

Use Projects to organize checks in your SITE_NAME account. Your account initially
has a single default project. You can create additional projects and transfer
your checks between them as your usage grows.

The default project has no name, so the project menu and the "All Projects" page show
it under the account's email address until you rename it. It starts with one check,
"My First Check" (slug `my-first-check`), and an email integration to the account's
address.

The project menu at the top left of every project page (it shows the current
project's name) switches between projects. Its "All Projects" item opens a page,
titled "My Projects", that lists every project with its overall status and its
numbers of checks and integrations; projects with a check down come first. Its
"New Project…" item, and the "New Project…" card on the "All Projects" page, open the
"Create New Project" dialog: enter a name (required, at most 60 characters) and click
**Create Project**. SITE_NAME opens the new project's "Checks" page. A new project
has no checks, integrations, API keys or ping key.

Checks and integrations are project-scoped: each check and each configured
integration always belongs to a particular project.

## Transferring Checks Between Projects {: #transferring-checks }

You can transfer a check between projects, **and keep its UUID ping URL**. To transfer
a check, go to its details page, and look for the "Transfer to Another Project&hellip;"
button.
In the dialog, pick the **Target Project** and click **Transfer**. The list offers
only your other projects, so a transfer needs at least two. The check's
integrations get reset: it loses its current notification channels and is assigned
all notification channels of the target project.

The check keeps its UUID, status, schedule, filtering rules and event log. Its slug
URL changes: a [slug URL](../http_api/#uuids-and-slugs) is made of the project's ping
key and the check's slug, so after the transfer the check answers at the target
project's ping key, and the old slug URL gets 404. The target project may need a
ping key created first, and if a check in the target project already has the same
slug, the slug URL gets "409 Conflict" ("ambiguous slug") until one of them changes.

## Project Settings {: #project-settings }

The "Settings" link in the top navigation of a project opens its settings, in three
sections:

* **Project Name**: "Change Project Name" renames the project (required, at most 60
characters).
* **API Access**: the rows "API key", "API key (read-only)" and "Ping key", each with
"Create" or "Revoke". An API key is shown once, when it is created; store it then.
The ping key stays visible in a masked form; click it to reveal it. Revoking a key
cannot be undone: you can create a new key, with a new value. See
[Authentication](../api/#authentication) for the API keys and
[UUIDs and Slugs](../http_api/#uuids-and-slugs) for the ping key.
* **Remove Project**: permanently deletes the project with all its checks and
integrations.

## Monthly / Weekly / Daily Email Reports

SITE_NAME can optionally send periodic email reports with a summary of checks
from all your projects. For each check, the reports show the check's current status
and its downtime statistics.

You can configure the frequency of the reports (monthly, on the 1st of every month,
or weekly, on Mondays, or daily) or turn them off altogether in
[Account Settings › Email Reports](../../accounts/profile/notifications/).
