from __future__ import annotations

import math
from statistics import mean
from typing import Dict, Iterable, List, Mapping, Optional, Sequence


def _percent(value: float, digits: int = 1) -> str:
    if math.isnan(value):
        return "—"
    return f"{value * 100:.{digits}f}%"


def _ratio(value: float, digits: int = 2) -> str:
    if math.isnan(value):
        return "—"
    return f"{value:.{digits}f}"


def _prepare_rows(summary: Mapping[str, Mapping[str, float]]) -> List[Dict[str, float]]:
    return [
        {"year": year, **metrics}
        for year, metrics in sorted(summary.items(), key=lambda item: int(item[0]))
    ]


def render_summary_report(
    summary: Mapping[str, Mapping[str, float]],
    top_holdings: Optional[Mapping[str, Sequence[Mapping[str, float]]]] = None,
) -> str:
    rows = _prepare_rows(summary)
    best_return = max(rows, key=lambda row: row["annual_return"])
    worst_return = min(rows, key=lambda row: row["annual_return"])
    lowest_volatility = min(rows, key=lambda row: row["volatility"])
    deepest_drawdown = min(rows, key=lambda row: row["max_drawdown"])
    latest_year = max(rows, key=lambda row: int(row["year"]))

    avg_return = mean(row["annual_return"] for row in rows)
    avg_volatility = mean(row["volatility"] for row in rows)
    avg_sharpe = mean(row["sharpe_ratio"] for row in rows)
    avg_drawdown = mean(row["max_drawdown"] for row in rows)

    split_year = 2017
    early_period = [row for row in rows if int(row["year"]) <= split_year]
    late_period = [row for row in rows if int(row["year"]) > split_year]

    def _avg(metric: str, dataset: Iterable[Mapping[str, float]]) -> float:
        values = [row[metric] for row in dataset]
        return mean(values) if values else float("nan")

    early_return = _avg("annual_return", early_period)
    early_volatility = _avg("volatility", early_period)
    late_return = _avg("annual_return", late_period)
    late_volatility = _avg("volatility", late_period)

    start_year = rows[0]["year"]
    end_year = rows[-1]["year"]

    holdings_by_year = top_holdings or {}

    lines: List[str] = [
        f"# ポートフォリオ年次パフォーマンス概要（{start_year}-{end_year}）",
        "",
        "視聴者がすぐに押さえたい要点をミニマルに整理した、最適ポートフォリオの年次サマリーです。",
        "",
        "## ハイライト",
        f"- **最高リターン:** {best_return['year']}年が年率{_percent(best_return['annual_return'])}でトップ。シャープレシオは{_ratio(best_return['sharpe_ratio'])}。",
        f"- **最低リターン:** {worst_return['year']}年は年率{_percent(worst_return['annual_return'])}で最も低調でした。",
        f"- **安定性:** ボラティリティ最小は{lowest_volatility['year']}年の{_percent(lowest_volatility['volatility'])}。最大ドローダウンは{_percent(lowest_volatility['max_drawdown'])}でした。",
        f"- **リスクイベント:** 最大ドローダウンは{deepest_drawdown['year']}年の{_percent(deepest_drawdown['max_drawdown'])}。",
        "",
        "## 年次指標一覧",
        "| 年 | 年率リターン | ボラティリティ | シャープレシオ | 最大ドローダウン |",
        "|---|-------------|----------------|-----------------|-------------------|",
    ]

    for row in rows:
        lines.append(
            "| {year} | {ret} | {vol} | {sharpe} | {dd} |".format(
                year=row["year"],
                ret=_percent(row["annual_return"]),
                vol=_percent(row["volatility"]),
                sharpe=_ratio(row["sharpe_ratio"]),
                dd=_percent(row["max_drawdown"]),
            )
        )

    lines.extend(
        [
            "",
            "## トレンドの掘り下げ",
            f"- 平均では年率リターン{_percent(avg_return)}, ボラティリティ{_percent(avg_volatility)}, シャープレシオ{_ratio(avg_sharpe)}, 最大ドローダウン{_percent(avg_drawdown)}。",
            f"- {start_year}年〜{split_year}年は平均リターン{_percent(early_return)} / ボラティリティ{_percent(early_volatility)}で安定推移。",
            f"- 最低リターンだった{worst_return['year']}年はボラティリティ{_percent(worst_return['volatility'])}、シャープレシオ{_ratio(worst_return['sharpe_ratio'])}。",
            f"- 直近の{latest_year['year']}年は年率{_percent(latest_year['annual_return'])}ながら、最大ドローダウン{_percent(latest_year['max_drawdown'])}と振れ幅が大きい点に留意。",
            "",
            "## 今後の着目点",
            f"- リスク許容度を確認し、{deepest_drawdown['year']}年の下落幅{_percent(deepest_drawdown['max_drawdown'])}を想定したドローダウン管理を整備しましょう。",
            f"- 安定性が際立った{lowest_volatility['year']}年の運用要因を分析し、再現可能性を検証します。",
            f"- マイナスリターンとなった{worst_return['year']}年の市場環境とポジションを振り返り、防衛的な戦略に反映させます。",
            "",
        ]
    )

    years = (
        sorted(holdings_by_year, key=int)
        if holdings_by_year
        else [str(latest_year["year"])]
    )

    for year in years:
        holdings = list(holdings_by_year.get(year, []))
        lines.extend([f"## {year}年ポートフォリオ上位10銘柄", ""])
        if holdings:
            for default_rank, holding in enumerate(holdings[:10], start=1):
                ticker = holding.get("ticker", "")
                name = holding.get("name") or ticker
                weight = float(holding.get("weight", float("nan")))
                rank = int(holding.get("rank", default_rank))
                lines.append(
                    f"- {rank}. {name}（{ticker}）: {_percent(weight)}"
                )
        else:
            lines.append("- データが不足しています。")
        lines.append("")

    return "\n".join(lines)
