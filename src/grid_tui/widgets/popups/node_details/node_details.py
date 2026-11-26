"""A pop-up with every detail of one node, grouped into sections.

It opens over the app (it isn't a tab) and Esc closes it. Details the API
didn't give are left out, and so is a section with nothing in it.
"""

from rich.table import Table
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Label, Static

from grid_tui.format import duration, interval, number, size, yes_no
from grid_tui.models import MetricInfo, Node

Section = tuple[str, list[tuple[str, str]]]  # a title, and (label, value) rows


def _rows(*pairs: tuple[str, str]) -> list[tuple[str, str]]:
    """The (label, value) pairs that have a value."""
    return [(label, value) for label, value in pairs if value]


def metric_text(metric: MetricInfo) -> str:
    """What a metric is and how often it is recorded, in one line.

    e.g. 'Power from the wattmeter · every 1 s (20 ms on request)'.
    """
    every = ''
    if metric.period:
        every = f'every {interval(metric.period)}'
        if metric.optional_period:
            every += f' ({interval(metric.optional_period)} on request)'
    return ' · '.join(part for part in (metric.description, every) if part) or '—'


def sections(node: Node, metrics: tuple[MetricInfo, ...] = ()) -> list[Section]:
    """Every detail of node, as titled sections of (label, value) rows.

    Args:
        node: The node to describe.
        metrics: What the node can measure (its cluster's metrics for it).

    Rows with no value are left out, and so is a section with no rows.
    """
    cpu, arch, os = node.processor, node.architecture, node.operating_system
    jobs, bios, chassis = node.supported_job_types, node.bios, node.chassis
    perf, monitoring = node.performance, node.monitoring

    found: list[Section] = [
        (
            'Node',
            _rows(
                ('Name', node.uid),
                ('Cluster', node.cluster_name),
                ('Exotic', yes_no(node.exotic) if node.exotic else ''),
            ),
        ),
        (
            'Processor',
            _rows(
                ('Model', cpu.name),
                ('Vendor', cpu.vendor),
                ('Version', cpu.version),
                ('Clock', f'{cpu.ghz:g} GHz' if cpu.clock_speed else ''),
                ('Sockets', number(arch.nb_procs)),
                ('Cores', number(arch.nb_cores)),
                ('Threads', number(arch.nb_threads)),
                ('Platform', arch.platform_type),
                ('Instruction set', cpu.instruction_set),
                ('Hyper-threading', yes_no(cpu.ht_capable) if cpu.ht_capable else ''),
                ('Microcode', cpu.microcode),
                ('L1 data cache', size(cpu.cache_l1d)),
                ('L1 instruction cache', size(cpu.cache_l1i)),
                ('L2 cache', size(cpu.cache_l2)),
                ('L3 cache', size(cpu.cache_l3)),
            ),
        ),
        (
            'Memory',
            _rows(('RAM', size(node.ram_gib * 1024**3)))
            + [
                (module.name or 'Module', size(module.size))
                for module in node.memory_devices
            ],
        ),
        (
            'Disks',
            [
                (
                    disk.device or f'Disk {i}',
                    ' · '.join(
                        part
                        for part in (
                            size(disk.size),
                            disk.storage,
                            disk.interface,
                            disk.model,
                        )
                        if part
                    ),
                )
                for i, disk in enumerate(node.storage_devices, 1)
            ],
        ),
        (
            'Network',
            [
                (
                    card.device or f'Card {i}',
                    ' · '.join(
                        part
                        for part in (
                            card.interface,
                            f'{card.gbps:g} Gb/s' if card.rate else '',
                            'connected' if card.mounted else 'not connected',
                            card.mac,
                            'KaVLAN' if card.kavlan else '',
                            ' '.join(p for p in (card.switch, card.switch_port) if p),
                        )
                        if part
                    ),
                )
                for i, card in enumerate(node.network_adapters, 1)
            ],
        ),
        (
            'GPUs',
            [
                (
                    f'GPU {i}',
                    ' · '.join(
                        part
                        for part in (gpu.vendor, gpu.model, size(gpu.memory))
                        if part
                    ),
                )
                for i, gpu in enumerate(node.gpu_devices)
            ],
        ),
        (
            'Performance',
            _rows(
                ('One core', f'{perf.core_gflops:g} GFLOPS' if perf.core_flops else ''),
                (
                    'Whole node',
                    f'{perf.node_gflops:g} GFLOPS' if perf.node_flops else '',
                ),
            ),
        ),
        (
            'Jobs',
            _rows(
                ('Deploy your own system', yes_no(jobs.deploy)),
                ('Best-effort jobs', yes_no(jobs.besteffort)),
                ('Virtualisation', jobs.virtual or 'no'),
                ('Longest job', duration(jobs.max_walltime) or 'no limit'),
                ('Queues', ', '.join(jobs.queues)),
            ),
        ),
        (
            'System settings',
            _rows(
                ('Hyper-threading on', yes_no(os.ht_enabled)),
                ('Turbo boost on', yes_no(os.turboboost_enabled)),
                ('CPU speed driver', os.pstate_driver),
                ('CPU speed governor', os.pstate_governor),
                ('CPU sleep driver', os.cstate_driver),
                ('Deepest sleep state', number(os.cstate_max_id)),
            ),
        ),
        (
            'Monitoring',
            _rows(
                ('Wattmeter', monitoring.wattmeter or 'no'),
                ('Power metric', monitoring.metric),
            ),
        ),
        (
            'Metrics',
            [(metric.name, metric_text(metric)) for metric in metrics],
        ),
        (
            'Power',
            [
                (pdu.uid or 'PDU', f'port {pdu.port}' if pdu.port else '')
                for pdu in node.pdu
            ],
        ),
        (
            'BIOS',
            _rows(
                ('Vendor', bios.vendor),
                ('Version', bios.version),
                ('Released', bios.release_date),
            ),
        ),
        (
            'Machine',
            _rows(
                ('Make', chassis.manufacturer),
                ('Model', chassis.name),
                ('Serial', chassis.serial),
            ),
        ),
    ]
    return [(title, rows) for title, rows in found if rows]


def _grid(rows: list[tuple[str, str]]) -> Table:
    """The rows of a section as two aligned columns: label, then value."""
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style='#a6adc8', no_wrap=True)  # the labels: grey
    grid.add_column(style='#cdd6f4')  # the values
    for label, value in rows:
        grid.add_row(label, value)
    return grid


class NodeDetails(ModalScreen):
    """A pop-up over the app with every detail of one node. Esc closes it."""

    CSS_PATH = 'node_details.tcss'  # next to this file
    BINDINGS = [
        Binding('escape', 'dismiss', 'Close'),
        Binding('q', 'dismiss', 'Close', show=False),  # not quit, while it is open
    ]

    def __init__(self, node: Node, metrics: tuple[MetricInfo, ...] = ()) -> None:
        """Make the pop-up.

        Args:
            node: The node to show.
            metrics: What the node can measure, for the Metrics section.
        """
        super().__init__()
        self.node = node
        self.metrics = metrics

    def compose(self) -> ComposeResult:
        """A framed box: a scrolling list of sections, each a title and its rows."""
        with Vertical(id='details'):
            with VerticalScroll(id='details-body'):
                for title, rows in sections(self.node, self.metrics):
                    yield Label(title, classes='section-title')
                    yield Static(_grid(rows), classes='section')

    def on_mount(self) -> None:
        """Name the node in the frame, and say how to close it."""
        box = self.query_one('#details')
        box.border_title = self.node.uid
        box.border_subtitle = 'Esc to close'
        self.query_one('#details-body').focus()  # so ↑ ↓ scroll at once
