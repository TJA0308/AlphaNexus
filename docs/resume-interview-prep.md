# Resume and interview preparation

Use these drafts only for work you contributed to and can explain. Adjust verbs
to reflect your own role and describe any tools or assistance accurately.

## Resume bullets

For a software engineering internship, choose two or three:

- Built a full-stack backtesting workbench with Python, FastAPI, Next.js, and
  SQLite, supporting three strategies, daily and hourly data, and simulated
  transaction costs.
- Fixed a look-ahead bias by executing signals on a later bar, and added
  regression tests for signal timing, trading costs, and portfolio accounting.
- Benchmarked the engine across 72 deterministic market scenarios and added a
  CI performance guard; replaced pandas row iteration with NumPy-array
  processing. A documented local 50,000-bar run fell from about 8.8 s to 0.17 s.

For a technical product or startup role, consider substituting:

- Built an auditable experiment workflow that saves inputs and results, replays
  previous runs, and exposes simulated fills, fees, and cash balances.

The performance comparison is a historical local engine measurement, not an
end-to-end API latency or a production SLA. Be ready to explain the workload,
environment and evidence; omit the speedup if you cannot defend the comparison.
The 72 scenarios use synthetic fixtures, not 72 live assets. Avoid claiming
users, investment returns, or adoption without independent evidence.

## One-minute explanation

AlphaNexus lets someone compare simple trading strategies with buy-and-hold on
historical market data. A Next.js dashboard sends a configuration to a FastAPI
backend, which validates prices, computes indicators, simulates a long-only
portfolio with costs, and returns an equity curve and an auditable trade ledger.
The main engineering challenge was making results explainable: signals execute
after the bar that generated them, and short or malformed data is rejected.
Saved experiments preserve inputs for replay. The application is a research and
education tool; its simulations do not establish a profitable strategy.

## Questions to practice

**Why delay the signal?** A close-based indicator is only known after that
bar's close. Acting on it at that same close uses unavailable information.
The engine shifts the target position one bar and executes at the next close.
That remains a simplified execution model, not a guarantee of achievable fills.

**Why is the execution loop sequential?** Each trade depends on current cash
and holdings, which depend on previous executions. NumPy arrays avoid the
overhead of building a pandas Series for each row while preserving that state.

**What does the benchmark prove?** It measures the engine on 8 synthetic
fixtures, 3 date windows and 3 strategies. It excludes market-data downloads,
network latency and frontend rendering. CI guards p95 at 100 ms; local timings
vary by hardware and load.

**How do you make an experiment reproducible?** Save the request, input prices,
results and provenance, then replay the saved input through the installed
engine and compare outputs. Replay does not install the historical engine, and
the default hosted SQLite filesystem is ephemeral.

**How does walk-forward evaluation reduce overfitting?** Each window selects a
configuration on training data and evaluates that choice on subsequent test
data. Test windows roll forward. This makes the train/test distinction explicit,
but does not prove a strategy will perform well in the future. Test windows of
one bar are rejected because a sample standard deviation cannot be estimated.

**What would you improve next?** Durable hosted storage and per-user ownership,
instrument and market-session metadata, and feedback from real users. Discuss
the trade-off you would prioritize for the role instead of claiming these exist.

## Before an interview

1. Open the live demo and explain an example result and its limitations.
2. Trace one request from the form through validation, signal generation,
   portfolio simulation, metrics and persistence.
3. Practice explaining one bug, the test that caught it, and the fix.
4. Verify current CI and benchmark results; do not present old local timing as
   a universal or current guarantee.
