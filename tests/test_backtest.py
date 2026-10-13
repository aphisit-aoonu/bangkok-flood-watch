from datetime import datetime, timedelta

import pytest

from floodwatch import backtest
from floodwatch.source import Reading

T0 = datetime(2026, 9, 25, 0, 0)


def series(fn, hours=72):
    return [Reading(1, T0 + timedelta(minutes=10 * i), fn(i / 6)) for i in range(hours * 6 + 1)]


def test_linear_trend_is_exact_on_straight_rise():
    score = backtest.run(series(lambda h: 1.0 + 0.02 * h))
    assert score.mae_cm("linear_trend", 3) == pytest.approx(0.0, abs=1e-6)
    assert score.mae_cm("same_as_now", 3) == pytest.approx(6.0)


def test_flat_water_every_method_is_exact():
    score = backtest.run(series(lambda h: 0.5))
    for name in backtest.METHODS:
        assert score.mae_cm(name, 1) == pytest.approx(0.0)


def test_only_moving_skips_quiet_periods():
    assert backtest.run(series(lambda h: 0.5), only_moving=0.01).count(1) == 0


def test_tidal_cycle_wins_on_tide_like_water():
    import math
    tide = lambda h: 1.0 + 0.5 * math.sin(2 * math.pi * h / (24 + 50 / 60))
    score = backtest.run(series(tide, hours=72))
    assert score.mae_cm("tidal_cycle", 6) == pytest.approx(0.0, abs=0.5)
    assert score.best_methods()[6] == "tidal_cycle"


def test_best_methods_none_without_data():
    assert backtest.Score().best_methods() is None


def test_gaps_are_skipped_not_guessed():
    readings = [r for r in series(lambda h: 1.0 + 0.02 * h) if not (6 <= (r.time - T0).total_seconds() / 3600 < 12)]
    full = backtest.run(series(lambda h: 1.0 + 0.02 * h)).count(1)
    assert 0 < backtest.run(readings).count(1) < full
