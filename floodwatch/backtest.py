"""Replay history: forecast from each past moment and compare with what really happened."""
from bisect import bisect_left
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .source import Reading
from .trend import forecast_damped, forecast_linear, forecast_tidal, slope_per_hour, window

HORIZONS_H = (1, 3, 6)
TREND_WINDOW_H = 2.0
STEP = timedelta(hours=1)
MATCH_TOLERANCE = timedelta(minutes=10)

# Every method: (level now, slope m/h, hours ahead, past_level(offset)) -> forecast or None
METHODS = {
    "same_as_now": lambda level, slope, h, past: level,
    "linear_trend": lambda level, slope, h, past: forecast_linear(level, slope, h),
    "damped_trend": lambda level, slope, h, past: forecast_damped(level, slope, h),
    "tidal_cycle": lambda level, slope, h, past: forecast_tidal(level, h, past),
}


@dataclass
class Score:
    abs_errors: dict = field(default_factory=lambda: {(m, h): [] for m in METHODS for h in HORIZONS_H})

    def add(self, method: str, horizon: int, error: float) -> None:
        self.abs_errors[(method, horizon)].append(abs(error))

    def merge(self, other: "Score") -> None:
        for key, errs in other.abs_errors.items():
            self.abs_errors[key].extend(errs)

    def mae_cm(self, method: str, horizon: int) -> float | None:
        errs = self.abs_errors[(method, horizon)]
        return None if not errs else 100 * sum(errs) / len(errs)

    def count(self, horizon: int) -> int:
        return len(self.abs_errors[(next(iter(METHODS)), horizon)])

    def best_methods(self) -> dict[int, str] | None:
        """Lowest-error method per horizon; None if there was nothing to score."""
        if any(self.count(h) == 0 for h in HORIZONS_H):
            return None
        return {h: min(METHODS, key=lambda m: self.mae_cm(m, h)) for h in HORIZONS_H}


def _actual_at(times: list[datetime], readings: list[Reading], at: datetime) -> float | None:
    i = bisect_left(times, at - MATCH_TOLERANCE)
    if i < len(times) and abs(times[i] - at) <= MATCH_TOLERANCE:
        return readings[i].level
    return None


def run(readings: list[Reading], only_moving: float = 0.0) -> Score:
    """Score every method on one station's series.

    only_moving: skip moments where |slope| is below this many metres/hour, so quiet
    periods (where 'same as now' trivially wins) don't hide performance during floods.
    """
    score = Score()
    if len(readings) < 10:
        return score
    times = [r.time for r in readings]
    at = times[0] + timedelta(hours=TREND_WINDOW_H)
    end = times[-1] - timedelta(hours=max(HORIZONS_H))
    while at <= end:
        now = _actual_at(times, readings, at)
        if now is not None:
            slope = slope_per_hour(window(readings, times, at, TREND_WINDOW_H))
            if slope is not None and abs(slope) >= only_moving:
                past = lambda offset, at=at: _actual_at(times, readings, at + offset)
                for h in HORIZONS_H:
                    actual = _actual_at(times, readings, at + timedelta(hours=h))
                    if actual is None:
                        continue
                    guesses = {name: method(now, slope, h, past) for name, method in METHODS.items()}
                    # compare methods on the same moments only
                    if None in guesses.values():
                        continue
                    for name, guess in guesses.items():
                        score.add(name, h, guess - actual)
        at += STEP
    return score
