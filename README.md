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

## Layout

```
pyproject.toml        dependencies (textual) and the grid-tui command
src/grid_tui/
  app.py              the Textual App
  __main__.py         python -m grid_tui
tests/                pytest, driving the app headless with app.run_test()
```
