"""Model access: the free-only OpenRouter gateway and a fake gateway for tests."""

from atrader.llm.errors import (
    AuthError,
    GatewayError,
    ModelNotAllowed,
    ProviderError,
    QuotaExhausted,
    RunBudgetExceeded,
    UnexpectedCharge,
)
from atrader.llm.gateway import (
    LLM,
    LLMGateway,
    OpenRouterGateway,
    RunBudget,
    StructuredResult,
    Tier,
)

__all__ = [
    "LLM",
    "AuthError",
    "GatewayError",
    "LLMGateway",
    "ModelNotAllowed",
    "OpenRouterGateway",
    "ProviderError",
    "QuotaExhausted",
    "RunBudget",
    "RunBudgetExceeded",
    "StructuredResult",
    "Tier",
    "UnexpectedCharge",
]
