"""Signal-flip prices: the nearest next-session close that would change each horizon's
signal, with every other input held as it is.

The search appends one hypothetical session at a trial close (volume, trades and
delivery at their 20-session averages; the comparison indices unchanged), recomputes
every metric and the scorecard exactly as a real run does, and steps away from the
last close until a signal changes. Bisection then narrows down the price. It answers
"what would have to happen for this to read differently", not "where will it go".
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from datetime import timedelta
from statistics import fmean

from atrader.analytics.metrics import pack_metrics
from atrader.analytics.scoring import base_scores, build_scorecard, score_pillars
from atrader.contracts import (
    AgentReport,
    EvidencePack,
    Horizon,
    HorizonNote,
    PriceBar,
    Scorecard,
    Signal,
    SignalFlip,
    Veto,
)

STEP_PCT = 1.0
MAX_PCT = 20.0
REFINE_STEPS = 5  # bisection halvings after a 1% step: about 0.03% precision
_AVERAGE_OVER = 20

_RANK = {Signal.STRONG_BEARISH: 0, Signal.BEARISH: 1, Signal.NEUTRAL: 2, Signal.BULLISH: 3,
         Signal.STRONG_BULLISH: 4}


def signal_flips(pack: EvidencePack, card: Scorecard, reports: Mapping[str, AgentReport],
                 vetoes: list[Veto], notes: Iterable[HorizonNote] = ()) -> list[SignalFlip]:
    if not pack.bars:
        return []
    notes = list(notes)
    now = {h.horizon: _RANK[h.signal] for h in card.horizons if h.signal in _RANK}
    close = pack.bars[-1].close

    def signals_at(price: float) -> dict[Horizon, Signal]:
        trial = _with_next_session(pack, price)
        pillars = score_pillars(base_scores(trial), dict(reports))
        trial_card = build_scorecard(trial, pillars, vetoes, notes)
        return {h.horizon: h.signal for h in trial_card.horizons}

    flips: list[SignalFlip] = []
    top = max(_RANK.values())
    for direction, sign in (("up", 1), ("down", -1)):
        # A signal already at the end of the scale cannot move further that way.
        pending = {h: rank for h, rank in now.items() if 0 <= rank + sign <= top}
        previous = close
        steps = int(MAX_PCT / STEP_PCT)
        for step in range(1, steps + 1):
            if not pending:
                break
            price = close * (1 + sign * step * STEP_PCT / 100)
            signals = signals_at(price)
            for horizon in [h for h in pending if _moved(signals[h], now[h], sign)]:
                exact, signal = _refine(signals_at, horizon, now[horizon], sign, previous,
                                        price, signals[horizon])
                flips.append(SignalFlip(horizon=horizon, direction=direction, price=exact,
                                        signal=signal, searched_pct=MAX_PCT))
                del pending[horizon]
            previous = price
        flips += [SignalFlip(horizon=h, direction=direction, price=None, searched_pct=MAX_PCT)
                  for h in pending]
    order = list(Horizon)
    return sorted(flips, key=lambda f: (order.index(f.horizon), f.direction != "up"))


def _moved(signal: Signal, rank_now: int, sign: int) -> bool:
    rank = _RANK.get(signal)
    return rank is not None and (rank - rank_now) * sign > 0


def _refine(signals_at: Callable[[float], dict[Horizon, Signal]], horizon: Horizon,
            rank_now: int, sign: int, unchanged: float, changed: float,
            signal: Signal) -> tuple[float, Signal]:
    """Narrow the interval between a price that keeps the signal and one that moves it."""
    for _ in range(REFINE_STEPS):
        middle = (unchanged + changed) / 2
        signal_middle = signals_at(middle)[horizon]
        if _moved(signal_middle, rank_now, sign):
            changed, signal = middle, signal_middle
        else:
            unchanged = middle
    return changed, signal


def _with_next_session(pack: EvidencePack, price: float) -> EvidencePack:
    bars = pack.bars
    last, recent = bars[-1], bars[-_AVERAGE_OVER:]
    session = last.session + timedelta(days=1)
    while session.weekday() >= 5:
        session += timedelta(days=1)
    volume = round(fmean(b.volume for b in recent))
    trades = [b.trades for b in recent if b.trades]
    delivery = [b.delivery_pct for b in recent if b.delivery_pct is not None]
    trial = PriceBar(
        session=session, open=last.close, high=max(last.close, price),
        low=min(last.close, price), close=price, prev_close=last.close, volume=volume,
        turnover_inr=price * volume, trades=round(fmean(trades)) if trades else None,
        delivery_pct=fmean(delivery) if delivery else None, provider=last.provider,
        adjustment=last.adjustment)
    indices = tuple(index.model_copy(update={"closes": (*index.closes,
                                                        (session, index.closes[-1][1]))})
                    if index.closes else index for index in pack.indices)
    new_bars = (*bars, trial)
    metrics = pack_metrics(new_bars, pack.facts, indices, levels=False)
    return pack.model_copy(update={"bars": new_bars, "indices": indices,
                                   "metrics": tuple(metrics)})
