# Measuring Script Run Time

 Append `/start` to a ping URL and use it to signal when a job starts.
 After receiving a start signal, SITE_NAME will show the check as "Started."
 It will store the "start" events and display the job execution times. SITE_NAME
 calculates the job execution times as the time gaps between adjacent "start" and
 "success" events.

Note: if appending `/start` to the ping URL on the client side is not feasible, you can
alternatively configure SITE_NAME to classify HTTP pings as start, success, or failure
signals [by looking for specific keywords in the HTTP request body](../configuring_checks/#filtering-rules).

## Alerting Logic

SITE_NAME applies an additional alerting rule for jobs that use the `/start` signal.

If a job sends a "start" signal but does not send a "success"
signal within its configured grace time, SITE_NAME will assume the job
has failed. It will mark the job as "down" and send out alerts.

## Usage Example

Below is a code example in Python:

```python
import requests
URL = "PING_URL"


# "/start" kicks off a timer: if the job takes longer than
# the configured grace time, SITE_NAME will mark it as "down"
try:
    requests.get(URL + "/start", timeout=5)
except requests.exceptions.RequestException:
    # If the network request fails for any reason, we don't want
    # it to prevent the main job from running
    pass


# TODO: run the job here
fib = lambda n: n if n < 2 else fib(n - 1) + fib(n - 2)
print("F(42) = %d" % fib(42))

# Signal success:
requests.get(URL)
```

## Viewing Measured Run Times

When SITE_NAME receives a "start" signal followed by a regular ping or a "fail"
signal, and the two events are less than 72 hours apart,
you will see the duration displayed in the list of checks. If the two events are
more than 72 hours apart, they are assumed to be unrelated, and the duration is
not displayed.

In the list of checks, the duration appears in the "Last Ping" column, below the
time of the last ping and after a stopwatch icon (for example, "7 min 22 sec"), and
when any check in the list shows one, the column heading gains a "Last Duration" line.
It is the duration of the run that the last success or failure ended: a later success
or failure that ends no run removes it.

You can also see the durations of the previous runs when viewing an individual
check: in the "Events" section of its details page, a success or failure that has
a matching earlier "start" event shows the time since it, after a stopwatch icon, at
the right end of its row ([Run IDs](../http_api/#run-ids) in the Pinging API
reference says how the start is matched). The [list pings](../api/#list-pings) call
of the Management API returns the same value as each ping's `duration` field.

## Specifying Run IDs

When several instances of the same job can run concurrently, the calculated run times
can come out wrong, as SITE_NAME cannot reliably determine which success event
corresponds to which start event. To work around this problem, the client can
optionally specify a run ID in the `rid` query parameter of any ping URL. When a
success event specifies the `rid` parameter, SITE_NAME will look for a
start event with a matching `rid` value when calculating the execution time.

The run IDs must be in a specific format: they must be UUID values in the canonical
textual representation (example: `728b3763-ea80-4113-9fc0-f49b3adf226a`, note no
curly braces). The letters in the UUID are allowed to be either in the lower or
upper case.

The client is free to pick run ID values randomly or use a deterministic process
to generate them. The only thing that matters is that the start and the success
pings of a single job execution use the same run ID value.

Below is an example shell script that generates the run ID using `uuidgen` and
makes HTTP requests using curl:

```bash
#!/bin/sh

RID=`uuidgen`

# send a start ping, specify rid parameter:
curl -fsS -m 10 --retry 5 PING_URL/start?rid=$RID

# ... FIXME: run the job here ...

# send the success ping, use the same rid parameter:
curl -fsS -m 10 --retry 5 PING_URL?rid=$RID
```

If the client specifies run IDs, SITE_NAME will display them in the "Events"
section in a shortened form, the first five characters in a grey label before the
source address (the "Ping #N" dialog of an event shows the whole run ID). Here two
runs overlap: run `3f2c8…` starts as event #1, run `b81d0…` starts as event #2 and
finishes as event #3, and run `3f2c8…` finishes as event #4:

![Log of received pings with run IDs and durations](IMG_URL/run_ids.png)

Also, note how the execution times are available for both "success" events. If the
run IDs were not used in this example, the event #4 would not show an execution time
since it is not preceded by a "start" event.

## Alerting Logic When Using Run IDs

If a job sends a "start" signal but does not send a "success"
signal within its configured grace time, SITE_NAME will assume the job
has failed and notify you. However, when using Run IDs, there is an important
caveat: SITE_NAME **will not monitor the execution times of all
concurrent job runs**. It will only monitor the execution time of the
most recently started run.

To illustrate, let's assume the grace time of 1 minute and look at the above example
again. The event #4 ran for 6 minutes 39 seconds and so overshot the time budget
of 1 minute. But SITE_NAME generated no alerts because **the most recently started
run completed within the time limit** (it took 37 seconds, which is less than 1 minute).
