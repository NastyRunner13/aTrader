"""Display formatting shared by prompts and reports (Indian units)."""

from __future__ import annotations

from decimal import Decimal

CRORE = Decimal(10_000_000)


def indian_grouping(number: Decimal | float, decimals: int = 2) -> str:
    """1234567.8 -> '12,34,567.80' (lakh/crore digit grouping)."""
    value = Decimal(str(number))
    sign = "-" if value < 0 else ""
    text = f"{abs(value):.{decimals}f}"
    whole, _, frac = text.partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups: list[str] = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join([*groups, tail])
    return f"{sign}{whole}.{frac}" if decimals else f"{sign}{whole}"


def format_value(value: Decimal | float | None, unit: str) -> str:
    if value is None:
        return "not reported"
    sign = "-" if float(value) < 0 else ""
    if unit == "INR":
        return f"{sign}₹{indian_grouping(abs(Decimal(str(value))) / CRORE)} cr"
    if unit == "INR/share":
        return f"{sign}₹{abs(float(value)):,.2f}/share"
    if unit == "%":
        return f"{float(value):.2f}%"
    if unit == "pp":
        return f"{float(value):+.2f} pp"
    if unit == "x":
        return f"{float(value):.2f}x"
    if unit == "signal":
        return {1.0: "positive", -1.0: "negative", 0.0: "none"}.get(float(value), str(value))
    if unit == "count":
        return f"{int(value)}"
    if unit == "pure":
        return f"{float(value):.2f}"
    return f"{float(value):,.2f} {unit}".strip()
