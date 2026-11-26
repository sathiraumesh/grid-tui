"""The app's data: plain classes that hold what the API returns."""

from grid_tui.models.base import ApiModel
from grid_tui.models.cluster import Cluster, Link
from grid_tui.models.job import Job
from grid_tui.models.metric import MetricInfo, MetricSource
from grid_tui.models.node import (
    Architecture,
    Bios,
    Chassis,
    Gpu,
    JobTypes,
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
from grid_tui.models.reservation import Reservation, Schedule
from grid_tui.models.site import Site
from grid_tui.models.usage import Usage

__all__ = [
    'ApiModel',
    'Architecture',
    'Bios',
    'Chassis',
    'Cluster',
    'Gpu',
    'Job',
    'JobTypes',
    'Link',
    'Memory',
    'MemoryDevice',
    'MetricInfo',
    'MetricSource',
    'Monitoring',
    'NetworkAdapter',
    'Node',
    'OperatingSystem',
    'PduPort',
    'Performance',
    'Processor',
    'Reservation',
    'Schedule',
    'Site',
    'StorageDevice',
    'Usage',
]
