import pytest
from pydantic import ValidationError

from grid_tui.models import Cluster


def test_only_uid_is_needed():
    cluster = Cluster(uid='gros')
    assert cluster.model == ''
    assert cluster.queues == ()
    assert cluster.exotic is False


def test_reads_api_json():
    cluster = Cluster.model_validate(
        {
            'uid': 'gros',
            'model': 'Dell PowerEdge R640',
            'queues': ['default', 'admin'],
            'exotic': False,
            'created_at': 'Thu, 01 Aug 2019 00:00:00 GMT',  # extra: ignored
        }
    )
    assert cluster == Cluster(
        uid='gros', model='Dell PowerEdge R640', queues=('default', 'admin')
    )


def test_null_values_become_defaults():
    cluster = Cluster.model_validate(
        {'uid': 'gros', 'model': None, 'queues': None, 'exotic': None}
    )
    assert cluster == Cluster(uid='gros')


def test_uid_is_required():
    with pytest.raises(ValidationError):
        Cluster.model_validate({'model': 'Dell'})


def test_cannot_be_changed():
    cluster = Cluster(uid='gros')
    with pytest.raises(ValidationError):
        cluster.uid = 'grisou'
