"""Tests for the Site model: reading a site from the API's JSON."""

import pytest
from pydantic import ValidationError

from grid_tui.models import Site


def test_only_uid_is_needed():
    """A Site needs only a uid; the rest default to ''."""
    site = Site(uid='nancy')
    assert site.uid == 'nancy'
    assert site.name == ''
    assert site.description == ''


def test_reads_api_json():
    """A site is read from the API's JSON."""
    site = Site.model_validate(
        {'uid': 'nancy', 'name': 'Nancy', 'description': 'Grid5000 Nancy site'}
    )
    assert site == Site(uid='nancy', name='Nancy', description='Grid5000 Nancy site')


def test_extra_fields_are_ignored():
    """Fields Site doesn't know are dropped."""
    site = Site.model_validate({'uid': 'nancy', 'latitude': 48.6, 'links': []})
    assert site == Site(uid='nancy')


def test_null_becomes_empty():
    """A null name or description is read as ''."""
    site = Site.model_validate({'uid': 'nancy', 'name': None, 'description': None})
    assert site.name == ''
    assert site.description == ''


def test_uid_is_required():
    """A site without a uid is an error."""
    with pytest.raises(ValidationError):
        Site.model_validate({'name': 'Nancy'})


def test_wrong_type_is_an_error():
    """A name that isn't text is an error."""
    with pytest.raises(ValidationError):
        Site.model_validate({'uid': 'nancy', 'name': 42})


def test_sites_with_same_values_are_equal():
    """Two sites with the same values are equal."""
    assert Site(uid='nancy', name='Nancy') == Site(uid='nancy', name='Nancy')
    assert Site(uid='nancy') != Site(uid='lyon')


def test_cannot_be_changed():
    """A Site is frozen: its fields can't be set."""
    site = Site(uid='nancy')
    with pytest.raises(ValidationError):
        site.uid = 'lyon'
