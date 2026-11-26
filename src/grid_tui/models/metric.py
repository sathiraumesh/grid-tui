"""What a cluster can measure: the metrics Kwollect records for its nodes.

As each cluster lists them in GET /sites/{site}/clusters, under "metrics".
"""

from typing import Any

from pydantic import BaseModel, Field, field_validator

from grid_tui.models.base import ApiModel


class MetricSource(ApiModel):
    """Where a metric's values come from."""

    protocol: str = ''  # how they are read, e.g. 'wattmetre', 'ipmisensor', 'snmp'
    id: str = ''  # what is read, e.g. a sensor or SNMP id


class MetricInfo(ApiModel):
    """One metric a cluster offers, e.g. its nodes' power from a wattmeter."""

    name: str  # e.g. 'wattmetre_power_watt': what to ask Kwollect for
    description: str = ''  # e.g. 'Power consumption of node reported by wattmetre'
    period: int = 0  # how often it is recorded, in milliseconds; 0 for unknown
    optional_period: int = 0  # a faster period you can ask for, in ms; 0 for none
    scale_factor: float = 1.0  # multiply the raw values by this
    source: MetricSource = MetricSource()
    labels: dict[str, str] = Field(
        default_factory=dict
    )  # extra tags, e.g. {'unit': 'W'}
    only_for: tuple[str, ...] = ()  # the nodes it is recorded for; () for every node

    @field_validator('source', mode='before')
    @classmethod
    def _source_is_an_object(cls, value: Any) -> Any:
        """A source that isn't an object (or a MetricSource) is read as unknown."""
        return value if isinstance(value, (dict, BaseModel)) else {}

    @field_validator('labels', mode='before')
    @classmethod
    def _labels_are_an_object(cls, value: Any) -> Any:
        """Labels that aren't an object are read as none."""
        return value if isinstance(value, dict) else {}

    @field_validator('only_for', mode='before')
    @classmethod
    def _only_for_is_a_list(cls, value: Any) -> Any:
        """only_for that isn't a list (or tuple) is read as every node."""
        return value if isinstance(value, (list, tuple)) else ()

    @property
    def period_seconds(self) -> float:
        """How often it is recorded, in seconds, e.g. 0.02 for 20 ms."""
        return self.period / 1000

    def applies_to(self, node: str) -> bool:
        """Is this metric recorded for node (e.g. 'gros-12')?"""
        return not self.only_for or node in self.only_for
