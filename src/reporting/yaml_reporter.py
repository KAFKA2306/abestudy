from __future__ import annotations

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


def _sort_universe(universe):
    return sorted(
        (
            {
                "ticker": item.get("ticker", ""),
                "name": item.get("name", ""),
            }
            for item in universe
        ),
        key=lambda item: item["ticker"],
    )


def _weight_entries(weights):
    return [
        {
            "ticker": ticker,
            "name": data.get("name", ""),
            "weight": float(data.get("weight", 0.0)),
        }
        for ticker, data in weights.items()
    ]


def _weights_by_ticker(entries):
    return {
        entry["ticker"]: {"name": entry["name"], "weight": entry["weight"]}
        for entry in sorted(entries, key=lambda item: item["ticker"])
    }


def _top_holdings(entries, limit=10):
    ranked = sorted(entries, key=lambda item: item["weight"], reverse=True)
    return [
        {
            "rank": position,
            "ticker": entry["ticker"],
            "name": entry["name"],
            "weight": entry["weight"],
        }
        for position, entry in enumerate(ranked[:limit], start=1)
    ]


def _tail_holdings(entries, limit=5):
    active = [entry for entry in entries if entry["weight"] > 0]
    ranked = sorted(active, key=lambda item: item["weight"])
    return [
        {
            "ticker": entry["ticker"],
            "name": entry["name"],
            "weight": entry["weight"],
        }
        for entry in ranked[:limit]
    ]


def _weight_buckets(entries):
    buckets = [
        ("10%以上", 0.10, None),
        ("5%-10%", 0.05, 0.10),
        ("1%-5%", 0.01, 0.05),
        ("1%未満", 0.0, 0.01),
    ]
    ranked = sorted(entries, key=lambda item: item["weight"], reverse=True)
    results = []
    for label, lower, upper in buckets:
        members = [
            entry
            for entry in ranked
            if entry["weight"] >= lower and (upper is None or entry["weight"] < upper)
        ]
        results.append(
            {
                "label": label,
                "count": len(members),
                "weight_share": sum(entry["weight"] for entry in members),
                "sample": [
                    {
                        "ticker": entry["ticker"],
                        "name": entry["name"],
                        "weight": entry["weight"],
                    }
                    for entry in members[:5]
                ],
            }
        )
    return results


def _allocation_summary(entries):
    total = len(entries)
    active = [entry for entry in entries if entry["weight"] > 0]
    inactive = total - len(active)
    ranked = sorted(entries, key=lambda item: item["weight"], reverse=True)
    top3 = sum(entry["weight"] for entry in ranked[:3])
    top10 = sum(entry["weight"] for entry in ranked[:10])
    return {
        "total_constituents": total,
        "invested_constituents": len(active),
        "zero_weight_constituents": inactive,
        "top3_weight": top3,
        "top10_weight": top10,
    }


def _format_year_report(year, payload):
    portfolio = payload["portfolio"]
    weight_entries = _weight_entries(portfolio["weights"])
    return {
        "year": year,
        "period": payload["period"],
        "conditions": {
            "training_window": portfolio.get("training_window", {}),
            "evaluation_window": portfolio.get("evaluation_window", {}),
        },
        "portfolio": {
            "risk_metrics": portfolio.get("risk_metrics", {}),
            "allocations": {
                "summary": _allocation_summary(weight_entries),
                "top_holdings": _top_holdings(weight_entries),
                "smallest_active_weights": _tail_holdings(weight_entries),
                "weight_buckets": _weight_buckets(weight_entries),
                "by_ticker": _weights_by_ticker(weight_entries),
            },
        },
        "universe": {
            "count": len(payload.get("universe", [])),
            "members": _sort_universe(payload.get("universe", [])),
        },
    }


def write_reports(results, directory):
    directory.mkdir(parents=True, exist_ok=True)
    formatted = {
        year: _round_numbers(_format_year_report(year, payload))
        for year, payload in results.items()
    }
    for year, payload in formatted.items():
        (directory / f"{year}.yaml").write_text(
            "\n".join(_yaml_lines(payload)) + "\n", encoding="utf-8"
        )
    if formatted:
        summary = {
            str(year): payload["portfolio"]["risk_metrics"]
            for year, payload in formatted.items()
        }
        holdings = {
            str(year): payload["portfolio"]["allocations"]["top_holdings"]
            for year, payload in formatted.items()
        }
        (directory / "summary.yaml").write_text(
            "\n".join(_yaml_lines({"years": summary})) + "\n",
            encoding="utf-8",
        )
        report = render_summary_report(summary, holdings)
        (directory / "summary_report.md").write_text(report, encoding="utf-8")
