// How long a request can run before the status explains the wait. A warm API
// answers in about a second, so anything past this is almost always the
// free-tier server waking from sleep.
export const SLOW_REQUEST_MS = 5_000;

export function loadingMessage({ hasResult, slow }: { hasResult: boolean; slow: boolean }) {
  if (slow) return "The free-tier API is waking up. This can take up to a minute.";
  return hasResult ? "Running backtest…" : "Loading an example AAPL backtest…";
}
