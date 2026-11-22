"""A small async client for the Grid'5000 API.

On a Grid'5000 frontend no login is needed. From anywhere else the API wants
HTTP basic auth with your Grid'5000 login, read from the environment:

    G5K_USER, G5K_PASSWORD   your Grid'5000 login (not needed on a frontend)
    G5K_API                  the API root, default DEFAULT_BASE_URL

Lists come wrapped as {"items": [...], "total": n, "offset": 0}.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import quote

import httpx

from grid_tui.grid5000.jobs import job_spec, jobs_path, submit_command
from grid_tui.models import GPU, NIC, Cluster, Disk, Hardware, Node, Reservation, Site, node_order
from grid_tui.models.job import JobRequest

DEFAULT_BASE_URL = "https://api.grid5000.fr/stable"
SITES_PATH = "/sites"


class ApiError(Exception):
    """An answer that isn't a success."""

    def __init__(self, method: str, path: str, status: int, detail: str = "") -> None:
        self.method, self.path, self.status, self.detail = method, path, status, detail
        message = f"{method} {path}: {status} {httpx.codes.get_reason_phrase(status)}"
        if detail:
            message += f": {detail}"
        if status == 401:
            message += " (outside Grid'5000, set G5K_USER and G5K_PASSWORD)"
        super().__init__(message)


class Client:
    """Calls the Grid'5000 API."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        user: str = "",
        password: str = "",
        *,
        transport: httpx.AsyncBaseTransport | None = None,  # tests give a fake one
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.user, self.password = user, password
        self._transport, self._timeout = transport, timeout

    @classmethod
    def from_env(cls) -> Client:
        """A client from G5K_API, G5K_USER and G5K_PASSWORD."""
        return cls(
            os.environ.get("G5K_API") or DEFAULT_BASE_URL,
            os.environ.get("G5K_USER", ""),
            os.environ.get("G5K_PASSWORD", ""),
        )

    def command(self, path: str) -> str:
        """The curl command for GET path, to show what a screen is made of."""
        return f"curl {self.base_url}{path}"

    async def _get(self, path: str) -> Any:
        return await self._request("GET", path)

    async def _request(self, method: str, path: str, body: Any = None) -> Any:
        """Call method path (with body as JSON) and return the JSON answer,
        or None if there is none."""
        auth = httpx.BasicAuth(self.user, self.password) if self.user else None
        async with httpx.AsyncClient(
            base_url=self.base_url, auth=auth, timeout=self._timeout, transport=self._transport
        ) as http:
            response = await http.request(method, path, json=body, headers={"Accept": "application/json"})
        if not response.is_success:
            raise ApiError(method, path, response.status_code, _detail(response))
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as e:
            if method != "GET":
                return None  # the job was made; the answer just isn't JSON
            raise ApiError(method, path, response.status_code, f"reading the answer: {e}") from e

    # Reserving and cancelling (see jobs.py).

    def login(self) -> str:
        """Who the jobs are made as: G5K_USER, or on a frontend the system's user."""
        return self.user or os.environ.get("USER", "")

    def submit_command(self, r: JobRequest) -> str:
        return submit_command(self.base_url, r)

    async def submit_job(self, r: JobRequest) -> int:
        """Ask OAR for the reservation r; the new job's number."""
        if not r.site or not r.cluster or r.nodes < 1 or r.walltime <= timedelta(0):
            raise ValueError("submit: a site, a cluster, nodes and a walltime are needed")
        answer = await self._request("POST", jobs_path(r.site), job_spec(r))
        job_id = int(num(answer, "uid"))
        if job_id <= 0:
            raise ValueError("submit: the answer has no job number")
        return job_id

    async def cancel_job(self, site: str, job_id: int) -> None:
        """Cancel job job_id of site."""
        if not site or job_id <= 0:
            raise ValueError("cancel: a site and a job are needed")
        await self._request("DELETE", f"{jobs_path(site)}/{job_id}")

    async def sites(self) -> list[Site]:
        """Every Grid'5000 site: GET /stable/sites."""
        data = await self._get(SITES_PATH)
        return [
            Site(uid=item.get("uid", ""), name=item.get("name", ""), description=item.get("description", ""))
            for item in data.get("items", [])
        ]

    async def clusters(self, site: str) -> list[Cluster]:
        """The clusters of a site: GET /stable/sites/{site}/clusters."""
        if not site:
            raise ValueError("clusters: no site given")
        data = await self._get(clusters_path(site))
        return [
            Cluster(
                uid=item.get("uid", ""),
                model=item.get("model") or "",
                queues=tuple(item.get("queues") or ()),
                metrics=tuple(m.get("name", "") for m in item.get("metrics") or () if isinstance(m, dict)),
            )
            for item in data.get("items", [])
        ]

    async def hardware(self, site: str, cluster: str) -> Hardware:
        """The hardware of a cluster, from its first node: GET …/clusters/{cluster}/nodes.

        Every value is read with dig/num/text: a field that is missing, null
        or of another type gives "" or 0 instead of failing the whole answer.
        """
        if not site or not cluster:
            raise ValueError("hardware: a site and a cluster are needed")
        data = await self._get(f"{clusters_path(site)}/{quote(cluster, safe='')}/nodes")
        items = dig(data, "items", default=[])
        if not isinstance(items, list) or not items:
            raise ValueError(f"{cluster} has no nodes")
        n = items[0]
        return Hardware(
            nodes=len(items),
            cpu=text(n, "processor", "other_description") or text(n, "processor", "model"),
            sockets=int(num(n, "architecture", "nb_procs")),
            cores=int(num(n, "architecture", "nb_cores")),
            threads=int(num(n, "architecture", "nb_threads")),
            clock_ghz=num(n, "processor", "clock_speed") / 1e9,
            memory=int(num(n, "main_memory", "ram_size")),
            disks=tuple(
                Disk(text(d, "storage"), text(d, "interface"), int(num(d, "size")))
                for d in each(n, "storage_devices")
            ),
            nics=tuple(
                NIC(text(a, "interface"), int(num(a, "rate")))
                for a in each(n, "network_adapters")
                if dig(a, "mounted") is True  # only the cards that are connected
            ),
            gpus=tuple(
                GPU(text(g, "vendor"), text(g, "model"), int(num(g, "memory")))
                for g in each(n, "gpu_devices")
            ),
        )


    async def nodes(self, site: str, cluster: str) -> list[Node]:
        """The nodes of a cluster with their jobs: GET …/clusters/{cluster}/status.

        The answer is {"nodes": {"gros-12.nancy.grid5000.fr": {"hard": …,
        "soft": …, "reservations": [{"uid", "user", "queue", "state",
        "walltime" (seconds), "started_at" / "scheduled_at" (UNIX time)}]}}}.
        A job not scheduled yet (no start time) is left out.
        """
        if not site or not cluster:
            raise ValueError("nodes: a site and a cluster are needed")
        data = await self._get(f"{clusters_path(site)}/{quote(cluster, safe='')}/status")
        return parse_status(data)

    async def site_nodes(self, site: str) -> list[Node]:
        """Every node of a site with its jobs, in one call: GET /sites/{site}/status.
        The answer has the same shape as a cluster's status."""
        if not site:
            raise ValueError("site nodes: no site given")
        return parse_status(await self._get(f"{SITES_PATH}/{quote(site, safe='')}/status"))


# Reading the API's JSON safely: each of these returns a default when a key
# is missing, a value is null, or it isn't of the type wanted.


def dig(obj: Any, *keys: str, default: Any = None) -> Any:
    """obj[k1][k2]…, or default as soon as a step isn't there.

    dig(node, "main_memory", "ram_size")  →  103079215104, or None
    """
    for k in keys:
        if not isinstance(obj, dict) or obj.get(k) is None:
            return default
        obj = obj[k]
    return obj


def text(obj: Any, *keys: str) -> str:
    """The string at keys, or ""."""
    v = dig(obj, *keys)
    return v if isinstance(v, str) else ""


def num(obj: Any, *keys: str) -> float:
    """The number at keys (a number in a string counts too), or 0."""
    v = dig(obj, *keys)
    if isinstance(v, bool):  # True is an int in Python: not a number here
        return 0
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            return 0
    return 0


def each(obj: Any, *keys: str) -> list[dict]:
    """The dicts at keys: a list's dicts, or a dict's values in key order
    (gpu_devices is {"0": {...}, "1": {...}}); [] if neither."""
    v = dig(obj, *keys)
    if isinstance(v, dict):
        v = [v[k] for k in sorted(v)]
    if not isinstance(v, list):
        return []
    return [x for x in v if isinstance(x, dict)]


def parse_status(data: Any) -> list[Node]:
    """The nodes of a status answer, by name; jobs not scheduled yet are left out."""
    found = dig(data, "nodes", default={})
    if not isinstance(found, dict):
        return []
    nodes = []
    for fqdn, n in found.items():
        if not isinstance(n, dict):
            continue
        jobs = []
        for r in each(n, "reservations"):
            start, walltime = num(r, "started_at") or num(r, "scheduled_at"), num(r, "walltime")
            if start <= 0 or walltime <= 0:
                continue  # not scheduled yet
            jobs.append(Reservation(
                job_id=int(num(r, "uid")),
                start=datetime.fromtimestamp(start).astimezone(),
                end=datetime.fromtimestamp(start + walltime).astimezone(),
                user=text(r, "user"),
                queue=text(r, "queue"),
                state=text(r, "state"),
            ))
        nodes.append(Node(
            name=str(fqdn).split(".", 1)[0],  # gros-12.nancy.grid5000.fr → gros-12
            hard=text(n, "hard"),
            soft=text(n, "soft"),
            reservations=tuple(sorted(jobs, key=lambda j: j.start)),
        ))
    return sorted(nodes, key=node_order)


def clusters_path(site: str) -> str:
    """The API path of the clusters of site (escaped: a name can't change the path)."""
    return f"{SITES_PATH}/{quote(site, safe='')}/clusters"


def _detail(response: httpx.Response) -> str:
    """What an error answer says: its JSON "message", else its first line of
    text; nothing for an HTML page."""
    text = response.text.strip()
    if not text or text.startswith("<"):
        return ""
    try:
        message = response.json().get("message", "")
        return message if isinstance(message, str) else ""
    except (ValueError, AttributeError):
        return text.splitlines()[0]
