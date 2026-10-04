"""Free-only model policy (docs/08, "Zero-cost gateway policy").

A model is eligible only if the live catalog reports zero for every price component
and it is an explicit free route (`:free` suffix or `openrouter/free`), unless the
user has reviewed and allowlisted a zero-priced ID. Unknown pricing fails closed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from atrader.llm.errors import ModelNotAllowed

FREE_ROUTER = "openrouter/free"
NEVER_ALLOWED = frozenset({"openrouter/auto"})  # may route to paid models


@dataclass(frozen=True)
class ModelInfo:
    id: str
    name: str = ""
    context_length: int | None = None
    pricing: dict[str, Any] = field(default_factory=dict)
    supported_parameters: tuple[str, ...] = ()
    output_modalities: tuple[str, ...] = ("text",)

    @classmethod
    def from_api(cls, row: dict[str, Any]) -> ModelInfo:
        architecture = row.get("architecture") or {}
        return cls(
            id=row["id"],
            name=row.get("name", ""),
            context_length=row.get("context_length"),
            pricing=dict(row.get("pricing") or {}),
            supported_parameters=tuple(row.get("supported_parameters") or ()),
            output_modalities=tuple(architecture.get("output_modalities") or ("text",)),
        )

    @property
    def supports_json_schema(self) -> bool:
        return "structured_outputs" in self.supported_parameters

    @property
    def supports_json_mode(self) -> bool:
        return "response_format" in self.supported_parameters

    @property
    def supports_reasoning(self) -> bool:
        return "reasoning" in self.supported_parameters


def ineligibility_reason(model: ModelInfo, allowlist: frozenset[str] = frozenset()) -> str | None:
    """None when the model may be used; otherwise the reason it may not."""
    if model.id in NEVER_ALLOWED:
        return "general auto-routing can select paid models"
    if not model.pricing:
        return "pricing is unknown"
    for component, raw in model.pricing.items():
        try:
            if Decimal(str(raw)) != 0:
                return f"nonzero {component} price ({raw})"
        except InvalidOperation:
            return f"unparseable {component} price ({raw!r})"
    if not (model.id.endswith(":free") or model.id == FREE_ROUTER or model.id in allowlist):
        return ("zero-priced but not an explicit free route; review it and add it to "
                "ATRADER_MODEL_ALLOWLIST to use it")
    if "text" not in model.output_modalities:
        return "does not produce text"
    return None


class FreeModelPolicy:
    def __init__(self, catalog: list[ModelInfo], allowlist: frozenset[str] = frozenset()) -> None:
        self._catalog = {m.id: m for m in catalog}
        self._allowlist = allowlist
        self._disabled: dict[str, str] = {}

    def check(self, model_id: str) -> ModelInfo:
        if model_id in self._disabled:
            raise ModelNotAllowed(f"{model_id} disabled: {self._disabled[model_id]}")
        model = self._catalog.get(model_id)
        if model is None:
            raise ModelNotAllowed(f"{model_id} is not in the current OpenRouter catalog")
        reason = ineligibility_reason(model, self._allowlist)
        if reason:
            raise ModelNotAllowed(f"{model_id}: {reason}")
        return model

    def disable(self, model_id: str, reason: str) -> None:
        self._disabled[model_id] = reason

    def eligible(self) -> list[ModelInfo]:
        return sorted(
            (m for m in self._catalog.values()
             if ineligibility_reason(m, self._allowlist) is None and m.id not in self._disabled),
            key=lambda m: m.id,
        )
