"""Free-only policy, budgets, structured-output repair and charge detection.

OpenRouter is replaced by an httpx MockTransport, so these tests never spend quota.
"""

from __future__ import annotations

import json

import httpx
import pytest
from pydantic import BaseModel

from atrader.llm import (
    ModelNotAllowed,
    OpenRouterGateway,
    QuotaExhausted,
    RunBudget,
    RunBudgetExceeded,
    UnexpectedCharge,
)
from atrader.llm.openrouter import OpenRouterClient
from atrader.llm.policy import FreeModelPolicy, ModelInfo, ineligibility_reason
from atrader.llm.structured import extract_json
from atrader.llm.usage import UsageLedger

FREE = ModelInfo(id="vendor/model:free", pricing={"prompt": "0", "completion": "0"},
                 supported_parameters=("structured_outputs", "reasoning"))


class Answer(BaseModel):
    stance: str
    score: int


@pytest.mark.parametrize(("model", "reason_fragment"), [
    (FREE, None),
    (ModelInfo(id="openrouter/free", pricing={"prompt": "0", "completion": "0"}), None),
    (ModelInfo(id="vendor/paid", pricing={"prompt": "0.000001", "completion": "0"}), "nonzero"),
    (ModelInfo(id="vendor/x:free", pricing={"prompt": "0", "request": "0.01"}), "request"),
    (ModelInfo(id="vendor/stealth", pricing={"prompt": "0", "completion": "0"}), "explicit"),
    (ModelInfo(id="vendor/unknown:free", pricing={}), "unknown"),
    (ModelInfo(id="openrouter/auto", pricing={"prompt": "0"}), "auto"),
    (ModelInfo(id="vendor/music:free", pricing={"prompt": "0"}, output_modalities=("audio",)),
     "text"),
])
def test_free_only_policy(model, reason_fragment):
    reason = ineligibility_reason(model)
    if reason_fragment is None:
        assert reason is None
    else:
        assert reason is not None and reason_fragment in reason


def test_allowlist_admits_reviewed_zero_priced_model():
    stealth = ModelInfo(id="vendor/stealth", pricing={"prompt": "0", "completion": "0"})
    assert ineligibility_reason(stealth, frozenset({"vendor/stealth"})) is None


def test_extract_json_tolerates_fences_and_prose():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Sure! Here it is: {"a": 2} hope that helps') == {"a": 2}


def _gateway(tmp_path, responses, cap=5, daily=50):
    sent = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        status, body = responses.pop(0)
        return httpx.Response(status, json=body)

    client = OpenRouterClient("test-key", "https://openrouter.test/api/v1", 5,
                              transport=httpx.MockTransport(handler))
    ledger = UsageLedger(tmp_path / "usage.sqlite3", daily)
    gateway = OpenRouterGateway(
        run_id="run-1", client=client, policy=FreeModelPolicy([FREE]), ledger=ledger,
        budget=RunBudget(cap), models={"quick": FREE.id, "deep": FREE.id},
        max_output_tokens=100, temperature=0, max_concurrency=1, reasoning_effort="low")
    return gateway, sent, ledger


def _ok(content: str, cost: float = 0.0, finish_reason: str = "stop"):
    return 200, {"model": FREE.id, "provider": "Test", "choices": [
        {"message": {"content": content}, "finish_reason": finish_reason}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": cost}}


def test_valid_structured_output_in_one_call(tmp_path):
    gateway, sent, ledger = _gateway(tmp_path, [_ok('{"stance": "mixed", "score": 3}')])
    result = gateway.structured(node="n", tier="quick", system="s", user="u", schema=Answer)
    assert result.value == Answer(stance="mixed", score=3)
    assert len(sent) == 1 and sent[0]["response_format"]["type"] == "json_schema"
    assert "models" not in sent[0]  # never ask OpenRouter for model fallbacks
    assert ledger.used_today() == 1


def test_invalid_output_gets_one_repair(tmp_path):
    gateway, sent, ledger = _gateway(tmp_path, [_ok('{"stance": "mixed"}'),
                                                _ok('{"stance": "mixed", "score": 1}')])
    result = gateway.structured(node="n", tier="quick", system="s", user="u", schema=Answer)
    assert result.value is not None and len(result.call_ids) == 2
    assert "did not validate" in sent[1]["messages"][-1]["content"]
    statuses = [c.status for c in ledger.calls_for_run("run-1")]
    assert statuses.count("invalid_output") == 1


def test_run_cap_stops_further_attempts(tmp_path):
    gateway, _, _ = _gateway(tmp_path, [_ok("{}"), _ok("{}")], cap=2)
    result = gateway.structured(node="n", tier="quick", system="s", user="u", schema=Answer)
    assert result.value is None
    with pytest.raises(RunBudgetExceeded):
        gateway.structured(node="n", tier="quick", system="s", user="u", schema=Answer)


def test_daily_allowance_is_enforced_locally(tmp_path):
    gateway, sent, _ = _gateway(tmp_path, [_ok('{"stance": "a", "score": 1}')], daily=1)
    gateway.structured(node="n", tier="quick", system="s", user="u", schema=Answer)
    with pytest.raises(QuotaExhausted):
        gateway.structured(node="n", tier="quick", system="s", user="u", schema=Answer)
    assert len(sent) == 1


def test_provider_daily_limit_pauses(tmp_path):
    gateway, _, _ = _gateway(tmp_path, [(429, {"error": {
        "message": "Rate limit exceeded: free-models-per-day"}})])
    with pytest.raises(QuotaExhausted):
        gateway.structured(node="n", tier="quick", system="s", user="u", schema=Answer)


def test_reported_cost_disables_the_route(tmp_path):
    gateway, _, _ = _gateway(tmp_path, [_ok('{"stance": "a", "score": 1}', cost=0.002)])
    with pytest.raises(UnexpectedCharge):
        gateway.structured(node="n", tier="quick", system="s", user="u", schema=Answer)
    with pytest.raises(ModelNotAllowed):
        gateway.structured(node="n", tier="quick", system="s", user="u", schema=Answer)


def test_unlisted_model_is_rejected_before_any_request(tmp_path):
    gateway, sent, _ = _gateway(tmp_path, [])
    gateway._models["deep"] = "vendor/paid-model"
    with pytest.raises(ModelNotAllowed):
        gateway.structured(node="n", tier="deep", system="s", user="u", schema=Answer)
    assert sent == []


def test_reasoning_is_bounded_and_hidden_when_supported(tmp_path):
    gateway, sent, _ = _gateway(tmp_path, [_ok('{"stance": "a", "score": 1}')])
    gateway.structured(node="n", tier="quick", system="s", user="u", schema=Answer)
    assert sent[0]["reasoning"] == {"exclude": True, "effort": "low"}


def test_truncated_answer_is_not_repaired(tmp_path):
    gateway, sent, ledger = _gateway(tmp_path, [_ok("", finish_reason="length")])
    result = gateway.structured(node="n", tier="quick", system="s", user="u", schema=Answer)
    assert result.value is None and "cut off" in (result.error or "")
    assert len(sent) == 1  # the repair would hit the same limit, so none is sent
    assert [c.status for c in ledger.calls_for_run("run-1")] == ["invalid_output"]
