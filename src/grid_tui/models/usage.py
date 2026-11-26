"""How busy the nodes are right now, from GET /sites/{site}/status."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# a node's hard state: is it there at all
UP = {'alive', 'standby'}  # standby: powered off, but starts when a job needs it


@dataclass(frozen=True)
class Usage:
    """How many nodes are up, and how many of those run a job."""

    busy: int = 0
    up: int = 0

    @property
    def percent(self) -> int:
        """How busy, 0 to 100; 0 when no node is up."""
        return round(100 * self.busy / self.up) if self.up else 0

    def __add__(self, other: Usage) -> Usage:
        """Two counts together, e.g. two sites'."""
        return Usage(self.busy + other.busy, self.up + other.up)

    @classmethod
    def from_status(cls, answer: Any) -> Usage:
        """Count the nodes in a status answer.

        A node counts when its hard state is alive or standby, and as busy
        when its soft state starts with 'busy' (e.g. 'busy', 'busy_free',
        'busy_besteffort'). The rest of the soft state is what comes next:
        'free_busy' is free now and busy soon.

        Args:
            answer: The JSON of GET /sites/{site}/status: {'nodes': {...}}.
        """
        nodes = answer.get('nodes') if isinstance(answer, dict) else None
        if not isinstance(nodes, dict):
            return cls()
        busy = up = 0
        for node in nodes.values():
            if not isinstance(node, dict) or node.get('hard') not in UP:
                continue
            up += 1
            soft = node.get('soft')
            if isinstance(soft, str) and soft.split('_')[0] == 'busy':
                busy += 1
        return cls(busy, up)
