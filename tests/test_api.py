"""The web API end to end, offline: a fake evidence source and placeholder model output.
Runs happen on a background thread, so tests wait for them to settle."""

from __future__ import annotations

import json
import threading
import time

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from atrader.api.app import create_app
from atrader.config import Settings
from atrader.contracts import Listing, ResearchRequest, RunStatus
from atrader.data.providers.nse_instruments import InstrumentMaster
from atrader.data.store import MarketStore
from atrader.graph.research_graph import ResearchGraph
from atrader.graph.run_registry import RunRegistry
from tests.conftest import LISTING, StaticEvidence, make_bars, make_pack

ORIGIN = "http://localhost:3000"
OTHER = Listing(symbol="OTHERCO", isin="INE000O01011", name="Other Industries Limited")


class GatedEvidence(StaticEvidence):
    """Holds the data steward until the test lets it go."""

    def __init__(self) -> None:
        super().__init__(make_pack())
        self.entered = threading.Event()
        self.release = threading.Event()

    def build(self, request):
        self.entered.set()
        assert self.release.wait(10), "the test never released the evidence source"
        return super().build(request)


def make_client(tmp_path, evidence=None, **overrides):
    options = {"openrouter_api_key": None, "api_hosts": ["testserver"], **overrides}
    settings = Settings(_env_file=None, data_dir=tmp_path / "data",
                        reports_dir=tmp_path / "reports", **options)
    evidence = evidence or StaticEvidence(make_pack())
    app = create_app(
        settings, load_master=lambda: InstrumentMaster([LISTING, OTHER]),
        make_graph=lambda **kw: ResearchGraph(settings, evidence_source=evidence, **kw))
    return TestClient(app), settings, evidence


@pytest.fixture
def client(tmp_path):
    return make_client(tmp_path)[0]


def settled(client, run_id, timeout=15.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = client.get(f"/v1/runs/{run_id}").json()
        if run["status"] not in ("queued", "running"):
            return run
        time.sleep(0.05)
    raise AssertionError(f"run {run_id} did not settle: {run}")


def start(client, **body):
    response = client.post("/v1/runs", json={"symbol": "TESTCO", "mode": "data_only", **body})
    assert response.status_code == 202, response.text
    return response.json()


# --- search, status ----------------------------------------------------------------------------


def test_search_and_status(client):
    found = client.get("/v1/instruments", params={"query": "test"}).json()
    assert [i["symbol"] for i in found] == ["TESTCO"]
    assert client.get("/v1/instruments", params={"query": ""}).json() == []
    status = client.get("/v1/status").json()
    assert status["model"]["api_key_set"] is False and status["latest_session"] is None
    assert status["usage"]["used_today"] == 0 and status["active_runs"] == 0
    assert client.get("/v1/usage").json()["usable"] == 40


# --- a run, from start to report ------------------------------------------------------------


def test_data_only_run_produces_a_report_the_app_can_read(client):
    queued = start(client)
    assert queued["status"] in ("queued", "running", "completed")
    run = settled(client, queued["run_id"])
    assert run["status"] == "completed" and run["report_id"]
    assert [s["state"] for s in run["stages"]] == ["done", "done"]  # evidence, scorecard

    summaries = client.get("/v1/reports").json()
    assert [s["report_id"] for s in summaries] == [run["report_id"]]
    summary = summaries[0]
    assert summary["symbol"] == "TESTCO" and summary["mode"] == "data_only"
    assert [h["horizon"] for h in summary["horizons"]] == ["1m", "6m", "2y"]
    assert summary["close"] and summary["dry_run"] is False

    report = client.get(f"/v1/reports/{run['report_id']}").json()
    assert report["scorecard"]["levels"]["levels"] and report["pack"]["metrics"]
    assert "bars" not in report["pack"] or report["pack"]["bars"] == []  # served separately
    assert all(not s.get("closes") for s in report["pack"]["indices"])

    evidence_id = report["pack"]["facts"][0]["evidence_id"]
    found = client.get(f"/v1/reports/{run['report_id']}/evidence/{evidence_id}").json()
    assert found["kind"] == "facts" and found["item"]["evidence_id"] == evidence_id
    assert client.get(f"/v1/reports/{run['report_id']}/evidence/F99999").status_code == 404

    card = client.get(f"/v1/reports/{run['report_id']}/export", params={"format": "card"})
    assert card.status_code == 200 and "Signal" in card.text
    export = client.get(f"/v1/reports/{run['report_id']}/export", params={"format": "json"})
    assert json.loads(export.text)["run_id"] == run["run_id"]


def test_report_ids_cannot_reach_other_files(client, tmp_path):
    (tmp_path / "secret.json").write_text("{}")
    for bad in ("..%2Fsecret", "..\\secret", "secret"):
        assert client.get(f"/v1/reports/{bad}").status_code == 404
        assert client.get(f"/v1/reports/{bad}/export").status_code == 404


def test_events_replay_every_step_and_end_with_the_outcome(client):
    run = settled(client, start(client, mode="compact", dry_run=True)["run_id"])
    assert run["status"] == "completed"
    assert [s["state"] for s in run["stages"]] == ["done"] * 5

    with client.stream("GET", f"/v1/runs/{run['run_id']}/events") as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        lines = [line for line in response.iter_lines() if line.startswith("data: ")]
    events = [json.loads(line.removeprefix("data: ")) for line in lines]
    assert [e["id"] for e in events] == list(range(1, len(events) + 1))
    started = {e["node"] for e in events if e["type"] == "node" and e["phase"] == "start"}
    assert {"data_steward", "market_analyst", "bull_researcher", "portfolio_manager",
            "finalize"} <= started
    assert events[-1]["type"] == "end" and events[-1]["report_id"] == run["report_id"]

    with client.stream("GET", f"/v1/runs/{run['run_id']}/events",
                       headers={"Last-Event-ID": str(len(events) - 1)}) as response:
        replay = [line for line in response.iter_lines() if line.startswith("data: ")]
    assert len(replay) == 1 and json.loads(replay[0].removeprefix("data: "))["type"] == "end"


def test_dry_run_reports_are_flagged(client):
    run = settled(client, start(client, mode="compact", dry_run=True)["run_id"])
    assert run["dry_run"] is True
    assert client.get("/v1/reports").json()[0]["dry_run"] is True


def test_unknown_symbol_and_future_cutoff_are_rejected(client):
    assert client.post("/v1/runs", json={"symbol": "NOPE", "mode": "data_only"}).status_code == 404
    future = client.post("/v1/runs", json={"symbol": "TESTCO", "mode": "data_only",
                                           "cutoff": "2999-01-01"})
    assert future.status_code == 422 and future.json()["code"] == "bad_cutoff"


def test_model_runs_need_a_key_and_quota(tmp_path):
    client, *_ = make_client(tmp_path)
    refused = client.post("/v1/runs", json={"symbol": "TESTCO", "mode": "compact"})
    assert refused.status_code == 409 and refused.json()["code"] == "no_api_key"

    client, *_ = make_client(tmp_path / "b", openrouter_api_key=SecretStr("k"),
                             daily_request_limit=10, daily_request_reserve=5)
    refused = client.post("/v1/runs", json={"symbol": "TESTCO", "mode": "compact"})
    assert refused.status_code == 409 and refused.json()["code"] == "quota"
    # data-only needs neither
    assert client.post("/v1/runs", json={"symbol": "TESTCO", "mode": "data_only"}
                       ).status_code == 202


# --- queueing, cancel, resume ---------------------------------------------------------------


def test_identical_runs_are_not_started_twice(tmp_path):
    client, _, evidence = make_client(tmp_path, GatedEvidence())
    first = start(client)
    assert evidence.entered.wait(5)
    assert start(client)["run_id"] == first["run_id"]
    assert client.get("/v1/status").json()["active_runs"] == 1
    other = client.post("/v1/runs", json={"symbol": "OTHERCO", "mode": "data_only"}).json()
    assert other["run_id"] != first["run_id"] and other["status"] == "queued"
    evidence.release.set()
    assert settled(client, first["run_id"])["status"] == "completed"
    assert settled(client, other["run_id"])["status"] == "completed"


def test_the_queue_has_a_limit(tmp_path):
    client, _, evidence = make_client(tmp_path, GatedEvidence(), max_queued_runs=2)
    start(client)
    assert evidence.entered.wait(5)
    start(client, cutoff="2026-09-01")
    full = client.post("/v1/runs", json={"symbol": "TESTCO", "mode": "data_only",
                                         "cutoff": "2026-08-01"})
    assert full.status_code == 409 and full.json()["code"] == "queue_full"
    evidence.release.set()


def test_cancel_stops_the_run_and_resume_continues_it(tmp_path):
    client, _, evidence = make_client(tmp_path, GatedEvidence())
    run_id = start(client)["run_id"]
    assert evidence.entered.wait(5)
    cancelling = client.post(f"/v1/runs/{run_id}/cancel").json()
    assert cancelling["cancel_requested"] is True
    assert client.post(f"/v1/runs/{run_id}/cancel").status_code == 200  # idempotent
    evidence.release.set()

    cancelled = settled(client, run_id)
    assert cancelled["status"] == "cancelled" and cancelled["report_id"] is None
    assert client.post(f"/v1/runs/{run_id}/resume").status_code == 202
    finished = settled(client, run_id)
    assert finished["status"] == "completed" and finished["report_id"]
    assert len(evidence.requests) == 1  # the evidence pack was not collected again
    assert client.post(f"/v1/runs/{run_id}/resume").status_code == 409  # nothing to resume


def test_cancel_and_resume_of_unknown_runs(client):
    assert client.post("/v1/runs/nope/cancel").status_code == 404
    assert client.post("/v1/runs/nope/resume").status_code == 404
    assert client.get("/v1/runs/nope").status_code == 404
    assert client.get("/v1/runs/nope/events").status_code == 404


def test_a_run_lost_in_a_restart_is_marked_failed_and_reports_its_outcome(tmp_path):
    _, settings, _ = make_client(tmp_path)
    registry = RunRegistry(settings.db_path)
    registry.create("lost", ResearchRequest(symbol="TESTCO"), dry_run=False)
    registry.set_status("lost", RunStatus.RUNNING)

    restarted = create_app(settings, load_master=lambda: InstrumentMaster([LISTING]))
    run = TestClient(restarted).get("/v1/runs/lost").json()
    assert run["status"] == "failed" and "interrupted" in run["detail"]
    with TestClient(restarted).stream("GET", "/v1/runs/lost/events") as response:
        lines = [line for line in response.iter_lines() if line.startswith("data: ")]
    assert json.loads(lines[0].removeprefix("data: "))["status"] == "failed"


# --- security --------------------------------------------------------------------------------


def test_changes_from_other_origins_are_refused(client):
    body = {"symbol": "TESTCO", "mode": "data_only"}
    refused = client.post("/v1/runs", json=body, headers={"Origin": "https://evil.example"})
    assert refused.status_code == 403 and refused.json()["code"] == "forbidden_origin"
    assert client.put("/v1/watchlist/TESTCO",
                      headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/v1/runs", json=body, headers={"Origin": ORIGIN}).status_code == 202
    # reading is governed by CORS, which the browser enforces: no Allow-Origin for others
    other = client.get("/v1/status", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in other.headers
    allowed = client.get("/v1/status", headers={"Origin": ORIGIN})
    assert allowed.headers["access-control-allow-origin"] == ORIGIN


def test_unknown_host_names_are_refused(client):
    assert client.get("/v1/status", headers={"Host": "attacker.example"}).status_code == 400


# --- prices and the watchlist -----------------------------------------------------------------


def test_bars_come_adjusted_with_averages_over_earlier_history(tmp_path):
    client, settings, _ = make_client(tmp_path)
    store = MarketStore(settings.db_path)
    store.upsert_bars((LISTING.symbol, "EQ", LISTING.isin, bar) for bar in make_bars(400))
    data = client.get("/v1/instruments/TESTCO/bars", params={"sessions": 100}).json()
    assert len(data["bars"]) == 100 and data["isin"] == LISTING.isin
    assert all(len(values) == 100 for values in data["averages"].values())
    assert data["averages"]["sma200"][0] is not None  # warmed up before the first drawn bar
    assert data["bars"][-1]["session"] > data["bars"][0]["session"]
    assert client.get("/v1/instruments/OTHERCO/bars").status_code == 404  # nothing stored
    assert client.get("/v1/instruments/NOPE/bars").status_code == 404


def test_watchlist_shows_the_quote_and_latest_signal(tmp_path):
    client, settings, _ = make_client(tmp_path)
    MarketStore(settings.db_path).upsert_bars(
        (LISTING.symbol, "EQ", LISTING.isin, bar) for bar in make_bars(30))
    assert client.get("/v1/watchlist").json() == []
    added = client.put("/v1/watchlist/testco", headers={"Origin": ORIGIN})
    assert added.status_code == 200 and added.json()["symbol"] == "TESTCO"
    assert added.json()["quote"]["close"] > 0 and added.json()["latest_report"] is None

    settled(client, start(client)["run_id"])
    item = client.get("/v1/watchlist").json()[0]
    assert item["latest_report"]["horizons"][0]["horizon"] == "1m"
    assert client.put("/v1/watchlist/NOPE").status_code == 404

    assert client.delete("/v1/watchlist/TESTCO").status_code == 204
    assert client.delete("/v1/watchlist/TESTCO").status_code == 404
    assert client.get("/v1/watchlist").json() == []
