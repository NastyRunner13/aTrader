"""The single path to a model. Agents never talk to a provider directly.

Responsibilities (docs/08): free-only routing, a hard per-run attempt cap shared by
retries and repairs, the persistent daily allowance, bounded concurrency, local
schema validation with at most one repair, and a record of every attempt.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Protocol

from pydantic import BaseModel, ValidationError

from atrader.contracts import ModelCall
from atrader.llm.errors import (
    GatewayError,
    ProviderError,
    QuotaExhausted,
    RunBudgetExceeded,
    UnexpectedCharge,
)
from atrader.llm.openrouter import ChatResponse, OpenRouterClient, RateLimited
from atrader.llm.policy import FreeModelPolicy, ModelInfo
from atrader.llm.structured import (
    OutputParseError,
    parse_output,
    response_format_for,
    schema_instructions,
)
from atrader.llm.usage import UsageLedger
from atrader.timeutil import now_utc

logger = logging.getLogger(__name__)

Tier = Literal["quick", "deep"]


@dataclass
class StructuredResult[T: BaseModel]:
    value: T | None
    call_ids: list[str] = field(default_factory=list)
    error: str | None = None


class LLMGateway(Protocol):
    """Implemented by `OpenRouterGateway` and `FakeGateway`."""

    run_id: str

    def structured[T: BaseModel](self, *, node: str, tier: Tier, system: str, user: str,
                                 schema: type[T]) -> StructuredResult[T]: ...

    def calls(self) -> list[ModelCall]: ...


class LLM:
    """A gateway bound to one model tier. Agents receive one of these as `llm`, the
    way TradingAgents passes `quick_thinking_llm` or `deep_thinking_llm`."""

    def __init__(self, gateway: LLMGateway, tier: Tier) -> None:
        self._gateway = gateway
        self.tier = tier

    def structured[T: BaseModel](self, *, node: str, system: str, user: str,
                                 schema: type[T]) -> StructuredResult[T]:
        return self._gateway.structured(node=node, tier=self.tier, system=system, user=user,
                                        schema=schema)


class RunBudget:
    """Thread-safe hard cap on dispatched attempts for one run."""

    def __init__(self, cap: int, already_used: int = 0) -> None:
        self.cap = cap
        self._used = already_used
        self._lock = threading.Lock()

    @property
    def used(self) -> int:
        return self._used

    def acquire(self, node: str) -> None:
        with self._lock:
            if self._used >= self.cap:
                raise RunBudgetExceeded(f"{node}: run attempt cap of {self.cap} reached")
            self._used += 1


class OpenRouterGateway:
    def __init__(
        self,
        *,
        run_id: str,
        client: OpenRouterClient,
        policy: FreeModelPolicy,
        ledger: UsageLedger,
        budget: RunBudget,
        models: dict[Tier, str],
        max_output_tokens: int,
        temperature: float,
        max_concurrency: int,
        reasoning_effort: str | None = None,
    ) -> None:
        self.run_id = run_id
        self._client = client
        self._policy = policy
        self._ledger = ledger
        self._budget = budget
        self._models = models
        self._max_tokens = max_output_tokens
        self._temperature = temperature
        self._reasoning_effort = reasoning_effort
        self._semaphore = threading.Semaphore(max_concurrency)

    def calls(self) -> list[ModelCall]:
        return self._ledger.calls_for_run(self.run_id)

    def structured[T: BaseModel](self, *, node: str, tier: Tier, system: str, user: str,
                                 schema: type[T]) -> StructuredResult[T]:
        model = self._policy.check(self._models[tier])
        messages = [
            {"role": "system", "content": f"{system}\n\n{schema_instructions(schema)}"},
            {"role": "user", "content": user},
        ]
        result: StructuredResult[T] = StructuredResult(value=None)
        for attempt in (1, 2):  # initial answer + one schema repair
            call_id, response = self._dispatch(node, model, messages, schema, attempt)
            result.call_ids.append(call_id)
            if response.truncated:
                # Resending the same prompt hits the same limit, so no repair is spent.
                problem = (f"answer cut off at {self._max_tokens} output tokens "
                           f"({response.completion_tokens} used, finish_reason="
                           f"{response.finish_reason}); raise ATRADER_MAX_OUTPUT_TOKENS or "
                           "lower ATRADER_REASONING_EFFORT")
                result.error = problem
                self._mark_invalid(call_id, problem)
                return result
            try:
                result.value = parse_output(response.content, schema)
                result.error = None
                return result
            except (OutputParseError, ValidationError) as exc:
                problem = _short_error(exc)
                result.error = f"invalid output: {problem}"
                self._mark_invalid(call_id, problem)
                messages = [*messages,
                            {"role": "assistant", "content": response.content[:4000]},
                            {"role": "user", "content": "Your answer did not validate: "
                             f"{problem}. Return only the corrected JSON object."}]
        return result

    # --- internals -----------------------------------------------------------------------

    def _dispatch(self, node: str, model: ModelInfo, messages: list[dict[str, str]],
                  schema: type[BaseModel], attempt: int) -> tuple[str, ChatResponse]:
        """One logical attempt; a single paced retry for transient provider errors."""
        last_error: GatewayError | None = None
        for transient_try in range(2):
            self._budget.acquire(node)
            call_id = f"{self.run_id[:8]}-{node}-{uuid.uuid4().hex[:6]}"
            started, clock = now_utc(), time.monotonic()
            with self._ledger.slot(), self._semaphore:
                try:
                    response = self._client.chat(
                        model=model.id, messages=messages, max_tokens=self._max_tokens,
                        temperature=self._temperature,
                        response_format=response_format_for(model, schema),
                        reasoning=self._reasoning_for(model),
                    )
                except QuotaExhausted:
                    self._record(call_id, node, attempt, model.id, started, clock, "error",
                                 error="daily quota exhausted")
                    raise
                except (RateLimited, ProviderError) as exc:
                    self._record(call_id, node, attempt, model.id, started, clock, "error",
                                 error=str(exc)[:300])
                    last_error = exc
                    time.sleep(4 if isinstance(exc, RateLimited) else 1)
                    logger.warning("%s attempt failed (%s); retry %d", node, exc, transient_try)
                    continue
            self._record(call_id, node, attempt, model.id, started, clock, "ok", response=response)
            if response.cost:
                self._policy.disable(model.id, f"reported cost {response.cost}")
                raise UnexpectedCharge(f"{model.id} reported a cost of {response.cost}; "
                                       "route disabled")
            return call_id, response
        assert last_error is not None
        raise last_error

    def _reasoning_for(self, model: ModelInfo) -> dict[str, object] | None:
        if not model.supports_reasoning:
            return None
        settings: dict[str, object] = {"exclude": True}
        if self._reasoning_effort:
            settings["effort"] = self._reasoning_effort
        return settings

    def _record(self, call_id: str, node: str, attempt: int, model: str, started: datetime,
                clock: float, status: Literal["ok", "invalid_output", "error", "blocked"], *,
                response: ChatResponse | None = None, error: str | None = None) -> None:
        self._ledger.record(ModelCall(
            call_id=call_id, run_id=self.run_id, node=node, attempt=attempt,
            requested_model=model,
            served_model=response.served_model if response else None,
            provider=response.provider if response else None,
            prompt_tokens=response.prompt_tokens if response else None,
            completion_tokens=response.completion_tokens if response else None,
            cost=response.cost if response else None,
            status=status, error=error, latency_ms=int((time.monotonic() - clock) * 1000),
            started_at=started,
        ))

    def _mark_invalid(self, call_id: str, problem: str) -> None:
        for call in self._ledger.calls_for_run(self.run_id):
            if call.call_id == call_id:
                self._ledger.record(call.model_copy(update={"status": "invalid_output",
                                                            "error": problem[:300]}))
                return


def _short_error(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        parts = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()[:5]]
        return "; ".join(parts)
    return str(exc)[:300]
