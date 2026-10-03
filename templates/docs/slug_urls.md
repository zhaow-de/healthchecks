# Slug URLs

SITE_NAME offers two different URL formats for sending ping HTTP requests:
UUID and slug URLs.

## A Quick Recap of UUID URLs

UUID-based ping URLs are the older and the default pinging URL format used in SITE_NAME.
Each check in the system has its own unique and immutable UUID. To send a success signal
("ping"), clients make a request to `PING_ENDPOINT` with the check’s UUID added at
the end. Example:

<pre>
PING_ENDPOINT<b>d1665499-e827-441f-bf13-8f15e8f4c0b9</b>
</pre>

To signal a start, a failure, or a particular exit status, and to log a diagnostic
message, clients can add more bits after the UUID:

<pre>
PING_ENDPOINTd1665499-e827-441f-bf13-8f15e8f4c0b9<b>/start</b>
PING_ENDPOINTd1665499-e827-441f-bf13-8f15e8f4c0b9<b>/fail</b>
PING_ENDPOINTd1665499-e827-441f-bf13-8f15e8f4c0b9<b>/123</b>
PING_ENDPOINTd1665499-e827-441f-bf13-8f15e8f4c0b9<b>/log</b>
</pre>

This is conceptually simple and works well. UUID-based ping URLs require no additional
authentication–the UUID value is the authentication, and the UUID address space is so
vast nobody is going to find valid ping URLs by random guessing.

There are a few downsides of UUID-based ping URLs:

* UUIDs are not particularly human-friendly. Unless you are good at memorizing UUIDs,
  it is not easy to associate a ping URL with a check just by looking at it. But it is
  easy to make mistakes when copying and pasting UUIDs around.
* Each UUID is a secret. Therefore, if you have many things to monitor, you will need
  to manage many secrets.

## Slug URLs

Slug URLs are an optional, alternative URL format introduced in 2021. In slug URLs,
instead of using UUIDs, we use two variable components, **a ping key** and **a slug**:

<pre>
PING_ENDPOINT<b>&lt;ping-key&gt;</b>/<b>&lt;slug&gt;</b>
</pre>

Here's a concrete example:

<pre>
PING_ENDPOINT<b>fqood6f4mmnuc3nztu01wq</b>/<b>db-backups</b>
</pre>

Slug URLs support start and failure signals the same way as UUID URLs do:

<pre>
PING_ENDPOINTfqood6f4mmnuc3nztu01wq/db-backups<b>/start</b>
PING_ENDPOINTfqood6f4mmnuc3nztu01wq/db-backups<b>/fail</b>
PING_ENDPOINTfqood6f4mmnuc3nztu01wq/db-backups<b>/123</b>
PING_ENDPOINTfqood6f4mmnuc3nztu01wq/db-backups<b>/log</b>
</pre>

All checks in a single project share the same ping key. The ping key is the only
secret you must manage to ping any check in the project. You can look up or create
the ping key in your project’s Settings screen, right next to your project’s API keys:
the "API Access" section has a "Ping key" row, which says "not set" and offers
a "Create" link until the project has one. After you create it, the row shows the key
masked, as its first four characters followed by asterisks; click the masked key to
reveal it, or "Revoke" to remove it.

The slug part of the URL (`db-backups`) is chosen by the user (you). You can pick
descriptive, human-readable values. Unlike UUID, each check's slug is mutable;
you can update an existing check's slug after the check is created.

The allowed characters in the slug are the lowercase ASCII letters (`a-z`),
digits (`0-9`), underscore (`_`), and hyphen (`-`).

The security of slug URLs relies on the ping key. This means you can hardcode slug
values in scripts, commit them to version control, or even share them publicly without
worrying about unexpected ping requests from crawlers, content scanning bots and random
curious individuals.

Compared to UUID URLs:

* You can pick descriptive, human-readable slug values. You can change an existing
  check's slug.
* You can monitor multiple processes using a single secret: the ping key.
* Slug URLs support [the check auto-provisioning feature](../autoprovisioning/).

## Duplicate Slug Values

SITE_NAME does not force you to pick unique slug values. If several checks have the
same slug, they will have the same slug-based ping URL. If you send an HTTP request to
it, you will get an HTTP 409 response with the text “ambiguous slug” in the response
body. The UUID-based ping URLs for these checks will, of course, still work.

The SITE_NAME web interface will also warn you about any checks with the same slugs:
while the checks list shows slug URLs (see the selector below), each check whose slug
another check in the project shares has a red "(not unique)" note after its ping URL.

## The UUID / Slug Selector

SITE_NAME shows a "uuid / slug" selector in two places: as two small links, "uuid" and
"slug", beside the "Ping URL" column heading of the checks list, and as two buttons,
"uuid" and "slug", at the right of the "How To Ping" heading on each check's details
page. The active choice is highlighted.

The selector lets you choose the URL format for display in the web interface.
The choice is saved for the whole project, so it applies to the checks list and to
every check's details page until you change it. With "slug" selected, a check with
no slug shows "unavailable, slug not set" in the checks list and
"(unavailable, set slug first)" on its details page, and a project without a ping
key shows a note on the details page linking to the project's Settings page.
It controls the display value only, and does not influence the operation of pinging
API: SITE_NAME will accept ping requests using either format, regardless of
the selector value.
