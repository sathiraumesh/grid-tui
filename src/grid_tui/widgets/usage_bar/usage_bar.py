"""The top-right line: the policy period, your usage, and how busy a site is.

    Day · until 19:00   You ██░░░░░░  12% quota · 1 job, 32 cores   nancy 91% busy

It is about one site: the one you last chose (a site, or a cluster's site).
Until you choose one, it is about all of Grid'5000 ('G5K').

- The period comes from the clock (see grid_tui.policy).
- Your usage (green) is your share of today's daytime quota on your most used
  cluster of the site, and what you run there now (see grid_tui.my_usage).
- How busy: the site's nodes that run a job, of those that are up.

Both are asked for again every minute. The line sits over the tab row's empty
right side and takes no room from the tabs.
"""

from __future__ import annotations

import asyncio
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
from grid_tui.my_usage import MyUsage, my_usage
from grid_tui.policy import PARIS, period_at

BAR_WIDTH = 8
REFRESH_SECONDS = 60  # how often to ask the API again
CLOCK_SECONDS = 30  # how often to check whether the period has changed

TABS_WIDTH = 34  # the tab labels on the left of the same row: keep clear of them
GREEN, RED = '#a6e3a1', '#f38ba8'
EMPTY = '#45475a'
MUTED = '#a6adc8'
ORANGE = '#fab387'


def bar(percent: int, width: int = BAR_WIDTH) -> Text:
    """A green bar for a percentage, e.g. '██░░░░░░' for 25; red from 100.

    Args:
        percent: How full; below 0 is empty, 100 or more is full (and red).
        width: How many cells the bar has.
    """
    filled = round(width * max(0, min(100, percent)) / 100)
    colour = RED if percent >= 100 else GREEN
    return Text.assemble(('█' * filled, colour), ('░' * (width - filled), EMPTY))


def jobs_text(mine: MyUsage) -> str:
    """What you run: '1 job, 32 cores', '2 jobs waiting', or 'no jobs'."""
    if mine.jobs:
        jobs = f'{mine.jobs} job{"s" if mine.jobs != 1 else ""}'
        return f'{jobs}, {mine.cores} cores'
    if mine.waiting:
        return f'{mine.waiting} waiting'
    return 'no jobs'


class UsageBar(Static):
    """The policy period, your usage and how busy Grid'5000 is, kept up to date."""

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
            client: Where to ask (your jobs need your login).
            clock: What gives the time now; tests pass a fixed one.
            **kwargs: Passed on to Static, e.g. id or classes.
        """
        super().__init__(**kwargs)
        self.client = client
        self.clock = clock or (lambda: datetime.now(PARIS))
        self.mine: MyUsage | None = None  # None until loaded
        self.platform: Usage | None = None
        self.failed = False  # did the last try fail
        self.site: str | None = None  # the site it's about; None for all

    def show_site(self, site: str | None) -> None:
        """Be about another site (None for all of Grid'5000), and load it.

        Args:
            site: The site, e.g. 'nancy'; None for every site.
        """
        if site == self.site:
            return
        self.site = site
        self.mine = self.platform = None  # the old site's numbers would mislead
        self.redraw()
        self.load()

    def on_mount(self) -> None:
        """Show the period at once, then load, and keep everything up to date."""
        self.redraw()
        self.load()
        self.set_interval(REFRESH_SECONDS, self.load)
        self.set_interval(CLOCK_SECONDS, self.redraw)

    @work(exclusive=True, group='usage')
    async def load(self) -> None:
        """Ask for your usage and how busy the site is, together, then redraw."""
        site = self.site
        mine, platform = await asyncio.gather(
            my_usage(self.client, self.clock(), site),
            self.client.status.usage(site),
            return_exceptions=True,
        )
        errors = (ApiError, httpx.HTTPError)
        self.failed = isinstance(mine, errors) or isinstance(platform, errors)
        for answer in (mine, platform):
            if isinstance(answer, BaseException) and not isinstance(answer, errors):
                raise answer  # a bug, not the network: let it show
        if isinstance(mine, MyUsage):
            self.mine = mine
        if isinstance(platform, Usage):
            self.platform = platform
        self.redraw()

    def redraw(self) -> None:
        """Draw the line, and put it in the top-right corner."""
        self.place()

    def place(self) -> None:
        """Draw the longest line that fits beside the tabs, against the right edge.

        Call it again when the terminal's size changes.
        """
        room = self.parent.size.width if self.parent is not None else 0
        for detail in (2, 1, 0):  # less and less detail until it fits
            text = self.line(detail)
            if text.cell_len + 2 <= room - TABS_WIDTH:
                break
        self.update(text)
        width = text.cell_len + 2  # the padding
        self.styles.width = width
        self.styles.offset = (max(room - width, 0), 0)

    def line(self, detail: int = 2) -> Text:
        """The line: period, your usage, how busy the platform is.

        Args:
            detail: 2 for all of it; 1 leaves out how busy the site is;
                0 also leaves out when the period ends.
        """
        now = self.clock()
        period = period_at(now)
        text = Text(period.name, f'bold {ORANGE}')
        if detail >= 1:
            text.append(f' · until {period.until(now)}', MUTED)
        text.append('   You ', 'bold')
        if self.mine is None:
            text.append('…' if not self.failed else '?', MUTED)
        else:
            if self.mine.quota_percent is not None:
                percent = self.mine.quota_percent
                text.append_text(bar(percent))
                colour = RED if percent >= 100 else GREEN
                text.append(f' {percent}% quota', f'bold {colour}')
                text.append(' · ', MUTED)
            text.append(jobs_text(self.mine), GREEN)
        if detail >= 2:
            text.append(f'   {self.site or "G5K"} ', MUTED)
            if self.platform is None:
                text.append('…' if not self.failed else '?', MUTED)
            else:
                text.append(f'{self.platform.percent}% busy', MUTED)
        if self.failed and (self.mine or self.platform):
            text.append(' (old)', MUTED)  # the last try failed: these are older
        return text
