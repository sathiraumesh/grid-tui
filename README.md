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
- `1`–`7` go to a tab (form fields take digits); `r` (or `ctrl+r` in a form) reloads; `q` quits.

## Layout

```
pyproject.toml          dependencies and the grid-tui command
src/grid_tui/
  app.py                the Textual App: the main screen
  api.py                what the panels load with (the Grid'5000 client, a fake in tests)
  format.py             how times read
  grid5000/             the API client: sites, clusters, hardware, status, jobs
  models/               the data: Site, Cluster, Hardware, Node, Gantt, JobRequest, Job, …
  panels/               one per tab: sites, clusters, nodes, reservations (Current), reserve, jobs, search
  screens/              main (the tabs), splash (at start-up), reserve (the dialogs)
  widgets/              list_panel (a table loaded in the background), timeline + reservations (the Gantt chart)
tests/                  the same folders as src/grid_tui
```
