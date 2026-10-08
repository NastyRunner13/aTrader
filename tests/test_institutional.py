"""Real response fixtures plus synthetic history: no live access or model requests."""

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest

from atrader.agents import context
from atrader.analytics.institutional import institutional_metrics
from atrader.analytics.metrics import number, resolve_metric_ids
from atrader.analytics.scoring import base_scores
from atrader.contracts import (
    ClaimDraft,
    Coverage,
    EvidencePack,
    InstitutionalActivity,
    SourceRef,
)
from atrader.data.evidence_builder import NseEvidenceBuilder
from atrader.data.http import Fetched, FetchError
from atrader.data.providers.nse_institutional import URLS, collect_activity, parse_activity
from atrader.data.store import MarketStore
from atrader.timeutil import IST, weekdays_back
from atrader.verification import verify_claims
from tests.conftest import make_pack

FIXTURES = Path(__file__).parent / "fixtures"
SESSION = date(2026, 10, 8)
OBSERVED = datetime(2026, 10, 8, 20, tzinfo=IST)


def observation(day=SESSION, *, participant="FPI", scope="nse", basis="provisional", net=100):
    observed = datetime.combine(day, OBSERVED.timetz())
    return InstitutionalActivity(
        session=day, participant=participant, scope=scope, basis=basis,
        purchases_inr=1000 + net, sales_inr=1000, net_inr=net, available_at=observed,
        source=SourceRef(provider="nse.institutional", url=URLS[scope], retrieved_at=observed))


@pytest.mark.parametrize("scope", ["nse", "combined"])
def test_live_response_fixture_preserves_scope_units_and_observation_time(scope):
    payload = json.loads((FIXTURES / f"nse_institutional_{scope}.json").read_text())
    source = SourceRef(provider="nse.institutional", url=URLS[scope], retrieved_at=OBSERVED)
    rows = parse_activity(payload, scope, source)
    assert len(rows) == 2 and {r.participant for r in rows} == {"FPI", "DII"}
    assert all(r.scope == scope and r.basis == "provisional" for r in rows)
    assert rows[0].purchases_inr == pytest.approx(float(payload[0]["buyValue"]) * 1e7)
    assert all(r.available_at == OBSERVED and r.source.published_at is None for r in rows)
    assert next(r for r in rows if r.participant == "FPI").net_inr < 0


@pytest.mark.parametrize("field,value", [
    ("buyValue", "-1"), ("sellValue", "--"), ("netValue", "NaN"),
    ("netValue", "100000"), ("category", "UNKNOWN"), ("date", "10-Oct-2026")])
def test_bad_provider_values_fail_closed(field, value):
    payload = json.loads((FIXTURES / "nse_institutional_nse.json").read_text())
    payload[0][field] = value
    with pytest.raises(ValueError):
        parse_activity(payload, "nse", SourceRef(provider="test", retrieved_at=OBSERVED))


@pytest.mark.parametrize("payload", [[], {}, "error", [None]])
def test_changed_or_empty_payload_is_not_zero_activity(payload):
    with pytest.raises(ValueError):
        parse_activity(payload, "nse", SourceRef(provider="test", retrieved_at=OBSERVED))


def test_collection_keeps_working_scope_when_other_scope_is_blocked(tmp_path):
    client, store = Mock(), MarketStore(tmp_path / "market.db")
    content = (FIXTURES / "nse_institutional_combined.json").read_bytes()

    def fetch(url, **kwargs):
        if url == URLS["nse"]:
            raise FetchError(url, "blocked", 403)
        return Fetched(url, content, OBSERVED, False)

    client.get.side_effect = fetch
    written, errors = collect_activity(client, store)
    assert written == 2 and len(errors) == 1 and errors[0].startswith("nse:")
    rows = store.institutional_activity(SESSION)
    assert len(rows) == 2 and all(r.scope == "combined" for r in rows)
    assert collect_activity(client, store)[0] == 0  # cached capture is idempotent


def test_revisions_are_retained_and_never_backdated(tmp_path):
    store = MarketStore(tmp_path / "market.db")
    original = observation()
    revised = original.model_copy(update={
        "available_at": OBSERVED + timedelta(days=1), "purchases_inr": 1500, "net_inr": 500})
    store.save_institutional_activity([original, revised, observation(scope="combined", net=200)])
    before = store.institutional_activity(SESSION)
    after = store.institutional_activity(SESSION + timedelta(days=1))
    assert next(r for r in before if r.scope == "nse").net_inr == 100
    assert next(r for r in after if r.scope == "nse").net_inr == 500
    assert len(after) == 2  # scopes do not overwrite each other
    assert store.institutional_activity(SESSION - timedelta(days=1)) == []

    old_session = observation(SESSION - timedelta(days=7)).model_copy(
        update={"available_at": OBSERVED})
    store.save_institutional_activity([old_session])
    assert store.institutional_activity(SESSION - timedelta(days=1)) == []


def test_complete_windows_keep_scopes_and_reporting_bases_separate():
    days = weekdays_back(SESSION, 60)
    rows = number([observation(day, scope=scope, net=net) for day in days
                   for scope, net in (("nse", 100), ("combined", 200))]
                  + [observation(day, basis="confirmed", net=50) for day in days], "I")
    metrics = institutional_metrics(rows, days)
    assert len(metrics) == 9
    five = [m for m in metrics if m.name.endswith("_5s")]
    assert {m.value for m in five} == {500, 1000, 250}
    assert all(len(m.inputs) == int(m.name.rsplit("_", 1)[1][:-1]) for m in metrics)
    assert all(m.category == "institutional" for m in metrics)


def test_missing_session_makes_long_window_unknown_instead_of_shortening_it():
    days = weekdays_back(SESSION, 60)
    rows = number([observation(d) for d in days if d != days[-10]], "I")
    metrics = institutional_metrics(rows, days)
    assert [m.value for m in metrics] == [500, None, None]
    assert "59/60" in metrics[-1].detail
    # A known holiday is absent from the trading calendar and is not a missing session.
    calendar = [d for d in days if d != days[-10]]
    assert institutional_metrics(rows, calendar)[1].value == 2000
    # A new market session with no captured activity invalidates even the short window.
    assert all(m.value is None for m in institutional_metrics(
        rows, [*days, SESSION + timedelta(days=1)]))
    assert institutional_metrics(rows, []) == []  # no verified market calendar


def test_duplicate_observations_cannot_be_double_counted():
    with pytest.raises(ValueError, match="one observation"):
        institutional_metrics([observation(), observation()], [SESSION])


def test_builder_historical_cutoff_uses_only_stored_observations(settings, monkeypatch):
    monkeypatch.setattr("atrader.data.evidence_builder.today_ist", lambda: date(2026, 10, 9))
    store, client = MarketStore(settings.db_path), Mock()
    store.save_institutional_activity([observation()])
    builder = NseEvidenceBuilder(client, store, settings)
    rows, metrics, coverage = builder._institutional(SESSION - timedelta(days=1))
    assert rows == [] and metrics == [] and coverage.status == Coverage.MISSING
    client.get.assert_not_called()


def test_institutional_evidence_is_citable_and_does_not_move_base_scores():
    rows = number([observation()], "I")
    pack = make_pack()
    enriched = pack.model_copy(update={
        "institutional_activity": tuple(rows),
        "metrics": tuple(resolve_metric_ids([*pack.metrics,
                                               *institutional_metrics(rows, [SESSION])]))})
    assert "I1" in enriched.evidence_ids()
    claims = verify_claims([ClaimDraft(statement="Net activity was INR 100.", kind="fact",
                                       evidence_ids=["I1"])], enriched, "market", "market")
    assert claims[0].status == "supported"
    assert "market-wide" in context.institutional(enriched)
    assert base_scores(enriched) == base_scores(pack)
    old = pack.model_dump(exclude={"institutional_activity"})
    assert EvidencePack.model_validate(old).institutional_activity == ()
