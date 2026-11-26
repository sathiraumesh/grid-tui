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
 1 Sites   2 Clusters   3 Nodes   4 Reservations   7 Search
                                  └ 4 Current   5 Reserve   6 My reservations
```

- **1 Sites → 2 Clusters → 3 Nodes → 4 Current**: `enter` goes down (a site's
  clusters, a cluster's hardware and nodes, a node's reservations), `esc` back up.
- **4 Current**: a cluster's reservations as a time line, a week or a month
  (`t w m`); `b` reserves from the cursor, `x` cancels one of your jobs.
- **5 Reserve**: choose a date, a time, a duration and how many nodes; see which
  clusters can take it; reserve on one (`Reserve`, then `Yes, send`).
- **6 My reservations**: your jobs on every site; `x` cancels, `enter` shows one's cluster.
- **7 Search**: the clusters of every site that meet a form of requirements.
- `1`–`7` go to a tab (form fields take digits); `r` reloads the tab that is showing; `q` quits.

## Layout

```
pyproject.toml          dependencies and the grid-tui command
src/grid_tui/
  app.py                the Textual App: the main screen
  format.py             how sizes, numbers and times read
  requirements.py       the Search tab's hardware needs, and which nodes meet them
  grid5000/             the API client: sites, clusters, nodes (login from ~/.grid-secret)
  models/               the data: Site, Cluster, Node, MetricInfo, …
  widgets/
    main_tabs/          the tabs, one panel in each
    panels/             what each tab shows: sites, clusters, nodes, search
    popups/             screens that open over the app: node_details
    thin_scrollbar/     a slimmer scrollbar
tests/                  the same folders as src/grid_tui
```
