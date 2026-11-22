"""Reserving and cancelling: OAR jobs through the API.

    POST   /sites/{site}/jobs        a new job
    DELETE /sites/{site}/jobs/{id}   cancel it

A reservation is what EnOSlib sends:

    {"name": "grid-tui",
     "resources": "{cluster='gros'}/nodes=2,walltime=02:00:00",
     "command": "sleep 31536000",
     "queue": "default",
     "project": "my-lab",              (only if one is given)
     "types": ["deploy"],              (only if some are ticked)
     "reservation": "2026-11-22 18:00:00"}   (only for a start in advance)

The command only keeps the job alive until its walltime ends; the nodes are
yours meanwhile. OAR reads the reservation's date in Grid'5000's time zone.
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

from grid_tui.models.job import JobRequest

OAR_ZONE = ZoneInfo("Europe/Paris")
KEEP_ALIVE = "sleep 31536000"


def jobs_path(site: str) -> str:
    """The API path of the jobs of a site."""
    return f"/sites/{quote(site, safe='')}/jobs"


def walltime(d: timedelta) -> str:
    """d as OAR writes it: "02:30:00"."""
    s = int(d.total_seconds())
    return f"{s // 3600:02d}:{s // 60 % 60:02d}:{s % 60:02d}"


def job_spec(r: JobRequest) -> dict[str, Any]:
    """The JSON the API gets for r."""
    spec: dict[str, Any] = {
        "name": r.name,
        "resources": f"{{cluster='{r.cluster}'}}/nodes={r.nodes},walltime={walltime(r.walltime)}",
        "command": KEEP_ALIVE,
        "queue": r.queue,
    }
    if r.project:
        spec["project"] = r.project
    if r.types:
        spec["types"] = list(r.types)
    if r.start is not None:
        spec["reservation"] = r.start.astimezone(OAR_ZONE).strftime("%Y-%m-%d %H:%M:%S")
    return spec


def submit_command(base_url: str, r: JobRequest) -> str:
    """The curl command that sends r, to show before it is sent."""
    return (f"curl -X POST {base_url}{jobs_path(r.site)} -H 'Content-Type: application/json' "
            f"-d '{json.dumps(job_spec(r))}'")
