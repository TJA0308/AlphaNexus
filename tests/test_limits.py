from concurrent.futures import ThreadPoolExecutor

import pytest

from api.limits import BacktestLimiter


def test_limits_are_independent_per_client_and_reset_after_expiry(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr("api.limits.time.monotonic", lambda: clock[0])
    limiter = BacktestLimiter(limit=1)
    assert limiter.retry_after("alice") == 0
    clock[0] += 0.1
    assert limiter.retry_after("alice") == 60
    assert limiter.retry_after("bob") == 0
    clock[0] = 1060.0
    assert limiter.retry_after("alice") == 0
    assert limiter.retry_after("bob") == 1


def test_full_limiter_does_not_evict_active_clients(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr("api.limits.time.monotonic", lambda: clock[0])
    limiter = BacktestLimiter(limit=1, max_clients=2)
    assert limiter.retry_after("alice") == 0
    assert limiter.retry_after("bob") == 0
    assert limiter.retry_after("charlie") == 60
    assert limiter.retry_after("alice") == 60
    clock[0] += 60
    assert limiter.retry_after("charlie") == 0


def test_concurrent_requests_cannot_exceed_the_budget():
    limiter = BacktestLimiter(limit=20)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(limiter.retry_after, ["alice"] * 100))
    assert results.count(0) == 20


@pytest.mark.parametrize("settings", [{"limit": 0}, {"window_seconds": -1}, {"max_clients": 0}])
def test_invalid_limits_are_rejected(settings):
    with pytest.raises(ValueError, match="positive"):
        BacktestLimiter(**settings)
