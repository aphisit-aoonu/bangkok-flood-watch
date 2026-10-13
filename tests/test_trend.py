from datetime import datetime, timedelta

import pytest

from floodwatch.source import Reading
from floodwatch.trend import (LUNAR_DAY, bank_margin, drop_spikes, forecast_damped, forecast_linear,
                            forecast_tidal, hours_to_bank, slope_per_hour, window)

T0 = datetime(2026, 9, 25, 0, 0)


def series(levels, step_min=10):
    return [Reading(1, T0 + timedelta(minutes=i * step_min), lv) for i, lv in enumerate(levels)]


def test_slope_of_steady_rise():
    # +5 cm every 10 minutes = 0.30 m/h
    assert slope_per_hour(series([1.00 + 0.05 * i for i in range(7)])) == pytest.approx(0.30)


def test_slope_needs_three_points():
    assert slope_per_hour(series([1.0, 1.1])) is None


def test_drop_spikes_removes_single_glitch():
    cleaned = drop_spikes(series([1.00, 1.01, 3.50, 1.02, 1.03]))
    assert [r.level for r in cleaned] == [1.00, 1.01, 1.02, 1.03]


def test_drop_spikes_keeps_real_step():
    # a sudden rise that stays up is real (e.g. gate opened), not a glitch
    assert len(drop_spikes(series([1.0, 1.0, 1.5, 1.5, 1.5]))) == 5


def test_window_takes_last_hours_only():
    readings = series([float(i) for i in range(13)])  # 2 hours of data
    times = [r.time for r in readings]
    picked = window(readings, times, readings[-1].time, 1)
    assert [r.level for r in picked] == [7.0, 8.0, 9.0, 10.0, 11.0, 12.0]


def test_forecasts():
    assert forecast_linear(1.0, 0.1, 3) == pytest.approx(1.3)
    assert forecast_linear(1.0, None, 3) == 1.0
    damped = forecast_damped(1.0, 0.1, 3)
    assert 1.0 < damped < 1.3


def test_tidal_forecast_repeats_yesterdays_change():
    history = {-LUNAR_DAY: 1.0, timedelta(hours=3) - LUNAR_DAY: 1.4}
    assert forecast_tidal(2.0, 3, history.get) == pytest.approx(2.4)


def test_tidal_forecast_needs_yesterday():
    assert forecast_tidal(2.0, 3, lambda offset: None) is None


def test_bank_margin_and_overflow_eta():
    assert bank_margin(0.80, 1.00) == pytest.approx(0.20)
    assert bank_margin(0.80, None) is None
    assert hours_to_bank(0.80, 0.05, 1.00) == pytest.approx(4.0)
    assert hours_to_bank(0.80, -0.05, 1.00) is None
    assert hours_to_bank(1.10, 0.05, 1.00) == 0.0
