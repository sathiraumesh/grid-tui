"""Reserving and cancelling through the API: the JSON, the calls, the errors."""

import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from grid_tui.grid5000 import ApiError, Client
from grid_tui.grid5000.jobs import job_spec, walltime
from grid_tui.models import JobRequest


def request(**changes) -> JobRequest:
    base = dict(site="nancy", cluster="gros", nodes=2, walltime=timedelta(hours=2, minutes=30),
                start=datetime(2026, 11, 22, 17, 0, tzinfo=timezone.utc),  # 18:00 in Paris
                queue="default", types=("deploy",))
    base.update(changes)
    return JobRequest(**base)


def test_job_spec() -> None:
    assert job_spec(request()) == {
        "name": "grid-tui",
        "resources": "{cluster='gros'}/nodes=2,walltime=02:30:00",
        "command": "sleep 31536000",
        "queue": "default",
        "types": ["deploy"],
        "reservation": "2026-11-22 18:00:00",  # Paris time
    }


def test_job_spec_leaves_out_what_isnt_asked() -> None:
    spec = job_spec(request(start=None, types=()))
    assert "reservation" not in spec and "types" not in spec and "project" not in spec
    assert job_spec(request(project="my-lab"))["project"] == "my-lab"


def test_walltime() -> None:
    assert walltime(timedelta(minutes=90, seconds=5)) == "01:30:05"
    assert walltime(timedelta(days=1)) == "24:00:00"


def recording_api(seen: list) -> httpx.MockTransport:
    def answer(r: httpx.Request) -> httpx.Response:
        seen.append((r.method, r.url.path, json.loads(r.content) if r.content else None,
                     r.headers.get("Content-Type", "")))
        if r.method == "POST" and r.url.path == "/stable/sites/nancy/jobs":
            return httpx.Response(201, json={"uid": 4710, "state": "waiting"})
        if r.method == "POST" and r.url.path == "/stable/sites/lyon/jobs":
            return httpx.Response(400, json={"code": 400, "message": "There are not enough resources for your request"})
        if r.method == "DELETE" and r.url.path == "/stable/sites/nancy/jobs/4710":
            return httpx.Response(202)
        return httpx.Response(404, json={"message": "no such job"})
    return httpx.MockTransport(answer)


async def test_submit_and_cancel() -> None:
    seen: list = []
    c = Client("https://api.test/stable", "alice", "secret", transport=recording_api(seen))
    assert await c.submit_job(request()) == 4710
    method, path, body, content_type = seen[-1]
    assert (method, path, content_type) == ("POST", "/stable/sites/nancy/jobs", "application/json")
    assert body["resources"] == "{cluster='gros'}/nodes=2,walltime=02:30:00"

    await c.cancel_job("nancy", 4710)
    assert seen[-1][:2] == ("DELETE", "/stable/sites/nancy/jobs/4710")


async def test_a_refused_job_says_why() -> None:
    c = Client("https://api.test/stable", transport=recording_api([]))
    with pytest.raises(ApiError, match="POST /sites/lyon/jobs: 400 Bad Request: There are not enough resources"):
        await c.submit_job(request(site="lyon"))
    with pytest.raises(ApiError, match="DELETE /sites/nancy/jobs/1: 404"):
        await c.cancel_job("nancy", 1)


async def test_submit_and_cancel_need_a_whole_request() -> None:
    c = Client("https://api.test/stable", transport=recording_api([]))
    with pytest.raises(ValueError):
        await c.submit_job(request(nodes=0))
    with pytest.raises(ValueError):
        await c.cancel_job("", 4710)


def test_login(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USER", "bob")
    assert Client(user="alice").login() == "alice"
    assert Client().login() == "bob"


def test_submit_command() -> None:
    cmd = Client().submit_command(request())
    assert cmd.startswith("curl -X POST https://api.grid5000.fr/stable/sites/nancy/jobs -H 'Content-Type: application/json' -d '{")


def test_summary() -> None:
    assert request(project="my-lab").summary() == (
        "2 node(s) of gros at nancy, from Sun 22 Nov 17:00, for 2h30 · queue default · project my-lab · deploy"
    )
    assert "as soon as possible" in request(start=None).summary()
