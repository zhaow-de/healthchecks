# Go

Below is an example of making an HTTP request to SITE_NAME from Go.

```go
package main

import (
    "fmt"
    "net/http"
    "time"
)

func main() {
    var client = &http.Client{
        Timeout: 10 * time.Second,
    }

    resp, err := client.Head("PING_URL")
    if err != nil {
        fmt.Println("Ping failed:", err)
        return
    }
    resp.Body.Close()
    if resp.StatusCode >= 300 {
        fmt.Println("Ping failed:", resp.Status)
    }
}

```

`client.Head` returns an error only when the request itself fails (a timeout, a
refused connection). A response with an error status, such as the 404 of a wrong
UUID, comes back with no error, so the example checks the status code: a 2xx status
means the ping was recorded, and any other status means it was not (see
[Status Codes](../http_api/#status-codes)). A HEAD request carries no body, and a
check that accepts POST requests only records it as ignored; to send a body, use
`client.Post` (see [Request Body](../http_api/#request-body)).

To retry failed pings, as the [reliability tips](../reliability_tips/) suggest, retry
errors and 5xx responses with a growing delay, and stop on any other status:

```go
package main

import (
    "fmt"
    "net/http"
    "time"
)

func ping(client *http.Client, url string) error {
    var err error
    delay := time.Second
    for attempt := 1; attempt <= 5; attempt++ {
        if attempt > 1 {
            time.Sleep(delay)
            delay *= 2
        }
        var resp *http.Response
        resp, err = client.Head(url)
        if err != nil {
            continue // timeout, refused connection: retry
        }
        resp.Body.Close()
        if resp.StatusCode < 300 {
            return nil
        }
        err = fmt.Errorf("HTTP %s", resp.Status)
        if resp.StatusCode < 500 {
            return err // 4xx: the URL is wrong, retrying will not help
        }
    }
    return err
}

func main() {
    var client = &http.Client{
        Timeout: 10 * time.Second,
    }

    if err := ping(client, "PING_URL"); err != nil {
        fmt.Println("Ping failed:", err)
    }
}
```

This makes up to 5 attempts, waiting 1, 2, 4 and 8 seconds between them.
