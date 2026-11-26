"""Pure SMA-crossover maths. No network, no Kite: easy to read and to test.

Vocabulary
  SMA (simple moving average): the average close of the last N days.
  Bullish crossover: the short SMA moves from below the long SMA to above it.
  Bearish crossover: the short SMA moves from above the long SMA to below it.
"""

from typing import List, Optional, Sequence, Tuple


def sma(values: Sequence[float], period: int) -> List[Optional[float]]:
    """Rolling average. The first `period - 1` entries are None (not enough data)."""
    out: List[Optional[float]] = [None] * len(values)
    for i in range(period - 1, len(values)):
        out[i] = sum(values[i - period + 1 : i + 1]) / period
    return out


def crossovers(closes: Sequence[float], short_period: int, long_period: int) -> List[Tuple[int, str, float, float]]:
    """Every crossover in the series, oldest first: (index, "bullish"|"bearish", short SMA, long SMA).

    How a crossover is decided: at each day we look at the sign of
    (short SMA - long SMA). A crossover is a change of sign. Days where the
    two averages are exactly equal are skipped, so a "touch" that then
    continues in the same direction is NOT counted as a crossover.
    """
    short_vals = sma(closes, short_period)
    long_vals = sma(closes, long_period)
    found: List[Tuple[int, str, float, float]] = []
    last_sign = 0
    for i in range(len(closes)):
        s, l = short_vals[i], long_vals[i]
        if s is None or l is None:
            continue
        diff = s - l
        sign = 1 if diff > 0 else -1 if diff < 0 else 0
        if sign == 0:
            continue
        if last_sign != 0 and sign != last_sign:
            found.append((i, "bullish" if sign > 0 else "bearish", s, l))
        last_sign = sign
    return found


def latest_crossover(
    dates: Sequence[str],
    closes: Sequence[float],
    short_period: int,
    long_period: int,
    lookback: int,
) -> Optional[dict]:
    """Find the most recent crossover among the last `lookback` candles.

    `dates` and `closes` are oldest-first and the same length.
    Returns None when there is no crossover in the window (or too little data).
    """
    window_start = max(0, len(closes) - lookback)
    found = None
    for i, kind, s, l in crossovers(closes, short_period, long_period):
        if i >= window_start:
            found = {"type": kind, "date": dates[i], "close": closes[i], "sma_short": s, "sma_long": l}
    return found
