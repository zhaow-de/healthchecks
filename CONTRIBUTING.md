# Contributing

This repository was created from
[healthchecks/healthchecks](https://github.com/healthchecks/healthchecks) and is
developed independently of it. Feature suggestions and code contributions are
welcome. For anything larger than a small, straightforward bugfix, open an issue
first so the approach can be agreed before the work is done.

## Pull Requests

Cut your branch from `develop` and open the pull request into `develop`; `main`
only receives releases. Commit messages follow
[Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/), because
the next version number is computed from them. Every pull request runs the
`Full test suite` check, which has to pass before it can be merged.

## Code Style

* Run the commit gate, `uv run pre-commit run -a`, before every commit. It
  formats and lints Python with [ruff](https://docs.astral.sh/ruff/), refusing
  the commit over a lint finding it cannot fix itself (the rule set is in
  `ruff.toml`), lints our JavaScript under `static/js` and the integrations'
  `static/js` with [ESLint](https://eslint.org/) for undefined and unused names
  (`eslint.config.js`, no formatter), and checks file hygiene and YAML. You do
  not need Node: on its first run pre-commit downloads the Node version the hook
  pins, together with ESLint, into its cache.
* Prefer simplicity over cleverness.
* If you are fixing a bug or adding a feature, add a test. Run
  `uv run pytest hc -n auto` (the Django suite) and `uv run pytest -n auto` (the
  tooling tests) before opening a pull request.

## Adding Documentation

This project uses the Markdown format for documentation. Use the `render_docs`
management command to generate the HTML version of the documentation. To add a new
documentation page:

1. Create the appropriate .md file under `templates/docs`
2. Generate the HTML version with `uv run ./manage.py render_docs`
3. Add the page to the navigation in `/templates/front/docs_single.html`

## Developing a New Integration

Before starting work on a new integration, please open an issue and
discuss it first. This fork keeps only the integrations its own deployment
uses, so a new one is added when that deployment needs it. Beyond that need,
we ask:

* Is the service we are integrating with developer-friendly? Does it have an open
  and well-documented API? Can we develop and test the integration while avoiding
  sales calls, contract signing, paid subscriptions?
* Does the new integration enable something that is otherwise not possible (or is
  very inconvenient) via webhooks or email?

The best way to build a new integration is to pick a similar existing integration
as a starting point for the new integration and replicate every aspect of it.
You will need to make changes in the following files:

* In `/hc/integrations/`, copy an existing integration to a new directory
* Edit the transport class in `/hc/integrations/<kind>/transport.py`.
* Edit the notification template(s) in `/hc/integrations/<kind>/templates/`.
* Write testcases for the transport class in
  `/hc/integrations/<kind>/tests/test_notify.py`.
* Update `TRANSPORTS` in `/hc/api/models.py`.
* Edit the view(s) for provisioning the integration in
  `/hc/integrations/<kind>/views.py`.
* Write an HTML template for the new view in
  `/hc/integrations/<kind>/templates/add_<kind>.html`, and prepare any supporting
  illustrations in `/hc/integrations/<kind>/static/img/`.
* Edit routes for the new view(s) in `/hc/integrations/<kind>/urls.py`.
* Include the new integration's urls.py in `/hc/urls.py`
* Write testcases for the new view in `/hc/integrations/<kind>/tests/test_add.py`.
* Update `/templates/front/channels.html` – add a new section in the list of available
  integrations, make sure an existing integration is displayed nicely.
* Update `/templates/front/event_summary.html` to make sure notifications sent to the
  new integration are displayed nicely.
* Add a logo in `/hc/integrations/<kind>/static/img/`.
* Update the icon font in `static/fonts/` (the IcoMoon project is
  `stuff/icons_icomoon_project.json`).
