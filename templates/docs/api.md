# Management API v3

With the Management API, you can programmatically manage the checks and integrations
in a SITE_NAME project: list, create, update, pause, resume and delete checks, read
the pings and status changes they recorded, and list the project's integrations.
It is separate from the [Pinging API](../http_api/), which your jobs call to
report success, start, failure and log events: the Management API records no pings.

## Quick Reference {: #quick-reference }

### Base URL

Every endpoint lives under `SITE_ROOT/api/v3/`; v3 is the only version. Paths are
matched exactly:

* A collection path is written with a trailing slash: `checks/`,
  `checks/<uuid>/pings/`, `checks/<uuid>/flips/`, `channels/`, `status/`,
  `metrics/`, `bounces/`. Each answers without the slash as well, the same way and
  for every method: nothing is redirected.
* A path that names one check has no trailing slash: `checks/<uuid>`,
  `checks/<uuid>/pause`, `checks/<uuid>/resume`, `checks/<uuid>/pings/<n>/body`.
  With one, it gets 404.
* `<uuid>` is the check's UUID in lowercase with dashes, as the `uuid` field returns
  it; any other spelling gets 404. `<unique_key>` is the 40-character `unique_key`
  field that responses to a read-only key carry.

### Authentication {: #authentication }

Every endpoint except [status](#status), [metrics](#metrics) and
[bounces](#bounces) needs an API key of the project. All API keys are
project-specific; there are no account-wide API keys. A key reads and changes its own
project's checks only: a check of another project
gets 403. A project has no API key until you create one in the **API Access** section
of the project's **Settings** page; the page shows a new key once, so copy it then.
Each key is 32 characters long, and its prefix tells its kind:

Key | Starts with | Works with
----|-------------|-----------
read-write | `hcw_` | every endpoint that takes a key
read-only | `hcr_` | [list checks](#list-checks), [get a check](#get-check), [list flips](#list-flips); every other endpoint that takes a key, [list integrations](#list-channels), [list pings](#list-pings) and [a ping's body](#ping-body) included, answers it with "401 wrong api key"

Send the key in the `X-Api-Key` request header:

```bash
curl --header "X-Api-Key: your-api-key" SITE_ROOT/api/v3/checks/
```

A POST request with a JSON body may carry the key in an `api_key` field of the body
instead; the header wins when both are present. A key in the header is checked
before the body is read, so a wrong one gets 401 even when the body is not JSON. GET
and DELETE requests read the header only, and no request reads the key from the
query string.

A read-only key receives check objects without the `uuid`, `ping_url`, `update_url`,
`pause_url`, `resume_url` and `channels` fields and with an extra `unique_key` field,
so it can read a check but cannot learn the URL that pings it. A read-only key sent
to an endpoint that needs a read-write key gets "401 wrong api key".

### Requests {: #requests }

POST requests (create, update, pause, resume) carry a JSON object as the body.
SITE_NAME parses the body as JSON whatever the `Content-Type` header says, so
`curl --data '{...}'` works; a `multipart/form-data` or URL-encoded form gets
"400 could not parse request body". An empty body counts as `{}`. Fields the
endpoint does not know are ignored. A body larger than 64 KiB (65,536 bytes) gets
"413 request body too large" before anything else is checked.

Field types are strict: `timeout` and `grace` are JSON integers (not strings, and not
numbers with a fraction or a decimal point such as `300.0`), booleans are `true` or
`false` (not `1` or `"true"`), and text fields are strings. `null` is refused for
every field: to leave a field unchanged, leave it out.

Only [list checks](#list-checks) and [list flips](#list-flips) take query parameters.
No cookies or CSRF token are needed.

### Responses {: #responses }

Responses are JSON (`Content-Type: application/json`), except [a ping's
body](#ping-body) (`text/plain`), [status](#status) (the text `OK`) and the error
responses the table below marks as text, HTML or empty. Timestamps are ISO 8601 in
UTC (`2020-03-24T14:02:03+00:00`), and durations are integers in seconds. Every
endpoint that returns a check returns the same [check object](#check-object).

Every response but the HTML error pages, those of status, metrics and bounces
included, carries
`Cache-Control: max-age=0, no-cache, no-store, must-revalidate, private`: check
objects hold ping URLs, which no cache should keep.

Every endpoint except status, metrics and bounces answers an OPTIONS request with
"204 No Content", and puts `Access-Control-Allow-Origin: *`,
`Access-Control-Allow-Headers: X-Api-Key, Content-Type`,
`Access-Control-Allow-Methods` (the endpoint's methods, then `OPTIONS`) and
`Access-Control-Max-Age: 600` on its responses, the 4xx ones included, so a browser
page on another origin can call the API. Only the HTML 404 page of a path that
matches no endpoint carries none of them.

### Status Codes and Errors {: #status-codes }

Status | Body | Meaning
-------|------|--------
200 | JSON | The request succeeded. Create returns 200 when `unique` found an existing check and updated it.
201 | JSON | Create made a new check.
204 | empty | The answer to an OPTIONS request.
400 | `{"error": "<message>"}` | The request body was refused; the messages are listed below.
400 | empty | [List flips](#list-flips): a query parameter is not valid.
401 | `{"error": "missing api key"}` | No key was found, or the key is not 32 characters long.
401 | `{"error": "wrong api key"}` | The key matches no project, or a read-only key was sent to an endpoint that needs a read-write key.
403 | empty | The check belongs to another project than the key; or, for [metrics](#metrics), the metrics key is missing or wrong.
403 | HTML page | A request to [status](#status) or [metrics](#metrics) with a method other than GET, HEAD, OPTIONS or TRACE: it fails Django's CSRF check.
404 | empty | The check, the ping or the ping's body does not exist.
404 | HTML page | The path matches no endpoint (a misspelled UUID, a trailing slash after a path that names one check).
405 | empty | The endpoint does not take this method (HEAD included); the `Allow` header lists the methods it takes.
409 | the text `check is not paused` | [Resume](#resume-check) was called on a check that is not paused.
413 | `{"error": "request body too large"}` | A POST body is larger than 64 KiB (65,536 bytes).
500 | HTML page | A server error; [status](#status) returns it when the database query fails.

The `error` messages of a 400 response:

* `could not parse request body`: the body is not JSON.
* `json validation error: value is not an object`: the body is JSON but not an object.
* `json validation error: <field> is not a string`, `is not a number`,
  `is not a boolean`, `is not an array`, `is too long`, `is too small`,
  `is too large`, `does not match pattern`, `has unexpected value`,
  `is not a valid timezone`, or `is not a valid cron or OnCalendar expression`:
  a field broke its rule in the [parameter table](#create-check). An invalid entry
  of `unique` reads `an item in 'unique' has unexpected value`. Only the first
  invalid field is reported.
* `invalid channel identifier: <value>`, `non-unique channel identifier: <value>`,
  `empty channel identifier`: the `channels` field names an integration that does not
  exist or is ambiguous, or has an empty item (as in `"a,,b"` or a trailing comma).

A 4xx response changes nothing: fix the request rather than repeating it. Creating a
check is not idempotent unless the request carries [`unique`](#create-check), so a
client that retries a create after a timeout should send `unique`.

### Rate Limits

SITE_NAME applies no rate limit to the Management API, and no request gets a 429
response.

### What to Call {: #task-index }

To | Call
---|-----
List every check with its current status | [List checks](#list-checks): `GET SITE_ROOT/api/v3/checks/`
Find checks by slug or by tags | [List checks](#list-checks) with `?slug=<slug>` or `?tag=<tag>`
Find a check by its name | [List checks](#list-checks) with no filter, and match `name` in the client: no call filters by name
Find a check's UUID and ping URL | [List checks](#list-checks) or [get a check](#get-check) with a read-write key: the `uuid` and `ping_url` fields
Read one check's status, last ping and next expected ping | [Get a check](#get-check): `GET SITE_ROOT/api/v3/checks/<uuid>`
Create a check that expects a ping every N seconds | [Create a check](#create-check) with `timeout` and `grace`
Create a check on a cron or OnCalendar schedule | [Create a check](#create-check) with `schedule` and `tz`
Create a check only if it does not exist yet, safe to repeat | [Create a check](#create-check) with `unique`, for example `["name"]`
Change a check's name, slug, tags, period, schedule, grace time or keyword filters | [Update a check](#update-check): `POST SITE_ROOT/api/v3/checks/<uuid>`
Choose which integrations alert for a check | [List integrations](#list-channels) for their IDs, then [update the check](#update-check) with `channels`
Stop monitoring a check for a while | [Pause](#pause-check): `POST SITE_ROOT/api/v3/checks/<uuid>/pause`
Monitor a paused check again | [Resume](#resume-check), or send the check a success ping when its `manual_resume` is off
Delete a check | [Delete](#delete-check): `DELETE SITE_ROOT/api/v3/checks/<uuid>`
Read the pings a check received | [List pings](#list-pings): `GET SITE_ROOT/api/v3/checks/<uuid>/pings/`
Read the output a job sent with a ping | [Get a ping's body](#ping-body), at the `body_url` of the ping
See when a check went down and came back up | [List flips](#list-flips): `GET SITE_ROOT/api/v3/checks/<uuid>/flips/`
Check that the SITE_NAME instance and its database are up | [Status](#status): `GET SITE_ROOT/api/v3/status/`
Send a ping (success, start, failure, exit status, log) | The [Pinging API](../http_api/), not this API
Get the project's ping key, for slug ping URLs | Not available through the API: the project's **Settings** page

### All Endpoints {: #endpoints }

<div id="api-toc"></div>

Endpoint Name                                         | Endpoint Address | Key
------------------------------------------------------|------------------|----
**Checks**                                            | |
[List existing checks](#list-checks)                  | `GET SITE_ROOT/api/v3/checks/` | read-only or read-write
[Get a single check](#get-check)                      | `GET SITE_ROOT/api/v3/checks/<uuid>`<br>`GET SITE_ROOT/api/v3/checks/<unique_key>` | read-only or read-write
[Create a new check](#create-check)                   | `POST SITE_ROOT/api/v3/checks/` | read-write
[Update an existing check](#update-check)             | `POST SITE_ROOT/api/v3/checks/<uuid>` | read-write
[Pause monitoring of a check](#pause-check)           | `POST SITE_ROOT/api/v3/checks/<uuid>/pause` | read-write
[Resume monitoring of a check](#resume-check)         | `POST SITE_ROOT/api/v3/checks/<uuid>/resume` | read-write
[Delete check](#delete-check)                         | `DELETE SITE_ROOT/api/v3/checks/<uuid>` | read-write
**Pings**                                             | |
[List check's logged pings](#list-pings)              | `GET SITE_ROOT/api/v3/checks/<uuid>/pings/` | read-write
[Get a ping's logged body](#ping-body)                | `GET SITE_ROOT/api/v3/checks/<uuid>/pings/<n>/body` | read-write
**Flips**                                             | |
[List check's status changes](#list-flips)            | `GET SITE_ROOT/api/v3/checks/<uuid>/flips/`<br>`GET SITE_ROOT/api/v3/checks/<unique_key>/flips/` | read-only or read-write
**Integrations**                                      | |
[List existing integrations](#list-channels)          | `GET SITE_ROOT/api/v3/channels/` | read-write
**Service status**                                    | |
[Check database connectivity](#status)                | `GET SITE_ROOT/api/v3/status/` | none
[Read service metrics](#metrics)                      | `GET SITE_ROOT/api/v3/metrics/` | the metrics key
[Receive email bounces](#bounces)                     | `POST SITE_ROOT/api/v3/bounces/` | internal, not for clients

## The Check Object {: #check-object }

Every endpoint that returns a check, a list of checks included, returns this object.
Which fields appear depends on the key and on the check's kind: a Simple check has
`timeout`, a Cron or OnCalendar check has `schedule` and `tz`, and there is no `kind`
field.

Field | Type | Present | Meaning
------|------|---------|--------
`name` | string | always | The check's name.
`slug` | string | always | The check's slug, used in slug ping URLs; `""` when it has none.
`tags` | string | always | Space-separated tags.
`desc` | string | always | The description.
`grace` | integer | always | The grace time in seconds.
`n_pings` | integer | always | How many pings the check has received in total, ignored ones included.
`status` | string | always | The current status: `new` (no ping yet, or resumed), `up`, `grace` (the ping is late, but the grace time has not run out), `down` or `paused`.
`started` | boolean | always | `true` while a start ping has opened a run that no success or failure ping has ended.
`last_ping` | string or null | always | The time of the latest success or failure ping; start and log pings do not change it.
`next_ping` | string or null | always | The time the grace period begins: when the next ping is due, or, while a run is open, the earlier of that and the run's start. `null` for a down check, and for a new or paused check with no open run.
`last_duration` | integer | when known | The run time in seconds of the latest run, when the latest success or failure ping ended a run that a start ping opened.
`manual_resume` | boolean | always | `true` if a paused check ignores pings until it is resumed.
`methods` | string | always | `""` (pings by any HTTP method count) or `"POST"` (only POST pings count).
`start_kw`, `success_kw`, `failure_kw` | string | always | Comma-separated keywords for [keyword filtering](#keyword-filtering).
`filter_http_body` | boolean | always | `true` if keyword filtering looks at the bodies of HTTP pings.
`filter_default_fail` | boolean | always | `true` if a filtered ping that matches no keyword counts as a failure.
`filter_subject`, `filter_body` | boolean | always | Inert, kept for compatibility with the original Healthchecks API v3 only.
`subject`, `subject_fail` | string | always | Deprecated: `success_kw` and `failure_kw` when `filter_subject` is `true`, and `""` otherwise.
`uuid` | string | read-write key | The check's UUID.
`ping_url` | string | read-write key | The URL that pings the check.
`update_url`, `pause_url`, `resume_url` | string | read-write key | The [update](#update-check), [pause](#pause-check) and [resume](#resume-check) URLs of the check.
`channels` | string | read-write key | Comma-separated UUIDs of the integrations assigned to the check; `""` for none.
`unique_key` | string | read-only key | A stable 40-character identifier, for the [get a check](#get-check) and [list flips](#list-flips) calls.
`timeout` | integer | Simple checks | The expected period in seconds.
`schedule` | string | Cron and OnCalendar checks | The cron or OnCalendar expression.
`tz` | string | Cron and OnCalendar checks | The time zone the schedule is read in.

Although the API omits the `*_url` fields in read-only responses, a client that knows
the check's UUID can construct them itself.

## List Existing Checks {: #list-checks .rule }

```text
GET SITE_ROOT/api/v3/checks/
```

Returns a list of the project's checks, in the order they were created, optionally
filtered by slug and by one or more tags.

**Authentication:** a read-write or a read-only key, in the `X-Api-Key` header.

### Parameters

Name | In | Type and allowed values | Required | Default | Meaning
-----|----|-------------------------|----------|---------|--------
`slug` | query | string | no | no filter | Returns only the checks with exactly this slug. If there are no matching checks, returns an empty list; if there are several, returns all of them. An empty value applies no filter.
`tag` | query | string; may be repeated | no | no filter | Returns only the checks that carry this tag, as a whole word: `tag=prod` does not match a check tagged `production`. Repeated, as in `?tag=foo&tag=bar`, it returns the checks that carry every one of the tags.

### Example

```bash
curl --header "X-Api-Key: your-api-key" SITE_ROOT/api/v3/checks/
```

```json
{
  "checks": [
    {
      "name": "Filesystem Backup",
      "slug": "filesystem-backup",
      "tags": "backup fs",
      "desc": "Runs incremental backup every hour",
      "grace": 600,
      "n_pings": 1,
      "status": "up",
      "started": false,
      "last_ping": "2020-03-24T14:02:03+00:00",
      "next_ping": "2020-03-24T15:02:03+00:00",
      "manual_resume": false,
      "methods": "",
      "subject": "SUCCESS",
      "subject_fail": "ERROR",
      "start_kw": "START",
      "success_kw": "SUCCESS",
      "failure_kw": "ERROR",
      "filter_subject": true,
      "filter_body": false,
      "filter_http_body": false,
      "filter_default_fail": false,
      "uuid": "31365bce-8da9-4729-8ff3-aaa71d56b712",
      "ping_url": "PING_ENDPOINT31365bce-8da9-4729-8ff3-aaa71d56b712",
      "update_url": "SITE_ROOT/api/v3/checks/31365bce-8da9-4729-8ff3-aaa71d56b712",
      "pause_url": "SITE_ROOT/api/v3/checks/31365bce-8da9-4729-8ff3-aaa71d56b712/pause",
      "resume_url": "SITE_ROOT/api/v3/checks/31365bce-8da9-4729-8ff3-aaa71d56b712/resume",
      "channels": "1bdea468-03bf-47b8-ab27-29a9dd0e4b94,51c6eb2b-2ae1-456b-99fe-6f1e0a36cd3c",
      "timeout": 3600
    },
    {
      "name": "Database Backup",
      "slug": "database-backup",
      "tags": "production db",
      "desc": "Runs ~/db-backup.sh",
      "grace": 1200,
      "n_pings": 7,
      "status": "down",
      "started": false,
      "last_ping": "2020-03-23T10:19:32+00:00",
      "next_ping": null,
      "manual_resume": false,
      "methods": "",
      "subject": "",
      "subject_fail": "",
      "start_kw": "",
      "success_kw": "",
      "failure_kw": "",
      "filter_subject": false,
      "filter_body": false,
      "filter_http_body": false,
      "filter_default_fail": false,
      "last_duration": 312,
      "uuid": "803f680d-e89b-492b-82ef-2be7b774a92d",
      "ping_url": "PING_ENDPOINT803f680d-e89b-492b-82ef-2be7b774a92d",
      "update_url": "SITE_ROOT/api/v3/checks/803f680d-e89b-492b-82ef-2be7b774a92d",
      "pause_url": "SITE_ROOT/api/v3/checks/803f680d-e89b-492b-82ef-2be7b774a92d/pause",
      "resume_url": "SITE_ROOT/api/v3/checks/803f680d-e89b-492b-82ef-2be7b774a92d/resume",
      "channels": "1bdea468-03bf-47b8-ab27-29a9dd0e4b94,51c6eb2b-2ae1-456b-99fe-6f1e0a36cd3c",
      "schedule": "15 5 * * *",
      "tz": "UTC"
    }
  ]
}
```

The [check object](#check-object) describes each field.

With a read-only key, the same request returns the checks without `uuid`, `ping_url`,
`update_url`, `pause_url`, `resume_url` and `channels`, and with an extra
`unique_key` field. The `unique_key` identifier is stable across API calls, and you
can use it in the [Get a single check](#get-check) and
[List check's status changes](#list-flips) API calls:

```json
{
  "checks": [
    {
      "name": "Filesystem Backup",
      "slug": "filesystem-backup",
      "tags": "backup fs",
      "desc": "Runs incremental backup every hour",
      "grace": 600,
      "n_pings": 1,
      "status": "up",
      "started": false,
      "last_ping": "2020-03-24T14:02:03+00:00",
      "next_ping": "2020-03-24T15:02:03+00:00",
      "manual_resume": false,
      "methods": "",
      "subject": "SUCCESS",
      "subject_fail": "ERROR",
      "start_kw": "START",
      "success_kw": "SUCCESS",
      "failure_kw": "ERROR",
      "filter_subject": true,
      "filter_body": false,
      "filter_http_body": false,
      "filter_default_fail": false,
      "unique_key": "a6c7b0a8a66bed0df66abfdab3c77736861703ee",
      "timeout": 3600
    }
  ]
}
```

### Errors

Only the errors every endpoint can return; see [Status codes](#status-codes).

## Get a Single Check {: #get-check .rule }

```text
GET SITE_ROOT/api/v3/checks/<uuid>
GET SITE_ROOT/api/v3/checks/<unique_key>
```

Returns a JSON representation of a single check. Accepts either the check's UUID or
its `unique_key` (a field derived from the UUID and returned by API responses to a
read-only key) as an identifier.

**Authentication:** a read-write or a read-only key, in the `X-Api-Key` header. Either
key works with either identifier; the response has the fields of the key's kind.

### Parameters

Name | In | Type and allowed values | Required | Default | Meaning
-----|----|-------------------------|----------|---------|--------
`uuid` or `unique_key` | path | UUID, lowercase with dashes; or 40 characters of `0-9` and `a-f` | yes | | The check.

### Example

```bash
curl --header "X-Api-Key: your-api-key" \
    SITE_ROOT/api/v3/checks/803f680d-e89b-492b-82ef-2be7b774a92d
```

```json
{
  "name": "Database Backup",
  "slug": "database-backup",
  "tags": "production db",
  "desc": "Runs ~/db-backup.sh",
  "grace": 1200,
  "n_pings": 7,
  "status": "down",
  "started": false,
  "last_ping": "2020-03-23T10:19:32+00:00",
  "next_ping": null,
  "manual_resume": false,
  "methods": "",
  "subject": "",
  "subject_fail": "",
  "start_kw": "",
  "success_kw": "",
  "failure_kw": "",
  "filter_subject": false,
  "filter_body": false,
  "filter_http_body": false,
  "filter_default_fail": false,
  "last_duration": 312,
  "uuid": "803f680d-e89b-492b-82ef-2be7b774a92d",
  "ping_url": "PING_ENDPOINT803f680d-e89b-492b-82ef-2be7b774a92d",
  "update_url": "SITE_ROOT/api/v3/checks/803f680d-e89b-492b-82ef-2be7b774a92d",
  "pause_url": "SITE_ROOT/api/v3/checks/803f680d-e89b-492b-82ef-2be7b774a92d/pause",
  "resume_url": "SITE_ROOT/api/v3/checks/803f680d-e89b-492b-82ef-2be7b774a92d/resume",
  "channels": "1bdea468-03bf-47b8-ab27-29a9dd0e4b94,51c6eb2b-2ae1-456b-99fe-6f1e0a36cd3c",
  "schedule": "15 5 * * *",
  "tz": "UTC"
}
```

The response to a read-only key omits `uuid`, `ping_url`, `update_url`, `pause_url`,
`resume_url` and `channels`, and adds `unique_key`:

```json
{
  "name": "Database Backup",
  "slug": "database-backup",
  "tags": "production db",
  "desc": "Runs ~/db-backup.sh",
  "grace": 1200,
  "n_pings": 7,
  "status": "down",
  "started": false,
  "last_ping": "2020-03-23T10:19:32+00:00",
  "next_ping": null,
  "manual_resume": false,
  "methods": "",
  "subject": "",
  "subject_fail": "",
  "start_kw": "",
  "success_kw": "",
  "failure_kw": "",
  "filter_subject": false,
  "filter_body": false,
  "filter_http_body": false,
  "filter_default_fail": false,
  "last_duration": 312,
  "unique_key": "124f983e0e3dcaeba921cfcef46efd084576e783",
  "schedule": "15 5 * * *",
  "tz": "UTC"
}
```

### Errors

Status | Body | When
-------|------|-----
403 | empty | The check (by UUID) belongs to another project.
404 | empty | No check has this UUID, or the key's project has no check with this `unique_key`.

Plus the errors every endpoint can return; see [Status codes](#status-codes).

## Create a Check {: #create-check .rule }

```text
POST SITE_ROOT/api/v3/checks/
```

Creates a new check and returns it, its ping URL included. Every field is optional,
and an omitted field takes its default, so an empty body creates a check with the
default period and grace time.

With this API call, you can create both Simple and Cron checks:

* To create a Simple check, specify the `timeout` parameter.
* To create a Cron (or OnCalendar) check, specify the `schedule` and `tz` parameters.

With the `unique` field, the call first looks for an existing check and updates it
instead of creating a duplicate (an "upsert").

**Authentication:** a read-write key, in the `X-Api-Key` header or as an `api_key`
field of the body.

### Parameters

All of them are fields of the JSON body. The [field notes](#field-notes) below explain
the ones that need more than a line.

Name | In | Type and allowed values | Required | Default | Meaning
-----|----|-------------------------|----------|---------|--------
`name` | body | string, at most 100 characters | no | `""` | The check's name. The slug is not generated from it.
`slug` | body | string of `a-z`, `0-9`, `-` and `_`, at most 100 characters | no | `""` | The slug for [slug ping URLs](../http_api/#uuids-and-slugs); `""` for none.
`tags` | body | string, at most 500 characters | no | `""` | Space-separated tags, for example `"reports staging"`.
`desc` | body | string, at most 10,000 characters | no | `""` | The description.
`timeout` | body | integer, 60 to 31536000 (one minute to 365 days) | no | {{ default_timeout }} | The expected period in seconds. Makes the check Simple. Ignored when `schedule` is given too.
`grace` | body | integer, 60 to 31536000 | no | {{ default_grace }} | The grace time in seconds.
`schedule` | body | string, a cron or OnCalendar expression, at most 100 characters | no | none | Makes the check a Cron or OnCalendar check; see [schedule](#field-schedule).
`tz` | body | string, an IANA time zone name such as `Europe/Riga` | no | `"UTC"` | The time zone the schedule is read in.
`manual_resume` | body | boolean | no | `false` | `true` keeps a paused check paused when pings arrive, until it is [resumed](#resume-check).
`methods` | body | `""` or `"POST"` | no | `""` | `""` counts pings sent by any HTTP method; `"POST"` records pings by other methods as "ignored".
`channels` | body | string: `"*"`, `""`, or a comma-separated list of integration UUIDs or names | no | none assigned | The integrations that alert for the check; see [channels](#field-channels).
`unique` | body | array of `"name"`, `"slug"`, `"tags"`, `"timeout"`, `"grace"` | no | `[]` | The fields that identify an existing check to update instead; see [unique](#field-unique).
`start_kw` | body | string, at most 200 characters | no | `""` | Comma-separated keywords that make an HTTP ping a start signal.
`success_kw` | body | string, at most 200 characters | no | `""` | Comma-separated keywords that make an HTTP ping a success signal.
`failure_kw` | body | string, at most 200 characters | no | `""` | Comma-separated keywords that make an HTTP ping a failure signal.
`filter_http_body` | body | boolean | no | `false` | Turns on [keyword filtering](#keyword-filtering) of HTTP ping bodies.
`filter_default_fail` | body | boolean | no | `false` | With keyword filtering on, `true` makes a ping that matches no keyword a failure, and `false` makes it ignored.
`filter_subject` | body | boolean | no | `false` | Inert; see [compatibility fields](#field-compat).
`filter_body` | body | boolean | no | `false` | Inert; see [compatibility fields](#field-compat).
`subject` | body | string, at most 200 characters | no | none | Deprecated; see [compatibility fields](#field-compat).
`subject_fail` | body | string, at most 200 characters | no | none | Deprecated; see [compatibility fields](#field-compat).
`api_key` | body | string | no | none | The API key, when it is not in the `X-Api-Key` header.

### Field Notes {: #field-notes }

schedule {: #field-schedule }
:   A cron or systemd OnCalendar expression defining this check's schedule.
    SITE_NAME detects the expression type automatically: a single line of five
    space-separated fields is cron, and anything else is OnCalendar.

    The `schedule` parameter takes precedence over the `timeout` field: if you specify
    both the `timeout` and the `schedule` parameters, SITE_NAME will save the
    `schedule` and ignore the `timeout`.

    Example using a cron expression ("run every half-hour"):

    <pre>{"schedule": "0,30 * * * *"}</pre>

    Example using an OnCalendar expression ("run at 12:00 of the last day of every
    month"):

    <pre>{"schedule": "\*-\*~1 12:00"}</pre>

tz
:   The time zone that the `schedule` is read in. This setting only has an effect in
    combination with the `schedule` parameter. A legacy zone name is stored under its
    current name: `Europe/Kiev` becomes `Europe/Kyiv`.

    Example:

    <pre>{"schedule": "15 5 * * *", "tz": "Europe/Riga"}</pre>

channels {: #field-channels }
:   By default, this API call assigns no integrations to the newly created
    check.

    Set this field to a special value "*" to automatically assign all existing
    integrations. Example:

    <pre>{"channels": "*"}</pre>

    To assign specific integrations, use a comma-separated list of integration
    UUIDs. You can look up integration UUIDs using the
    [List Existing Integrations](#list-channels) API call.

    Example:

    <pre>{"channels":
     "4ec5a071-2d08-4baa-898a-eb4eb3cd6941,746a083e-f542-4554-be1a-707ce16d3acc"}</pre>

    Alternatively, if you have named your integrations in SITE_NAME dashboard,
    you can specify integrations by their names. For this to work, your integrations
    need non-empty unique names, and they must not contain commas.
    The names must match exactly, whitespace is significant. UUIDs and names can be
    mixed in one list.

    Example:

    <pre>{"channels": "Email to Alice,Slack to Alice"}</pre>

    An item that matches no integration, an item that matches more than one, and an
    empty item each refuse the whole request with 400.

unique {: #field-unique }
:   Enables "upsert" functionality. Before creating a check, SITE_NAME looks for
    an existing check in the project whose fields listed in `unique` equal the values
    in the request.

    If SITE_NAME does not find a matching check, it creates a new check and returns it
    with the HTTP status code 201.

    If SITE_NAME finds a matching check, it updates the existing check with all the
    fields in the request and returns it with the HTTP status code 200. If several
    checks match, it updates the one created first.

    Every field named in `unique` has to be in the request too: if one is missing,
    SITE_NAME does not look and always creates a new check.

    Example:

    <pre>{"name": "Backups", "unique": ["name"]}</pre>

    In this example, if a check named "Backups" exists, it will be returned.
    Otherwise, a new check will be created and returned.

keyword filtering {: #keyword-filtering }
:   With `filter_http_body` set to `true`, SITE_NAME classifies each HTTP ping by
    the keywords in the first PING_BODY_LIMIT_FORMATTED of its request body. It looks
    for the `failure_kw`, `success_kw` and `start_kw` keywords, in that order, and the
    first list with a match decides: failure, success or start. Separate multiple
    keywords using commas. Keywords are case-sensitive.

    If no keywords match, the ping is ignored when `filter_default_fail` is `false`,
    and classified as a failure signal when it is `true`.

    Example:

    <pre>{"filter_http_body": true, "start_kw": "STARTED"}</pre>

    In this example, SITE_NAME classifies an HTTP ping as a start signal if the
    request body contains the word "STARTED".

    Example:

    <pre>{"filter_http_body": true, "success_kw": "SUCCESS,COMPLETED"}</pre>

    In this example, an HTTP ping counts as success if the request body
    contains either the word "SUCCESS" or the word "COMPLETED".

    Example:

    <pre>{"filter_http_body": true, "failure_kw": "FAILED,ERROR"}</pre>

    In this example, an HTTP ping counts as failure if the request body
    contains either the word "FAILED" or the word "ERROR".

    Example:

    <pre>{
        "filter_http_body": true,
        "filter_default_fail": true,
        "success_kw": "Backup successful"
    }</pre>

    In this example, an HTTP ping will be classified as a success signal if and only if
    the request body contains the string "Backup successful". In all other cases,
    including HTTP GET requests with an empty request body, the ping will be classified
    as a failure signal.

    The Pinging API page describes [how SITE_NAME interprets a
    ping](../http_api/#interpreting-pings) in full.

compatibility fields {: #field-compat }
:   `filter_subject` and `filter_body` are inert, kept for compatibility with the
    original Healthchecks API v3 only. In the original, they enable keyword filtering
    on the subject line and the body of inbound email messages. SITE_NAME does not
    accept email pings: it stores and returns the values, but they have no effect on
    pings.

    `subject` and `subject_fail` are deprecated, kept for compatibility with the
    original Healthchecks API v3 only. `subject` sets `success_kw` to the value, and
    `subject_fail` sets `failure_kw`; either one also sets the inert `filter_subject`
    to `true` if `success_kw` or `failure_kw` is non-empty (`false` otherwise). An
    explicit `success_kw` or `failure_kw` in the same request takes precedence.

### Example

```bash
curl SITE_ROOT/api/v3/checks/ \
    --header "X-Api-Key: your-api-key" \
    --data '{"name": "Backups", "tags": "prod www", "timeout": 3600, "grace": 60}'
```

Or, alternatively:

```bash
curl SITE_ROOT/api/v3/checks/ \
    --data '{"api_key": "your-api-key", "name": "Backups", "tags": "prod www", "timeout": 3600, "grace": 60}'
```

The response is "201 Created" with the new check:

```json
{
  "name": "Backups",
  "slug": "",
  "tags": "prod www",
  "desc": "",
  "grace": 60,
  "n_pings": 0,
  "status": "new",
  "started": false,
  "last_ping": null,
  "next_ping": null,
  "manual_resume": false,
  "methods": "",
  "subject": "",
  "subject_fail": "",
  "start_kw": "",
  "success_kw": "",
  "failure_kw": "",
  "filter_subject": false,
  "filter_body": false,
  "filter_http_body": false,
  "filter_default_fail": false,
  "uuid": "7918b17b-a745-4db1-8575-9d2e07c97f79",
  "ping_url": "PING_ENDPOINT7918b17b-a745-4db1-8575-9d2e07c97f79",
  "update_url": "SITE_ROOT/api/v3/checks/7918b17b-a745-4db1-8575-9d2e07c97f79",
  "pause_url": "SITE_ROOT/api/v3/checks/7918b17b-a745-4db1-8575-9d2e07c97f79/pause",
  "resume_url": "SITE_ROOT/api/v3/checks/7918b17b-a745-4db1-8575-9d2e07c97f79/resume",
  "channels": "",
  "timeout": 3600
}
```

### Errors

Status | Body | When
-------|------|-----
400 | `{"error": "..."}` | The body is not a JSON object, a field breaks its rule, or `channels` names an unknown or ambiguous integration; see [Status codes](#status-codes) for the messages.
401 | `{"error": "wrong api key"}` | The key is a read-only key.

Plus the errors every endpoint can return; see [Status codes](#status-codes).

## Update an Existing Check {: #update-check .rule }

```text
POST SITE_ROOT/api/v3/checks/<uuid>
```

Updates an existing check and returns it. All request parameters are optional. If you
omit any parameter, SITE_NAME will leave its value unchanged. The check's status, its
pings and its flips do not change.

A `timeout` makes the check a Simple check, and a `schedule` makes it a Cron or
OnCalendar check, whatever kind it was before; with both, `schedule` wins.

**Authentication:** a read-write key, in the `X-Api-Key` header or as an `api_key`
field of the body.

### Parameters

The body fields are those of [Create a Check](#create-check), with the same types and
rules, and the [field notes](#field-notes) apply; only the defaults differ.

Name | In | Type and allowed values | Required | Default | Meaning
-----|----|-------------------------|----------|---------|--------
`uuid` | path | UUID, lowercase with dashes | yes | | The check to update.
`name`, `slug`, `tags`, `desc` | body | strings, as for create | no | unchanged | The name, slug, tags and description.
`timeout` | body | integer, 60 to 31536000 | no | unchanged | The period in seconds; makes the check Simple.
`grace` | body | integer, 60 to 31536000 | no | unchanged | The grace time in seconds.
`schedule` | body | string, a cron or OnCalendar expression | no | unchanged | The schedule; makes the check Cron or OnCalendar.
`tz` | body | string, an IANA time zone name | no | unchanged | The time zone the schedule is read in.
`manual_resume` | body | boolean | no | unchanged | Whether a paused check ignores pings until it is resumed.
`methods` | body | `""` or `"POST"` | no | unchanged | The HTTP methods whose pings count.
`channels` | body | string: `"*"`, `""`, or a comma-separated list of integration UUIDs or names | no | unchanged | Replaces the assigned integrations: `"*"` assigns all of them, `""` unassigns all of them, and a list assigns exactly those.
`start_kw`, `success_kw`, `failure_kw` | body | strings, at most 200 characters | no | unchanged | The keywords of [keyword filtering](#keyword-filtering).
`filter_http_body`, `filter_default_fail` | body | booleans | no | unchanged | The switches of [keyword filtering](#keyword-filtering).
`filter_subject`, `filter_body`, `subject`, `subject_fail` | body | as for create | no | unchanged | The [compatibility fields](#field-compat).
`unique` | body | as for create | no | | Validated, then ignored: an update never looks for another check.
`api_key` | body | string | no | none | The API key, when it is not in the `X-Api-Key` header.

### Example

```bash
curl SITE_ROOT/api/v3/checks/7918b17b-a745-4db1-8575-9d2e07c97f79 \
    --header "X-Api-Key: your-api-key" \
    --data '{"name": "Backups", "tags": "prod www", "timeout": 3600, "grace": 60}'
```

Or, alternatively:

```bash
curl SITE_ROOT/api/v3/checks/7918b17b-a745-4db1-8575-9d2e07c97f79 \
    --data '{"api_key": "your-api-key", "name": "Backups", "tags": "prod www", "timeout": 3600, "grace": 60}'
```

The response is "200 OK" with the updated check:

```json
{
  "name": "Backups",
  "slug": "",
  "tags": "prod www",
  "desc": "",
  "grace": 60,
  "n_pings": 0,
  "status": "new",
  "started": false,
  "last_ping": null,
  "next_ping": null,
  "manual_resume": false,
  "methods": "",
  "subject": "",
  "subject_fail": "",
  "start_kw": "",
  "success_kw": "",
  "failure_kw": "",
  "filter_subject": false,
  "filter_body": false,
  "filter_http_body": false,
  "filter_default_fail": false,
  "uuid": "7918b17b-a745-4db1-8575-9d2e07c97f79",
  "ping_url": "PING_ENDPOINT7918b17b-a745-4db1-8575-9d2e07c97f79",
  "update_url": "SITE_ROOT/api/v3/checks/7918b17b-a745-4db1-8575-9d2e07c97f79",
  "pause_url": "SITE_ROOT/api/v3/checks/7918b17b-a745-4db1-8575-9d2e07c97f79/pause",
  "resume_url": "SITE_ROOT/api/v3/checks/7918b17b-a745-4db1-8575-9d2e07c97f79/resume",
  "channels": "",
  "timeout": 3600
}
```

### Errors

Status | Body | When
-------|------|-----
400 | `{"error": "..."}` | The body is not a JSON object, a field breaks its rule, or `channels` names an unknown or ambiguous integration; see [Status codes](#status-codes) for the messages.
401 | `{"error": "wrong api key"}` | The key is a read-only key.
403 | empty | The check belongs to another project.
404 | empty | No check has this UUID, or it was deleted during the update.

Plus the errors every endpoint can return; see [Status codes](#status-codes).

## Pause Monitoring of a Check {: #pause-check .rule }

```text
POST SITE_ROOT/api/v3/checks/<uuid>/pause
```

Disables monitoring for a check without removing it. The check goes into a "paused"
state: it ends any open run, it is never late, and it sends no alerts. Pausing a
check that is already paused changes nothing and returns it unchanged.

A paused check leaves the paused state when it receives a success or failure ping,
unless its `manual_resume` is `true`; then it records every ping as ignored and stays
paused until the [Resume](#resume-check) API call. A start or log ping does not
unpause it.

**Authentication:** a read-write key, in the `X-Api-Key` header or as an `api_key`
field of a JSON body.

### Parameters

Name | In | Type and allowed values | Required | Default | Meaning
-----|----|-------------------------|----------|---------|--------
`uuid` | path | UUID, lowercase with dashes | yes | | The check to pause.

The body may be empty.

### Example

```bash
curl SITE_ROOT/api/v3/checks/7918b17b-a745-4db1-8575-9d2e07c97f79/pause \
    --request POST --header "X-Api-Key: your-api-key" --data ""
```

Note: the `--data ""` argument forces curl to send a `Content-Length` request header
even though the request body is empty. For HTTP POST requests, the `Content-Length`
header is sometimes required by some network proxies and web servers.

The response is "200 OK" with the check:

```json
{
  "name": "Backups",
  "slug": "",
  "tags": "prod www",
  "desc": "",
  "grace": 60,
  "n_pings": 0,
  "status": "paused",
  "started": false,
  "last_ping": null,
  "next_ping": null,
  "manual_resume": false,
  "methods": "",
  "subject": "",
  "subject_fail": "",
  "start_kw": "",
  "success_kw": "",
  "failure_kw": "",
  "filter_subject": false,
  "filter_body": false,
  "filter_http_body": false,
  "filter_default_fail": false,
  "uuid": "7918b17b-a745-4db1-8575-9d2e07c97f79",
  "ping_url": "PING_ENDPOINT7918b17b-a745-4db1-8575-9d2e07c97f79",
  "update_url": "SITE_ROOT/api/v3/checks/7918b17b-a745-4db1-8575-9d2e07c97f79",
  "pause_url": "SITE_ROOT/api/v3/checks/7918b17b-a745-4db1-8575-9d2e07c97f79/pause",
  "resume_url": "SITE_ROOT/api/v3/checks/7918b17b-a745-4db1-8575-9d2e07c97f79/resume",
  "channels": "",
  "timeout": 3600
}
```

### Errors

Status | Body | When
-------|------|-----
401 | `{"error": "wrong api key"}` | The key is a read-only key.
403 | empty | The check belongs to another project.
404 | empty | No check has this UUID.

Plus the errors every endpoint can return; see [Status codes](#status-codes).

## Resume Monitoring of a Check {: #resume-check .rule }

```text
POST SITE_ROOT/api/v3/checks/<uuid>/resume
```

Resumes a paused check. The check goes into the "new" state, and its last ping time
and any open run are cleared: like a newly created check, it waits for its first ping
and does not go down before it. Use this API call to resume the monitoring of checks
that are in the paused state, and have the `manual_resume` configuration parameter
set to `true`.

**Authentication:** a read-write key, in the `X-Api-Key` header or as an `api_key`
field of a JSON body.

### Parameters

Name | In | Type and allowed values | Required | Default | Meaning
-----|----|-------------------------|----------|---------|--------
`uuid` | path | UUID, lowercase with dashes | yes | | The check to resume.

The body may be empty.

### Example

```bash
curl SITE_ROOT/api/v3/checks/7918b17b-a745-4db1-8575-9d2e07c97f79/resume \
    --request POST --header "X-Api-Key: your-api-key" --data ""
```

Note: the `--data ""` argument forces curl to send a `Content-Length` request header
even though the request body is empty. For HTTP POST requests, the `Content-Length`
header is sometimes required by some network proxies and web servers.

The response is "200 OK" with the check:

```json
{
  "name": "Backups",
  "slug": "",
  "tags": "prod www",
  "desc": "",
  "grace": 60,
  "n_pings": 0,
  "status": "new",
  "started": false,
  "last_ping": null,
  "next_ping": null,
  "manual_resume": false,
  "methods": "",
  "subject": "",
  "subject_fail": "",
  "start_kw": "",
  "success_kw": "",
  "failure_kw": "",
  "filter_subject": false,
  "filter_body": false,
  "filter_http_body": false,
  "filter_default_fail": false,
  "uuid": "7918b17b-a745-4db1-8575-9d2e07c97f79",
  "ping_url": "PING_ENDPOINT7918b17b-a745-4db1-8575-9d2e07c97f79",
  "update_url": "SITE_ROOT/api/v3/checks/7918b17b-a745-4db1-8575-9d2e07c97f79",
  "pause_url": "SITE_ROOT/api/v3/checks/7918b17b-a745-4db1-8575-9d2e07c97f79/pause",
  "resume_url": "SITE_ROOT/api/v3/checks/7918b17b-a745-4db1-8575-9d2e07c97f79/resume",
  "channels": "",
  "timeout": 3600
}
```

### Errors

Status | Body | When
-------|------|-----
401 | `{"error": "wrong api key"}` | The key is a read-only key.
403 | empty | The check belongs to another project.
404 | empty | No check has this UUID.
409 | the text `check is not paused` | The check is not in the paused state.

Plus the errors every endpoint can return; see [Status codes](#status-codes).

## Delete Check {: #delete-check .rule }

```text
DELETE SITE_ROOT/api/v3/checks/<uuid>
```

Permanently deletes the check from the project, with its pings and flips. Its ping
URLs stop working at once, and the UUID cannot be reused or restored. Returns the JSON
representation of the check that was just deleted, with `channels` empty.

**Authentication:** a read-write key, in the `X-Api-Key` header (a DELETE request's
body is not read).

### Parameters

Name | In | Type and allowed values | Required | Default | Meaning
-----|----|-------------------------|----------|---------|--------
`uuid` | path | UUID, lowercase with dashes | yes | | The check to delete.

### Example

```bash
curl SITE_ROOT/api/v3/checks/7918b17b-a745-4db1-8575-9d2e07c97f79 \
    --request DELETE --header "X-Api-Key: your-api-key"
```

```json
{
  "name": "Backups",
  "slug": "",
  "tags": "prod www",
  "desc": "",
  "grace": 60,
  "n_pings": 0,
  "status": "new",
  "started": false,
  "last_ping": null,
  "next_ping": null,
  "manual_resume": false,
  "methods": "",
  "subject": "",
  "subject_fail": "",
  "start_kw": "",
  "success_kw": "",
  "failure_kw": "",
  "filter_subject": false,
  "filter_body": false,
  "filter_http_body": false,
  "filter_default_fail": false,
  "uuid": "7918b17b-a745-4db1-8575-9d2e07c97f79",
  "ping_url": "PING_ENDPOINT7918b17b-a745-4db1-8575-9d2e07c97f79",
  "update_url": "SITE_ROOT/api/v3/checks/7918b17b-a745-4db1-8575-9d2e07c97f79",
  "pause_url": "SITE_ROOT/api/v3/checks/7918b17b-a745-4db1-8575-9d2e07c97f79/pause",
  "resume_url": "SITE_ROOT/api/v3/checks/7918b17b-a745-4db1-8575-9d2e07c97f79/resume",
  "channels": "",
  "timeout": 3600
}
```

### Errors

Status | Body | When
-------|------|-----
401 | `{"error": "missing api key"}` | The key was sent in the body instead of the header.
401 | `{"error": "wrong api key"}` | The key is a read-only key.
403 | empty | The check belongs to another project.
404 | empty | No check has this UUID, or it is already deleted.

Plus the errors every endpoint can return; see [Status codes](#status-codes).

## List check's logged pings {: #list-pings .rule }

```text
GET SITE_ROOT/api/v3/checks/<uuid>/pings/
```

Returns a list of pings this check has received, ignored ones included.

This endpoint returns pings in reverse order (most recent first), and the total
number of returned pings depends on the account's ping log limit (100 by default),
capped at 1000. Older pings are not returned, even while the database still holds
them.

**Authentication:** a read-write key, in the `X-Api-Key` header. A read-only key gets
"401 wrong api key".

### Parameters

Name | In | Type and allowed values | Required | Default | Meaning
-----|----|-------------------------|----------|---------|--------
`uuid` | path | UUID, lowercase with dashes | yes | | The check.

### Example

```bash
curl SITE_ROOT/api/v3/checks/f618072a-7bde-4eee-af63-71a77c5723bc/pings/ \
    --header "X-Api-Key: your-api-key"
```

```json
{
  "pings": [
    {
      "type": "success",
      "date": "2020-06-09T14:51:06.113073+00:00",
      "n": 4,
      "scheme": "http",
      "remote_addr": "192.0.2.0",
      "method": "POST",
      "ua": "curl/7.68.0",
      "rid": "123e4567-e89b-12d3-a456-426614174000",
      "body_url": "SITE_ROOT/api/v3/checks/f618072a-7bde-4eee-af63-71a77c5723bc/pings/4/body",
      "duration": 2.9
    },
    {
      "type": "start",
      "date": "2020-06-09T14:51:03.216337+00:00",
      "n": 3,
      "scheme": "http",
      "remote_addr": "192.0.2.0",
      "method": "GET",
      "ua": "curl/7.68.0",
      "rid": "123e4567-e89b-12d3-a456-426614174000",
      "body_url": null
    },
    {
      "type": "success",
      "date": "2020-06-09T14:50:59.633577+00:00",
      "n": 2,
      "scheme": "http",
      "remote_addr": "192.0.2.0",
      "method": "GET",
      "ua": "curl/7.68.0",
      "rid": null,
      "body_url": null,
      "duration": 3.0
    },
    {
      "type": "start",
      "date": "2020-06-09T14:50:56.635601+00:00",
      "n": 1,
      "scheme": "http",
      "remote_addr": "192.0.2.0",
      "method": "GET",
      "ua": "curl/7.68.0",
      "rid": null,
      "body_url": null
    }
  ]
}
```

Each ping has these fields:

Field | Type | Meaning
------|------|--------
`type` | string | `success`, `start`, `fail`, `log`, or `ign` (ignored: the check's settings discarded it; see [how SITE_NAME interprets a ping](../http_api/#interpreting-pings)). A ping to the exit status endpoint counts as `success` for 0 and `fail` otherwise, unless the check's settings make it `ign` or a keyword filter decides.
`date` | string | When SITE_NAME received the ping, ISO 8601 in UTC with microseconds.
`n` | integer | The ping's number within the check, counting from 1; the [ping body](#ping-body) call takes it.
`scheme` | string | `https` when the ping reached the server over HTTPS, as its reverse proxy reports in the `X-Forwarded-Proto` request header; `http` otherwise.
`remote_addr` | string or null | The client's IP address: the `X-Forwarded-For` entry that the server's `TRUSTED_PROXY_HOPS` setting selects from the right, or the address of the connection. `null` when that is not an IP address.
`method` | string | The HTTP method of the ping, cut to 10 characters.
`ua` | string | The first 200 characters of the `User-Agent` header.
`rid` | string or null | The [run ID](../http_api/#run-ids) the ping carried.
`body_url` | string or null | The URL of the ping's body; `null` when the ping had no body.
`duration` | number | Present on a success or failure ping that follows a start ping with the same run ID within 72 hours, with no success or failure in between: the seconds since that start, rounded to two decimals.

No field carries the exit status that a ping to the exit status endpoint sent: `type`
says only how SITE_NAME counted the ping.

### Errors

Status | Body | When
-------|------|-----
401 | `{"error": "wrong api key"}` | The key is a read-only key.
403 | empty | The check belongs to another project.
404 | empty | No check has this UUID.

Plus the errors every endpoint can return; see [Status codes](#status-codes).

## Get a ping's logged body {: #ping-body .rule }

```text
GET SITE_ROOT/api/v3/checks/<uuid>/pings/<n>/body
```

Returns a ping's logged body. The response always has the `Content-Type: text/plain`
response header and the ping body is returned verbatim in the response body: the
bytes the ping sent, up to the first PING_BODY_LIMIT bytes, which need not be
valid UTF-8. The `body_url` field of [the ping list](#list-pings) is this URL.

**Authentication:** a read-write key, in the `X-Api-Key` header. A read-only key gets
"401 wrong api key".

### Parameters

Name | In | Type and allowed values | Required | Default | Meaning
-----|----|-------------------------|----------|---------|--------
`uuid` | path | UUID, lowercase with dashes | yes | | The check.
`n` | path | integer | yes | | The ping's `n` from [the ping list](#list-pings).

### Example

```bash
curl SITE_ROOT/api/v3/checks/f618072a-7bde-4eee-af63-71a77c5723bc/pings/4/body \
    --header "X-Api-Key: your-api-key"
```

```http
HTTP/1.1 200 OK
Content-Type: text/plain

Backup finished, 42 files
```

### Errors

Status | Body | When
-------|------|-----
401 | `{"error": "wrong api key"}` | The key is a read-only key.
403 | empty | The check belongs to another project.
404 | empty | The check does not exist, the ping does not exist or is older than the ping log limit, or the ping has no body data.

Plus the errors every endpoint can return; see [Status codes](#status-codes).

## List check's status changes {: #list-flips .rule }

```text
GET SITE_ROOT/api/v3/checks/<uuid>/flips/
GET SITE_ROOT/api/v3/checks/<unique_key>/flips/
```

Returns a list of "flips" this check has experienced, most recent first, by the
time of the flip (`timestamp`). A flip is a
change of status: the check going up or down, and also the changes that pausing and
resuming make. `up` is `1` when the check became up and `0` for every other new
status, paused and new included.

This API endpoint supports time filtering via the `seconds`, `start`, and `end` query
parameters. If no time filters are specified, the API returns all stored
flips for a given check. Filters given together all apply.

Notes about flip retention: when a check prunes its old pings, SITE_NAME also removes
the check's flips that are older than 93 days, enough for the current month and the
two full months before it, and older than the check's oldest kept ping too; a flip
whose alerts have not been sent yet stays. Pruning happens on every 100th ping and in
the server's daily cleanup; until then, this API call returns these flips as well.
Clearing a check's events in the web UI removes all of its flips at once.

**Authentication:** a read-write or a read-only key, in the `X-Api-Key` header.

### Parameters

Name | In | Type and allowed values | Required | Default | Meaning
-----|----|-------------------------|----------|---------|--------
`uuid` or `unique_key` | path | UUID, lowercase with dashes; or 40 characters of `0-9` and `a-f` | yes | | The check.
`seconds` | query | integer, 0 to 31536000 | no | no filter | Returns the flips from the last `seconds` seconds; `0` applies no filter.
`start` | query | integer UNIX timestamp, 0 to 10000000000 | no | no filter | Returns the flips at or after this time.
`end` | query | integer UNIX timestamp, 0 to 10000000000 | no | no filter | Returns the flips before this time.

Examples:

* `SITE_ROOT/api/v3/checks/<uuid|unique_key>/flips/?seconds=3600`
* `SITE_ROOT/api/v3/checks/<uuid|unique_key>/flips/?start=1592214380`
* `SITE_ROOT/api/v3/checks/<uuid|unique_key>/flips/?end=1592217980`

### Example

```bash
curl SITE_ROOT/api/v3/checks/f618072a-7bde-4eee-af63-71a77c5723bc/flips/ \
    --header "X-Api-Key: your-api-key"
```

```json
{
  "flips": [
    {
      "timestamp": "2020-03-23T10:18:23+00:00",
      "up": 1
    },
    {
      "timestamp": "2020-03-23T10:17:15+00:00",
      "up": 0
    },
    {
      "timestamp": "2020-03-23T10:16:18+00:00",
      "up": 1
    }
  ]
}
```

`timestamp` is when the flip happened, ISO 8601 in UTC.

### Errors

Status | Body | When
-------|------|-----
400 | empty | `seconds`, `start` or `end` is not an integer or is out of range.
403 | empty | The check (by UUID) belongs to another project.
404 | empty | No check has this UUID, or the key's project has no check with this `unique_key`.

Plus the errors every endpoint can return; see [Status codes](#status-codes).

## List Existing Integrations {: #list-channels .rule }

```text
GET SITE_ROOT/api/v3/channels/
```

Returns a list of integrations belonging to the project. Use their `id` or `name` in
the `channels` field of [create](#create-check) and [update](#update-check).

**Authentication:** a read-write key, in the `X-Api-Key` header. A read-only key gets
"401 wrong api key".

### Parameters

None.

### Example

```bash
curl --header "X-Api-Key: your-api-key" SITE_ROOT/api/v3/channels/
```

```json
{
  "channels": [
    {
      "id": "4ec5a071-2d08-4baa-898a-eb4eb3cd6941",
      "name": "My Work Email",
      "kind": "email"
    },
    {
      "id": "746a083e-f542-4554-be1a-707ce16d3acc",
      "name": "Team Slack",
      "kind": "slack"
    }
  ]
}
```

Field | Type | Meaning
------|------|--------
`id` | string | The integration's UUID.
`name` | string | The integration's name; `""` when it has none.
`kind` | string | `email`, `group`, `slack` or `webhook`.

### Errors

Status | Body | When
-------|------|-----
401 | `{"error": "wrong api key"}` | The key is a read-only key.

Plus the errors every endpoint can return; see [Status codes](#status-codes).

## Check Database Connectivity {: #status .rule }

```text
GET SITE_ROOT/api/v3/status/
```

Runs a test query and returns HTTP 200 if the query completes successfully.
Use this endpoint to monitor the uptime of your SITE_NAME instance with an
external uptime monitoring system.

**Authentication:** none. Send GET or HEAD; OPTIONS and TRACE get the same answer as
GET. Any other method, POST, PUT, PATCH and DELETE among them, fails Django's CSRF
check and gets 403 with an HTML "CSRF verification failed" page, so point an uptime
monitor at it with GET.

### Parameters

None.

### Example

```bash
curl SITE_ROOT/api/v3/status/
```

```http
HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8
Cache-Control: max-age=0, no-cache, no-store, must-revalidate, private

OK
```

### Errors

Status | Body | When
-------|------|-----
403 | HTML page | The method is not GET, HEAD, OPTIONS or TRACE.
500 | HTML page | The test database query did not succeed.

## Read Service Metrics {: #metrics .rule }

```text
GET SITE_ROOT/api/v3/metrics/
```

Returns a few counters about the instance's background work, for an operator's
monitoring: the newest ping and notification IDs, and how many status changes wait
for the `sendalerts` process to handle them. A growing `num_unprocessed_flips` means
alerts are not going out.

**Authentication:** the `X-Metrics-Key` header, equal to the server's `METRICS_KEY`
setting; project API keys do not work here. While `METRICS_KEY` is unset, the endpoint
answers 403 to every request. Send GET or HEAD; OPTIONS and TRACE get the same answer
as GET, and any other method, POST, PUT, PATCH and DELETE among them, gets 403 with an
HTML "CSRF verification failed" page, the metrics key notwithstanding.

### Parameters

Name | In | Type and allowed values | Required | Default | Meaning
-----|----|-------------------------|----------|---------|--------
`X-Metrics-Key` | header | string | yes | | The value of `METRICS_KEY`.

### Example

```bash
curl --header "X-Metrics-Key: your-metrics-key" SITE_ROOT/api/v3/metrics/
```

```json
{
  "ts": 1791051876,
  "max_ping_id": 18342,
  "max_notification_id": 517,
  "num_unprocessed_flips": 0
}
```

`ts` is the current UNIX time; `max_ping_id` and `max_notification_id` are `null`
while there are none.

### Errors

Status | Body | When
-------|------|-----
403 | empty | `METRICS_KEY` is unset, or the header is missing or does not match it.
403 | HTML page | The method is not GET, HEAD, OPTIONS or TRACE.

## Receive Email Bounces {: #bounces .rule }

```text
POST SITE_ROOT/api/v3/bounces/
```

An internal endpoint, not for API clients: the outgoing mail service posts delivery
failure reports here, as raw email messages. A permanent failure of an alert email
disables that email integration, and a permanent failure of a report email turns
reports and reminders off. It answers 200 to every request, and acts only on messages
addressed with a valid signature from the last 48 hours.
