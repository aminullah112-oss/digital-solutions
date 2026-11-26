"""Pure SMA-crossover maths. No network, no Kite: easy to read and to test.

Vocabulary
  SMA (simple moving average): the average close of the last N days.
  Bullish crossover: the short SMA moves from below the long SMA to above it.
  Bearish crossover: the short SMA moves from above the long SMA to below it.
"""

from typing import List, Optional, Sequence


def sma(values: Sequence[float], period: int) -> List[Optional[float]]:
    """Rolling average. The first `period - 1` entries are None (not enough data)."""
    out: List[Optional[float]] = [None] * len(values)
    for i in range(period - 1, len(values)):
        out[i] = sum(values[i - period + 1 : i + 1]) / period
    return out


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

    How a crossover is decided: at each day we look at the sign of
    (short SMA - long SMA). A crossover is a change of sign. Days where the
    two averages are exactly equal are skipped, so a "touch" that then
    continues in the same direction is NOT counted as a crossover.
    """
    short_vals = sma(closes, short_period)
    long_vals = sma(closes, long_period)
    window_start = max(0, len(closes) - lookback)

    last_sign = 0
    found = None
    for i in range(len(closes)):
        s, l = short_vals[i], long_vals[i]
        if s is None or l is None:
            continue
        diff = s - l
        sign = 1 if diff > 0 else -1 if diff < 0 else 0
        if sign == 0:
            continue
        if last_sign != 0 and sign != last_sign and i >= window_start:
            found = {
                "type": "bullish" if sign > 0 else "bearish",
                "date": dates[i],
                "close": closes[i],
                "sma_short": s,
                "sma_long": l,
            }
        last_sign = sign
    return found
