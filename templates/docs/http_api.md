# Pinging API

With the Pinging API, your jobs signal **success**, **start**, **failure**,
**exit status** and **log** events to SITE_NAME by making HTTP requests to a
check's ping URL. It is separate from the [Management API](../api/), which creates,
reads, updates and deletes checks: the Pinging API only records events against
checks.

## Quick Reference {: #quick-reference }

### Base URLs

Every ping URL starts with `PING_ENDPOINT` and names one check in one of two
forms:

Form | URL | Identifies the check by
-----|-----|------------------------
UUID | `PING_ENDPOINT<uuid>` | the check's UUID, lowercase with dashes
Slug | `PING_ENDPOINT<ping-key>/<slug>` | the project's ping key and the check's slug

A suffix selects the event: none (success), `/start`, `/fail`, `/log`, or
`/<exit-status>`. [UUIDs and Slugs](#uuids-and-slugs) explains both forms.

### Authentication

There is no API key. The UUID, or the ping key, in the URL is the secret that
authorizes the request; anyone who has the URL can ping the check. The Management
API's keys, read-write and read-only, are neither needed nor read here.

The Management API returns a check's `uuid` and `ping_url` to a read-write key
only, and never returns the ping key: the ping key is created and shown on the
project's **Settings** page in the web UI.

### Requests {: #requests }

Every endpoint accepts any HTTP method, which the endpoint sections write as `ANY`;
GET, HEAD and POST are the usual ones, and a check can be set to accept POST only (see
[How SITE_NAME Interprets a Ping](#interpreting-pings)). The one query parameter
is `rid`, a [run ID](#run-ids). The request body is optional, may be any
content type, and is stored with the ping (see [Request Body](#request-body)).
No cookies, CSRF token or special headers are needed.

### Responses

The response body is short plain text, although the
`Content-Type` header says `text/html; charset=utf-8`; a HEAD response has no
body. Read the status code, not the body. A 2xx response means the ping was
recorded; any other response means it was not. Successful responses carry these
headers:

```http
HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8
Ping-Body-Limit: PING_BODY_LIMIT
Access-Control-Allow-Origin: *
Cache-Control: max-age=0, no-cache, no-store, must-revalidate, private

OK
```

`Ping-Body-Limit` is the number of request body bytes SITE_NAME stores per ping.
When the server's body limit setting is `None`, which stores every body whole, the
header is absent from every response, including those the examples on this page
show (see the body limit setting in
[Server Configuration](../self_hosted_configuration/#PING%5FBODY%5FLIMIT)).
`Access-Control-Allow-Origin: *` is set on 200 responses only, so a browser
page on another origin can read a successful response; error responses do not
carry it.

### Status Codes {: #status-codes }

Status | Body | Meaning
-------|------|--------
200 | `OK` | The ping was recorded (also when it was recorded as "ignored").
400 | `invalid url format` | The slug has uppercase letters (an uppercase suffix after a UUID, such as `/Fail`, counts as a slug), or the exit status is above 255.
400 | `invalid uuid format` | The `rid` parameter is not a UUID.
400 | an HTML error page | The request body is larger than 2.5 MiB (2,621,440 bytes), or than the body limit when that is higher.
404 | `not found` | No check has this UUID; no check has this slug under this ping key; no project has this ping key; an unknown lowercase suffix follows a UUID; or any lowercase suffix follows an uppercase or undashed UUID (in these two, the URL is read as a slug URL).
404 | an HTML error page | The URL matches no ping route: an uppercase or undashed UUID with no suffix, a trailing slash after a slug or a suffix, or an unknown suffix after a slug.
409 | `ambiguous slug` | More than one check in the project has this slug.

A 4xx response means the request itself is wrong: fix the URL, the `rid` or the
body rather than repeating it.

### Rate Limits

SITE_NAME applies no rate limit to pings: it records every
request it accepts. Each ping is stored, and the check's event log keeps only the
most recent pings (100 by default), so a job that pings more often than needed
pushes useful events out of the log sooner.

### Protocol

HTTP or HTTPS, the HTTP version and IPv4 or IPv6 are decided by the
web server in front of SITE_NAME, not by SITE_NAME itself.

### What to Call {: #task-index }

To | Call
---|-----
Report that a job finished successfully | [Success](#success-uuid): `PING_ENDPOINT<uuid>`
Report that a job started, to measure its run time and catch a run that never finishes | [Start](#start-uuid): `PING_ENDPOINT<uuid>/start`
Report that a job failed, and alert right away | [Failure](#fail-uuid): `PING_ENDPOINT<uuid>/fail`
Report a script's exit code and let SITE_NAME decide success or failure | [Exit status](#exitcode-uuid): `PING_ENDPOINT<uuid>/<exit-status>`
Record a message without changing the check's status | [Log](#log-uuid): `PING_ENDPOINT<uuid>/log`
Attach a job's output to any event | POST the output as the [request body](#request-body)
Pair each start with its finish when runs overlap | Add [`?rid=<uuid>`](#run-ids) to both pings
Ping by a readable name instead of a UUID | The [slug URLs](#success-slug): `PING_ENDPOINT<ping-key>/<slug>`
Create a check, to get a UUID to ping | Management API: [create a check](../api/#create-check) with a read-write key; the response carries `uuid` and `ping_url`.
Find a check's UUID or ping URL | Management API: [list checks](../api/#list-checks) or [get a check](../api/#get-check), with a read-write key
Read back the pings a check received, and their bodies | Management API: [list pings](../api/#list-pings) and [get a ping's body](../api/#ping-body)
Read back how long a run took | Management API: the `duration` field of the finishing ping in [list pings](../api/#list-pings), or the check's `last_duration` from [get a check](../api/#get-check)
Change a check's period, grace time, allowed methods or keyword filters | Management API: [update a check](../api/#update-check)

### All Endpoints {: #endpoints }

Endpoint Name                                               | Endpoint Address
------------------------------------------------------------|-------
[Success (UUID)](#success-uuid)       | `PING_ENDPOINT<uuid>`
[Start (UUID)](#start-uuid)           | `PING_ENDPOINT<uuid>/start`
[Failure (UUID)](#fail-uuid)          | `PING_ENDPOINT<uuid>/fail`
[Log (UUID)](#log-uuid)               | `PING_ENDPOINT<uuid>/log`
[Report script's exit status (UUID)](#exitcode-uuid)           | `PING_ENDPOINT<uuid>/<exit-status>`
[Success (slug)](#success-slug)       | `PING_ENDPOINT<ping-key>/<slug>`
[Start (slug)](#start-slug)           | `PING_ENDPOINT<ping-key>/<slug>/start`
[Failure (slug)](#fail-slug)          | `PING_ENDPOINT<ping-key>/<slug>/fail`
[Log (slug)](#log-slug)               | `PING_ENDPOINT<ping-key>/<slug>/log`
[Report script's exit status (slug)](#exitcode-slug)           | `PING_ENDPOINT<ping-key>/<slug>/<exit-status>`

## UUIDs and Slugs {: #uuids-and-slugs }

Each Pinging API request needs to identify a check uniquely.
SITE_NAME supports two ways of identifying a check: by the check's UUID
or by a combination of the project's ping key and the check's slug.

**Check's UUID** is automatically assigned when the check is created. It is
immutable. You cannot replace the automatically assigned UUID with a manually
chosen one. When you delete a check, you lose its UUID and cannot get it back.
In a ping URL, the UUID is written in lowercase with dashes
(`5bf66975-d4c7-4bf5-bcc8-b8d8a82ea278`); any other spelling gets a 404.

You can look up the UUIDs of your checks in the web UI or via
[Management API](../api/) calls: the `uuid` and `ping_url` fields of a check, which
only a read-write API key receives.

**Project's ping key** is shared by all checks in a project. A project has none
until you create it on the project's **Settings** page, where you can also look it
up and revoke it; revoking it stops every slug URL of the project from working,
and UUID URLs keep working. A generated ping key is 22 characters of `a-z` and
`0-9`, and the ping key in the URL must match it exactly.

**Check's slug** can be chosen by the user. The slug should only contain the following
characters: `a-z`, `0-9`, hyphens, and underscores, and be at most 100 characters
long. A common practice is to derive the slug from the check's name (for example,
a check named "Database Backup" might have a slug "database-backup"), but the user
is free to pick arbitrary slug values. A slug URL with an uppercase letter in the
slug gets "400 invalid url format"; a check with an empty slug has no slug URL.

Check's slug **can be changed** by the user, from the web interface or by using
[Management API](../api/) calls (the `slug` field).

Check's slug is **not guaranteed to be unique**. If you make a Pinging API request
using a non-unique slug, SITE_NAME will return the "409 Conflict" HTTP status code
with the body "ambiguous slug" and ignore the request. The UUID URLs of those checks
keep working.

## How SITE_NAME Interprets a Ping {: #interpreting-pings }

The endpoint gives each ping its meaning, and three check settings can change it.
SITE_NAME applies these steps in order:

1. **The endpoint.** No suffix means success, `/start` start, `/fail` failure,
   `/log` log; `/<exit-status>` means success for 0 and failure for 1 to 255.
2. **Allowed methods.** If the check accepts POST requests only (`"methods": "POST"`
   in the Management API), a request with any other method is recorded as
   **ignored**, and the next step is skipped.
3. **Keyword filtering.** If the check filters by keywords (`filter_http_body`),
   SITE_NAME decodes the request body as UTF-8 and looks for the `failure_kw`,
   `success_kw` and `start_kw` keywords, in that order. Each is a comma-separated
   list, matched as case-sensitive substrings. The first list with a match decides:
   failure, success or start. When nothing matches, the ping is a failure if
   `filter_default_fail` is set and **ignored** otherwise. This step overrides the
   endpoint, `/log` and `/<exit-status>` included. Bytes that are not valid UTF-8,
   such as a multibyte character cut short by the body limit, are read as the
   replacement character (U+FFFD), and the rest of the body is matched as usual.
4. **Manual resume.** If the check is paused and requires a manual resume
   (`manual_resume`), every ping is recorded as **ignored**.

What each kind of ping then does:

Kind | Check's status | Other effects
-----|----------------|--------------
success | Becomes **up**. Alerts are sent when it was down; not when it was new or paused. | Sets the last ping time, from which SITE_NAME computes when the next ping is due. Ends the open run, unless the ping carries a run ID other than the start's (see [Run IDs](#run-ids)).
failure | Becomes **down**, and alerts are sent unless it was down already. | Sets the last ping time. Ends the open run, if any.
start | Unchanged. | Marks the check as running (`"started": true` in the Management API); a run that sends no success or failure within the check's grace time turns the check **down**.
log | Unchanged. | None.
ignored | Unchanged. | None; the event shows as "Ignored".

Every ping, ignored ones included, is added to the check's event log and counted in
its `n_pings`. SITE_NAME records with it the time, the HTTP method, the scheme (from
the `X-Forwarded-Proto` request header, "http" when absent), the client's IP address
(the first address in `X-Forwarded-For` when present), the first 200 characters of
the `User-Agent`, the body, the run ID and the exit status. The
[list pings](../api/#list-pings) call of the Management API returns all of them but
the exit status, which no API call returns: a ping's `type` says only how SITE_NAME
counted it, and the ping's details in the web UI show the number.

## Request Body {: #request-body }

Any request may carry a body, of any content type and with any method (a POST is
the usual way). SITE_NAME stores up to PING_BODY_LIMIT bytes of it with the ping.
With a numeric body limit, it stores the first that many bytes and drops the rest,
without an error, and the `Ping-Body-Limit` response header states the limit in bytes,
so a client can adjust what it sends next. For example, if the limit is 100 and the
client sends 123 bytes, SITE_NAME stores the first 100 and ignores the remaining 23.
When the server's body limit setting is `None`, SITE_NAME stores the body whole and
sends no `Ping-Body-Limit` header; the size cap below is then the only limit.

A request whose body is larger than 2.5 MiB (2,621,440 bytes), or than the body
limit when that is higher, is refused with 400 and an HTML error page, and nothing
is recorded.

The body is stored as bytes, so it need not be text, also when the check
[filters by keywords](#interpreting-pings).

## Run IDs {: #run-ids }

Every endpoint takes an optional `rid` query parameter: a client-picked UUID in the
canonical textual representation, in lower or upper case
(`rid=123e4567-e89b-12d3-a456-426614174000`). Any other value gets
"400 invalid uuid format". Use the same run ID on the start ping and the finishing
ping of one run, and a new one for each run:

* A start ping opens a run and remembers its run ID. SITE_NAME tracks one open run
  per check: a later start replaces it.
* A success or failure ping with the open run's run ID (or with none, when the start
  had none) ends the run, and SITE_NAME records its duration: the check's
  `last_duration` in the Management API, in whole seconds.
* With a different run ID, a failure ping still ends the open run; a success ping
  ends it only when it carries no run ID, and otherwise leaves it open.
* In the event log, a success or failure ping shows the time since the latest
  earlier start with the same run ID, within the last 72 hours, unless a success or
  failure with that run ID came in between. The [list pings](../api/#list-pings) call
  returns the same time as the ping's `duration` field, in seconds with two decimals.

[Measuring script run time](../measuring_script_run_time/) shows this with an
example.

## Send a "success" Signal Using UUID {: #success-uuid .rule }

```text
ANY PING_ENDPOINT<uuid>
```

Signals to SITE_NAME that the job has been completed successfully (or
a continuously running process is still running and healthy). Any HTTP method
works; see [Requests](#requests). A trailing slash
(`PING_ENDPOINT<uuid>/`) is accepted as well.

**Authentication:** none; the UUID in the URL identifies the check.

### Parameters

Name | In | Type and allowed values | Required | Default | Meaning
-----|----|------|----------|---------|--------
`uuid` | path | UUID, lowercase with dashes | yes | | The check's UUID.
`rid` | query | UUID | no | none | The [run ID](#run-ids); ends the run that a start with the same run ID opened.
body | body | any bytes | no | empty | Stored with the ping, up to the first PING_BODY_LIMIT bytes; see [Request Body](#request-body).

### Example

```bash
curl -fsS -m 10 --retry 5 --data-raw "Backup finished, 42 files" \
    PING_ENDPOINT5bf66975-d4c7-4bf5-bcc8-b8d8a82ea278
```

```http
HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8
Ping-Body-Limit: PING_BODY_LIMIT
Access-Control-Allow-Origin: *

OK
```

### Errors

Status | Body | When
-------|------|-----
400 | `invalid uuid format` | `rid` is not a UUID.
404 | `not found` | No check has this UUID.

Plus the errors every endpoint can return; see [Status codes](#status-codes).

## Send a "start" Signal Using UUID {: #start-uuid .rule }

```text
ANY PING_ENDPOINT<uuid>/start
```

Sends a "job has started!" message to SITE_NAME. Sending a "start" signal is optional,
but it enables a few extra features:

* SITE_NAME will measure and display job execution times
* SITE_NAME will detect if the job runs longer than its configured grace time

The check's status does not change.

**Authentication:** none; the UUID in the URL identifies the check.

### Parameters

Name | In | Type and allowed values | Required | Default | Meaning
-----|----|------|----------|---------|--------
`uuid` | path | UUID, lowercase with dashes | yes | | The check's UUID.
`rid` | query | UUID | no | none | The [run ID](#run-ids) of the run this start opens; send the same value on the finishing ping.
body | body | any bytes | no | empty | Stored with the ping, up to the first PING_BODY_LIMIT bytes; see [Request Body](#request-body).

### Example

```bash
curl -fsS -m 10 --retry 5 \
    "PING_ENDPOINT5bf66975-d4c7-4bf5-bcc8-b8d8a82ea278/start?rid=123e4567-e89b-12d3-a456-426614174000"
```

```http
HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8
Ping-Body-Limit: PING_BODY_LIMIT
Access-Control-Allow-Origin: *

OK
```

### Errors

Status | Body | When
-------|------|-----
400 | `invalid uuid format` | `rid` is not a UUID.
404 | `not found` | No check has this UUID.

Plus the errors every endpoint can return; see [Status codes](#status-codes).

## Send a "failure" Signal Using UUID {: #fail-uuid .rule }

```text
ANY PING_ENDPOINT<uuid>/fail
```

Signals to SITE_NAME that the job has failed. Actively signaling a failure
minimizes the delay from your monitored service failing to you receiving an alert.
The check goes down at once.

**Authentication:** none; the UUID in the URL identifies the check.

### Parameters

Name | In | Type and allowed values | Required | Default | Meaning
-----|----|------|----------|---------|--------
`uuid` | path | UUID, lowercase with dashes | yes | | The check's UUID.
`rid` | query | UUID | no | none | The [run ID](#run-ids); a failure ends the open run whatever its run ID.
body | body | any bytes | no | empty | Stored with the ping, up to the first PING_BODY_LIMIT bytes; see [Request Body](#request-body).

### Example

```bash
curl -fsS -m 10 --retry 5 --data-raw "pg_dump: connection refused" \
    PING_ENDPOINT5bf66975-d4c7-4bf5-bcc8-b8d8a82ea278/fail
```

```http
HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8
Ping-Body-Limit: PING_BODY_LIMIT
Access-Control-Allow-Origin: *

OK
```

### Errors

Status | Body | When
-------|------|-----
400 | `invalid uuid format` | `rid` is not a UUID.
404 | `not found` | No check has this UUID.

Plus the errors every endpoint can return; see [Status codes](#status-codes).

## Send a "log" Signal Using UUID {: #log-uuid .rule }

```text
ANY PING_ENDPOINT<uuid>/log
```

Sends logging information to SITE_NAME without signaling success or failure.
SITE_NAME will log the event and display it in the check's "Events" section with the
"Log" label. The check's status will remain the same.

**Authentication:** none; the UUID in the URL identifies the check.

### Parameters

Name | In | Type and allowed values | Required | Default | Meaning
-----|----|------|----------|---------|--------
`uuid` | path | UUID, lowercase with dashes | yes | | The check's UUID.
`rid` | query | UUID | no | none | A [run ID](#run-ids), stored with the event; it does not open or end a run.
body | body | any bytes | no | empty | The message to log, stored up to the first PING_BODY_LIMIT bytes; see [Request Body](#request-body).

### Example

```bash
curl -fsS -m 10 --retry 5 --data-raw "Hello World" \
    PING_ENDPOINT5bf66975-d4c7-4bf5-bcc8-b8d8a82ea278/log
```

```http
HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8
Ping-Body-Limit: PING_BODY_LIMIT
Access-Control-Allow-Origin: *

OK
```

### Errors

Status | Body | When
-------|------|-----
400 | `invalid uuid format` | `rid` is not a UUID.
404 | `not found` | No check has this UUID.

Plus the errors every endpoint can return; see [Status codes](#status-codes).

## Report Script's Exit Status (Using UUID) {: #exitcode-uuid .rule }

```text
ANY PING_ENDPOINT<uuid>/<exit-status>
```

Sends a success or failure signal depending on the exit status
included in the URL. The exit status is a 0-255 integer. SITE_NAME
interprets 0 as a success and all other values as a failure, and stores the exit
status with the ping, where the web UI shows it; the Management API does not return
it.

**Authentication:** none; the UUID in the URL identifies the check.

### Parameters

Name | In | Type and allowed values | Required | Default | Meaning
-----|----|------|----------|---------|--------
`uuid` | path | UUID, lowercase with dashes | yes | | The check's UUID.
`exit-status` | path | integer, 0 to 255 | yes | | 0 is success; 1 to 255 is failure.
`rid` | query | UUID | no | none | The [run ID](#run-ids); ends the run that a start opened, as a success or failure ping does.
body | body | any bytes | no | empty | Stored with the ping, up to the first PING_BODY_LIMIT bytes; see [Request Body](#request-body).

### Example

```bash
/usr/local/bin/backup.sh
curl -fsS -m 10 --retry 5 PING_ENDPOINT5bf66975-d4c7-4bf5-bcc8-b8d8a82ea278/$?
```

```http
HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8
Ping-Body-Limit: PING_BODY_LIMIT
Access-Control-Allow-Origin: *

OK
```

### Errors

Status | Body | When
-------|------|-----
400 | `invalid url format` | The exit status is above 255.
400 | `invalid uuid format` | `rid` is not a UUID.
404 | `not found` | No check has this UUID.

Plus the errors every endpoint can return; see [Status codes](#status-codes).

## Send a "success" Signal (Using Slug) {: #success-slug .rule }

```text
ANY PING_ENDPOINT<ping-key>/<slug>
```

Signals to SITE_NAME that the job has been completed successfully (or
a continuously running process is still running and healthy).

**Authentication:** none; the project's ping key and the check's slug in the URL
identify the check. See [UUIDs and Slugs](#uuids-and-slugs).

### Parameters

Name | In | Type and allowed values | Required | Default | Meaning
-----|----|------|----------|---------|--------
`ping-key` | path | string | yes | | The project's ping key, matched exactly.
`slug` | path | string of `a-z`, `0-9`, `-`, `_` | yes | | The check's slug.
`rid` | query | UUID | no | none | The [run ID](#run-ids); ends the run that a start with the same run ID opened.
body | body | any bytes | no | empty | Stored with the ping, up to the first PING_BODY_LIMIT bytes; see [Request Body](#request-body).

### Example

```bash
curl -fsS -m 10 --retry 5 PING_ENDPOINTu0b6xgqk2xh3w5dc0rmwmq/database-backup
```

```http
HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8
Ping-Body-Limit: PING_BODY_LIMIT
Access-Control-Allow-Origin: *

OK
```

### Errors

Status | Body | When
-------|------|-----
400 | `invalid url format` | The slug has uppercase letters.
400 | `invalid uuid format` | `rid` is not a UUID.
404 | `not found` | No check has this slug under this ping key, or no project has this ping key.
409 | `ambiguous slug` | More than one check in the project has this slug.

Plus the errors every endpoint can return; see [Status codes](#status-codes).

## Send a "start" Signal (Using Slug) {: #start-slug .rule }

```text
ANY PING_ENDPOINT<ping-key>/<slug>/start
```

Sends a "job has started!" message to SITE_NAME. Sending a "start" signal is
optional, but it enables a few extra features:

* SITE_NAME will measure and display job execution times
* SITE_NAME will detect if the job runs longer than its configured grace time

The check's status does not change.

**Authentication:** none; the project's ping key and the check's slug in the URL
identify the check. See [UUIDs and Slugs](#uuids-and-slugs).

### Parameters

Name | In | Type and allowed values | Required | Default | Meaning
-----|----|------|----------|---------|--------
`ping-key` | path | string | yes | | The project's ping key, matched exactly.
`slug` | path | string of `a-z`, `0-9`, `-`, `_` | yes | | The check's slug.
`rid` | query | UUID | no | none | The [run ID](#run-ids) of the run this start opens; send the same value on the finishing ping.
body | body | any bytes | no | empty | Stored with the ping, up to the first PING_BODY_LIMIT bytes; see [Request Body](#request-body).

### Example

```bash
curl -fsS -m 10 --retry 5 PING_ENDPOINTu0b6xgqk2xh3w5dc0rmwmq/database-backup/start
```

```http
HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8
Ping-Body-Limit: PING_BODY_LIMIT
Access-Control-Allow-Origin: *

OK
```

### Errors

Status | Body | When
-------|------|-----
400 | `invalid url format` | The slug has uppercase letters.
400 | `invalid uuid format` | `rid` is not a UUID.
404 | `not found` | No check has this slug under this ping key, or no project has this ping key.
409 | `ambiguous slug` | More than one check in the project has this slug.

Plus the errors every endpoint can return; see [Status codes](#status-codes).

## Send a "failure" Signal (Using Slug) {: #fail-slug .rule }

```text
ANY PING_ENDPOINT<ping-key>/<slug>/fail
```

Signals to SITE_NAME that the job has failed. Actively signaling a failure
minimizes the delay from your monitored service failing to you receiving an alert.
The check goes down at once.

**Authentication:** none; the project's ping key and the check's slug in the URL
identify the check. See [UUIDs and Slugs](#uuids-and-slugs).

### Parameters

Name | In | Type and allowed values | Required | Default | Meaning
-----|----|------|----------|---------|--------
`ping-key` | path | string | yes | | The project's ping key, matched exactly.
`slug` | path | string of `a-z`, `0-9`, `-`, `_` | yes | | The check's slug.
`rid` | query | UUID | no | none | The [run ID](#run-ids); a failure ends the open run whatever its run ID.
body | body | any bytes | no | empty | Stored with the ping, up to the first PING_BODY_LIMIT bytes; see [Request Body](#request-body).

### Example

```bash
curl -fsS -m 10 --retry 5 --data-raw "pg_dump: connection refused" \
    PING_ENDPOINTu0b6xgqk2xh3w5dc0rmwmq/database-backup/fail
```

```http
HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8
Ping-Body-Limit: PING_BODY_LIMIT
Access-Control-Allow-Origin: *

OK
```

### Errors

Status | Body | When
-------|------|-----
400 | `invalid url format` | The slug has uppercase letters.
400 | `invalid uuid format` | `rid` is not a UUID.
404 | `not found` | No check has this slug under this ping key, or no project has this ping key.
409 | `ambiguous slug` | More than one check in the project has this slug.

Plus the errors every endpoint can return; see [Status codes](#status-codes).

## Send a "log" Signal (Using Slug) {: #log-slug .rule }

```text
ANY PING_ENDPOINT<ping-key>/<slug>/log
```

Sends logging information to SITE_NAME without signaling success or failure.
SITE_NAME will log the event and display it in check's "Events" section with the
"Log" label. The check's status will not change.

**Authentication:** none; the project's ping key and the check's slug in the URL
identify the check. See [UUIDs and Slugs](#uuids-and-slugs).

### Parameters

Name | In | Type and allowed values | Required | Default | Meaning
-----|----|------|----------|---------|--------
`ping-key` | path | string | yes | | The project's ping key, matched exactly.
`slug` | path | string of `a-z`, `0-9`, `-`, `_` | yes | | The check's slug.
`rid` | query | UUID | no | none | A [run ID](#run-ids), stored with the event; it does not open or end a run.
body | body | any bytes | no | empty | The message to log, stored up to the first PING_BODY_LIMIT bytes; see [Request Body](#request-body).

### Example

```bash
curl -fsS -m 10 --retry 5 --data-raw "Hello World" \
    PING_ENDPOINTu0b6xgqk2xh3w5dc0rmwmq/database-backup/log
```

```http
HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8
Ping-Body-Limit: PING_BODY_LIMIT
Access-Control-Allow-Origin: *

OK
```

### Errors

Status | Body | When
-------|------|-----
400 | `invalid url format` | The slug has uppercase letters.
400 | `invalid uuid format` | `rid` is not a UUID.
404 | `not found` | No check has this slug under this ping key, or no project has this ping key.
409 | `ambiguous slug` | More than one check in the project has this slug.

Plus the errors every endpoint can return; see [Status codes](#status-codes).

## Report Script's Exit Status (Using Slug) {: #exitcode-slug .rule }

```text
ANY PING_ENDPOINT<ping-key>/<slug>/<exit-status>
```

Sends a success or failure signal depending on the exit status
included in the URL. The exit status is a 0-255 integer. SITE_NAME
interprets 0 as a success and all other values as a failure, and stores the exit
status with the ping, where the web UI shows it; the Management API does not return
it.

**Authentication:** none; the project's ping key and the check's slug in the URL
identify the check. See [UUIDs and Slugs](#uuids-and-slugs).

### Parameters

Name | In | Type and allowed values | Required | Default | Meaning
-----|----|------|----------|---------|--------
`ping-key` | path | string | yes | | The project's ping key, matched exactly.
`slug` | path | string of `a-z`, `0-9`, `-`, `_` | yes | | The check's slug.
`exit-status` | path | integer, 0 to 255 | yes | | 0 is success; 1 to 255 is failure.
`rid` | query | UUID | no | none | The [run ID](#run-ids); ends the run that a start opened, as a success or failure ping does.
body | body | any bytes | no | empty | Stored with the ping, up to the first PING_BODY_LIMIT bytes; see [Request Body](#request-body).

### Example

```bash
/usr/local/bin/backup.sh
curl -fsS -m 10 --retry 5 PING_ENDPOINTu0b6xgqk2xh3w5dc0rmwmq/database-backup/$?
```

```http
HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8
Ping-Body-Limit: PING_BODY_LIMIT
Access-Control-Allow-Origin: *

OK
```

### Errors

Status | Body | When
-------|------|-----
400 | `invalid url format` | The slug has uppercase letters, or the exit status is above 255.
400 | `invalid uuid format` | `rid` is not a UUID.
404 | `not found` | No check has this slug under this ping key, or no project has this ping key.
409 | `ambiguous slug` | More than one check in the project has this slug.

Plus the errors every endpoint can return; see [Status codes](#status-codes).
