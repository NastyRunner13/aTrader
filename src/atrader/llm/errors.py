"""Gateway errors. Only `QuotaExhausted` pauses a run; the others fail one node."""

from __future__ import annotations


class GatewayError(RuntimeError):
    pass


class QuotaExhausted(GatewayError):
    """The daily request allowance is used up. The run checkpoints and can resume."""


class RunBudgetExceeded(GatewayError):
    """This run reached its hard attempt cap (planned calls + retries + repairs)."""


class ModelNotAllowed(GatewayError):
    """The model is not an eligible zero-cost route under the free-only policy."""


class UnexpectedCharge(GatewayError):
    """A call reported a nonzero cost. The route is disabled pending investigation."""


class ProviderError(GatewayError):
    """The provider failed, timed out or returned an unusable response."""


class AuthError(GatewayError):
    """The API key is missing or rejected."""
