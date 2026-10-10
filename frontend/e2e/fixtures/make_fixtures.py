"""Regenerate the API responses the end-to-end tests play back.

The browser tests stub the network so they never depend on a live API or on
yfinance. The stubbed responses are produced here by the real engine and the
real FastAPI app, run on the repository's synthetic benchmark data, so the
dashboard is tested against exactly the shapes the API returns.

Run from the repository root:  python frontend/e2e/fixtures/make_fixtures.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

import api.main as api_main  # noqa: E402
from benchmarks.scenarios import load_fixture  # noqa: E402

OUT = Path(__file__).resolve().parent


def fixture_prices(asset: str):
    prices = load_fixture(asset)
    return prices[(prices["date"] >= "2024-01-01") & (prices["date"] <= "2024-12-31")].reset_index(drop=True)


def main() -> None:
    os.environ["DATABASE_PATH"] = os.path.join(tempfile.mkdtemp(), "e2e.db")
    client = TestClient(api_main.app)
    base = {"ticker": "AAPL", "start": "2024-01-01", "end": "2024-12-31", "interval": "1d"}

    cases = {
        "backtest-sma.json": ("trend_up", {**base, "strategy": "sma_crossover", "fast_window": 17, "slow_window": 50}),
        "backtest-rsi.json": ("mean_revert", {**base, "strategy": "rsi_mean_reversion"}),
    }
    for name, (asset, body) in cases.items():
        api_main.fetch_prices = lambda *_args, _asset=asset, **_kwargs: fixture_prices(_asset)
        response = client.post("/backtests", json=body)
        response.raise_for_status()
        (OUT / name).write_text(json.dumps(response.json(), separators=(",", ":")) + "\n")

    runs = client.get("/backtests")
    runs.raise_for_status()
    (OUT / "runs.json").write_text(json.dumps(runs.json(), indent=2) + "\n")

    for path in sorted(OUT.glob("*.json")):
        print(f"{path.name}: {path.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
