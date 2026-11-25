"""Tests for ApiModel: frozen, and nulls read as the defaults."""

import pytest
from pydantic import ValidationError

from grid_tui.models import ApiModel


class Thing(ApiModel):
    """A small model to test ApiModel with."""

    uid: str
    name: str = ''
    count: int = 0


def test_null_values_use_the_defaults():
    """Every null field gets its default."""
    assert Thing.model_validate({'uid': 'x', 'name': None, 'count': None}) == Thing(
        uid='x'
    )


def test_a_null_required_field_is_still_an_error():
    """Dropping a null doesn't make a required field optional."""
    with pytest.raises(ValidationError):
        Thing.model_validate({'uid': None})


def test_unknown_fields_are_ignored():
    """Fields the model doesn't list are dropped."""
    assert Thing.model_validate({'uid': 'x', 'other': 1}) == Thing(uid='x')


def test_cannot_be_changed():
    """An ApiModel is frozen: its fields can't be set."""
    thing = Thing(uid='x')
    with pytest.raises(ValidationError):
        thing.uid = 'y'
