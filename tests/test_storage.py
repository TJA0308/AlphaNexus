import os

from alphanexus import storage


def sample_metrics(total_return: float) -> dict[str, float | int]:
    return {
        "total_return": total_return,
        "benchmark_return": 0.05,
        "sharpe_ratio": 1.2,
        "max_drawdown": -0.1,
        "trade_count": 3,
    }


def test_save_and_fetch_runs_returns_newest_first(tmp_path, monkeypatch):
    # Point storage at a throwaway database file for this test only.
    monkeypatch.setenv("DATABASE_PATH", os.path.join(tmp_path, "test_runs.db"))

    storage.save_run("AAPL", "sma_crossover", "2024-01-01", "2024-06-01", "1d", sample_metrics(0.10))
    storage.save_run("MSFT", "rsi_mean_reversion", "2024-01-01", "2024-06-01", "1d", sample_metrics(0.20))

    runs = storage.recent_runs()

    assert len(runs) == 2
    # Newest run (MSFT) comes back first.
    assert runs[0]["ticker"] == "MSFT"
    assert runs[1]["ticker"] == "AAPL"
    assert runs[0]["total_return"] == 0.20
    assert runs[0]["trade_count"] == 3


def test_recent_runs_respects_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", os.path.join(tmp_path, "test_runs.db"))

    for _ in range(5):
        storage.save_run("AAPL", "sma_crossover", "2024-01-01", "2024-06-01", "1d", sample_metrics(0.10))

    assert len(storage.recent_runs(limit=3)) == 3
