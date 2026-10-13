"""Print forecast accuracy (MAE in cm) across all stored stations.

The headline table is an honest train/test split: each station picks its method
using the 2025 rainy season only, then is scored on 2026 data it has never seen.

Usage: python -m scripts.backtest_report
"""
import json
from datetime import datetime
from pathlib import Path

from floodwatch import backtest, store, trend
from scripts.fetch_history import DB, PROVINCES

SPLIT = datetime(2026, 1, 1)
ACCURACY_OUT = Path("web/data/accuracy.json")
BASELINE = "same_as_now"


def mae(errors: list[float]) -> str:
    return "-" if not errors else f"{100 * sum(errors) / len(errors):.1f} cm"


def main() -> None:
    conn = store.connect(DB)
    every = backtest.Score()
    picked = {h: [] for h in backtest.HORIZONS_H}
    baseline = {h: [] for h in backtest.HORIZONS_H}
    used = 0
    for st in store.stations_in(conn, PROVINCES):
        readings = trend.drop_spikes(store.series(conn, st.id))
        every.merge(backtest.run(readings))
        train = backtest.run([r for r in readings if r.time < SPLIT])
        test = backtest.run([r for r in readings if r.time >= SPLIT])
        choice = train.best_methods()
        if choice is None or test.count(max(backtest.HORIZONS_H)) == 0:
            continue
        used += 1
        for h, method in choice.items():
            picked[h] += test.abs_errors[(method, h)]
            baseline[h] += test.abs_errors[(BASELINE, h)]

    print(f"Train 2025 -> test 2026, {used} stations")
    print(f"{'horizon':<10}{'same_as_now':>14}{'forecast':>12}{'better by':>12}{'samples':>10}")
    rows = []
    for h in backtest.HORIZONS_H:
        base, ours = sum(baseline[h]) / len(baseline[h]), sum(picked[h]) / len(picked[h])
        print(f"{f'+{h}h':<10}{mae(baseline[h]):>14}{mae(picked[h]):>12}{1 - ours / base:>12.0%}{len(picked[h]):>10}")
        rows.append({"h": h, "baseline_cm": round(base * 100, 1), "ours_cm": round(ours * 100, 1),
                     "better_pct": round((1 - ours / base) * 100, 1), "samples": len(picked[h])})
    ACCURACY_OUT.parent.mkdir(parents=True, exist_ok=True)
    ACCURACY_OUT.write_text(json.dumps({"stations": used, "train": "2025", "test": "2026", "rows": rows}), encoding="utf-8")

    print("\nEach method on all data (for reference)")
    for name in backtest.METHODS:
        print(f"{name:<14}" + "".join(f"{f'{every.mae_cm(name, h):.1f} cm':>10}" for h in backtest.HORIZONS_H))


if __name__ == "__main__":
    main()
