"""A deterministic stand-in gateway for tests and `--dry-run`.

It costs nothing and calls no provider. Its default responder writes placeholder
outputs that cite real evidence IDs from the prompt, so the whole graph, verifier
and report can be exercised end to end.
"""

from __future__ import annotations

import re
import threading
import uuid
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from atrader.contracts import (
    AnalystOutput,
    DebateOutput,
    Horizon,
    ModelCall,
    NewsAnalystOutput,
    RiskOutput,
    SynthesisOutput,
)
from atrader.llm.gateway import RunBudget, StructuredResult, Tier
from atrader.timeutil import now_utc

Responder = Callable[[str, type[BaseModel], str], dict[str, Any]]

_EVIDENCE = re.compile(r"\[([FMASNI]\d+)\]")
_CLAIM = re.compile(r"\[(C-[a-z_]+-\d+-\d+|C-[a-z_]+-\d+)\]")


class FakeGateway:
    def __init__(self, run_id: str, responder: Responder | None = None,
                 budget: RunBudget | None = None) -> None:
        self.run_id = run_id
        self._responder = responder or demo_responder
        self._budget = budget
        self._calls: list[ModelCall] = []
        self._lock = threading.Lock()

    def calls(self) -> list[ModelCall]:
        with self._lock:
            return list(self._calls)

    def structured[T: BaseModel](self, *, node: str, tier: Tier, system: str, user: str,
                                 schema: type[T]) -> StructuredResult[T]:
        if self._budget:
            self._budget.acquire(node)
        call_id = f"fake-{node}-{uuid.uuid4().hex[:6]}"
        with self._lock:
            self._calls.append(ModelCall(
                call_id=call_id, run_id=self.run_id, node=node, attempt=1,
                requested_model=f"fake/{tier}", served_model=f"fake/{tier}", status="ok",
                cost=0.0, started_at=now_utc()))
        value = schema.model_validate(self._responder(node, schema, user))
        return StructuredResult(value=value, call_ids=[call_id])


def demo_responder(node: str, schema: type[BaseModel], prompt: str) -> dict[str, Any]:
    ids = list(dict.fromkeys(_EVIDENCE.findall(prompt)))
    first = ids[:2]
    claims = list(dict.fromkeys(_CLAIM.findall(prompt)))
    note = "[dry run: placeholder text, no model was called]"
    if schema is AnalystOutput:
        return {"stance": "mixed", "summary": f"{note} {node} reviewed its evidence sections.",
                "claims": [{"statement": f"{note} Observation grounded in {', '.join(first)}.",
                            "kind": "interpretation", "evidence_ids": first}] if first else [],
                "gaps": []}
    if schema is NewsAnalystOutput:
        disclosures = [i for i in ids if i[0] in "AN"][:1]
        return {"stance": "mixed", "summary": f"{note} {node} reviewed the disclosures.",
                "claims": [], "gaps": [],
                "events": [{"event": f"{note} An event.", "impact": 1, "materiality": "medium",
                            "evidence_ids": disclosures}] if disclosures else []}
    if schema is DebateOutput:
        side = "bull" if "bull" in node else "bear"
        challenges = ([{"target_claim_id": claims[0], "dispute": "assumption",
                        "argument": f"{note} {side} disputes this claim.", "evidence_ids": first}]
                      if claims else [])
        return {"thesis": f"{note} The {side} case.", "claims": [
            {"statement": f"{note} {side} point citing {', '.join(first)}.",
             "kind": "interpretation", "evidence_ids": first}] if first else [],
            "challenges": challenges, "falsifiers": [f"{note} A falsifier for the {side} case."]}
    if schema is RiskOutput:
        return {"verdict": "fair", "objections": [note], "evidence_ids": first,
                "rationale": note}
    if schema is SynthesisOutput:
        return {"summary": note,
                "pros": [{"statement": note, "evidence_ids": first}],
                "cons": [{"statement": note, "evidence_ids": first}],
                "horizons": [{"horizon": h.value, "drivers": [note], "up_if": [note],
                              "down_if": [note]} for h in Horizon],
                "unresolved": [note]}
    raise ValueError(f"demo responder has no answer for {schema.__name__}")
