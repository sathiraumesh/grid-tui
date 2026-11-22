"""The search: the clusters of every site that meet some requirements.

    ╭─ requirements ──────────╮╭─ matches: 3 of 41 · loading sites 7/9 ─────────────────╮
    │ [x] Has GPU             ││ SITE   CLUSTER  NODES  CPU                   CORES  …   │
    │ [ ] Wattmeter           ││ lyon   gemini   2      2 × Intel Xeon E5-2698 40        │
    │ Site       any       ▾  ││ …                                                       │
    │ CPU        any       ▾  ││                                                         │
    │ Min cores / node  [32]  ││                                                         │
    ╰─────────────────────────╯╰─────────────────────────────────────────────────────────╯

/ on the sites opens it. The first time, every site's clusters and their
hardware load, a site at a time in parallel; each fills in the results
when it arrives. The screen is kept, with what it loaded and what is set,
for the next /; ctrl+r loads everything again.

Every change to the form updates the results. tab moves between the
fields and the results; enter on a result opens its detail; esc goes back.
The choices (sites, CPU makers, GPU models) are what was found.
"""

from __future__ import annotations

import asyncio

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Checkbox, DataTable, Footer, Header, Input, Label, Select, Static

from grid_tui.models import Hardware, Site
from grid_tui.models.search import (
    DISK_KINDS,
    Requirements,
    SearchEntry,
    cpu_choices,
    gpu_choices,
    results,
    site_choices,
)
from grid_tui.screens.base import Api
from grid_tui.screens.cluster import ClusterDetailScreen, gib, gpus, joined, nic

# The form's choices and numbers: (widget id, label).
CHOICES = [("site", "Site"), ("cpu", "CPU"), ("gpu", "GPU model"), ("disk", "Disk")]
NUMBERS = [
    ("min_nodes", "Min nodes"),
    ("min_cores", "Min cores / node"),
    ("min_memory_gib", "Min memory (GiB)"),
    ("min_gpu_memory_gib", "Min GPU memory (GiB)"),
    ("min_network_gbps", "Min network (Gbps)"),
]
COLUMNS = ("SITE", "CLUSTER", "NODES", "CPU", "CORES", "MEMORY", "GPU", "NETWORK", "WATTMETER")


class SearchScreen(Screen):
    """A form of requirements, and the clusters of every site that meet them."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+r", "reload", "Reload"),  # r is a letter: the fields take it
    ]

    DEFAULT_CSS = """
    SearchScreen #form {
        width: 38;
        border: round $accent;
        border-title-color: $text;
        padding: 0 1;
    }
    SearchScreen #form Label { margin-top: 1; color: $text-muted; }
    SearchScreen #form Checkbox { margin-top: 1; }
    SearchScreen #results {
        width: 1fr;
        border: round $accent;
        border-title-color: $text;
        border-subtitle-color: $text-muted;
    }
    SearchScreen #status { height: 1; padding: 0 1; color: $text-muted; }
    SearchScreen #status.error { color: $error; text-style: bold; }
    """

    def __init__(self, api: Api, sites: list[Site] | None = None) -> None:
        super().__init__()
        self.api = api
        self.sites = sites  # None: load them first
        self.entries: dict[str, list[SearchEntry]] = {}  # by site
        self.sites_total = 0
        self.sites_done = 0
        self.errors: list[str] = []
        self.matches: list[SearchEntry] = []
        self.choices: dict[str, list[str]] = {}  # what each Select offers now

    # The screen.

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with VerticalScroll(id="form") as form:
                form.border_title = "requirements"
                yield Checkbox("Has GPU", id="has_gpu")
                yield Checkbox("Wattmeter", id="wattmeter")
                for key, label in CHOICES:
                    yield Label(label)
                    options = [(d, d) for d in DISK_KINDS] if key == "disk" else []
                    yield Select(options, prompt="any", id=key)
                for key, label in NUMBERS:
                    yield Label(label)
                    yield Input(placeholder="any", type="integer", id=key)
            table: DataTable = DataTable(id="results", cursor_type="row", zebra_stripes=True)
            table.border_subtitle = "$ " + self.api.command("/sites/{site}/clusters") + " and …/{cluster}/nodes, every site"
            yield table
        yield Static("", id="status", markup=False)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#results", DataTable).add_columns(*COLUMNS)
        self.refresh_results()
        self.load()

    def action_reload(self) -> None:
        self.load()

    # Loading every site.

    @work(exclusive=True)  # a reload replaces a load still on its way
    async def load(self) -> None:
        """Load every site's clusters and hardware, a site at a time in
        parallel; each fills in the results when it arrives."""
        self.errors = []
        self.set_status("loading the sites…")
        try:
            sites = self.sites if self.sites else await self.api.sites()
        except Exception as e:
            self.set_status(f"error: {e}", error=True)
            return
        self.sites_total, self.sites_done = len(sites), 0
        self.refresh_results()
        for done in asyncio.as_completed([self.index_site(s.uid) for s in sites]):
            site, entries, error = await done
            if error:
                self.errors.append(f"{site}: {error}")
            else:
                self.entries[site] = entries
            self.sites_done += 1
            self.refresh_choices()
            self.refresh_results()
        if self.errors:
            self.set_status(f"{len(self.errors)} site(s) failed: " + "; ".join(self.errors), error=True)
        else:
            self.set_status("")

    async def index_site(self, site: str) -> tuple[str, list[SearchEntry], str]:
        """A site's clusters with their hardware, all at the same time. A
        cluster whose hardware failed is kept, marked failed."""
        try:
            clusters = await self.api.clusters(site)
        except Exception as e:
            return site, [], str(e)
        hardware = await asyncio.gather(
            *(self.api.hardware(site, c.uid) for c in clusters), return_exceptions=True
        )
        entries = [
            SearchEntry(site, c, None, failed=True) if isinstance(h, BaseException) else SearchEntry(site, c, h)
            for c, h in zip(clusters, hardware)
        ]
        return site, entries, ""

    @property
    def all_entries(self) -> list[SearchEntry]:
        return [e for es in self.entries.values() for e in es]

    # The form.

    def requirements(self) -> Requirements:
        """What the form asks for."""

        def choice(key: str) -> str | None:
            select = self.query_one(f"#{key}", Select)
            return None if select.is_blank() else str(select.value)

        def number(key: str) -> int:
            v = self.query_one(f"#{key}", Input).value.strip()
            return int(v) if v.lstrip("-").isdigit() and int(v) > 0 else 0

        return Requirements(
            has_gpu=self.query_one("#has_gpu", Checkbox).value,
            wattmeter=self.query_one("#wattmeter", Checkbox).value,
            **{key: choice(key) for key, _ in CHOICES},
            **{key: number(key) for key, _ in NUMBERS},
        )

    def on_checkbox_changed(self, _: Checkbox.Changed) -> None:
        self.refresh_results()

    def on_select_changed(self, _: Select.Changed) -> None:
        self.refresh_results()

    def on_input_changed(self, _: Input.Changed) -> None:
        self.refresh_results()

    def refresh_choices(self) -> None:
        """The choices found so far, keeping what is chosen."""
        found = {"site": site_choices(self.all_entries), "cpu": cpu_choices(self.all_entries),
                 "gpu": gpu_choices(self.all_entries)}
        for key, choices in found.items():
            if self.choices.get(key) == choices:
                continue  # the same as now: leave the Select alone
            select = self.query_one(f"#{key}", Select)
            current = None if select.is_blank() else select.value
            select.set_options([(c, c) for c in choices])
            self.choices[key] = choices
            if current in choices:
                select.value = current  # keep what was chosen

    # The results.

    def refresh_results(self) -> None:
        """Show the clusters that meet the form, keeping the cursor's row."""
        table = self.query_one("#results", DataTable)
        row = table.cursor_row
        self.matches = results(self.all_entries, self.requirements())
        table.clear()
        for e in self.matches:
            table.add_row(e.site, e.cluster.uid, *hardware_cells(e), key=f"{e.site}/{e.cluster.uid}")
        title = f"matches: {len(self.matches)} of {len(self.all_entries)}"
        if self.sites_done < self.sites_total:
            title += f" · loading sites {self.sites_done}/{self.sites_total}"
        table.border_title = title
        if self.matches:
            table.move_cursor(row=min(row, len(self.matches) - 1))

    def on_data_table_row_selected(self, _: DataTable.RowSelected) -> None:
        """enter (or a click) on a result opens its detail."""
        table = self.query_one("#results", DataTable)
        if self.matches and 0 <= table.cursor_row < len(self.matches):
            e = self.matches[table.cursor_row]
            self.app.push_screen(ClusterDetailScreen(self.api, Site(e.site), e.cluster))

    def set_status(self, text: str, *, error: bool = False) -> None:
        status = self.query_one("#status", Static)
        status.update(text)
        status.set_class(error, "error")


def hardware_cells(e: SearchEntry) -> tuple[str, ...]:
    """A result's NODES … WATTMETER cells: "…" while its hardware loads, "?"
    if it failed."""
    watt = "yes" if e.cluster.wattmeter else "no"
    hw: Hardware | None = e.hardware
    if hw is None:
        mark = "?" if e.failed else "…"
        return (mark,) * 6 + (watt,)
    name = f"{hw.sockets} × {hw.cpu}" if hw.cpu and hw.sockets > 0 else hw.cpu or "-"
    return (
        str(hw.nodes) if hw.nodes else "-",
        name,
        str(hw.cores) if hw.cores else "-",
        gib(hw.memory) or "-",
        gpus(hw.gpus),
        joined(nic(n) for n in hw.nics),
        watt,
    )

