# Signaling failures

You can actively signal a failure to SITE_NAME by slightly changing the
ping URL: append either `/fail` or `/{exit-status}` to your normal ping URL.
The exit status should be a 0-255 integer. SITE_NAME will interpret
exit status 0 as success and all non-zero values as failures. An exit status above
255 gets "400 invalid url format" and is not recorded.

A failure signal turns the check down at once and sends alerts, unless the check
was down already; it also ends a run opened by a start signal. Two check settings
can change its meaning: a check that accepts POST requests only records a GET or HEAD
failure ping as "Ignored", and a check with keyword filtering classifies every ping
by its body instead of by the URL. See
[How SITE_NAME Interprets a Ping](../http_api/#interpreting-pings). In the check's
"Events" section, a `/fail` ping shows a red "Failure" badge, and a non-zero exit
status a red "Status N" badge.

Examples:

```bash

# Reports failure by appending the /fail suffix:
curl -fsS -m 10 --retry 5 -o /dev/null PING_URL/fail

# Reports failure by appending a non-zero exit status:
curl -fsS -m 10 --retry 5 -o /dev/null PING_URL/1
```

The curl options are the ones the [cron jobs page](../monitoring_cron_jobs/)
explains. With a bare `--retry 3`, curl has no time limit, and it prints a progress
meter to stderr when its output is not a terminal, which cron then mails to you.

By actively signaling failures to SITE_NAME, you can minimize the delay from your
monitored service encountering a problem to you getting notified about it.

Alternatively, if using different URLs for success and failure signals is
not feasible, you can configure SITE_NAME to classify HTTP pings as success or failure
signals [by looking for specific keywords in the HTTP request body](../configuring_checks/#filtering-rules).

## Shell Scripts

The below shell script appends `$?` (a special variable that contains the
exit status of the last executed command) to the ping URL:

```bash
#!/bin/sh

/usr/bin/certbot renew
curl -fsS -m 10 --retry 5 -o /dev/null PING_URL/$?

```

## Python

Below is a skeleton code example in Python which signals a failure when the
work function returns an unexpected value or throws an exception:

```python
import requests
URL = "PING_URL"

def do_work():
    # Do your number crunching, backup dumping, newsletter sending work here.
    # Return a truthy value on success.
    # Return a falsy value or throw an exception on failure.
    return True

success = False
try:
    success = do_work()
finally:
    # On success, requests PING_URL
    # On failure, requests PING_URL/fail
    requests.get(URL if success else URL + "/fail")
```
