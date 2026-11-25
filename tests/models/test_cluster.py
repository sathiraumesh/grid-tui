import pytest
from pydantic import ValidationError

from grid_tui.models import Cluster, Link

# roughly what GET /sites/nancy/clusters gives for one cluster
GROS = {
    'uid': 'gros',
    'model': 'Dell PowerEdge R640',
    'created_at': 'Thu, 01 Aug 2019 00:00:00 GMT',
    'type': 'cluster',
    'version': 'abc123',
    'queues': ['default', 'admin'],
    'metrics': [{'name': 'wattmetre_power', 'description': 'Power'}],
    'exotic': False,
    'kavlan': True,
    'links': [
        {'rel': 'self', 'href': '/stable/sites/nancy/clusters/gros'},
        {'rel': 'nodes', 'href': '/stable/sites/nancy/clusters/gros/nodes'},
    ],
}


def test_only_uid_is_needed():
    cluster = Cluster(uid='gros')
    assert cluster.model == ''
    assert cluster.created_at == ''
    assert cluster.type == ''
    assert cluster.version == ''
    assert cluster.queues == ()
    assert cluster.metrics == ()
    assert cluster.exotic is False
    assert cluster.kavlan is False
    assert cluster.links == ()


def test_reads_api_json():
    cluster = Cluster.model_validate(GROS)
    assert cluster.uid == 'gros'
    assert cluster.model == 'Dell PowerEdge R640'
    assert cluster.created_at == 'Thu, 01 Aug 2019 00:00:00 GMT'
    assert cluster.type == 'cluster'
    assert cluster.version == 'abc123'
    assert cluster.queues == ('default', 'admin')
    assert cluster.metrics == ('wattmetre_power',)
    assert cluster.exotic is False
    assert cluster.kavlan is True
    assert cluster.links[1] == Link(
        rel='nodes', href='/stable/sites/nancy/clusters/gros/nodes'
    )


def test_unknown_fields_are_ignored():
    cluster = Cluster.model_validate({'uid': 'gros', 'something_new': 1})
    assert cluster == Cluster(uid='gros')


def test_null_values_become_defaults():
    nulls = {key: None for key in GROS if key != 'uid'}
    cluster = Cluster.model_validate({'uid': 'gros', **nulls})
    assert cluster == Cluster(uid='gros')


def test_a_number_version_is_read_as_text():
    assert Cluster.model_validate({'uid': 'gros', 'version': 3}).version == '3'


def test_bad_metrics_are_skipped():
    cluster = Cluster.model_validate(
        {'uid': 'gros', 'metrics': [{'name': 'ok'}, 'oops', {'no_name': 1}]}
    )
    assert cluster.metrics == ('ok',)


def test_uid_is_required():
    with pytest.raises(ValidationError):
        Cluster.model_validate({'model': 'Dell'})


def test_cannot_be_changed():
    cluster = Cluster(uid='gros')
    with pytest.raises(ValidationError):
        cluster.uid = 'grisou'
