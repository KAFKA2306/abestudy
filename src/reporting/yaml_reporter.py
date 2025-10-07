from pathlib import Path


def _round_numbers(data):
    if isinstance(data, float):
        return round(data, 6)
    if isinstance(data, dict):
        return {key: _round_numbers(value) for key, value in data.items()}
    if isinstance(data, list):
        return [_round_numbers(value) for value in data]
    return data


def _scalar(value):
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def _yaml_lines(data, indent=0):
    prefix = "  " * indent
    if isinstance(data, dict):
        lines = []
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.extend(_yaml_lines(value, indent + 1))
            else:
                lines.append(f"{prefix}{key}: {_scalar(value)}")
        return lines
    if isinstance(data, list):
        lines = []
        for value in data:
            if isinstance(value, (dict, list)):
                lines.append(f"{prefix}-")
                lines.extend(_yaml_lines(value, indent + 1))
            else:
                lines.append(f"{prefix}- {_scalar(value)}")
        return lines
    return [f"{prefix}{_scalar(data)}"]


def write_reports(results, directory):
    directory.mkdir(parents=True, exist_ok=True)
    summary = {}
    for year, payload in results.items():
        rounded = _round_numbers(payload)
        lines = _yaml_lines(rounded)
        (directory / f"{year}.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
        summary[str(year)] = rounded["portfolio"]["risk_metrics"]
    if summary:
        lines = _yaml_lines({"years": summary})
        (directory / "summary.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
