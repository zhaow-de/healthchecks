# Status Badges

SITE_NAME provides status badges that you can embed in your READMEs, internal
dashboards, or public status pages. Each SITE_NAME badge reports the combined status of
all checks in the project, the status of checks tagged with a specific tag, or the
status of a single specific check.

To get a badge, open the project's "Badges" page from the top navigation. Its Badge
Generator has three choices: what the badge reports on (all checks in the project,
the checks tagged with one tag, or one specific check; the tag choice appears only
when some check in the project has a tag, and the check choice only when the project
has checks), the badge format, and the badge states. The Preview beside it shows the
resulting badge with its URL, and for the SVG and Shields.io formats also
ready-to-paste HTML and Markdown code.

The badges have public but hard-to-guess URLs. A badge shows its label and status;
the JSON format also gives the numbers of matching, late and down checks. Ping URLs
cannot be derived from badge URLs. A single-check badge's label is the check's name,
or, for a check with no name, its UUID, which is the secret in its ping URL: name a
check before you publish its badge.

## Badge URLs {: #badge-urls }

* All checks in the project: `SITE_ROOT/badge/<project badge key>/<signature>.<fmt>`
* The checks with one tag: `SITE_ROOT/badge/<project badge key>/<signature>/<tag>.<fmt>`
* One check: `SITE_ROOT/b/<states>/<check badge key>.<fmt>`

`<fmt>` is `svg`, `json` or `shields`. `<states>` is `2` or `3`; for the project and
tag badges, a signature that ends in `-2` means two states. The Management API
returns the project and tag badge URLs from
[List Project's Badges](../api/#list-badges), and a check's two-state SVG badge URL
as its `badge_url`. Badge URLs need no key, allow cross-origin GET requests and are
not cached. There is no way to change them: a check's badge works until the check is
deleted, and the project and tag badge signatures change only if the server's
[`SECRET_KEY`](../self_hosted_configuration/#SECRET_KEY) changes.

## Badge States

Each badge can be in one of the following three states:

* **up** (green) – all matching checks are up.
* **late** (orange) – at least one check is running late (but has not exceeded its grace time yet).
* **down** (red) – at least one check is currently down.

By default, SITE_NAME displays badge URLs that only report the
**up** and **down** states (and treat **late** as **up**). Using the "Badge states"
radio buttons, you can switch to alternate URLs that report all three states.

Only down and late checks change a badge: new and paused checks count as up, and a
tag badge whose tag matches no check reports up. The label of the all-checks badge
is the server's
[`MASTER_BADGE_LABEL`](../self_hosted_configuration/#MASTER_BADGE_LABEL) setting
(by default, the site name); a tag badge's label is the tag; a check badge's label is
the check's name (its UUID if it has none).

## Badge Formats

SITE_NAME offers badges in three different formats:

* SVG: returns an SVG document that you can use directly in an `<img>` element or
  a Markdown document.
* JSON: returns the current status and the check counts as a JSON document,
  `{"status": "up", "total": 3, "grace": 0, "down": 0}`, with no label; `status` is
  `up`, `late` or `down`, `total` is the number of matching checks, `grace` the
  number of late ones and `down` the number of down ones. Use this
  if you want to render the badge yourself. This can also serve as an integration
  point with a hosted status page: instruct your status page provider to monitor the
  badge URL and look for the keyword "up" in the returned data.
* Shields.io: returns the badge label and the current status as a
  Shields.io-compatible JSON document,
  `{"schemaVersion": 1, "label": "...", "message": "up", "color": "success"}`, with
  the color `success`, `important` or `critical` for up, late and down. See
  [Shields.io documentation](https://shields.io/endpoint)
  on how to use it. The generator shows an `https://img.shields.io/endpoint?url=…`
  address that wraps the badge's own `.shields` URL, so Shields.io must be able to
  reach this SITE_NAME instance over the internet. The main benefit of using
  Shields.io to generate badges is the extra visual styles and customization options
  that Shields.io supports.
