"""The main screen: the app's panels as tabs across the top.

     1 Sites   2 Clusters   3 Nodes   4 Reservations   7 Search
                                      └ 4 Current   5 Reserve   6 My reservations

Picking moves down the tabs: a site (enter) shows its clusters, a cluster
its nodes, a node the cluster's current reservations; esc goes back up.
Search's and Reserve's results, and My reservations, jump into the same
tabs. 1-7 go to a tab (the form fields take digits, so typing in them
doesn't); a tab can also be clicked.

A splash screen shows over it until the sites have loaded. A panel that
loads every site (Search, Reserve, My reservations) does so the first time
its tab is shown; a loading animation covers what is loading.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, TabbedContent, TabPane

from grid_tui.api import Api
from grid_tui.panels import (
    ClustersPanel,
    JobsPanel,
    NodesPanel,
    ReservationsPanel,
    ReservePanel,
    SearchPanel,
    SitesPanel,
)
from grid_tui.panels.messages import ClusterChosen, NodeChosen, SiteChosen, SitesLoaded
from grid_tui.screens.splash import SplashScreen

# The tabs inside Reservations.
RESERVATION_TABS = ("current", "reserving", "mine")


class MainScreen(Screen):
    BINDINGS = [
        Binding("1", "tab('sites')", "Sites"),
        Binding("2", "tab('clusters')", "Clusters"),
        Binding("3", "tab('nodes')", "Nodes"),
        Binding("4", "tab('current')", "Reservations"),
        Binding("5", "tab('reserving')", "Reserve"),
        Binding("6", "tab('mine')", "Mine"),
        Binding("7", "tab('search')", "Search"),
        Binding("escape", "back", "Back", show=False),
        Binding("q", "app.quit", "Quit"),
    ]

    DEFAULT_CSS = """
    MainScreen TabPane { padding: 0; }
    MainScreen #reservations TabbedContent ContentSwitcher { height: 1fr; }
    """

    def __init__(self, api: Api) -> None:
        super().__init__()
        self.api = api

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(id="tabs", initial="sites"):
            with TabPane("1 Sites", id="sites"):
                yield SitesPanel(self.api)
            with TabPane("2 Clusters", id="clusters"):
                yield ClustersPanel(self.api)
            with TabPane("3 Nodes", id="nodes"):
                yield NodesPanel(self.api)
            with TabPane("4 Reservations", id="reservations"):
                with TabbedContent(id="reservation-tabs", initial="current"):
                    with TabPane("4 Current", id="current"):
                        yield ReservationsPanel(self.api)
                    with TabPane("5 Reserve", id="reserving"):
                        yield ReservePanel(self.api)
                    with TabPane("6 My reservations", id="mine"):
                        yield JobsPanel(self.api)
            with TabPane("7 Search", id="search"):
                yield SearchPanel(self.api)
        yield Footer()

    def on_mount(self) -> None:
        self.splash: SplashScreen | None = SplashScreen()
        self.app.push_screen(self.splash)  # until the sites have loaded
        self.call_after_refresh(self.focus_panel, "sites")

    def on_sites_loaded(self, _: SitesLoaded) -> None:
        """The sites are there (or failed, to say why): the splash goes."""
        splash, self.splash = self.splash, None
        if splash is not None and self.app.screen is splash:
            self.app.pop_screen()

    # The panels.

    @property
    def sites(self) -> SitesPanel:
        return self.query_one(SitesPanel)

    @property
    def clusters(self) -> ClustersPanel:
        return self.query_one(ClustersPanel)

    @property
    def nodes(self) -> NodesPanel:
        return self.query_one(NodesPanel)

    @property
    def current(self) -> ReservationsPanel:
        return self.query_one(ReservationsPanel)

    @property
    def reserve(self) -> ReservePanel:
        return self.query_one(ReservePanel)

    @property
    def mine(self) -> JobsPanel:
        return self.query_one(JobsPanel)

    @property
    def search(self) -> SearchPanel:
        return self.query_one(SearchPanel)

    @property
    def active(self) -> str:
        """The tab shown: one of the top ones, or one inside Reservations."""
        top = self.query_one("#tabs", TabbedContent).active
        if top == "reservations":
            return self.query_one("#reservation-tabs", TabbedContent).active
        return top

    # Moving between the tabs.

    def action_tab(self, name: str) -> None:
        if name in RESERVATION_TABS:
            self.query_one("#tabs", TabbedContent).active = "reservations"
            self.query_one("#reservation-tabs", TabbedContent).active = name
        else:
            self.query_one("#tabs", TabbedContent).active = name
        self.focus_panel(name)

    def focus_panel(self, name: str) -> None:
        """Start a panel's loading the first time, and put the focus in it."""
        panel = {
            "sites": self.sites, "clusters": self.clusters, "nodes": self.nodes, "current": self.current,
            "reserving": self.reserve, "mine": self.mine, "search": self.search,
        }[name]
        if hasattr(panel, "activate"):
            panel.activate()
        if name == "current" and self.current.cluster is None:
            self.current_from_context()
        if name == "current":
            self.current.view.focus()
        elif name == "nodes":
            self.nodes.query_one("#nodes", DataTable).focus()
        else:
            panel.query(DataTable).first().focus()

    def current_from_context(self) -> None:
        """Current opened with nothing chosen for it: the Gantt chart of the
        cluster in Nodes (with its nodes), else of the one under the cursor
        in Clusters (it loads)."""
        nodes, clusters = self.nodes, self.clusters
        if nodes.site is not None and nodes.cluster is not None:
            row = nodes.query_one("#nodes", DataTable).cursor_row
            self.current.show_cluster(nodes.site, nodes.cluster, nodes.nodes or None, max(row, 0))
        elif clusters.site is not None and clusters.selected is not None:
            self.current.show_cluster(clusters.site, clusters.selected)

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        """A tab clicked (or opened): its panel, as action_tab would.

        The tabs inside Reservations say so too when they are made, while
        another tab is shown: then they are let be (focusing in a hidden tab
        would show it)."""
        if event.tabbed_content.id == "reservation-tabs" and self.query_one("#tabs", TabbedContent).active != "reservations":
            return
        name = event.pane.id or ""
        if name == "reservations":
            name = self.query_one("#reservation-tabs", TabbedContent).active or "current"
        if name in ("sites", "clusters", "nodes", "search", *RESERVATION_TABS):
            self.focus_panel(name)

    def action_back(self) -> None:
        """esc: up the tabs, Reservations → Nodes → Clusters → Sites."""
        back = {"clusters": "sites", "nodes": "clusters", "current": "nodes"}.get(self.active)
        if back == "nodes" and self.nodes.cluster is None:
            back = "clusters"  # the reservations came straight from Clusters
        if back:
            self.action_tab(back)

    # What the panels tell.

    def on_site_chosen(self, m: SiteChosen) -> None:
        self.clusters.show_site(m.site)
        self.action_tab("clusters")

    def on_cluster_chosen(self, m: ClusterChosen) -> None:
        if m.reservations:
            self.current.show_cluster(m.site, m.cluster)
            self.action_tab("current")
        else:
            self.nodes.show_cluster(m.site, m.cluster)
            self.action_tab("nodes")

    def on_node_chosen(self, m: NodeChosen) -> None:
        self.current.show_cluster(m.site, m.cluster, m.nodes, m.node)
        self.action_tab("current")
