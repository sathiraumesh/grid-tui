"""Tests for the Search panel: the form, the results, and choosing one."""

from textual.app import App
from textual.widgets import Checkbox, DataTable, Input, Label, Select

from grid_tui.panels.search import SearchPanel
from grid_tui.panels.search.search import COLUMNS, HINT
from grid_tui.requirements import ANY_GPU, Requirements
from tests.grid5000.fakes import CLUSTERS, NODES, SITES, fake_client, g5k_client
from tests.panels.helpers import rows, settle


class SearchApp(App):
    """A tiny app that shows only the SearchPanel, and keeps the clusters chosen."""

    def __init__(self, client) -> None:
        """Make the app.

        Args:
            client: What the panel loads from.
        """
        super().__init__()
        self.client = client
        self.chosen: list[tuple[str, str]] = []

    def compose(self):
        """The only widget: the Search panel."""
        yield SearchPanel(self.client)

    def on_search_panel_chosen(self, message: SearchPanel.Chosen) -> None:
        """Keep each cluster the panel says was chosen."""
        self.chosen.append((message.site, message.cluster))


def panel(app: App) -> SearchPanel:
    """The Search panel."""
    return app.query_one(SearchPanel)


def found(app: App) -> list[tuple[str, str]]:
    """The (site, cluster) of every result, top to bottom."""
    return [(row[0], row[1]) for row in rows(panel(app).query_one(DataTable))]


def status(app: App) -> str:
    """The line between the form and the results."""
    return str(app.query_one('#search-status', Label).render())


async def search_with(app: App, pilot, **boxes) -> None:
    """Fill the form (cores, ram, gpu, disk, wattmeter, site) and search.

    gpu, disk and site: a value to pick, or None for the dropdown's blank.
    """
    if 'cores' in boxes:
        app.query_one('#min-cores', Input).value = str(boxes['cores'])
    if 'ram' in boxes:
        app.query_one('#min-ram', Input).value = str(boxes['ram'])
    if 'wattmeter' in boxes:
        app.query_one('#need-wattmeter', Checkbox).value = boxes['wattmeter']
    for box, select_id in (
        ('gpu', '#need-gpu'),
        ('disk', '#need-disk'),
        ('site', '#search-site'),
    ):
        if box in boxes:
            select = app.query_one(select_id, Select)
            if boxes[box] is None:
                select.clear()
            else:
                select.value = boxes[box]
    panel(app).run_search()
    await settle(app, pilot)


# Before searching


async def test_starts_with_a_hint_and_no_results():
    """Before a search, the table is empty and the status says what to do."""
    app = SearchApp(g5k_client())
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        assert found(app) == []
        assert status(app) == HINT


async def test_has_the_columns():
    """The results have a cluster's name and its hardware."""
    app = SearchApp(g5k_client())
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        columns = panel(app).query_one(DataTable).columns.values()
        assert [str(c.label) for c in columns] == list(COLUMNS)


async def test_an_empty_form_asks_for_nothing():
    """Empty boxes and no ticks mean no needs."""
    app = SearchApp(g5k_client())
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        assert panel(app).requirements() == Requirements()


async def test_the_form_reads_every_need():
    """The boxes, ticks and site become the Requirements."""
    app = SearchApp(g5k_client())
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        app.query_one('#min-cores', Input).value = '16'
        app.query_one('#min-ram', Input).value = '64.5'
        app.query_one('#need-gpu', Select).value = 'Tesla V100'
        app.query_one('#need-disk', Select).value = 'NVMe'
        app.query_one('#need-wattmeter', Checkbox).value = True
        app.query_one('#search-site', Select).value = 'lyon'
        assert panel(app).requirements() == Requirements(
            min_cores=16,
            min_ram_gib=64.5,
            gpu='Tesla V100',
            disk='NVMe',
            wattmeter=True,
            site='lyon',
        )


# Searching


async def test_no_needs_finds_every_cluster_with_nodes():
    """With no needs, every cluster that has nodes is found, by site."""
    app = SearchApp(g5k_client())
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        await search_with(app, pilot)
        assert found(app) == [('lyon', 'nova'), ('nancy', 'grisou'), ('nancy', 'gros')]
        assert status(app) == '3 cluster(s), 4 node(s) match.'


async def test_min_cores_and_ram():
    """Cores and RAM leave out the clusters with no big enough node."""
    app = SearchApp(g5k_client())
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        await search_with(app, pilot, cores=17, ram=100)
        assert found(app) == [('lyon', 'nova')]  # grisou: 16 cores; gros: 96 GiB


async def test_gpu_disk_and_wattmeter():
    """Each need finds the clusters with that hardware."""
    app = SearchApp(g5k_client())
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        await search_with(app, pilot, gpu=ANY_GPU)
        assert found(app) == [('lyon', 'nova')]
        await search_with(app, pilot, gpu=None, disk='SSD')
        assert found(app) == [('nancy', 'grisou')]
        await search_with(app, pilot, disk=None, wattmeter=True)
        # nova: its monitoring; gros: its cluster's wattmetre metric for gros-1
        assert found(app) == [('lyon', 'nova'), ('nancy', 'gros')]


async def test_a_result_row_counts_the_good_nodes():
    """The Nodes cell is good nodes / all nodes, and the hardware is shown."""
    app = SearchApp(g5k_client())
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        await search_with(app, pilot, wattmeter=True, site='nancy')
        [row] = rows(panel(app).query_one(DataTable))
        assert row[:3] == ['nancy', 'gros', '1/2']  # gros-1 only
        assert row[3:6] == ['Intel Xeon Gold 5220', '18', '96 GiB']
        assert row[-1] == 'yes'


async def test_by_site():
    """With a site, only its clusters are found."""
    app = SearchApp(g5k_client())
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        await search_with(app, pilot, site='nancy')
        assert found(app) == [('nancy', 'grisou'), ('nancy', 'gros')]


async def test_no_match_says_so():
    """When nothing matches, the table is empty and the status says so."""
    app = SearchApp(g5k_client())
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        await search_with(app, pilot, cores=1000)
        assert found(app) == []
        assert status(app) == 'No cluster has a node that meets all of that.'


async def test_enter_in_a_box_searches():
    """Enter in a box runs the search."""
    app = SearchApp(g5k_client())
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        app.query_one('#min-cores', Input).focus()
        await pilot.press('3', '0', 'enter')
        await settle(app, pilot)
        assert found(app) == [('lyon', 'nova')]


async def test_the_nodes_are_loaded_once():
    """The second search uses what the first one loaded."""
    app = SearchApp(g5k_client())
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        await search_with(app, pilot)
        loaded = panel(app).found
        await search_with(app, pilot, gpu=ANY_GPU)
        assert panel(app).found is loaded


async def test_load_forgets_and_searches_again():
    """load() (the r key) loads everything again and re-runs the last search."""
    app = SearchApp(g5k_client())
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        await search_with(app, pilot, gpu=ANY_GPU)
        loaded = panel(app).found
        panel(app).load()
        await settle(app, pilot)
        assert panel(app).found is not loaded
        assert found(app) == [('lyon', 'nova')]


async def test_an_error_shows_a_notification():
    """If the clusters can't be loaded, a red toast says so."""
    app = SearchApp(g5k_client(status=401))
    async with app.run_test(size=(120, 30), notifications=True) as pilot:
        await settle(app, pilot)
        await search_with(app, pilot)
        assert found(app) == []
        assert [n.severity for n in app._notifications] == ['error']
        assert 'r to try again' in status(app)


async def test_a_cluster_whose_nodes_fail_is_left_out_with_a_warning():
    """A cluster with no nodes answer is skipped; the others are still found."""
    nodes = {key: value for key, value in NODES.items() if key != ('nancy', 'grisou')}
    app = SearchApp(fake_client(SITES, CLUSTERS, nodes=nodes))  # grisou: a 404
    async with app.run_test(size=(120, 30), notifications=True) as pilot:
        await settle(app, pilot)
        await search_with(app, pilot)
        assert found(app) == [('lyon', 'nova'), ('nancy', 'gros')]
        [note] = app._notifications
        assert note.severity == 'warning'
        assert '1 cluster' in note.message


# Choosing a result


async def test_enter_on_a_result_sends_chosen():
    """Enter on a result sends Chosen with its site and cluster."""
    app = SearchApp(g5k_client())
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        await search_with(app, pilot)
        panel(app).query_one(DataTable).focus()
        await pilot.press('down', 'enter')  # the second result: nancy / grisou
        await pilot.pause()
        assert app.chosen == [('nancy', 'grisou')]


# How the form looks


async def test_a_clicked_checkbox_stays_one_row_and_shows_its_x():
    """Clicking a tick box ticks it, and focus doesn't make it 2 rows tall."""
    app = SearchApp(g5k_client())
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        await pilot.click('#need-wattmeter')
        await pilot.pause()
        box = app.query_one('#need-wattmeter', Checkbox)
        assert box.value is True
        assert box.has_focus
        assert box.region.height == 1  # Textual's focus border would make it 2
        cells = [segment.text for segment in box.render_line(0)]
        assert cells[:3] == ['▐', 'X', '▌']  # the box is drawn, not cut off


# Choosing a GPU model and a disk type


async def test_the_gpu_list_has_the_models_found():
    """Once the nodes are loaded, the GPU list has 'Any GPU' and each model."""
    app = SearchApp(g5k_client())
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        select = app.query_one('#need-gpu', Select)
        select.value = 'Tesla V100'  # only possible if it is in the list
        assert select.selection == 'Tesla V100'
        select.value = ANY_GPU
        assert select.selection == ANY_GPU


async def test_a_gpu_model_finds_only_its_clusters():
    """Picking a GPU model finds the clusters with that model."""
    nodes = {
        **NODES,
        ('nancy', 'grisou'): [
            {'uid': 'grisou-1', 'gpu_devices': [{'model': 'A100'}]},
        ],
    }
    app = SearchApp(fake_client(SITES, CLUSTERS, nodes=nodes))
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        await search_with(app, pilot, gpu='A100')
        assert found(app) == [('nancy', 'grisou')]
        await search_with(app, pilot, gpu='Tesla V100')
        assert found(app) == [('lyon', 'nova')]
        await search_with(app, pilot, gpu=ANY_GPU)
        assert found(app) == [('lyon', 'nova'), ('nancy', 'grisou')]


async def test_the_disk_list_has_every_type():
    """The disk list offers SSD, HDD and NVMe."""
    app = SearchApp(g5k_client())
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        select = app.query_one('#need-disk', Select)
        for kind in ('SSD', 'HDD', 'NVMe'):
            select.value = kind
            assert select.selection == kind


async def test_a_gpu_picked_is_kept_when_the_list_is_refilled():
    """Loading again (r) keeps the GPU model that was picked."""
    app = SearchApp(g5k_client())
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        await search_with(app, pilot, gpu='Tesla V100')
        panel(app).load()
        await settle(app, pilot)
        assert app.query_one('#need-gpu', Select).selection == 'Tesla V100'
        assert found(app) == [('lyon', 'nova')]


# Loading ahead


async def test_the_nodes_load_as_soon_as_the_panel_shows():
    """Showing the panel starts loading the nodes, before any search."""
    app = SearchApp(g5k_client())
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        assert panel(app).found is not None
        assert found(app) == []  # loaded, but nothing searched yet
