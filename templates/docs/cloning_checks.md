# Cloning Checks

You can clone individual checks from the "Check Details"
page: click "Create a Copy…" in its "Danger Zone" section, and confirm with
"Create a Copy" in the dialog that opens.

The "Create a Copy..." function creates a new check in the same project and copies
over the following:

* Name, with " (copy)" appended; when that would make it longer than 100 characters,
  the first 90 characters of the name followed by "... (copy)"
* Slug, with "-copy" appended; the copy gets an empty slug when the check has none,
  or when "-copy" would make it longer than 100 characters
* Tags, description
* Schedule: its type, period or expression, time zone, and grace time
* Filtering rules: every setting of the "Filtering Rules" dialog
* Assigned notification methods

The newly created check has a different ping URL and an empty event log, and starts
in the "new" state. SITE_NAME then opens its details page with a "Copy created!" note.

## Cloning All Checks Into a New Project

It is sometimes useful to clone an entire project. For example, when recreating
an existing deployment in a new region. The SITE_NAME web interface does
not have a function to clone an entire project, but you can clone all checks in the
project relatively easily using the [Management API](../api/) calls.
Below is an example using Python and the [requests](https://requests.readthedocs.io/en/master/) library:

```python
import requests

API_URL = "SITE_ROOT/api/v3/checks/"
SOURCE_PROJECT_READONLY_KEY = "..."
TARGET_PROJECT_KEY = "..."

r = requests.get(API_URL, headers={"X-Api-Key": SOURCE_PROJECT_READONLY_KEY})
for check in r.json()["checks"]:
    print("Cloning %s" % check["name"])
    requests.post(API_URL, json=check, headers={"X-Api-Key": TARGET_PROJECT_KEY})
```
