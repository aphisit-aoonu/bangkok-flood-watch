"""Trend, forecast and bank-margin calculations on a station's readings."""
from bisect import bisect_right
from datetime import datetime, timedelta

from .source import Reading

SPIKE_M = 0.30
# Tides repeat every lunar day (24 h 50 min), which is exactly 149 ten-minute steps
LUNAR_DAY = timedelta(hours=24, minutes=50)


def drop_spikes(readings: list[Reading], limit: float = SPIKE_M) -> list[Reading]:
    """Remove single-point glitches: a value far from both neighbours, which agree with each other."""
    if len(readings) < 3:
        return list(readings)
    out = [readings[0]]
    for prev, cur, nxt in zip(readings, readings[1:], readings[2:]):
        jump_in, jump_out = cur.level - prev.level, nxt.level - cur.level
        is_spike = abs(jump_in) > limit and abs(jump_out) > limit and (jump_in > 0) != (jump_out > 0)
        if not is_spike:
            out.append(cur)
    out.append(readings[-1])
    return out


def window(readings: list[Reading], times: list[datetime], at: datetime, hours: float) -> list[Reading]:
    """Readings in (at - hours, at]. `times` must be the sorted times of `readings`."""
    end = bisect_right(times, at)
    start = bisect_right(times, at - timedelta(hours=hours))
    return readings[start:end]


def slope_per_hour(points: list[Reading]) -> float | None:
    """Least-squares slope in metres per hour, or None if there is not enough data."""
    if len(points) < 3:
        return None
    t0 = points[0].time
    xs = [(p.time - t0).total_seconds() / 3600 for p in points]
    ys = [p.level for p in points]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx


def forecast_linear(level: float, slope: float | None, hours: float) -> float:
    return level if slope is None else level + slope * hours


def forecast_damped(level: float, slope: float | None, hours: float, half_life_h: float = 2.0) -> float:
    """Trend that fades out: rivers rarely keep rising at the same rate for hours."""
    if slope is None:
        return level
    # integral of slope * 0.5^(t/half_life) from 0 to hours
    k = half_life_h / 0.6931471805599453
    return level + slope * k * (1 - 0.5 ** (hours / half_life_h))


def forecast_tidal(level: float, hours: float, past_level, period: timedelta = LUNAR_DAY) -> float | None:
    """Repeat the change seen one tidal day ago: lower Chao Phraya rises and falls with the sea.

    past_level(offset) returns the reading at now + offset (offset is negative), or None.
    """
    then = past_level(-period)
    then_later = past_level(timedelta(hours=hours) - period)
    if then is None or then_later is None:
        return None
    return level + (then_later - then)


def bank_margin(level: float, min_bank: float | None) -> float | None:
    """Metres left before the water tops the lowest bank. Negative = already over."""
    return None if min_bank is None else min_bank - level


def hours_to_bank(level: float, slope: float | None, min_bank: float | None) -> float | None:
    """Hours until overflow if the current rise continues; None if not rising or no bank data."""
    margin = bank_margin(level, min_bank)
    if margin is None or slope is None or slope <= 0:
        return None
    if margin <= 0:
        return 0.0
    return margin / slope
