# grid-tui (Python / Textual)

A terminal UI for Grid'5000, built with [Textual](https://textual.textualize.io).

## Set up

```sh
python3 -m venv .venv            # already done once
source .venv/bin/activate
pip install -e '.[dev]'          # the app, plus pytest and textual-dev
```

## Run

```sh
grid-tui                         # or: python -m grid_tui
textual run --dev src/grid_tui/app.py   # with live CSS reload; `textual console` in another terminal for logs
```

Outside Grid'5000 the API needs your login. Set `G5K_USER` / `G5K_PASSWORD` in
the environment, or put them base64-encoded in `~/.grid-secret/`, one file per
variable:

```sh
make secret                      # asks for the user and password and writes them; or by hand:
mkdir -p ~/.grid-secret && chmod 700 ~/.grid-secret
printf '%s' 'alice'    | base64 > ~/.grid-secret/G5K_USER
printf '%s' 'p4ssw0rd' | base64 > ~/.grid-secret/G5K_PASSWORD
chmod 600 ~/.grid-secret/*
```

## Test

```sh
pytest
```

## Using it

```
 1 Sites   2 Clusters   3 Nodes   4 Reservations   5 Search
```

- **1 Sites → 2 Clusters → 3 Nodes**: `enter` goes down (a site's clusters, a
  cluster's nodes, a node's details). Moving onto a site shows its usage top right.
- **2 Clusters**: `s` (or `SSH ›`) opens a shell on the site's frontend.
- **4 Reservations**: a cluster's reservations on a timeline: nodes down the
  side, time across, an orange line for now, the daytime-quota hours shaded.
  Set *nodes* and *hours* to find the next free slot. `z` zooms (12 h to 7 days),
  `[` `]` move earlier and later, `n` comes back to now.
- **5 Search**: the clusters of every site that meet a form of requirements.
- Top right: the policy period, your quota and jobs, and how busy it is.
- `1`–`5` go to a tab (form fields take digits); `r` reloads the tab; `q` quits.

## Layout

```
pyproject.toml          dependencies and the grid-tui command
src/grid_tui/
  app.py                the Textual App: the main screen
  format.py             how sizes, numbers and times read
  requirements.py       the Search tab's hardware needs, and which nodes meet them
  policy.py             the usage policy's periods: day, night, weekend, holidays
  my_usage.py           your jobs now, and today's daytime quota
  grid5000/             the API client: sites, clusters, nodes, status, jobs (login from ~/.grid-secret)
  models/               the data: Site, Cluster, Node, MetricInfo, …
  widgets/
    main_tabs/          the tabs, one panel in each
    panels/             what each tab shows: sites, clusters, nodes, reservations, search
    popups/             screens that open over the app: node_details
    thin_scrollbar/     a slimmer scrollbar
    usage_bar/          the top-right line: policy period, your usage, how busy
  utils/                helpers: ssh (open a shell on a site's frontend)
tests/                  the same folders as src/grid_tui
```
