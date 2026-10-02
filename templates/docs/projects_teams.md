# Projects and Teams

Use Projects to organize checks in your SITE_NAME account. Your account initially
has a single default project. You can create additional projects and transfer
your checks between them as your usage grows.

![An overview of projects](IMG_URL/projects.png)

Checks and integrations are project-scoped: each check and each configured
integration always belongs to a particular project.

## Team Access

You can grant your colleagues access to a project by inviting them into
the project's team. Each project has its separate team, so you can grant access
selectively. Inviting team members is **more convenient and more
secure** than sharing a password to a single account.

You can manage each project's team from its Settings page:

![Team access section](IMG_URL/team_access.png)

The user who created the project is listed as **Owner**. When you invite a user
to the project, you can select one of the three roles for their membership:
**Team Member** (what you usually want), **Manager** or **Read-only**.

Team Members can:

* create, edit and remove checks
* create and remove integrations
* rename the project
* view and regenerate project's API keys
* give up their membership
(from their [Account Settings](../../accounts/profile/) page)

Team Members can not:

* invite new members to the project
* change project's owner
* remove the project

**Managers** have the same permissions as Team Members, with one exception:
Managers can invite new members and remove existing members from the project's team.
Managers still can not change or remove the project's owner.

**Read-only** members can:

* view checks, including check details and ping logs
* view integrations
* give up their membership

Read-only members can not modify checks, integrations, or project settings.
They also cannot access the project's API keys, as that would effectively give them
read-write access through API.

## Transferring Checks Between Projects {: #transferring-checks }

You can transfer a check between projects, **and keep its ping address**. To transfer
a check, go to its details page, and look for the "Transfer to Another Project&hellip;"
button.

![The transfer dialog](IMG_URL/transfer_check.png)

The transfer dialog will list all projects you have access to (with the Team Member
or Manager role). If you do not see a particular project in the dialog, make sure
you are logged into the correct user account, and your user account belongs to the
project's team.

## Transferring Projects Between Accounts {: #transferring-projects }

You can transfer entire projects between SITE_NAME accounts. This is particularly
useful when consolidating multiple accounts into one account.
To transfer a project, go to its settings page, and look for the
"Transfer Project&hellip;" button. Only project's owner can transfer the project to
another account–if you are not the owner, you will not see the button.

![The transfer dialog](IMG_URL/transfer_project.png)

The transfer dialog will list the current team members. Select the desired new
owner, and click "Initiate Transfer". The chosen team member will receive
an email asking to confirm the ownership change. After they confirm,
they will become the project's owner, and you will become a Team Member.

## Monthly / Weekly / Daily Email Reports

SITE_NAME can optionally send periodic email reports with a summary of checks
from **all projects you have access to** – both the projects you own and the projects
you are a member of. For each check, the reports show the check's current status
and its downtime statistics.

You can configure the frequency of the reports (monthly, on the 1st of every month,
or weekly, on Mondays, or daily) or turn them off altogether in
[Account Settings › Email Reports](../../accounts/profile/notifications/).
