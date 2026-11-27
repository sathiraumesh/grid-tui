"""A Grid'5000 job (a reservation of nodes), from GET /sites/{site}/jobs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

ACTIVE = {'running', 'launching', 'waiting', 'tolaunch', 'toLaunch', 'hold'}


class Job(BaseModel):
    """One job: when it ran, for how long, on what.

    The jobs list gives no nodes or cores; GET /sites/{site}/jobs/{uid} does.
    """

    model_config = ConfigDict(frozen=True, extra='ignore')

    uid: int
    site: str = ''  # not in the answer: set by the client
    state: str = ''  # e.g. 'running', 'waiting', 'terminated', 'error'
    queue: str = ''  # e.g. 'default', 'production', 'besteffort'
    walltime: int = 0  # how long it may last, in seconds
    submitted_at: int | None = None  # when it was asked for, in seconds since 1970
    started_at: int | None = None  # when it started, in seconds since 1970
    stopped_at: int | None = None  # when it ended, if it has
    assigned_nodes: tuple[str, ...] = ()  # e.g. ('gros-1.nancy.grid5000.fr',)
    cores: int = 0  # how many cores it holds
    types: tuple[str, ...] = ()  # e.g. ('deploy',): how it was asked for

    @field_validator('submitted_at', 'started_at', 'stopped_at', mode='before')
    @classmethod
    def _zero_is_none(cls, value: Any) -> Any:
        """The API uses 0 or null for 'not yet'."""
        return value or None

    @field_validator('assigned_nodes', 'types', mode='before')
    @classmethod
    def _null_is_empty(cls, value: Any) -> Any:
        """No nodes yet (or null) is none."""
        return () if value is None else value

    @classmethod
    def from_api(cls, answer: dict, site: str) -> Job:
        """Read a job from the API, counting its cores.

        Args:
            answer: The JSON of one job.
            site: The site it is on, e.g. 'nancy'.
        """
        cores = (answer.get('resources_by_type') or {}).get('cores') or []
        return cls.model_validate({**answer, 'site': site, 'cores': len(cores)})

    @property
    def is_deploy(self) -> bool:
        """Was it asked for with -t deploy (your own system, reached as root)?"""
        return 'deploy' in self.types

    @property
    def is_active(self) -> bool:
        """Running, or about to (waiting for its start)."""
        return self.state in ACTIVE

    @property
    def is_running(self) -> bool:
        """Running now."""
        return self.state in ('running', 'launching')

    @property
    def cluster(self) -> str:
        """The cluster its nodes are in, e.g. 'gros'; '' if it has none yet."""
        if not self.assigned_nodes:
            return ''
        return self.assigned_nodes[0].split('.')[0].rsplit('-', 1)[0]

    def ran(self, now: float) -> tuple[float, float] | None:
        """When it ran, as (start, end) in seconds; None if it hasn't started.

        A job still running counts up to now.
        """
        if self.started_at is None:
            return None
        end = self.stopped_at or min(now, self.started_at + self.walltime)
        return (self.started_at, max(end, self.started_at))
