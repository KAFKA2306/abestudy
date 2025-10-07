from .markdown_reporter import render_summary_report


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
        return [
            line
            for key, value in data.items()
            for line in (
                [f"{prefix}{key}:"] + _yaml_lines(value, indent + 1)
                if isinstance(value, (dict, list))
                else [f"{prefix}{key}: {_scalar(value)}"]
            )
        ]
    if isinstance(data, list):
        return [
            line
            for value in data
            for line in (
                [f"{prefix}-"] + _yaml_lines(value, indent + 1)
                if isinstance(value, (dict, list))
                else [f"{prefix}- {_scalar(value)}"]
            )
        ]
    return [f"{prefix}{_scalar(data)}"]


def write_reports(results, directory):
    directory.mkdir(parents=True, exist_ok=True)
    rounded = {year: _round_numbers(payload) for year, payload in results.items()}
    for year, payload in rounded.items():
        (directory / f"{year}.yaml").write_text("\n".join(_yaml_lines(payload)) + "\n", encoding="utf-8")
    if rounded:
        summary = {str(year): payload["portfolio"]["risk_metrics"] for year, payload in rounded.items()}
        (directory / "summary.yaml").write_text("\n".join(_yaml_lines({"years": summary})) + "\n", encoding="utf-8")
        report = render_summary_report(summary)
        (directory / "summary_report.md").write_text(report, encoding="utf-8")
