"""A cluster of a site."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Cluster:
    """One cluster of a site, as GET /sites/{site}/clusters lists it."""

    uid: str  # e.g. "gros": used in every API path
    model: str = ""  # the hardware, e.g. "Dell PowerEdge R640"
    queues: tuple[str, ...] = ()  # OAR queues it is in, e.g. ("default", "admin")
    metrics: tuple[str, ...] = ()  # what Kwollect measures on its nodes, e.g. "wattmetre_power_watt"

    @property
    def wattmeter(self) -> bool:
        """Whether its nodes have a wattmeter: a wattmetre_* metric."""
        return any(m.startswith("wattmetre") for m in self.metrics)
