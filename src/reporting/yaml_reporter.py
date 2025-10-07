from collections.abc import Mapping, Sequence
from pathlib import Path

import yaml


def _map_nested(data, transform):
    if isinstance(data, float):
        return transform(data)
    if isinstance(data, Mapping):
        return {key: _map_nested(value, transform) for key, value in data.items()}
    if isinstance(data, Sequence) and not isinstance(data, (str, bytes)):
        return [_map_nested(value, transform) for value in data]
    return data


def _dump_yaml(data):
    formatted = _map_nested(data, lambda value: f"{value:.6f}")
    return yaml.safe_dump(formatted, sort_keys=False, allow_unicode=True)


def write_reports(results, directory):
    directory.mkdir(parents=True, exist_ok=True)
    summary = {}
    for year, payload in results.items():
        rounded = _map_nested(payload, lambda value: round(value, 6))
        (directory / f"{year}.yaml").write_text(_dump_yaml(rounded), encoding="utf-8")
        summary[str(year)] = rounded["portfolio"]["risk_metrics"]
    if summary:
        (directory / "summary.yaml").write_text(_dump_yaml({"years": summary}), encoding="utf-8")
