# Attaching Logs

SITE_NAME ping endpoints accept any HTTP method (see [Requests](../http_api/#requests)).
A check set to accept POST requests only records other methods as "Ignored".

**You can include an arbitrary payload in the request body**, with any method; POST
is the usual way.
SITE_NAME will log the first PING_BODY_LIMIT bytes of the request body (with the
server's body limit setting `None`, the whole body), so that you can inspect it later.

Keep the request body to the output you need to read later: SITE_NAME stores it in
its database along with every other ping in the check's log.

## Logging Command Output

In this example, we run `certbot renew`, capture its output (both the stdout
and stderr streams), and submit the captured output to SITE_NAME:

```bash
#!/bin/sh

m=$(/usr/bin/certbot renew 2>&1)
curl -fsS -m 10 --retry 5 --data-raw "$m" PING_URL
```

We can extend the previous example and signal either success or failure
depending on the exit code:

```bash
#!/bin/sh

m=$(/usr/bin/certbot renew 2>&1)
curl -fsS -m 10 --retry 5 --data-raw "$m" PING_URL/$?
```

If the command produces a lot of output, you may run into the following error:

```
/usr/bin/curl: Argument list too long
```

In that case, one workaround is to save the output to a temporary file,
then tell curl to send the file as the request body:

```bash
#!/bin/sh

/usr/bin/certbot renew > /tmp/certbot-renew.log 2>&1
curl -fsS -m 10 --retry 5 --data-binary @/tmp/certbot-renew.log PING_URL/$?
```

SITE_NAME stores at most the first PING_BODY_LIMIT_FORMATTED and drops the rest
silently (with the server's body limit setting `None`, it stores the body whole),
but it refuses a request whose body is larger than 2.5 MiB (2,621,440 bytes, or the
body limit when that is higher) with 400 and records nothing, so the success or
failure signal is lost too (see [Request Body](../http_api/#request-body)). When the
output can be that large, send only its end, keeping the exit status in a variable
first:

```bash
#!/bin/sh

/usr/bin/certbot renew > /tmp/certbot-renew.log 2>&1
rc=$?
tail -c PING_BODY_LIMIT /tmp/certbot-renew.log | curl -fsS -m 10 --retry 5 --data-binary @- PING_URL/$rc
```

## Using Runitor

[Runitor](https://github.com/bdd/runitor) is a third-party utility that runs the
supplied command, captures its output and reports to SITE_NAME.
It also measures the execution time and retries HTTP requests on transient errors.
Best of all, the syntax is simple and clean:

```bash
runitor -api-url PING_ENDPOINT -uuid your-uuid-here -- /usr/bin/certbot renew
```

Without `-api-url` (or the `HC_API_URL` environment variable), runitor sends its
pings to https://hc-ping.com, not to this server. runitor sends the last part of the
output: as many bytes as the `Ping-Body-Limit` header of its start ping's response
states, but at most 10,000,000, or, when `-ping-body-limit` is given, the smaller of
that flag and the header. When it gets no such header (the server's body limit
setting is `None`, the start ping failed, or `-no-start-ping` is given), it sends
the last `-ping-body-limit` bytes, 10,000 by default.

## Sending Logs Without Signalling Success or Failure

You may sometimes want to log diagnostic information without altering the check's
current state. SITE_NAME provides the [/log endpoint](../http_api/#log-uuid) just for
that. When you send a request to this endpoint (a POST, to carry a body), SITE_NAME
logs the event, shows it in the check's "Events" section with a "Log" label, and keeps
the check's state unchanged. The exception is a check that filters by keywords: there
the body decides, as for any ping, so a /log ping whose body matches a failure keyword
turns the check down, and one that matches no keyword is recorded as "Ignored" (or as
a failure when "If no keywords match" is set to "Classify the ping as failure"). See
[How SITE_NAME Interprets a Ping](../http_api/#interpreting-pings).

## Handling More Than PING_BODY_LIMIT_FORMATTED of Logs

While SITE_NAME can store a small amount of logs in a pinch, it is not specifically
designed for that. If your logs get cut off, or are too large to send, consider
the following options:

* See if the logs can be made less verbose. For example, if you have a batch job
that outputs a line of text per item processed, perhaps it can output a summary with
the totals instead.
* If the important content is usually at the end, submit the
**last PING_BODY_LIMIT_FORMATTED** instead of the first. Here is an example that
submits the last PING_BODY_LIMIT_FORMATTED of `dmesg` output:

```bash
#!/bin/sh

dmesg | tail -c PING_BODY_LIMIT | curl -fsS -m 10 --retry 5 --data-binary @- PING_URL
```

* Finally, if it is critical to capture the entire log output,
consider using a dedicated log aggregation service for capturing the logs.


## Where to See Captured Logs

In the check's details page, Events section, click on individual events to see
full event details, including the captured log information. The Events section lists
the 30 most recent events, and its "Show More…" link opens the check's full log,
where events open the same way. SITE_NAME keeps only the check's most recent pings
(100 by default, bodies included) and deletes older ones, so a log is readable only
until that many more pings have arrived; to keep it longer, read it into another
system with
[get a ping's body](../api/#ping-body). A ping that carried a body shows the start
of it in its row, after the source address.

Clicking a ping opens the "Ping #N" dialog: the time received, the source (protocol,
method and IP address), the duration and run ID when the ping has them, the user
agent, and, under "Request Body", the body decoded as UTF-8, with invalid bytes
replaced. Use the "Download Original" link below the body to download the stored
body bytes undecoded (the first PING_BODY_LIMIT_FORMATTED of what was submitted), as
a file named `<check-uuid>-<N>.txt`.

To read the body from a script, use the Management API's
[get a ping's body](../api/#ping-body) call.
