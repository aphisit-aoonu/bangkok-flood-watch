import json
from datetime import datetime
from pathlib import Path

from floodwatch.source import parse_history, parse_latest

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_latest_reads_station_and_level():
    stations, readings = parse_latest(load("latest_sample.json"))
    assert len(stations) == 2
    first = stations[0]
    assert first.id == 575568
    assert first.min_bank == 0.91
    assert first.province_code == "11"
    assert first.area_en == "Bang Krasop, Phra Pradaeng"
    assert readings[0].level == 1.60
    assert readings[0].time == datetime(2026, 10, 13, 9, 30)


def test_parse_latest_skips_missing_level_but_keeps_station():
    stations, readings = parse_latest(load("latest_sample.json"))
    assert len(stations) == 2
    assert len(readings) == 1


def test_parse_history_drops_nulls():
    readings = parse_history(575568, load("history_sample.json"))
    assert len(readings) == 3
    assert readings[0].level == 0.43
    assert all(r.station_id == 575568 for r in readings)
