# Shell Scripts

You can easily add SITE_NAME monitoring to a shell script. All you
have to do is make an HTTP request at an appropriate place in the script.
[curl](https://curl.se/docs/manpage.html) and
[wget](https://www.gnu.org/software/wget/manual/wget.html)
are two common command-line HTTP clients you can use.

```bash
# Sends an HTTP GET request with curl:
curl -m 10 --retry 5 PING_URL

# Silent version (no stdout/stderr output unless curl hits an error):
curl -fsS -m 10 --retry 5 -o /dev/null PING_URL

# Sends an HTTP GET request with wget:
wget PING_URL -T 10 -t 5 -O /dev/null
```

With wget, `-T 10` is the timeout in seconds, `-t 5` the number of tries in total,
and `-O /dev/null` discards the response.

Here's what each curl parameter does:

**-m &lt;seconds&gt;**
:   Maximum time in seconds that you allow the HTTP request to take.
    If you use the `--retry` parameter, then the time counter is reset
    at the start of each retry.

**--retry &lt;num&gt;**
:   On transient errors, retry up to this many times. By default, curl
    uses an increasing delay between each retry (1s, 2s, 4s, 8s, ...).
    See also [--retry-delay](https://curl.se/docs/manpage.html#--retry-delay).
    Transient errors are: timeouts, HTTP status codes 408, 429, 500, 502, 503, 504.
    A refused connection, such as while the server restarts, is not a transient
    error; add `--retry-connrefused` to retry it too.

**-f, --fail**
:   Makes curl treat HTTP responses with a status of 400 or above as errors, and
    [exit with code 22](https://curl.se/docs/manpage.html#-f).

**-s, --silent**
:   Silent or quiet mode. Hides the progress meter, but also
    hides error messages.

**-S, --show-error**
:   Re-enables error messages when -s is used.

**-o /dev/null**
:   Redirects curl's stdout to /dev/null (error messages still go to stderr).

## Signaling Failure from Shell Scripts

You can append `/fail` or `/{exit-status}` to any ping URL and use the resulting URL
to actively signal a failure. The exit status should be a 0-255 integer.
SITE_NAME will interpret exit status 0 as success and all non-zero values as failures.
An exit status above 255 gets "400 invalid url format" and is not recorded. On a check
that filters by keywords, the body decides instead of the exit status; on a check that
accepts POST requests only, a GET ping such as a plain curl call is ignored. See
[Report Script's Exit Status](../http_api/#exitcode-uuid) and
[How SITE_NAME Interprets a Ping](../http_api/#interpreting-pings).

The following example runs `/usr/bin/certbot renew`, and uses the `$?` variable to
look up its exit status:

```bash
#!/bin/sh

# Payload here:
/usr/bin/certbot renew
# Ping SITE_NAME
curl -m 10 --retry 5 PING_URL/$?
```

Note on pipelines (`command1 | command2 | command3`) in Bash scripts: by default, a
pipeline's exit status is the exit status of the rightmost command in the pipeline.
Use `set -o pipefail` if you need the pipeline to return non-zero exit status if *any*
part of the pipeline fails:

```bash
#!/bin/bash

set -o pipefail
pg_dump somedb | gpg --encrypt --recipient alice@example.org --output somedb.sql.gpg
# Without pipefail, if pg_dump command fails, but gpg succeeds, $? will be 0,
# and the script will report success.
# With pipefail, the pipeline's status is that of the last command in it that failed:
# pg_dump's code when only pg_dump fails, gpg's when both fail.
curl -m 10 --retry 5 PING_URL/$?
```

## Logging Command Output

Any request may carry extra diagnostic information in its body. SITE_NAME stores
at most the first PING_BODY_LIMIT_FORMATTED of it, as bytes whatever the encoding,
and drops the rest (with the server's body limit setting `None`, it stores the body
whole). A body larger than 2.5 MiB, or than the body limit when that is higher, is
refused and the ping is not recorded: the server may close the connection without a
response, and curl then exits with code 52. See
[Request Body](../http_api/#request-body).

In the below example, certbot's output is captured and submitted via HTTP POST,
together with certbot's exit status:

```bash
#!/bin/sh

m=$(/usr/bin/certbot renew 2>&1)
rc=$?
printf '%s' "$m" | tail -c PING_BODY_LIMIT | curl -fsS -m 10 --retry 5 --data-binary @- PING_URL/$rc
```

`tail -c` sends only the last PING_BODY_LIMIT bytes, which is the most SITE_NAME
keeps; this avoids the 400 that a body over the size cap gets, which loses the
ping. Reading the body from stdin (`@-`) also avoids the shell's limit on argument
length (128 KiB per argument on Linux), which `--data-raw "$m"` hits. `/$rc`
reports certbot's exit status together with its output.
