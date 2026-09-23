from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import median
from time import perf_counter
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# These imports have to follow the sys.path setup above so the script can be run
# directly as `python benchmarks/run_backtest_benchmark.py`.
from alphanexus.backtest import run_backtest  # noqa: E402
from benchmarks.scenarios import (  # noqa: E402
    DATE_WINDOWS,
    FIXTURE_ASSETS,
    STRATEGIES,
    iter_scenarios,
    load_prices_for_scenario,
)


def percentile(values: list[float], percentile_value: float) -> float:
    if not values:
        return 0.0

    sorted_values = sorted(values)
    rank = (len(sorted_values) - 1) * percentile_value
    lower = int(rank)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = rank - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def run_benchmark() -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    total_rows = 0

    for scenario in iter_scenarios():
        try:
            prices = load_prices_for_scenario(scenario)
            total_rows += len(prices)

            start = perf_counter()
            result, metrics = run_backtest(prices, scenario.strategy_config, scenario.backtest_config)
            runtime_ms = (perf_counter() - start) * 1_000

            results.append(
                {
                    "scenario": scenario.id,
                    "asset": scenario.asset,
                    "date_window": scenario.date_window,
                    "strategy": scenario.strategy_name,
                    "rows": len(result),
                    "runtime_ms": runtime_ms,
                    "ending_equity": float(metrics["ending_equity"]),
                    "total_return": float(metrics["total_return"]),
                    "max_drawdown": float(metrics["max_drawdown"]),
                    "trade_count": int(metrics["trade_count"]),
                }
            )
        except Exception as exc:
            failures.append({"scenario": scenario.id, "error": str(exc)})

    runtimes = [item["runtime_ms"] for item in results]
    total_scenarios = len(results) + len(failures)

    return {
        "scenario_count": total_scenarios,
        "passed": len(results),
        "failed": len(failures),
        "pass_rate": len(results) / total_scenarios if total_scenarios else 0,
        "fixture_assets": len(FIXTURE_ASSETS),
        "date_windows": len(DATE_WINDOWS),
        "strategies": len(STRATEGIES),
        "total_rows": total_rows,
        "median_runtime_ms": median(runtimes) if runtimes else 0,
        "p95_runtime_ms": percentile(runtimes, 0.95),
        "max_runtime_ms": max(runtimes) if runtimes else 0,
        "results": results,
        "failures": failures,
    }


def print_human_summary(summary: dict[str, Any]) -> None:
    print("AlphaNexus deterministic backtest benchmark")
    print(
        f"Matrix: {summary['fixture_assets']} fixtures x "
        f"{summary['date_windows']} date windows x {summary['strategies']} strategies"
    )
    print(f"Scenarios passed: {summary['passed']}/{summary['scenario_count']} ({summary['pass_rate']:.1%})")
    print(f"Fixture rows processed: {summary['total_rows']:,}")
    print(f"Median engine runtime: {summary['median_runtime_ms']:.2f} ms")
    print(f"P95 engine runtime: {summary['p95_runtime_ms']:.2f} ms")
    print(f"Max engine runtime: {summary['max_runtime_ms']:.2f} ms")

    if summary["failures"]:
        print("\nFailures:")
        for failure in summary["failures"]:
            print(f"- {failure['scenario']}: {failure['error']}")

    slowest = sorted(summary["results"], key=lambda item: item["runtime_ms"], reverse=True)[:5]
    if slowest:
        print("\nSlowest scenarios:")
        for item in slowest:
            print(f"- {item['scenario']}: {item['runtime_ms']:.2f} ms, {item['rows']} rows")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic AlphaNexus backtest benchmarks.")
    parser.add_argument("--json", action="store_true", help="Print the benchmark summary as JSON.")
    parser.add_argument(
        "--fail-on-p95-ms",
        type=float,
        default=None,
        help="Exit with a non-zero status if p95 runtime exceeds this threshold.",
    )
    args = parser.parse_args()

    summary = run_benchmark()
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print_human_summary(summary)

    if summary["failed"]:
        return 1
    if args.fail_on_p95_ms is not None and summary["p95_runtime_ms"] > args.fail_on_p95_ms:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
