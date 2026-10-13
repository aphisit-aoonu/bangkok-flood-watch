"""SQLite storage for stations and readings."""
import sqlite3
from datetime import datetime
from pathlib import Path

from .source import Reading, Station, TIME_FMT

SCHEMA = """
CREATE TABLE IF NOT EXISTS station (
    id INTEGER PRIMARY KEY,
    name_th TEXT, name_en TEXT,
    province_code TEXT, province_en TEXT,
    lat REAL, lon REAL,
    min_bank REAL, ground_level REAL,
    area_en TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS reading (
    station_id INTEGER NOT NULL,
    time TEXT NOT NULL,
    level REAL NOT NULL,
    PRIMARY KEY (station_id, time)
);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(station)")}
    if "area_en" not in columns:  # databases created before the column existed
        conn.execute("ALTER TABLE station ADD COLUMN area_en TEXT DEFAULT ''")
    return conn


def save_stations(conn: sqlite3.Connection, stations: list[Station]) -> None:
    conn.executemany(
        "INSERT OR REPLACE INTO station VALUES (?,?,?,?,?,?,?,?,?,?)",
        [(s.id, s.name_th, s.name_en, s.province_code, s.province_en, s.lat, s.lon, s.min_bank, s.ground_level, s.area_en)
         for s in stations],
    )
    conn.commit()


def save_readings(conn: sqlite3.Connection, readings: list[Reading]) -> int:
    before = conn.total_changes
    conn.executemany(
        "INSERT OR IGNORE INTO reading VALUES (?,?,?)",
        [(r.station_id, r.time.strftime(TIME_FMT), r.level) for r in readings],
    )
    conn.commit()
    return conn.total_changes - before


def stations_in(conn: sqlite3.Connection, province_codes: list[str]) -> list[Station]:
    marks = ",".join("?" * len(province_codes))
    rows = conn.execute(f"SELECT * FROM station WHERE province_code IN ({marks}) ORDER BY id", province_codes)
    return [Station(*row) for row in rows]


def series(conn: sqlite3.Connection, station_id: int) -> list[Reading]:
    rows = conn.execute("SELECT time, level FROM reading WHERE station_id=? ORDER BY time", (station_id,))
    return [Reading(station_id, datetime.strptime(t, TIME_FMT), lv) for t, lv in rows]
