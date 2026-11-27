"""The top-right line: the policy period, and how busy it is.

    Day · until 19:00   nancy 91% · G5K 69% busy

It follows a site: the one highlighted in the Sites tab, or the last site or
cluster chosen. Until there is one, it shows all of Grid'5000 ('G5K').

- The period comes from the clock (see grid_tui.policy).
- How busy: the site's nodes that run a job, of those that are up, and the
  same for all of Grid'5000. Every site's status comes in one round, so
  switching site shows its number at once.

Your quota is per cluster, so it is in the Clusters tab, not here; bar() and
level_colour() draw it there.

How busy is asked for again every 2 minutes. The line sits over the tab
row's empty right side and takes no room from the tabs.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from rich.text import Text
from textual import work
from textual.widgets import Static

from grid_tui.grid5000 import ApiError, Client
from grid_tui.models import Usage
from grid_tui.policy import PARIS, period_at

BAR_WIDTH = 8
BUSY_SECONDS = 120  # how often to ask how busy every site is
TICK_SECONDS = 30  # how often to redraw and see what's old; costs no request

TABS_WIDTH = 34  # the tab labels on the left of the same row: keep clear of them
GREEN, RED = '#a6e3a1', '#f38ba8'
YELLOW = '#f9e2af'
EMPTY = '#45475a'
MUTED = '#a6adc8'
ORANGE = '#fab387'


# how full the quota is → its colour: the first limit it is under
LEVELS = ((50, GREEN), (80, YELLOW), (100, ORANGE))


def level_colour(percent: int) -> str:
    """The colour of a quota this full: green, yellow from 50, orange from 80,
    red from 100 (used up)."""
    for limit, colour in LEVELS:
        if percent < limit:
            return colour
    return RED


PARTS = ' ▏▎▍▌▋▊▉'  # a cell filled 0/8 to 7/8, from the left


def bar(percent: int, width: int = BAR_WIDTH) -> Text:
    """A bar for a percentage, e.g. '██░░░░░░' for 25, coloured by how full.

    It is drawn in eighths of a cell, so a small share still shows: 3% is a
    sliver ('▎'), not an empty bar. Anything above 0 shows at least 1/8.

    Args:
        percent: How full; below 0 is empty, 100 or more is full (and red).
        width: How many cells the bar has.
    """
    share = max(0, min(100, percent)) / 100
    eighths = round(width * 8 * share)
    if percent > 0:
        eighths = max(eighths, 1)  # some use shows, however small
    full, part = divmod(eighths, 8)
    colour = level_colour(percent)
    text = Text()
    text.append('█' * full, colour)
    if part:
        # the partial cell: its filled left part coloured, on the empty colour
        text.append(PARTS[part], f'{colour} on {EMPTY}')
    text.append('░' * (width - full - (1 if part else 0)), EMPTY)
    return text


class UsageBar(Static):
    """The policy period and how busy Grid'5000 is, kept up to date."""

    DEFAULT_CSS = (Path(__file__).parent / 'usage_bar.tcss').read_text()

    def __init__(
        self,
        client: Client,
        *,
        clock: Callable[[], datetime] | None = None,
        **kwargs: Any,
    ) -> None:
        """Make the line.

        Args:
            client: Where to ask.
            clock: What gives the time now; tests pass a fixed one.
            **kwargs: Passed on to Static, e.g. id or classes.
        """
        super().__init__(**kwargs)
        self.client = client
        self.clock = clock or (lambda: datetime.now(PARIS))
        self.by_site: dict[str, Usage] | None = None  # how busy each site is
        self.failed = False  # did the last try fail
        self.site: str | None = None  # the site it's about; None for all
        self._busy_at = 0.0  # when it was last loaded

    def show_site(self, site: str | None) -> None:
        """Be about another site (None for all of Grid'5000).

        How busy each site is is already loaded, so it shows at once.

        Args:
            site: The site, e.g. 'nancy'; None for every site.
        """
        if site != self.site:
            self.site = site
            self.redraw()

    def on_mount(self) -> None:
        """Show the period at once, then load, and keep everything up to date."""
        self.redraw()
        self.load()
        self.set_interval(TICK_SECONDS, self._tick)

    def _tick(self) -> None:
        """Every 30 s: redraw (the period may change), and load what's old.

        Nothing is asked while the app is in the background or an SSH
        session runs (see Grid5KApp.polling); when it comes back, the next
        tick catches up.
        """
        polling = getattr(self.app, 'polling', True)
        if polling and time.monotonic() - self._busy_at >= BUSY_SECONDS:
            self.load()
            return
        self.redraw()

    @work(exclusive=True, group='usage')
    async def load(self, *, refresh: bool = False) -> None:
        """Ask how busy every site is, then redraw.

        Args:
            refresh: Ask the API even for answers it remembers.
        """
        try:
            by_site = await self.client.status.usage_by_site(refresh=refresh)
        except (ApiError, httpx.HTTPError):
            self.failed = True
        else:
            self.by_site, self.failed = by_site, False
            self._busy_at = time.monotonic()
        self.redraw()

    def busy(self, site: str | None) -> Usage | None:
        """How busy a site is (None: all of Grid'5000); None if not known."""
        if self.by_site is None:
            return None
        if site is None:
            return sum(self.by_site.values(), Usage())
        return self.by_site.get(site)

    def redraw(self) -> None:
        """Draw the line, and put it in the top-right corner."""
        self.place()

    def place(self) -> None:
        """Draw the longest line that fits beside the tabs, against the right edge.

        Call it again when the terminal's size changes.
        """
        room = self.parent.size.width if self.parent is not None else 0
        tabs_end = self.tabs_end()
        for detail in (2, 1, 0):  # less and less detail until it fits
            text = self.line(detail)
            if text.cell_len + 2 <= room - tabs_end:
                break
        self.update(text)
        width = text.cell_len + 2  # the padding
        self.styles.width = width
        self.styles.offset = (max(room - width, 0), 0)

    def tabs_end(self) -> int:
        """Where the tab labels end on the row (keep clear of them)."""
        try:
            tabs = list(self.screen.query('Tab'))
        except Exception:  # noqa: BLE001 - not on a screen yet
            return TABS_WIDTH
        ends = [tab.region.right for tab in tabs if tab.region.width]
        return max(ends) + 2 if ends else TABS_WIDTH

    def line(self, detail: int = 3) -> Text:
        """The line: the period, how busy the site and Grid'5000 are.

        Args:
            detail: 2 for all of it; 1 leaves out when the period ends; 0
                also leaves out Grid'5000's number (the site's stays).
        """
        now = self.clock()
        period = period_at(now)
        text = Text(period.name, f'bold {ORANGE}')
        if detail >= 2:
            text.append(f' · until {period.until(now)}', MUTED)
        text.append('   ')
        parts = [self.site] if self.site else []
        if detail >= 1 or not self.site:
            parts.append(None)  # all of Grid'5000
        for index, site in enumerate(parts):
            if index:
                text.append(' · ', MUTED)
            usage = self.busy(site)
            number = '?' if self.failed else '…'
            if usage is not None:
                number = f'{usage.percent}%'
            text.append(f'{site or "G5K"} ', MUTED)
            text.append(number, 'bold' if site else MUTED)
        text.append(' busy', MUTED)
        if self.failed and self.by_site:
            text.append(' (old)', MUTED)  # the last try failed: these are older
        return text
