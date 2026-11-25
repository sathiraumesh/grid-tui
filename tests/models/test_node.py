"""Tests for the Node model: reading a node and its hardware from the API's JSON."""

import pytest
from pydantic import ValidationError

from grid_tui.models import (
    Architecture,
    Bios,
    Chassis,
    Gpu,
    JobTypes,
    Link,
    Memory,
    MemoryDevice,
    Monitoring,
    NetworkAdapter,
    Node,
    OperatingSystem,
    PduPort,
    Performance,
    Processor,
    StorageDevice,
)

# roughly what GET /sites/nancy/clusters/gros/nodes gives for one node
GROS_12 = {
    'uid': 'gros-12',
    'cluster': 'gros',
    'architecture': {
        'nb_procs': 1,
        'nb_cores': 18,
        'nb_threads': 36,
        'platform_type': 'x86_64',
    },
    'processor': {
        'vendor': 'Intel',
        'model': 'Intel Xeon',
        'other_description': 'Intel Xeon Gold 5220',
        'clock_speed': 2_200_000_000,
    },
    'main_memory': {'ram_size': 96 * 1024**3},
    'storage_devices': [
        {
            'device': 'sda',
            'storage': 'SSD',
            'interface': 'SATA',
            'model': 'SAMSUNG MZ7KH480',
            'size': 480_103_981_056,
        },
    ],
    'network_adapters': [
        {
            'device': 'eth0',
            'interface': 'Ethernet',
            'rate': 25 * 10**9,
            'mounted': True,
        },
        {'device': 'eth1', 'interface': 'Ethernet', 'rate': 0, 'mounted': False},
    ],
    'gpu_devices': {},
    'memory_devices': {
        'dimm_b0': {'size': 32 * 1024**3},
        'dimm_a0': {'size': 64 * 1024**3},
    },
    'bios': {'vendor': 'Dell Inc.', 'version': '2.12.2', 'release_date': '07/09/2021'},
    'chassis': {'manufacturer': 'Dell Inc.', 'name': 'PowerEdge R640', 'serial': 'ABC'},
    'operating_system': {
        'ht_enabled': True,
        'turboboost_enabled': True,
        'pstate_driver': 'intel_pstate',
        'pstate_governor': 'performance',
        'cstate_driver': 'intel_idle',
        'cstate_max_id': 3,
    },
    'performance': {'core_flops': 22_000_000_000, 'node_flops': 790_000_000_000},
    'supported_job_types': {
        'deploy': True,
        'besteffort': True,
        'virtual': 'ivt',
        'max_walltime': 0,
        'queues': ['default', 'admin'],
    },
    'monitoring': {'wattmeter': True, 'metric': 'power'},
    'pdu': [{'uid': 'gros-pdu1', 'port': 12}],
    'exotic': False,
    'links': [
        {'rel': 'self', 'href': '/stable/sites/nancy/clusters/gros/nodes/gros-12'}
    ],
}


def test_only_uid_is_needed():
    """A Node needs only a uid; the hardware defaults to empty."""
    node = Node(uid='gros-12')
    assert node.cluster == ''
    assert node.architecture == Architecture()
    assert node.processor == Processor()
    assert node.main_memory == Memory()
    assert node.storage_devices == ()
    assert node.network_adapters == ()
    assert node.gpu_devices == ()
    assert node.exotic is False
    assert node.memory_devices == ()
    assert node.bios == Bios()
    assert node.chassis == Chassis()
    assert node.operating_system == OperatingSystem()
    assert node.performance == Performance()
    assert node.supported_job_types == JobTypes()
    assert node.monitoring == Monitoring()
    assert node.pdu == ()
    assert node.links == ()


def test_reads_api_json():
    """Every part of a node is read from the API's JSON."""
    node = Node.model_validate(GROS_12)
    assert node.uid == 'gros-12'
    assert node.cluster == 'gros'
    assert node.architecture == Architecture(
        nb_procs=1, nb_cores=18, nb_threads=36, platform_type='x86_64'
    )
    assert node.processor.name == 'Intel Xeon Gold 5220'
    assert node.main_memory.ram_size == 96 * 1024**3
    assert node.storage_devices == (
        StorageDevice(
            device='sda',
            storage='SSD',
            interface='SATA',
            model='SAMSUNG MZ7KH480',
            size=480_103_981_056,
        ),
    )
    assert [a.device for a in node.network_adapters] == ['eth0', 'eth1']
    assert node.gpu_devices == ()


def test_unknown_fields_are_ignored():
    """Fields Node doesn't know are dropped."""
    node = Node.model_validate({'uid': 'gros-12', 'something_new': {'a': 1}})
    assert node == Node(uid='gros-12')


def test_null_parts_become_defaults():
    """A null in any part, or inside one, gives the default."""
    nulls = {key: None for key in GROS_12 if key != 'uid'}
    assert Node.model_validate({'uid': 'gros-12', **nulls}) == Node(uid='gros-12')
    node = Node.model_validate({'uid': 'gros-12', 'processor': {'model': None}})
    assert node.processor == Processor()


def test_numbers_in_text_are_read_as_numbers():
    """A number sent as text, e.g. '18', is read as a number."""
    node = Node.model_validate({'uid': 'gros-12', 'architecture': {'nb_cores': '18'}})
    assert node.architecture.nb_cores == 18


def test_gpus_given_by_number_are_kept_in_order():
    """GPUs come as {'0': ..., '1': ...}; they are kept in that order."""
    node = Node.model_validate(
        {
            'uid': 'chifflot-1',
            'gpu_devices': {
                '1': {
                    'vendor': 'Nvidia',
                    'model': 'Tesla P100',
                    'memory': 16 * 1024**3,
                },
                '0': {
                    'vendor': 'Nvidia',
                    'model': 'Tesla V100',
                    'memory': 32 * 1024**3,
                },
            },
        }
    )
    assert [gpu.model for gpu in node.gpu_devices] == ['Tesla V100', 'Tesla P100']
    assert node.gpu_devices[0] == Gpu(
        vendor='Nvidia', model='Tesla V100', memory=32 * 1024**3
    )


def test_gpus_given_as_a_list_are_read_too():
    """A plain list of GPUs is read as it is."""
    node = Node.model_validate({'uid': 'x', 'gpu_devices': [{'model': 'A100'}]})
    assert node.gpu_devices == (Gpu(model='A100'),)


def test_broken_entries_are_skipped():
    """Disk, card and GPU entries that aren't objects are left out."""
    node = Node.model_validate(
        {
            'uid': 'x',
            'storage_devices': [{'device': 'sda'}, 'oops', None],
            'network_adapters': 'not a list',
            'gpu_devices': {'0': {'model': 'A100'}, '1': 42},
        }
    )
    assert node.storage_devices == (StorageDevice(device='sda'),)
    assert node.network_adapters == ()
    assert node.gpu_devices == (Gpu(model='A100'),)


def test_connected_adapters_are_the_mounted_ones():
    """connected_adapters leaves out the cards that aren't connected."""
    node = Node.model_validate(GROS_12)
    assert [a.device for a in node.connected_adapters] == ['eth0']


def test_sizes_and_speeds_in_readable_units():
    """The hardware gives GHz, GiB and Gbit/s as well as the raw numbers."""
    node = Node.model_validate(GROS_12)
    assert node.processor.ghz == 2.2
    assert node.main_memory.gib == 96.0
    assert node.storage_devices[0].gib == pytest.approx(447.1, abs=0.1)
    assert node.network_adapters[0].gbps == 25.0
    assert Gpu(memory=32 * 1024**3).gib == 32.0


def test_processor_name_falls_back_to_the_model():
    """With no full description, the processor's name is its model."""
    assert Processor(model='AMD EPYC').name == 'AMD EPYC'


def test_uid_is_required():
    """A node without a uid is an error."""
    with pytest.raises(ValidationError):
        Node.model_validate({'cluster': 'gros'})


def test_wrong_type_is_an_error():
    """A core count that isn't a number is an error."""
    with pytest.raises(ValidationError):
        Node.model_validate({'uid': 'x', 'architecture': {'nb_cores': 'many'}})


def test_cannot_be_changed():
    """A Node and its parts are frozen."""
    node = Node.model_validate(GROS_12)
    with pytest.raises(ValidationError):
        node.uid = 'gros-13'
    with pytest.raises(ValidationError):
        node.processor.clock_speed = 0


def test_network_adapter_defaults_to_not_connected():
    """A card with no mounted flag counts as not connected."""
    assert NetworkAdapter(device='eth0').mounted is False


# The other parts of a node


def test_reads_the_bios_and_chassis():
    """The BIOS and the machine's make are read."""
    node = Node.model_validate(GROS_12)
    assert node.bios == Bios(
        vendor='Dell Inc.', version='2.12.2', release_date='07/09/2021'
    )
    assert node.chassis == Chassis(
        manufacturer='Dell Inc.', name='PowerEdge R640', serial='ABC'
    )


def test_reads_the_operating_system_settings():
    """The CPU settings of the default system are read."""
    assert Node.model_validate(GROS_12).operating_system == OperatingSystem(
        ht_enabled=True,
        turboboost_enabled=True,
        pstate_driver='intel_pstate',
        pstate_governor='performance',
        cstate_driver='intel_idle',
        cstate_max_id=3,
    )


def test_reads_the_performance():
    """The benchmark speeds are read, and given in GFLOPS too."""
    performance = Node.model_validate(GROS_12).performance
    assert performance == Performance(
        core_flops=22_000_000_000, node_flops=790_000_000_000
    )
    assert performance.core_gflops == 22.0
    assert performance.node_gflops == 790.0


def test_reads_the_job_types():
    """What jobs the node takes is read."""
    assert Node.model_validate(GROS_12).supported_job_types == JobTypes(
        deploy=True,
        besteffort=True,
        virtual='ivt',
        max_walltime=0,
        queues=('default', 'admin'),
    )


def test_no_virtualisation_is_empty_text():
    """virtual: false is read as ''."""
    node = Node.model_validate({'uid': 'x', 'supported_job_types': {'virtual': False}})
    assert node.supported_job_types.virtual == ''


def test_reads_the_monitoring():
    """A node with a wattmeter says so."""
    monitoring = Node.model_validate(GROS_12).monitoring
    assert monitoring == Monitoring(wattmeter='yes', metric='power')
    assert monitoring.has_wattmeter is True


def test_a_shared_wattmeter_counts_as_a_wattmeter():
    """wattmeter: 'shared' is kept as it is, and counts as having one."""
    monitoring = Monitoring.model_validate({'wattmeter': 'shared'})
    assert monitoring.wattmeter == 'shared'
    assert monitoring.has_wattmeter is True


def test_no_wattmeter():
    """wattmeter: false means no wattmeter."""
    assert Monitoring.model_validate({'wattmeter': False}).has_wattmeter is False


def test_reads_the_pdu_and_a_number_port_as_text():
    """The power strip is read; its port number is read as text."""
    assert Node.model_validate(GROS_12).pdu == (PduPort(uid='gros-pdu1', port='12'),)


def test_reads_the_links():
    """The node's links to related API pages are read."""
    [link] = Node.model_validate(GROS_12).links
    assert link == Link(
        rel='self', href='/stable/sites/nancy/clusters/gros/nodes/gros-12'
    )


def test_memory_devices_are_named_after_their_keys_in_order():
    """RAM modules come as {'dimm_a0': {...}}; each keeps its key as its name."""
    modules = Node.model_validate(GROS_12).memory_devices
    assert modules == (
        MemoryDevice(name='dimm_a0', size=64 * 1024**3),
        MemoryDevice(name='dimm_b0', size=32 * 1024**3),
    )
    assert modules[0].gib == 64.0


def test_memory_devices_given_as_a_list_are_read_too():
    """A plain list of RAM modules is read as it is."""
    node = Node.model_validate({'uid': 'x', 'memory_devices': [{'size': 8}]})
    assert node.memory_devices == (MemoryDevice(size=8),)


def test_reads_the_processor_details():
    """The processor's caches, version and abilities are read."""
    processor = Processor.model_validate(
        {
            'version': 'Gold 5220',
            'instruction_set': 'x86-64',
            'microcode': '0x5003006',
            'ht_capable': True,
            'cache_l1d': 32768,
            'cache_l1i': 32768,
            'cache_l2': 1048576,
            'cache_l3': 25952256,
        }
    )
    assert processor.version == 'Gold 5220'
    assert processor.instruction_set == 'x86-64'
    assert processor.microcode == '0x5003006'
    assert processor.ht_capable is True
    assert (processor.cache_l1d, processor.cache_l1i) == (32768, 32768)
    assert (processor.cache_l2, processor.cache_l3) == (1048576, 25952256)


def test_reads_the_network_adapter_details():
    """A card's MAC, KaVLAN support and switch port are read."""
    adapter = NetworkAdapter.model_validate(
        {
            'mac': '0c:42:a1:00:00:01',
            'kavlan': True,
            'switch': 'gw-nancy',
            'switch_port': 12,
        }
    )
    assert adapter == NetworkAdapter(
        mac='0c:42:a1:00:00:01', kavlan=True, switch='gw-nancy', switch_port='12'
    )


def test_a_part_that_is_not_an_object_is_empty():
    """A part sent as text or a number (e.g. 'n/a') is read as empty."""
    node = Node.model_validate(
        {'uid': 'x', 'bios': 'n/a', 'performance': 0, 'monitoring': []}
    )
    assert node.bios == Bios()
    assert node.performance == Performance()
    assert node.monitoring == Monitoring()


def test_cluster_name_falls_back_to_the_nodeset():
    """With no cluster, cluster_name is the nodeset."""
    assert Node(uid='x', nodeset='gros').cluster_name == 'gros'
    assert Node(uid='x', cluster='gros', nodeset='other').cluster_name == 'gros'


def test_ram_from_main_memory_or_the_modules():
    """ram_gib is main_memory, or the RAM modules added up if that is missing."""
    assert Node.model_validate(GROS_12).ram_gib == 96.0
    node = Node.model_validate(
        {
            'uid': 'x',
            'memory_devices': {'a': {'size': 2 * 1024**3}, 'b': {'size': 1024**3}},
        }
    )
    assert node.ram_gib == 3.0


def test_parts_given_ready_made_are_kept():
    """A part passed as a model, e.g. bios=Bios(...), is kept, not emptied."""
    node = Node(
        uid='x', bios=Bios(vendor='Dell Inc.'), performance=Performance(node_flops=1)
    )
    assert node.bios.vendor == 'Dell Inc.'
    assert node.performance.node_flops == 1
