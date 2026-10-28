"""Test-only API process: real routes/storage, deterministic provider data."""

import atexit
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
test_database = tempfile.TemporaryDirectory(prefix="alphanexus-integration-")
atexit.register(test_database.cleanup)
os.environ["DATABASE_PATH"] = str(Path(test_database.name) / "experiments.db")

import api.main as api  # noqa: E402
from benchmarks.scenarios import load_fixture  # noqa: E402


def fixture_prices(ticker, start, end, interval="1d"):
    prices = load_fixture("mean_revert")
    prices = prices[(prices.date >= str(start)) & (prices.date <= str(end))].copy()
    prices.attrs["source"] = "synthetic-integration-fixture"
    return prices


api.fetch_prices = fixture_prices
app = api.app
