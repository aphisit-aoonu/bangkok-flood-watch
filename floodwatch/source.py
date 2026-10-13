"""Fetch and parse water-level data from the ThaiWater (HII) public API."""
import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime

BASE = "https://api-v3.thaiwater.net/api/v1/thaiwater30/public"
USER_AGENT = "bangkok-flood-watch/0.1 (personal research project)"
TIME_FMT = "%Y-%m-%d %H:%M"


@dataclass(frozen=True)
class Station:
    id: int
    name_th: str
    name_en: str
    province_code: str
    province_en: str
    lat: float
    lon: float
    min_bank: float | None
    ground_level: float | None
    area_en: str = ""


@dataclass(frozen=True)
class Reading:
    station_id: int
    time: datetime
    level: float


def _get(path: str, params: dict | None = None, timeout: int = 60) -> dict:
    url = f"{BASE}/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _float(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _area_en(geo: dict) -> str:
    """'Bang Krasop, Phra Pradaeng' from the geocode block; used when a station has no English name."""
    parts = [(geo.get(k) or {}).get("en", "").replace(" District", "").strip() for k in ("tumbon_name", "amphoe_name")]
    return ", ".join(dict.fromkeys(p for p in parts if p))


def parse_latest(payload: dict) -> tuple[list[Station], list[Reading]]:
    stations, readings = [], []
    for row in payload["waterlevel_data"]["data"]:
        st = row["station"]
        geo = row.get("geocode") or {}
        station = Station(
            id=int(st["id"]),
            name_th=(st.get("tele_station_name") or {}).get("th", ""),
            name_en=(st.get("tele_station_name") or {}).get("en", ""),
            province_code=str(geo.get("province_code", "")),
            province_en=(geo.get("province_name") or {}).get("en", ""),
            lat=float(st["tele_station_lat"]),
            lon=float(st["tele_station_long"]),
            min_bank=_float(st.get("min_bank")),
            ground_level=_float(st.get("ground_level")),
            area_en=_area_en(geo),
        )
        stations.append(station)
        level = _float(row.get("waterlevel_msl"))
        if level is not None and row.get("waterlevel_datetime"):
            readings.append(Reading(station.id, datetime.strptime(row["waterlevel_datetime"], TIME_FMT), level))
    return stations, readings


def parse_history(station_id: int, payload: dict) -> list[Reading]:
    out = []
    for point in payload["data"]["graph_data"]:
        level = _float(point.get("value"))
        if level is not None:
            out.append(Reading(station_id, datetime.strptime(point["datetime"], TIME_FMT), level))
    return out


def fetch_latest() -> tuple[list[Station], list[Reading]]:
    return parse_latest(_get("waterlevel_load"))


def fetch_history(station_id: int, start: str, end: str) -> list[Reading]:
    payload = _get("waterlevel_graph", {
        "station_type": "tele_waterlevel",
        "station_id": station_id,
        "start_date": start,
        "end_date": end,
    })
    return parse_history(station_id, payload)
