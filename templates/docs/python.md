# Python

If you are already using the [requests](https://requests.readthedocs.io/en/master/)
library, it is convenient to also use it here:

```python
import requests

try:
    requests.get("PING_URL", timeout=10).raise_for_status()
except requests.RequestException as e:
    # Log ping failure here...
    print("Ping failed: %s" % e)
```

requests does not raise an exception on an error status, such as the 404 of a wrong
UUID; `raise_for_status()` turns any 4xx or 5xx response into a `RequestException`.
A 2xx status means the ping was recorded (see
[Status Codes](../http_api/#status-codes)).

To retry failed pings, as the [reliability tips](../reliability_tips/) suggest, use
a session with a retry policy:

```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

retry = Retry(
    total=5,
    backoff_factor=1,
    status_forcelist=[500, 502, 503, 504],
    allowed_methods=None,
)
session = requests.Session()
session.mount("http://", HTTPAdapter(max_retries=retry))
session.mount("https://", HTTPAdapter(max_retries=retry))

try:
    session.get("PING_URL", timeout=10).raise_for_status()
except requests.RequestException as e:
    print("Ping failed: %s" % e)
```

This retries timeouts, refused connections and 5xx responses up to 5 times, waiting
0, 2, 4, 8 and 16 seconds before the retries, and does not retry a 4xx.
`allowed_methods=None` lets it retry a POST too, which urllib3 does not do by default.

Otherwise, you can use the [urllib.request](https://docs.python.org/3/library/urllib.request.html)
module from Python 3 standard library:

```python
import urllib.request

try:
    with urllib.request.urlopen("PING_URL", timeout=10):
        pass
except OSError as e:
    # Log ping failure here...
    print("Ping failed: %s" % e)
```

`urlopen` raises `HTTPError` on a 4xx or 5xx response, and `URLError` or a timeout
error when the request itself fails; `OSError` catches all of them.

You can include additional diagnostic information in the request body (for POST requests):

```python
# Passing diagnostic information in the POST body:
import requests

try:
    requests.post("PING_URL", data="temperature=-7", timeout=10).raise_for_status()
except requests.RequestException as e:
    print("Ping failed: %s" % e)
```

SITE_NAME stores the body with the ping; see [Request Body](../http_api/#request-body)
for how much of it is kept and how large a body may be.
