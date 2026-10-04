"""Minimal OpenRouter HTTP client. All policy decisions live in the gateway."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from atrader.llm.errors import AuthError, ProviderError, QuotaExhausted
from atrader.llm.policy import ModelInfo


class RateLimited(ProviderError):
    """Per-minute throttling; worth one paced retry."""


@dataclass(frozen=True)
class ChatResponse:
    content: str
    served_model: str | None
    provider: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    cost: float | None
    finish_reason: str | None = None

    @property
    def truncated(self) -> bool:
        """The answer was cut off by the output-token cap (often spent on reasoning)."""
        return self.finish_reason == "length" or not self.content


class OpenRouterClient:
    def __init__(self, api_key: str | None, base_url: str, timeout_s: float,
                 transport: httpx.BaseTransport | None = None) -> None:
        headers = {"HTTP-Referer": "https://localhost/atrader", "X-Title": "aTrader"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._has_key = bool(api_key)
        self._client = httpx.Client(base_url=base_url, timeout=timeout_s, headers=headers,
                                    transport=transport)

    def close(self) -> None:
        self._client.close()

    def list_models(self) -> list[ModelInfo]:
        response = self._client.get("/models")
        _raise_for_status(response)
        return [ModelInfo.from_api(row) for row in response.json().get("data", [])]

    def key_info(self) -> dict[str, Any]:
        response = self._client.get("/key")
        _raise_for_status(response)
        data: dict[str, Any] = response.json().get("data", {})
        return data

    def chat(self, *, model: str, messages: list[dict[str, str]], max_tokens: int,
             temperature: float, response_format: dict[str, Any] | None,
             reasoning: dict[str, Any] | None = None) -> ChatResponse:
        if not self._has_key:
            raise AuthError("OPENROUTER_API_KEY is not set")
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "usage": {"include": True},
        }
        if response_format:
            body["response_format"] = response_format
        if reasoning:
            body["reasoning"] = reasoning
        try:
            response = self._client.post("/chat/completions", json=body)
        except httpx.TimeoutException as exc:
            raise ProviderError("timed out; the provider may still have processed the call") \
                from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"network error: {exc.__class__.__name__}") from exc
        _raise_for_status(response)
        payload = response.json()
        if payload.get("error"):
            raise ProviderError(str(payload["error"].get("message", payload["error"]))[:300])
        choices = payload.get("choices") or []
        if not choices:
            raise ProviderError("response contained no choices")
        message = choices[0].get("message") or {}
        usage = payload.get("usage") or {}
        return ChatResponse(
            content=(message.get("content") or "").strip(),
            served_model=payload.get("model"),
            provider=payload.get("provider"),
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            cost=usage.get("cost"),
            finish_reason=choices[0].get("finish_reason"),
        )


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code < 400:
        return
    text = response.text[:400]
    if response.status_code in (401, 403):
        raise AuthError(f"OpenRouter rejected the key (HTTP {response.status_code})")
    if response.status_code == 402:
        raise ProviderError("payment required: the route is not free for this account")
    if response.status_code == 429:
        if "per-day" in text or "per day" in text or "daily" in text.lower():
            raise QuotaExhausted(f"OpenRouter daily free-model limit reached: {text}")
        raise RateLimited(f"rate limited: {text}")
    raise ProviderError(f"HTTP {response.status_code}: {text}")
