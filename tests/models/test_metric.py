"""Tests for MetricInfo: what a cluster can measure, read from the API's JSON."""

import pytest
from pydantic import ValidationError

from grid_tui.models import Cluster, MetricInfo, MetricSource

# roughly how a cluster lists one of its metrics
WATTMETRE = {
    'name': 'wattmetre_power_watt',
    'description': 'Power consumption of node reported by wattmetre, in watt',
    'period': 1000,
    'optional_period': 20,
    'scale_factor': 1,
    'source': {'protocol': 'wattmetre', 'id': 'wattmetre1-port12'},
    'labels': {'unit': 'W'},
    'only_for': ['gros-1', 'gros-2'],
}
BMC = {
    'name': 'bmc_node_power_watt',
    'description': 'Power from the BMC',
    'period': 5000,
}


def test_reads_api_json() -> None:
    """Every part of a metric is read."""
    metric = MetricInfo.model_validate(WATTMETRE)
    assert metric == MetricInfo(
        name='wattmetre_power_watt',
        description='Power consumption of node reported by wattmetre, in watt',
        period=1000,
        optional_period=20,
        scale_factor=1.0,
        source=MetricSource(protocol='wattmetre', id='wattmetre1-port12'),
        labels={'unit': 'W'},
        only_for=('gros-1', 'gros-2'),
    )


def test_only_name_is_needed() -> None:
    """A metric needs only a name; the rest have defaults."""
    metric = MetricInfo(name='x')
    assert metric.description == ''
    assert (metric.period, metric.optional_period) == (0, 0)
    assert metric.scale_factor == 1.0
    assert metric.source == MetricSource()
    assert metric.labels == {}
    assert metric.only_for == ()


def test_name_is_required() -> None:
    """A metric without a name is an error."""
    with pytest.raises(ValidationError):
        MetricInfo.model_validate({'description': 'no name'})


def test_nulls_and_odd_parts_become_defaults() -> None:
    """Nulls, and parts of the wrong kind, give the defaults."""
    metric = MetricInfo.model_validate(
        {
            'name': 'x',
            'description': None,
            'source': 'n/a',
            'labels': ['not', 'a', 'dict'],
            'only_for': 'gros-1',
        }
    )
    assert metric == MetricInfo(name='x')


def test_label_numbers_are_read_as_text() -> None:
    """A label given as a number is read as text."""
    assert MetricInfo.model_validate({'name': 'x', 'labels': {'port': 12}}).labels == {
        'port': '12'
    }


def test_period_in_seconds() -> None:
    """period_seconds gives the period in seconds."""
    assert MetricInfo(name='x', period=20).period_seconds == 0.02


def test_applies_to_only_the_nodes_listed() -> None:
    """A metric with only_for is recorded only for those nodes."""
    metric = MetricInfo.model_validate(WATTMETRE)
    assert metric.applies_to('gros-1') is True
    assert metric.applies_to('gros-9') is False


def test_applies_to_every_node_without_only_for() -> None:
    """A metric with no only_for is recorded for every node."""
    assert MetricInfo.model_validate(BMC).applies_to('gros-9') is True


# A cluster's metrics


def test_cluster_reads_its_metrics() -> None:
    """A cluster's metrics are read as MetricInfo, in order."""
    cluster = Cluster.model_validate({'uid': 'gros', 'metrics': [WATTMETRE, BMC]})
    assert cluster.metrics == (
        MetricInfo.model_validate(WATTMETRE),
        MetricInfo.model_validate(BMC),
    )
    assert cluster.metric_names == ('wattmetre_power_watt', 'bmc_node_power_watt')


def test_cluster_skips_a_metric_it_cannot_read() -> None:
    """A broken metric is left out; the cluster and its other metrics are kept."""
    broken = {'name': 'x', 'period': 'often'}  # not a number
    cluster = Cluster.model_validate({'uid': 'gros', 'metrics': [broken, BMC, 'oops']})
    assert cluster.metric_names == ('bmc_node_power_watt',)


def test_cluster_metrics_for_a_node() -> None:
    """metrics_for gives the metrics recorded for one node."""
    cluster = Cluster.model_validate({'uid': 'gros', 'metrics': [WATTMETRE, BMC]})
    for_listed = [m.name for m in cluster.metrics_for('gros-1')]
    for_other = [m.name for m in cluster.metrics_for('gros-9')]
    assert for_listed == ['wattmetre_power_watt', 'bmc_node_power_watt']
    assert for_other == ['bmc_node_power_watt']


def test_cluster_with_no_metrics() -> None:
    """A cluster with no or null metrics has none."""
    assert Cluster.model_validate({'uid': 'gros', 'metrics': None}).metrics == ()
    assert Cluster(uid='gros').metric_names == ()
