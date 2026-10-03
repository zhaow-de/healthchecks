# Pinging Reliability Tips

Sending monitoring signals over the public internet is inherently unreliable.
HTTP requests can sometimes take excessively long or fail completely
for a variety of reasons. Here are some general tips to make your monitoring
code more robust.

## Specify HTTP Request Timeout

Put a time limit on how long each ping is allowed to take. This is especially
important when sending a "start" signal at the start of a job: you don't want
a stuck ping to prevent the actual job from running. Another case is a continuously
running worker process that pings SITE_NAME after each completed item. A stuck
request could block the whole process. An explicit per-request time limit mitigates
this problem.

Specifying the timeout depends on the tool you use. curl, for example, has the
`--max-time` (shorthand: `-m`) parameter:

```bash
# Send an HTTP request, 10 second timeout:
curl -m 10 PING_URL
```

With retries (see below), the worst case is the sum of all attempts and the delays
between them: `curl -m 10 --retry 5` can take 6 × 10 seconds plus 1 + 2 + 4 + 8 + 16
seconds of delays, about 90 seconds. Put a cap on the total with
`--retry-max-time <seconds>` when a start ping must not hold the job back.

## Use Retries

To minimize the amount of false alerts you get from SITE_NAME, instruct your HTTP
client to retry failed requests several times.

Specifying the retry policy depends on the tool you use. curl, for example, has the
`--retry` parameter:

```bash
# Retry up to 5 times, uses an increasing delay between each retry (1s, 2s, 4s, 8s, ...)
curl -fsS -m 10 --retry 5 --retry-connrefused -o /dev/null PING_URL
```

`--retry` alone retries timeouts and HTTP 408, 429, 500, 502, 503 and 504
responses, but not a refused connection, which is what a client sees while the
SITE_NAME server restarts; `--retry-connrefused` (curl 7.52 and later) retries that
too. The other options are explained on the [Shell Scripts](../bash/) page.

Retry timeouts, refused connections and 5xx responses. Do not retry a 4xx: the
URL, the `rid` or the body is wrong, and repeating the request gets the same answer
(see [Status Codes](../http_api/#status-codes)). A retried ping whose first attempt
was recorded but answered too slowly is recorded twice. That is mostly harmless: the
second one sends no new alert, but it shows in the event log, a second success
clears the check's last duration (the run time shown in the list of checks; the
first success's own duration stays in the event log), and a second start moves the
run's start to the retry's time.

## Handle Exceptions

Make sure you know how your HTTP client handles failed requests. For example,
if you use an HTTP library that raises exceptions, decide if you want to
catch the exceptions or let them bubble up.

Many HTTP libraries (Python's requests, Go's net/http, JavaScript's fetch) do not
raise an error on a 404, so check the status code yourself: any status other than
200 or 201 means the ping was not recorded.

## Use the Request Method the Check Accepts

If a check accepts POST requests only, GET and HEAD pings, such as a plain
`curl PING_URL`, are recorded as ignored. See
[How SITE_NAME Interprets a Ping](../http_api/#interpreting-pings).
