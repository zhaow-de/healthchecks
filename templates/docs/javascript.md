# Javascript

Below is a minimal example of making an HTTP request to SITE_NAME from Node.js. It
uses the global `fetch` of Node.js 18 and later, which handles both `http://` and
`https://` URLs and needs no package:

```js
async function ping(url) {
    try {
        const res = await fetch(url, {signal: AbortSignal.timeout(10000)});
        if (!res.ok) throw new Error("HTTP " + res.status);
    } catch (error) {
        // Log the error and continue. A ping failure should
        // not prevent the job from running.
        console.error("Ping failed: " + error);
    }
}

ping("PING_URL");
```

`fetch` rejects only when the request itself fails (a timeout, a refused
connection). A response with an error status, such as the 404 of a wrong UUID,
resolves normally, so the example checks `res.ok`: a 2xx status means the ping was
recorded, and any other status means it was not (see
[Status Codes](../http_api/#status-codes)). Node's `https` module, used by older
examples, accepts only `https://` URLs: `https.get()` throws
`ERR_INVALID_PROTOCOL` for an `http://` ping URL.

Note: requests run asynchronously. If you send both "start" and "success" signals
without waiting for the first to finish, you can encounter a race condition where
the "success" signal arrives before the "start" signal. The check is then left
running, and goes down when its grace time passes. Avoid the race condition by
using callbacks, promises or the async/await feature. Here is an example that uses
async/await and the `ping` function above:

```js
async function runJob() {
    const pingUrl = "PING_URL";

    await ping(pingUrl + "/start");
    try {
        console.log("TODO: run the job here");

        await ping(pingUrl); // success
    } catch (error) {
        await ping(pingUrl + "/fail");
    }
}

runJob();
```

## Browser

You can also send pings from a browser environment. SITE_NAME sets
`Access-Control-Allow-Origin: *` on successful (200 and 201) responses, so a GET,
HEAD, or POST with a `text/plain` body (or no body) from a page on another origin
works:

```js
var xhr = new XMLHttpRequest();
xhr.open('GET', 'PING_URL', true);
xhr.send(null);
```

Error responses carry no CORS header, so the page cannot read their status:
`XMLHttpRequest` reports status 0 and `fetch` rejects, instead of showing the 404.

Do not send a request that needs a CORS preflight, such as one with a JSON content
type, custom headers, or a method other than GET, HEAD and POST. SITE_NAME records
the preflight OPTIONS request as a ping, and the browser then blocks the real
request, because the response has no `Access-Control-Allow-Methods` or
`Access-Control-Allow-Headers` header. The preflight is classified as a ping of that
URL with an empty body would be: by default, as a ping of the URL's kind (a preflight
of a `/fail` URL is a failure); on a check that accepts POST requests only, as
"Ignored"; on a check that filters by keywords, as "Ignored", or as a failure when
"If no keywords match" is set to "Classify the ping as failure" (see
[How SITE_NAME Interprets a Ping](../http_api/#interpreting-pings)).

A ping URL in a page's source can be read, and used, by anyone who loads the page.
