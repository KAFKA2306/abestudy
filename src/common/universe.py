from __future__ import annotations
import datetime as dt
from functools import lru_cache
from typing import Dict, Iterable, Mapping, MutableMapping
import yaml
from .config import TICKER_NAMES_FILE, UNIVERSE_SNAPSHOTS_FILE
def _to_date(value) -> dt.date:
    if isinstance(value, dt.datetime):
        return value.date()
    if hasattr(value, "to_pydatetime"):
        return value.to_pydatetime().date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        return dt.date.fromisoformat(value)
    return dt.date.fromisoformat(str(value))
def _load_snapshots() -> MutableMapping[dt.date, Dict[str, str]]:
    raw = yaml.safe_load(UNIVERSE_SNAPSHOTS_FILE.read_text(encoding="utf-8")) or {}
    snapshots: Dict[dt.date, Dict[str, str]] = {}
    for key, members in raw.items():
        date = _to_date(key)
        snapshots[date] = dict(members or {})
    return snapshots
_SNAPSHOTS = _load_snapshots()
_SNAPSHOT_DATES = sorted(_SNAPSHOTS)
@lru_cache(maxsize=None)
def universe_for_date(as_of) -> Dict[str, str]:
    target = _to_date(as_of)
    latest = None
    for date in _SNAPSHOT_DATES:
        if date <= target:
            latest = date
        else:
            break
    return dict(_SNAPSHOTS[latest])
def universe_for_year(year: int) -> Dict[str, str]:
    return universe_for_date(dt.date(year, 1, 1))
def tickers_for_year(year: int) -> Iterable[str]:
    return universe_for_year(year).keys()
ALL_TICKERS = sorted({ticker for members in _SNAPSHOTS.values() for ticker in members})
TICKER_NAMES: Dict[str, str] = {
    ticker: name
    for members in _SNAPSHOTS.values()
    for ticker, name in members.items()
}
def union_names() -> Mapping[str, str]:
    return dict(TICKER_NAMES)
def load_names() -> Dict[str, str]:
    data = yaml.safe_load(TICKER_NAMES_FILE.read_text(encoding="utf-8"))
    return data or {}
