"""Structured output: schema instructions, response formats and tolerant JSON parsing.

The local Pydantic validation is authoritative; provider-side schema enforcement is
only a helpful hint, because support varies by endpoint (docs/08).
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel

from atrader.llm.policy import ModelInfo

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class OutputParseError(ValueError):
    pass


def schema_instructions(schema: type[BaseModel]) -> str:
    compact = json.dumps(schema.model_json_schema(), separators=(",", ":"))
    return (
        "Respond with a single JSON object and nothing else: no prose, no markdown fences. "
        f"It must validate against this JSON Schema:\n{compact}"
    )


def response_format_for(model: ModelInfo, schema: type[BaseModel]) -> dict[str, Any] | None:
    if model.supports_json_schema:
        return {"type": "json_schema", "json_schema": {
            "name": schema.__name__, "strict": False, "schema": schema.model_json_schema()}}
    if model.supports_json_mode:
        return {"type": "json_object"}
    return None


def extract_json(text: str) -> Any:
    cleaned = _FENCE.sub("", text.strip()).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        raise OutputParseError("no JSON object found in the response")
    try:
        return json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError as exc:
        raise OutputParseError(f"invalid JSON: {exc.msg} at char {exc.pos}") from exc


def parse_output[T: BaseModel](text: str, schema: type[T]) -> T:
    if not text:
        raise OutputParseError("empty response")
    return schema.model_validate(extract_json(text))
