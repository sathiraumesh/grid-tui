"""A node of a Grid'5000 cluster, and its hardware.

As GET /sites/{site}/clusters/{cluster}/nodes lists it. Sizes are in bytes,
speeds in hertz and rates in bits per second, as the API gives them.
"""

from typing import Any

from pydantic import BaseModel, field_validator

from grid_tui.models.base import ApiModel
from grid_tui.models.cluster import Link

GIB = 1024**3  # bytes in a gibibyte
GHZ = 10**9  # hertz in a gigahertz
GBPS = 10**9  # bits per second in a gigabit per second
GFLOPS = 10**9  # floating-point operations per second in a gigaflops


def _yes_or_text(value: Any) -> Any:
    """A yes/no-or-text answer as text: True → 'yes', False or null → ''.

    Used where the API gives either a flag or a word, e.g. a wattmeter that is
    true, false or 'shared'.
    """
    if value is True:
        return 'yes'
    if value is False or value is None:
        return ''
    return value


class Architecture(ApiModel):
    """How many CPUs, cores and threads a node has."""

    nb_procs: int = 0  # CPU sockets, e.g. 2
    nb_cores: int = 0  # cores in all, e.g. 36
    nb_threads: int = 0  # threads in all, e.g. 72
    platform_type: str = ''  # e.g. 'x86_64'


class Processor(ApiModel):
    """A node's CPU model."""

    vendor: str = ''  # e.g. 'Intel'
    model: str = ''  # e.g. 'Intel Xeon'
    other_description: str = ''  # the full name, e.g. 'Intel Xeon Gold 5220'
    version: str = ''  # e.g. 'Gold 5220'
    clock_speed: int = 0  # in hertz, e.g. 2_200_000_000
    instruction_set: str = ''  # e.g. 'x86-64'
    microcode: str = ''  # the CPU's firmware version, e.g. '0x5003006'
    ht_capable: bool = False  # can it do hyper-threading
    cache_l1d: int = 0  # level 1 data cache, in bytes
    cache_l1i: int = 0  # level 1 instruction cache, in bytes
    cache_l2: int = 0  # level 2 cache, in bytes
    cache_l3: int = 0  # level 3 cache, in bytes

    @property
    def name(self) -> str:
        """The fullest name the API gives, e.g. 'Intel Xeon Gold 5220'."""
        return self.other_description or self.model

    @property
    def ghz(self) -> float:
        """The clock speed in GHz, e.g. 2.2."""
        return self.clock_speed / GHZ


class Memory(ApiModel):
    """A node's RAM."""

    ram_size: int = 0  # in bytes, e.g. 103_079_215_104

    @property
    def gib(self) -> float:
        """The RAM in GiB, e.g. 96.0."""
        return self.ram_size / GIB


class StorageDevice(ApiModel):
    """One disk of a node."""

    device: str = ''  # e.g. 'sda'
    storage: str = ''  # 'SSD' or 'HDD'
    interface: str = ''  # e.g. 'SATA' or 'NVMe'
    model: str = ''  # e.g. 'SAMSUNG MZ7KM480'
    size: int = 0  # in bytes

    @property
    def gib(self) -> float:
        """The size in GiB."""
        return self.size / GIB


class NetworkAdapter(ApiModel):
    """One network card of a node."""

    device: str = ''  # e.g. 'eth0'
    interface: str = ''  # e.g. 'Ethernet' or 'InfiniBand'
    rate: int = 0  # in bits per second, e.g. 25_000_000_000
    mounted: bool = False  # is it connected
    mac: str = ''  # e.g. '0c:42:a1:00:00:01'
    kavlan: bool = False  # can it be put in its own network (KaVLAN)
    switch: str = ''  # the switch it is plugged into, e.g. 'gw-nancy'
    switch_port: str = ''  # the port on that switch, e.g. 'Ethernet1/12'

    @property
    def gbps(self) -> float:
        """The rate in Gbit/s, e.g. 25.0."""
        return self.rate / GBPS


class Gpu(ApiModel):
    """One GPU of a node."""

    vendor: str = ''  # e.g. 'Nvidia'
    model: str = ''  # e.g. 'Tesla V100-PCIE-32GB'
    memory: int = 0  # in bytes

    @property
    def gib(self) -> float:
        """The GPU's memory in GiB."""
        return self.memory / GIB


class MemoryDevice(ApiModel):
    """One RAM module of a node."""

    name: str = ''  # e.g. 'dimm_a0'
    size: int = 0  # in bytes

    @property
    def gib(self) -> float:
        """The size in GiB."""
        return self.size / GIB


class Bios(ApiModel):
    """A node's BIOS."""

    vendor: str = ''  # e.g. 'Dell Inc.'
    version: str = ''  # e.g. '2.12.2'
    release_date: str = ''  # e.g. '07/09/2021'


class Chassis(ApiModel):
    """The machine itself."""

    manufacturer: str = ''  # e.g. 'Dell Inc.'
    name: str = ''  # e.g. 'PowerEdge R640'
    serial: str = ''  # its serial number


class OperatingSystem(ApiModel):
    """The CPU settings of a node's default system."""

    ht_enabled: bool = False  # hyper-threading on
    turboboost_enabled: bool = False  # turbo boost on
    pstate_driver: str = ''  # how the CPU speed is set, e.g. 'intel_pstate'
    pstate_governor: str = ''  # e.g. 'performance'
    cstate_driver: str = ''  # how the CPU sleeps, e.g. 'intel_idle'
    cstate_max_id: int = 0  # its deepest sleep state


class Performance(ApiModel):
    """How fast a node computed in a benchmark."""

    core_flops: int = 0  # one core, in operations per second
    node_flops: int = 0  # the whole node, in operations per second

    @property
    def core_gflops(self) -> float:
        """One core's speed in GFLOPS."""
        return self.core_flops / GFLOPS

    @property
    def node_gflops(self) -> float:
        """The whole node's speed in GFLOPS."""
        return self.node_flops / GFLOPS


class JobTypes(ApiModel):
    """The kinds of jobs a node takes."""

    deploy: bool = False  # can you install your own system on it (kadeploy)
    besteffort: bool = False  # can it run best-effort jobs
    virtual: str = ''  # its virtualisation support, e.g. 'ivt'; '' for none
    max_walltime: int = 0  # the longest job, in seconds; 0 for no limit
    queues: tuple[str, ...] = ()  # e.g. ('default', 'admin')

    @field_validator('virtual', mode='before')
    @classmethod
    def _virtual_as_text(cls, value: Any) -> Any:
        """virtual is false or a word like 'ivt': read it as text."""
        return _yes_or_text(value)


class Monitoring(ApiModel):
    """What measures a node."""

    wattmeter: str = ''  # 'yes', 'shared', 'multiple'…; '' for none
    metric: str = ''  # the power metric to ask for, e.g. 'power'

    @field_validator('wattmeter', mode='before')
    @classmethod
    def _wattmeter_as_text(cls, value: Any) -> Any:
        """wattmeter is true, false or a word: read it as text."""
        return _yes_or_text(value)

    @property
    def has_wattmeter(self) -> bool:
        """Does a power meter measure this node (alone or shared)."""
        return bool(self.wattmeter)


class PduPort(ApiModel):
    """A power strip (PDU) a node is plugged into, and the port."""

    uid: str = ''  # e.g. 'grimoire-pdu1'
    port: str = ''  # e.g. '12'


class Node(ApiModel):
    """One node of a cluster, with its hardware."""

    uid: str  # e.g. 'gros-12': its name on the site
    cluster: str = ''  # e.g. 'gros'
    nodeset: str = ''  # the cluster, as some answers name it
    exotic: bool = False  # unusual hardware: must be asked for by name
    architecture: Architecture = Architecture()
    processor: Processor = Processor()
    main_memory: Memory = Memory()
    memory_devices: tuple[MemoryDevice, ...] = ()
    storage_devices: tuple[StorageDevice, ...] = ()
    network_adapters: tuple[NetworkAdapter, ...] = ()
    gpu_devices: tuple[Gpu, ...] = ()
    bios: Bios = Bios()
    chassis: Chassis = Chassis()
    operating_system: OperatingSystem = OperatingSystem()
    performance: Performance = Performance()
    supported_job_types: JobTypes = JobTypes()
    monitoring: Monitoring = Monitoring()
    pdu: tuple[PduPort, ...] = ()
    links: tuple[Link, ...] = ()

    @field_validator(
        'architecture',
        'processor',
        'main_memory',
        'bios',
        'chassis',
        'operating_system',
        'performance',
        'supported_job_types',
        'monitoring',
        mode='before',
    )
    @classmethod
    def _a_part_is_an_object(cls, value: Any) -> Any:
        """A part that isn't an object (e.g. 'n/a') is read as empty.

        A part given ready-made, e.g. bios=Bios(...), is kept as it is.
        """
        return value if isinstance(value, (dict, BaseModel)) else {}

    @field_validator(
        'storage_devices', 'network_adapters', 'pdu', 'links', mode='before'
    )
    @classmethod
    def _only_dicts(cls, value: Any) -> Any:
        """Keep only the entries that are objects; a broken entry is skipped."""
        if not isinstance(value, list):
            return ()
        return tuple(item for item in value if isinstance(item, dict))

    @field_validator('gpu_devices', mode='before')
    @classmethod
    def _gpus_in_order(cls, value: Any) -> Any:
        """The API gives GPUs as {'0': {...}, '1': {...}}: keep them in key order.

        A plain list of GPUs is read as it is.
        """
        if isinstance(value, dict):
            value = [value[key] for key in sorted(value)]
        if not isinstance(value, list):
            return ()
        return tuple(item for item in value if isinstance(item, dict))

    @field_validator('memory_devices', mode='before')
    @classmethod
    def _memory_devices_by_name(cls, value: Any) -> Any:
        """The API gives RAM modules as {'dimm_a0': {'size': ...}, ...}.

        Each becomes a MemoryDevice named after its key, in key order. A plain
        list of modules is read as it is.
        """
        if isinstance(value, dict):
            value = [
                {'name': name, **module}
                for name, module in sorted(value.items())
                if isinstance(module, dict)
            ]
        if not isinstance(value, list):
            return ()
        return tuple(item for item in value if isinstance(item, dict))

    @property
    def cluster_name(self) -> str:
        """The node's cluster: cluster, or nodeset if that is all there is."""
        return self.cluster or self.nodeset

    @property
    def ram_gib(self) -> float:
        """All the RAM in GiB: main_memory, or the modules added up."""
        if self.main_memory.ram_size:
            return self.main_memory.gib
        return sum(module.size for module in self.memory_devices) / GIB

    @property
    def connected_adapters(self) -> tuple[NetworkAdapter, ...]:
        """The network cards that are connected (mounted)."""
        return tuple(adapter for adapter in self.network_adapters if adapter.mounted)
