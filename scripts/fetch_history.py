"""Download station list + 10-minute history for Bangkok and nearby provinces into data/floodwatch.db.

Usage: python -m scripts.fetch_history
"""
import time

from floodwatch import source, store

DB = "data/floodwatch.db"
# Bangkok, Samut Prakan, Nonthaburi, Pathum Thani, Ayutthaya, Nakhon Pathom, Samut Sakhon
PROVINCES = ["10", "11", "12", "13", "14", "73", "74"]
# Rainy seasons; the API serves at most a few months per request
PERIODS = [
    ("2025-08-01", "2025-11-30"),
    ("2026-08-01", None),
]
PAUSE_S = 1.0


def main() -> None:
    conn = store.connect(DB)
    stations, latest = source.fetch_latest()
    store.save_stations(conn, stations)
    store.save_readings(conn, latest)
    targets = store.stations_in(conn, PROVINCES)
    today = time.strftime("%Y-%m-%d")
    print(f"{len(stations)} stations total, {len(targets)} in target provinces")
    for i, st in enumerate(targets, 1):
        added = 0
        for start, end in PERIODS:
            try:
                added += store.save_readings(conn, source.fetch_history(st.id, start, end or today))
            except Exception as exc:  # one bad station must not stop the run
                print(f"  ! {st.id} {start}: {exc}")
            time.sleep(PAUSE_S)
        print(f"[{i}/{len(targets)}] {st.id} {st.name_en} ({st.province_en}): +{added}")


if __name__ == "__main__":
    main()
