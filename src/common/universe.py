from __future__ import annotations

import datetime as dt
import re
from functools import lru_cache
from typing import Dict, Iterable, Mapping, MutableMapping

import yaml

from .config import (
    TICKER_NAMES_FILE,
    UNIVERSE_PROVENANCE_FILE,
    UNIVERSE_SNAPSHOTS_FILE,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _to_date(value) -> dt.date:
    if isinstance(value, dt.datetime):
        return value.date()
    if hasattr(value, "to_pydatetime"):
        return value.to_pydatetime().date()
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value))


def _date_text(value) -> str:
    return _to_date(value).isoformat()


def _load_yaml_mapping(path, label: str) -> dict:
    if not path.exists():
        raise ValueError(f"{label} file does not exist: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{label} must contain a mapping")
    return raw


def _load_snapshots() -> MutableMapping[dt.date, Dict[str, str]]:
    raw = _load_yaml_mapping(UNIVERSE_SNAPSHOTS_FILE, "universe snapshot")
    if not raw:
        raise ValueError("Nikkei 225 membership snapshot file is empty")

    snapshots: Dict[dt.date, Dict[str, str]] = {}
    for key, members in raw.items():
        date = _to_date(key)
        if date in snapshots:
            raise ValueError(f"duplicate universe snapshot date: {date.isoformat()}")
        if not isinstance(members, dict) or not members:
            raise ValueError(f"empty universe snapshot: {date.isoformat()}")
        snapshots[date] = {str(ticker): str(name) for ticker, name in members.items()}
    return snapshots


def _load_provenance() -> dict:
    return _load_yaml_mapping(UNIVERSE_PROVENANCE_FILE, "universe provenance")


def _validate_provenance(
    snapshots: Mapping[dt.date, Mapping[str, str]], provenance: Mapping,
) -> list[str]:
    errors: list[str] = []
    if provenance.get("dataset_status") != "verified":
        errors.append("dataset_status must be 'verified'")

    raw_records = provenance.get("snapshots")
    if not isinstance(raw_records, dict):
        errors.append("provenance.snapshots must be a mapping")
        return errors

    records: dict[str, object] = {}
    for raw_date, record in raw_records.items():
        try:
            normalized_date = _date_text(raw_date)
        except Exception:
            errors.append(f"invalid provenance snapshot date: {raw_date!r}")
            continue
        if normalized_date in records:
            errors.append(f"duplicate provenance snapshot date: {normalized_date}")
            continue
        records[normalized_date] = record

    expected_dates = {date.isoformat() for date in snapshots}
    record_dates = set(records)
    missing = sorted(expected_dates - record_dates)
    extra = sorted(record_dates - expected_dates)
    if missing:
        errors.append(f"missing provenance for snapshots: {', '.join(missing)}")
    if extra:
        errors.append(f"provenance has unknown snapshots: {', '.join(extra)}")

    for date_text in sorted(expected_dates & record_dates):
        record = records[date_text]
        if not isinstance(record, dict):
            errors.append(f"{date_text}: provenance entry must be a mapping")
            continue
        try:
            as_of = _date_text(record.get("as_of"))
        except Exception:
            as_of = ""
        if as_of != date_text:
            errors.append(f"{date_text}: as_of must match the snapshot date")
        source_url = str(record.get("source_url", ""))
        if not source_url.startswith("https://"):
            errors.append(f"{date_text}: source_url must be an https URL")
        for field in ("published_at", "retrieved_at"):
            try:
                _to_date(record.get(field))
            except Exception:
                errors.append(f"{date_text}: {field} must be an ISO date")
        digest = str(record.get("file_sha256", "")).lower()
        if not _SHA256_RE.fullmatch(digest):
            errors.append(f"{date_text}: file_sha256 must be a 64-character digest")
        if record.get("verified_by") in (None, ""):
            errors.append(f"{date_text}: verified_by is required")
    return errors


_SNAPSHOTS = _load_snapshots()
_PROVENANCE = _load_provenance()
_PROVENANCE_ERRORS = _validate_provenance(_SNAPSHOTS, _PROVENANCE)
_SNAPSHOT_DATES = sorted(_SNAPSHOTS)


def assert_verified_universe() -> None:
    """未検証または出典不明の構成銘柄表を分析へ渡さない。"""
    if _PROVENANCE_ERRORS:
        details = "; ".join(_PROVENANCE_ERRORS)
        raise RuntimeError(
            "historical Nikkei 225 universe is quarantined because its "
            f"provenance is not verified: {details}"
        )


@lru_cache(maxsize=None)
def universe_for_date(as_of) -> Dict[str, str]:
    assert_verified_universe()
    target = _to_date(as_of)
    eligible_dates = [date for date in _SNAPSHOT_DATES if date <= target]
    if not eligible_dates:
        first = _SNAPSHOT_DATES[0].isoformat()
        raise ValueError(
            f"no universe snapshot on or before {target.isoformat()}; "
            f"earliest available snapshot is {first}"
        )
    return dict(_SNAPSHOTS[eligible_dates[-1]])


def universe_for_year(year: int) -> Dict[str, str]:
    return universe_for_date(dt.date(int(year), 1, 1))


def tickers_for_year(year: int) -> Iterable[str]:
    return universe_for_year(year).keys()


def all_tickers() -> list[str]:
    assert_verified_universe()
    return sorted({ticker for members in _SNAPSHOTS.values() for ticker in members})


ALL_TICKERS = all_tickers() if not _PROVENANCE_ERRORS else []
TICKER_NAMES: Dict[str, str] = (
    {
        ticker: name
        for members in _SNAPSHOTS.values()
        for ticker, name in members.items()
    }
    if not _PROVENANCE_ERRORS
    else {}
)


def union_names() -> Mapping[str, str]:
    assert_verified_universe()
    return dict(TICKER_NAMES)


def load_names() -> Dict[str, str]:
    data = yaml.safe_load(TICKER_NAMES_FILE.read_text(encoding="utf-8"))
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError("ticker_names.yaml must contain a mapping")
    return dict(data)
