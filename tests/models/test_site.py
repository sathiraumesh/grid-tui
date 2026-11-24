import pytest
from pydantic import ValidationError

from grid_tui.models import Site


def test_only_uid_is_needed():
    site = Site(uid='nancy')
    assert site.uid == 'nancy'
    assert site.name == ''
    assert site.description == ''


def test_reads_api_json():
    site = Site.model_validate(
        {'uid': 'nancy', 'name': 'Nancy', 'description': 'Grid5000 Nancy site'}
    )
    assert site == Site(uid='nancy', name='Nancy', description='Grid5000 Nancy site')


def test_extra_fields_are_ignored():
    site = Site.model_validate({'uid': 'nancy', 'latitude': 48.6, 'links': []})
    assert site == Site(uid='nancy')


def test_null_becomes_empty():
    site = Site.model_validate({'uid': 'nancy', 'name': None, 'description': None})
    assert site.name == ''
    assert site.description == ''


def test_uid_is_required():
    with pytest.raises(ValidationError):
        Site.model_validate({'name': 'Nancy'})


def test_wrong_type_is_an_error():
    with pytest.raises(ValidationError):
        Site.model_validate({'uid': 'nancy', 'name': 42})


def test_sites_with_same_values_are_equal():
    assert Site(uid='nancy', name='Nancy') == Site(uid='nancy', name='Nancy')
    assert Site(uid='nancy') != Site(uid='lyon')


def test_cannot_be_changed():
    site = Site(uid='nancy')
    with pytest.raises(ValidationError):
        site.uid = 'lyon'
