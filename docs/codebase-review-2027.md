# AlphaNexus: codebase and 2027 internship review

Reviewed 2026-10-26 at commit `6d0fe5fc0758d894d06db273e276f18af87a3ec4`.
This is an evaluation and proposed roadmap, not a claim that the proposed features have been implemented.

## Verdict

AlphaNexus is already worth putting on an internship resume. It demonstrates a complete request-to-result path, readable domain logic, API design, frontend state management, testing, deployment configuration, and performance work. Its strongest positioning is backend/full-stack engineering applied to research tooling.

The current product is a well-built single-run backtesting demonstration. The strongest next version is a reproducible experiment workbench for student investment clubs and finance students: a researcher can preserve an experiment, compare assumptions, inspect every execution, and hand the result to another person who can reproduce it. That solves a concrete collaboration and research-integrity problem.

The project is not evidence of profitable trading, institutional research readiness, production scale, or ML expertise. Actual users and measured usefulness are not established by the repository. A score would be subjective; the most useful assessment is strong engineering foundation, moderate product differentiation, and incomplete research reproducibility and operating evidence.

## Evidence and verification

- Read the engine, indicators, strategies, metrics, data adapter, persistence, API, limiter, frontend page/components/helpers, tests, benchmark, deployment configuration, CI, and architecture/interview documentation.
- Inspected the checked-in dashboard screenshot. This is a visual assessment of that artifact and the source, not a live accessibility audit.
- Python: 129 tests passed, 97.51% line coverage. Pytest reported a cache-directory permission warning, not a test failure.
- Frontend: 42 unit tests passed; ESLint, TypeScript checking and the production build passed. All 22 Playwright tests passed using installed Microsoft Edge across desktop and mobile viewports (11 cases each); these tests mock API responses.
- The deployed frontend returned HTTP 200 and the deployed API health endpoint returned `{"status":"ok"}`. These checks establish reachability, not complete production correctness.
- One live, unsaved API backtest also succeeded: AAPL, 2024-01-01 through 2024-12-31, SMA 17/50, HTTP 200, 251 equity points and five executions (two completed round trips plus an open entry). This verifies one live provider-to-result path, not exhaustive production behavior or a live browser journey.
- Python Ruff lint passed.
- Deterministic engine benchmark: 72/72 scenarios, 24,120 total rows, median 11.79 ms, p95 34.60 ms, max 78.34 ms in this run. Timing was measured while other review checks were active; it is not a controlled comparative performance result.
- Additional local probes used synthetic data and unsaved TestClient requests. They reproduced the invalid-cost result, missing fill-price disclosure, permissive data validation, and RSI initialization difference described below.
- The installed environment is not the declared dependency environment: examples include pandas 2.3.0 versus required >=3.0.6, yfinance 1.4.1 versus >=1.7.0, FastAPI 0.139.0 versus >=0.142.2, and installed Next.js 15.5.27 versus >=15.5.28. Passing checks here do not certify a clean deployment with declared versions.
- Docker execution, remote branch protection, private hosting settings, dependency vulnerability status, and production load behavior were not verified by this review.

## What is already good

1. **Appropriate architecture.** A small modular monolith is a sensible choice. Domain calculations do not import FastAPI or React. The storage module provides a clear replacement boundary.
2. **Meaningful correctness tests.** Signal lag, RSI warm-up, cash allocation, fees, slippage, executed trade quantities, open positions, and metric calculations receive direct tests. These are stronger evidence than coverage alone.
3. **Good state handling.** The frontend stores a result with the request that produced it, preventing edited controls from silently relabeling old output.
4. **Operational care.** The cache and limiter are bounded and locked; SQLite connections close explicitly; history has a retention cap; Docker runs as a non-root user.
5. **Honest presentation.** The app acknowledges underperformance, calls raw return difference excess return rather than alpha, and documents next-close execution and costless buy-and-hold.
6. **Useful automation.** Unit, browser, lint, build, benchmark, and container-health checks are represented in CI. The benchmark excludes unreliable network timing.

## Findings, ordered by practical importance

### 1. Persisted history cannot reproduce a run — high product priority

Evidence: `alphanexus/storage.py:54`, `api/main.py:84`, and `frontend/components/RunHistory.tsx`.

The database stores aggregate metrics plus ticker, strategy name, dates, and interval. It omits strategy parameters, fees, slippage, cash, allocation, data snapshot/hash, engine version, complete results, and ownership. POST discards the ID returned by `save_run`; there is no GET-by-ID endpoint. Two different experiments can therefore look identical in history, and a user cannot reopen the exact result.

Persist a versioned experiment record containing the normalized request, dataset reference/hash, provider and retrieval timestamp, price-adjustment policy, engine revision, result, and completion/save status. Add GET-by-ID, reopen, clone, and export-manifest actions. Preserve input data where its permitted use allows, or support user-supplied datasets. A hash alone cannot reconstruct missing data.

Acceptance: after restarting the service, reopen an experiment and reproduce metrics and trades from its preserved inputs without downloading newer data. Use explicit numerical tolerances and record dependency versions.

### 2. Extreme costs produce impossible long-only results — confirmed correctness bug

Evidence: `api/main.py:41` and `alphanexus/backtest.py:85`.

Fees and slippage have lower bounds but no upper bounds. A local request using the existing synthetic sample, SMA 2/5, and `slippage_bps=20000` returned HTTP 200, ending equity about -$3,330 from $10,000 and a -133.3% return. `fee_bps=20000` also produced negative proceeds. Slippage above 100% makes the sell execution price negative.

Define supported financial ranges, reject non-finite values and excessive magnitudes, and enforce domain invariants in the engine as well as the API. Direct engine callers currently bypass even the API's nonnegative-cost checks. Validate strategy constraints before downloading market data.

Acceptance: invalid costs fail before provider work; supported inputs preserve nonnegative cash/shares and positive fill prices. Include zero-cost and boundary cases.

### 3. The ledger omits actual execution prices and fees — confirmed auditability gap

Evidence: `alphanexus/backtest.py:71`, `api/main.py:74`, and `frontend/app/page.tsx` trade/export mapping.

The engine calculates an execution price and fee, but returns the bar close as the ledger's displayed `price`. With a $12 close and 1% slippage the buy actually fills at $12.12. The UI/CSV displays $12 and does not show the fee, preventing direct cash reconciliation from the ledger alone.

Persist signal timestamp, execution timestamp, reference close, fill price, quantity, fee, cash before/after, and realized PnL. Label reference price separately. Add a selected-trade explanation showing the arithmetic.

Acceptance: every entry and exit can be reconciled using only its exported trade record, without reading application source.

### 4. Asset scope and metric assumptions disagree — high research priority

Evidence: `alphanexus/metrics.py:16`, `alphanexus/data.py` ticker pattern, and `frontend/lib/format.ts`.

The API accepts symbols such as crypto and foreign listings, while annualization always assumes 252 US equity sessions and seven hourly bars per session; the UI always displays USD. These assumptions are not valid for all accepted assets.

Start by explicitly supporting USD-denominated US equities/ETFs with validated asset metadata, currency and exchange calendar. Expand only when calendars, currencies and annualization are modeled. Seven bars is a documented approximation for US hourly data, not a universal statistical guarantee: the short last bar, overnight returns and serial dependence still matter.

Acceptance: unsupported instruments are rejected clearly or have correct metadata-dependent calculations; currency is explicit in output.

### 5. Provider outages can still look like bad user input — confirmed adapter mismatch

Evidence: `alphanexus/data.py:125` and upstream yfinance 1.7.0 `multi.py`.

AlphaNexus assumes an empty download proves the ticker/window is invalid. The upstream downloader catches per-symbol exceptions and substitutes empty frames. Consequently a provider/network failure can reach AlphaNexus as an empty frame and become HTTP 400 instead of 502. Existing tests cover an exception thrown by the stub and a separate empty frame; they do not establish the actual adapter distinction.

Use a provider boundary that preserves structured errors, with tested behavior for the pinned dependency. Distinguish unavailable provider, missing dataset, unsupported interval, and invalid input. Do not treat every empty frame as evidence that the user made a mistake.

Source: https://github.com/ranaroussi/yfinance/blob/1.7.0/yfinance/multi.py

### 6. Input data lacks a quality contract — confirmed validation gap

Evidence: `alphanexus/data.py:64` and `alphanexus/backtest.py:32`.

Normalization checks columns, drops null dates/closes, and sorts. A local probe confirmed duplicate timestamps and a negative close survive. There are no systematic checks for finite numeric prices, positive closes, OHLC consistency, timezone/calendar consistency, missing sessions, or incomplete current bars. Direct engine callers can also pass missing closes, which are removed only after signal generation.

Validate before calculating indicators. Reject invalid structural data; report legitimate calendar gaps with an explicit policy rather than silently inventing prices. Record requested and actual coverage. Treat current, incomplete bars explicitly. Historical provider data can be revised, so the comment claiming a closed historical window never changes should be corrected.

Acceptance: duplicate/non-finite/nonpositive data fixtures fail deterministically; malformed input never generates a successful result containing NaN or infinity.

### 7. RSI initialization differs from conventional SMA-seeded Wilder RSI

Evidence: `alphanexus/indicators.py:42` and the interview sheet's Wilder description.

`ewm(alpha=1/window, adjust=False)` uses the first observation to seed the recurrence. `min_periods` masks early output but does not replace that seed with the average of the first window. On closes [10, 11, 10, 12] with window 3, the current first defined RSI is 83.3333; SMA-seeded Wilder RSI is 75. This can change threshold crossings.

Either document the exact variant or implement the intended initialization and verify against a small independently hand-calculated reference. Boundedness and monotonic-series tests do not establish equivalence to the named convention.

### 8. Research comparisons need explicit policies, not just more metrics

Evidence: `alphanexus/backtest.py:111`, the data adapter, and README limitations.

Current behavior intentionally uses next-close execution, no dividend income, costless buy-and-hold from the first bar, and strategy warm-up inside the measured window. These are documented modeling choices, not hidden look-ahead bugs. However, long-window SMA results include a substantial idle period while the benchmark is already invested, and dividends are missing from both sides.

Add a pre-roll window to warm indicators before the evaluation period. Define the first tradable evaluation bar precisely. Offer explicit price-return versus total-return policies and a benchmark cost policy. If using adjusted OHLC for research, label its synthetic nature; if modeling actual holdings, handle corporate actions and cash distributions consistently. Simply toggling `auto_adjust` does not create a full brokerage accounting model.

Add chronological train/validation/holdout evaluation. Parameters must be selected using training data only; earlier bars may warm indicators without fitting on held-out outcomes. Define position state at fold boundaries. Record the number of configurations tried, because repeatedly inspecting a holdout compromises its role.

### 9. Save failure and durability are not visible to users

Evidence: `api/main.py:213`, `alphanexus/storage.py` module documentation, and `render.yaml`.

The POST endpoint logs SQLite failure and still returns a successful result. Keeping the computed result is good, but the response does not say saving failed. GET history does not have the equivalent graceful error handling. History is shared globally and deployment configuration does not establish a persistent database volume.

Return `run_id`, `saved`, and a user-readable warning when persistence fails. For the real shared-workbench use case, add managed identity, server-enforced ownership, durable storage, migrations, and backup/restore verification. For a public anonymous demo, clearly label shared ephemeral history instead. SQLite on durable disk remains appropriate for a small single-instance application; Postgres becomes useful with hosted multi-user access and concurrency requirements.

### 10. Browser coverage is not yet full-stack integration coverage

Evidence: `frontend/e2e/dashboard.e2e.ts:10` and `.github/workflows/ci.yml`.

Playwright intercepts every backtest/history call. This is good deterministic UI coverage, but it cannot detect a broken browser-to-FastAPI contract or persistence failure. Python TestClient tests exercise another important slice independently.

Keep both and add one CI journey using the real local API, temporary database, and deterministic provider fixture: submit, inspect result, save, reload, reopen, export and reconcile. Also verify failed-save behavior and ownership boundaries when introduced. Ensure generated browser fixtures cannot silently drift from the response schema.

### 11. Operational and claim hygiene

- Pin/lock Python dependency resolution and use an isolated environment. Verify builds against committed manifests, not stale node_modules. Run tests on the supported runtime.
- Add request IDs and structured timings for download, cache lookup, simulation, serialization, and persistence. Measure complete request latency separately from engine runtime.
- Add a global concurrency/work budget and input-size limits if the service is exposed broadly. Per-IP limits do not bound total work. Cache locking protects dictionary state but does not coalesce simultaneous misses for the same dataset.
- Keep the synchronous endpoint for small runs. A queue, worker, job status and cancellation become useful for parameter grids/walk-forward jobs; they are unnecessary overhead for today's small single run.
- The health endpoint is liveness, not evidence of provider/database readiness. Expose appropriately scoped diagnostics and test recovery without making liveness depend on Yahoo being reachable.
- The frontend timeout is cleared once response headers arrive, before the body is read. Move body consumption into the timeout's protected scope if promising a total request deadline.
- README counts are stale: 98 Python/32 frontend/14 browser versus 129 Python/42 frontend and 11 browser cases configured across two viewports. Its architecture labels Render as Docker, while `render.yaml` and deployment docs specify native Python.
- The checked-in benchmark matrix has at most roughly 503 bars per scenario. The headline 50,000-bar/50x claim is not reproduced by that command. Preserve a before/after harness or exact commits, machine details, repeated timing and output-equivalence evidence before using that number in an interview.

## Recommended product and UI

Target one workflow: a student investment-club researcher evaluates a rule, tests whether its conclusion survives costs and another date window, and hands a reproducible report to a teammate.

Proposed flow: define a hypothesis -> choose a dataset -> inspect data quality -> run a baseline -> compare a small parameter/cost grid -> evaluate a held-out period -> save -> reopen/share -> export evidence.

The existing dark layout is coherent. A redesign is less valuable than improving decisions and inspection:

1. Add a compact run summary above charts: requested/actual dates, source timestamp, price policy, execution model, data warnings, and saved status.
2. Show a complete read-only configuration for the displayed result, including strategy-specific windows/thresholds. Mark edited-but-not-run settings clearly.
3. Make History useful: name, reopen, clone and compare experiments; clearly distinguish personal runs from public examples.
4. Add buy/sell markers, synchronized chart tooltips and a ledger-linked execution inspector. Show close, actual fill and fees separately.
5. Add side-by-side baseline comparison with changed assumptions highlighted. Distinguish training and held-out periods visually.
6. Add an explicitly labeled bundled example with fixed dates/results for reliable first visits. Offer live execution separately; never disguise cached example results as a fresh run.
7. Use metric help text, units, sample counts and meaningful undefined states. Preserve keyboard operation and inspect screen-reader/chart alternatives and contrast rather than relying only on a no-overflow mobile test.
8. Provide exact numeric SMA entry as well as sliders. Show field-level errors and useful user-facing recovery actions; deployment environment variable names belong in developer diagnostics.

Validate this with 3-5 intended users. Ask each to compare two assumptions, reopen an experiment later, and explain one trade. Measure task completion, time, mistakes and repeat usage. Record actual observations; do not turn the number of classmates invited into an adoption claim.

## Sequenced roadmap

Effort estimates assume focused part-time work and familiarity with the code; adjust them to learning needs.

| Stage | Scope | Completion evidence | Approximate effort |
| --- | --- | --- | --- |
| 1 | Validate costs/data/assets; correct provider error handling; define RSI convention; expose fills/fees | Hand-calculated regression fixtures and reconciled CSV | 4-7 focused days |
| 2 | Versioned complete runs, GET-by-ID, reopen/clone, durable persistence and honest save status | Restart-and-replay test with no provider fetch | 1-2 weeks |
| 3 | Pre-roll, explicit price/benchmark policies, small sensitivity comparison and chronological holdout | Controlled example where selecting on training cannot inspect holdout | 1-2 weeks |
| 4 | Full-stack CI journey, logs/timings, reliable example, ownership if multi-user | One reproducible user journey plus failure/recovery demonstration | About 1 week |
| 5 | User sessions, targeted UI changes, case study and interview rehearsal | Measured task outcomes and an explainable demo | About 1 week, partly parallel with development |

Interview preparation should start in stage 1. Avoid postponing applications until every optional feature is complete. Do not add Kubernetes, microservices, an LLM chat panel, more indicators or live brokerage execution merely to lengthen the technology list.

## 2027 resume positioning

This assessment is about project fit, not a prediction of interview callbacks or an assessment of the rest of the resume.

| Role | Current fit | What would make the evidence stronger |
| --- | --- | --- |
| Backend / full-stack SWE intern | Strongest fit | Reproducible persistence, failure handling, real user workflow |
| Fintech / financial-software intern | Good | Data/asset policies, auditable ledger, cost and benchmark correctness |
| QA / SDET / developer tooling | Good | Independent reference cases, real integration journey, reproducible failures |
| Data engineering / analytics engineering | Supporting project | Versioned datasets, quality checks, lineage, ingestion/replay |
| Quant developer | Credible starting point | Numerical references, financial conventions, profiling and stronger research protocol |
| Quant research / ML research | Limited evidence today | Statistical validation and research methodology; there is no ML model here |
| Infrastructure / SRE | Supporting evidence | Deployment/recovery exercises, observability, measured load behavior |

Current 2027 postings support emphasizing ownership and fundamentals. Amazon's SDE internship explicitly discusses validating AI-generated code, AI-assisted development, the development lifecycle, and operation. Atlassian lists programming, data structures/algorithms, project experience and system-design awareness. These examples do not establish a universal policy for every employer.

Sources:
- https://www.amazon.jobs/en/jobs/10552937/software-development-engineer-intern-summer-2027-usa
- https://www.atlassian.com/company/careers/details/26266

Suggested current resume wording, subject to truthful personal attribution:

- Built a Python/FastAPI and Next.js/TypeScript backtesting workbench with configurable execution costs, benchmark comparison, CSV export and SQLite run history.
- Added regression coverage for execution timing, indicator warm-up and portfolio accounting; verified 129 Python tests at 97.5% line coverage and 42 frontend unit tests.
- Implemented a deterministic 72-scenario engine benchmark and CI checks for tests, linting, frontend builds and container health.

Use 2-3 bullets, tailored to the job. Replace a testing bullet with a measured user outcome once one exists. Only claim the 50x optimization after reproducing its evidence and understanding it. Describe deployment as Vercel + Render, with a separately CI-tested Docker image, unless production configuration changes.

## Interview preparation: ownership through demonstrations

The existing `docs/project-defense.md` is a useful map. Update its counts, RSI description and unsupported performance claims, and use it as a practice guide rather than a script to memorize. A source review cannot establish what the author personally understands; a practical rehearsal can.

### Week 1: trace one experiment and calculate it by hand

Draw: React form/state -> HTTP/JSON -> Pydantic -> provider/cache -> normalized data -> indicators -> lagged target -> sequential execution -> metrics -> SQLite -> response -> charts/exports.

Explain where validation, serialization, side effects and failures occur. Reconstruct a six-to-ten-bar SMA example manually, showing signal time, fill time, cash and shares.

For one entry: spend $1,000, reference close $100, slippage 1%, fee 1%. Fill price is $101; position notional is $1,000/1.01; quantity is $1,000/(1.01*101), approximately 9.80296 shares. On exit at reference $110, fill is $108.90 and fee is 1% of gross proceeds, leaving about $1,056.44. Realized PnL is about $56.44. Explain why marking an open position to the close differs from liquidating it with costs.

Study Python dataclasses, pandas rolling/ewm operations, NumPy arrays, floating-point arithmetic, O(n) loop time/memory, sample standard deviation, drawdown, and Sharpe assumptions.

### Week 2: own the backend and data boundaries

Explain 400/422/429/502, why CORS is not authentication, why SQLite transactions matter, why connections close, and what happens on a failed save. Trace a request using logs and a debugger.

Explain threadpool handling of synchronous FastAPI endpoints, the GIL's limits, cache TTL/eviction, duplicate concurrent downloads, process-local limits, and why adding workers changes their meaning. Explain when durable SQLite is enough and when shared Postgres is justified.

Implement one small domain fix independently, starting with a failing test. Good exercises: reject invalid costs, return save status, or add execution-price reporting.

### Week 3: own the frontend, integration and research limitations

Explain React render/state/effects, hydration, why initial dates are set after mount, why displayed results retain their original request, and the difference between TypeScript compile-time types and runtime response validation.

Inspect a browser request and response; explain timeout/error states, charts and export generation. Demonstrate a regression that unit tests miss but a browser test detects, and another that mocked browser tests miss but full-stack integration catches.

Explain the exact next-close model, warm-up policy, dividends, benchmark cost mismatch, partial bars, asset calendars, overfitting, chronological evaluation and repeated holdout inspection. Do not say one signal shift eliminates every possible form of research leakage.

### Week 4: rehearse defending decisions and failures

Prepare a 60-second pitch, a five-minute demo, a ten-minute architecture walkthrough and a deeper debugging conversation. Practice without AI assistance before using AI to critique the explanation.

Prepare three evidence-backed stories: a correctness defect, a performance/design tradeoff, and a user-driven improvement. For each: reproduce the issue, explain the cause, compare alternatives, show the fix/test and acknowledge its limits. Distinguish personal decisions from suggestions generated by tools.

An honest AI-workflow explanation, only if accurate: "I used AI for scaffolding, tests and implementation suggestions. I own the behavior: I can trace the execution, reproduce defects, explain design choices and show the tests I used to verify the changes."

Readiness checks:

- Can you draw the request path without opening the README?
- Can you explain one entry/exit calculation and one metric by hand?
- Can you locate and repair a small defect without an AI tool writing the answer?
- Can you explain what each test layer proves and what it misses?
- Can you explain why the benchmark excludes downloads and why 72 scenarios is not 72 statistically independent strategy discoveries?
- Can you explain how a saved run survives deployment and is reproduced after data revisions?
- Can you state one known limitation before an interviewer discovers it?
- Can you demonstrate a real user completing the intended workflow?

Continue separate data-structures/algorithms and general interview practice. Project fluency complements those skills; it does not replace them.
