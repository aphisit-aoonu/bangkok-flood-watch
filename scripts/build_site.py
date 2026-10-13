"""Refresh recent readings and write web/data/stations.json for the map page.

Usage: python -m scripts.build_site [--no-refresh]
"""
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from floodwatch import backtest, source, store, trend
from scripts.fetch_history import DB, PAUSE_S, PROVINCES

OUT = Path("web/data/stations.json")
CHART_HOURS = 24
STALE_AFTER = timedelta(hours=6)
NEAR_BANK_M = 0.30


def refresh(conn) -> None:
    stations, latest = source.fetch_latest()
    store.save_stations(conn, stations)
    store.save_readings(conn, latest)
    start = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")
    for st in store.stations_in(conn, PROVINCES):
        try:
            store.save_readings(conn, source.fetch_history(st.id, start, today))
        except Exception as exc:
            print(f"  ! {st.id}: {exc}")
        time.sleep(PAUSE_S)


def status(margin: float | None, slope: float | None) -> str:
    if margin is not None and margin < 0:
        return "over"
    if margin is not None and margin < NEAR_BANK_M:
        return "near"
    if slope is not None and slope >= 0.03:
        return "rising"
    return "normal"


def station_summary(st, readings, now: datetime) -> dict | None:
    if not readings:
        return None
    last = readings[-1]
    times = [r.time for r in readings]
    past = lambda offset: backtest._actual_at(times, readings, last.time + offset)
    slope = trend.slope_per_hour(trend.window(readings, times, last.time, backtest.TREND_WINDOW_H))
    choice = backtest.run(readings).best_methods() or {h: "same_as_now" for h in backtest.HORIZONS_H}

    forecast = []
    for h in backtest.HORIZONS_H:
        guess = backtest.METHODS[choice[h]](last.level, slope, h, past)
        if guess is None:
            guess = last.level
        forecast.append({"h": h, "level": round(guess, 3), "method": choice[h]})

    margin = trend.bank_margin(last.level, st.min_bank)
    overflow_in = None
    if st.min_bank is not None and margin is not None and margin > 0:
        overflow_in = next((f["h"] for f in forecast if f["level"] >= st.min_bank), None)

    cutoff = last.time - timedelta(hours=CHART_HOURS)
    chart = [[r.time.strftime("%Y-%m-%dT%H:%M"), r.level] for r in readings if r.time >= cutoff and r.time.minute % 20 == 0]

    return {
        "id": st.id,
        "name_th": st.name_th,
        "name_en": st.name_en or st.area_en or st.name_th,
        "province_en": st.province_en,
        "lat": st.lat,
        "lon": st.lon,
        "time": last.time.strftime("%Y-%m-%dT%H:%M"),
        "stale": now - last.time > STALE_AFTER,
        "level": last.level,
        "bank": st.min_bank,
        "margin": None if margin is None else round(margin, 3),
        "slope_cm_h": None if slope is None else round(slope * 100, 1),
        "status": status(margin, slope),
        "forecast": forecast,
        "overflow_within_h": overflow_in,
        "chart": chart,
    }


def main() -> None:
    conn = store.connect(DB)
    if "--no-refresh" not in sys.argv:
        refresh(conn)
    now = datetime.now()
    out = []
    for st in store.stations_in(conn, PROVINCES):
        summary = station_summary(st, trend.drop_spikes(store.series(conn, st.id)), now)
        if summary:
            out.append(summary)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"generated": now.strftime("%Y-%m-%dT%H:%M"), "stations": out}, ensure_ascii=False),
                   encoding="utf-8")
    counts = {s: sum(1 for x in out if x["status"] == s and not x["stale"]) for s in ("over", "near", "rising", "normal")}
    print(f"{len(out)} stations written to {OUT} | {counts} | stale {sum(x['stale'] for x in out)}")


if __name__ == "__main__":
    main()
