"""Bounded, process-local request limits for the public backtest endpoint."""

from __future__ import annotations

import math
import time
from collections import OrderedDict
from threading import Lock


class BacktestLimiter:
    """Fixed windows per client; expired windows are removed in start order.

    At capacity, new clients wait for expiry rather than evicting live limits.
    Multiple workers each have their own budget; use a shared gateway limiter
    if the service is scaled beyond a single worker.
    """

    def __init__(self, limit: int = 20, window_seconds: int = 60, max_clients: int = 4096) -> None:
        if min(limit, window_seconds, max_clients) <= 0:
            raise ValueError("rate limit settings must be positive")
        self.limit = limit
        self.window_seconds = window_seconds
        self.max_clients = max_clients
        self._windows: OrderedDict[str, tuple[float, int]] = OrderedDict()
        self._lock = Lock()

    def retry_after(self, client: str) -> int:
        """Consume one request, or return seconds until a request can proceed."""
        with self._lock:
            now = time.monotonic()
            while self._windows:
                _, (started, _) = next(iter(self._windows.items()))
                if now - started < self.window_seconds:
                    break
                self._windows.popitem(last=False)

            window = self._windows.get(client)
            if window is None:
                if len(self._windows) >= self.max_clients:
                    started, _ = next(iter(self._windows.values()))
                    return max(1, math.ceil(started + self.window_seconds - now))
                self._windows[client] = (now, 1)
                return 0

            started, count = window
            if count >= self.limit:
                return max(1, math.ceil(started + self.window_seconds - now))
            self._windows[client] = (started, count + 1)
            return 0
