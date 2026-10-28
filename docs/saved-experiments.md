# Saved experiments and replay

New manual runs save their full request, validated input price rows, original
metrics/equity/trades, dataset SHA-256, capture time, available download time,
source label, price policy, engine source hash, and Python/NumPy/pandas versions.
Automatic example runs still use `save=false`.

## User workflow

1. Run an experiment. The result says whether it was saved and gives its ID.
2. Open History, then Open a run. Its original settings and results are restored.
3. Verify replay to recompute from the preserved input prices, without downloads.
4. Export experiment JSON to keep the request, input data, provenance and results.
5. Clone settings to edit the form and submit a separate run. Cloning alone does
   not execute or save anything and does not relabel the displayed result.

The original result is never overwritten by replay. Comparison covers every
metric, equity point and execution using relative tolerance `1e-10` and absolute
tolerance `1e-8`. A changed engine can report a mismatch; that is a useful finding,
not a reason to replace the saved result. Replay runs the installed engine, not
an archived executable. Provenance identifies the old code/environment but does
not install it automatically. Input hashing detects accidental row corruption;
it is not a signature proving authenticity against a malicious database editor.

## API

| Endpoint | Behavior |
| --- | --- |
| `POST /backtests` | Calculate and atomically save summary plus snapshot |
| `POST /backtests?save=false` | Calculate only |
| `GET /backtests` | Summaries with `has_snapshot` capability |
| `GET /backtests/{id}` | Complete experiment, suitable for JSON export |
| `POST /backtests/{id}/replay` | Recompute preserved inputs and compare; no new saved row |

Backtest responses include `run_id`, `saved`, and `save_warning`. A save failure
keeps the calculated result usable and explicitly says it was not saved. History
read failures return 503. Missing/expired runs return 404. Legacy summaries cannot
be reopened/replayed and return 409. Unsupported snapshot versions or failed
input integrity checks return 409 on replay. Replay shares the backtest rate limit.

## Migration and storage

SQLite `user_version=1` adds an `experiments` child table referencing `runs`.
Existing summary rows remain intact; they are shown as "Summary only". The
application never invents parameters or input data for old runs. Inserts and
retention pruning use the same transaction, and foreign keys cascade deletions.
Schema setup is idempotent. Newer unknown database versions are rejected.

Retention limits: newest 1,000 summaries and at most 128 MiB of serialized
experiment payloads, deleting the oldest experiments first. A single snapshot
over 8 MiB is refused with an unsaved-result warning. SQLite's allocated file
size may remain larger than retained payload size until vacuumed; these are
logical retention limits, not an OS disk quota.

History is shared and unauthenticated, as before. It is not a private workspace.
Do not store confidential inputs here. Export important runs before retention
removes them. Provider usage terms still apply to captured market data.

Snapshots survive process restarts **only while the database file survives**.
The current Render free deployment still uses ephemeral disk. Durable hosting
requires a persistent, writable volume and `DATABASE_PATH` pointing into it,
or a later managed-database implementation. No remote deployment or hosting
configuration has been changed by this build.

Before deploying: back up the database using SQLite's online backup API, deploy
the API before the frontend, and verify saved-run reopening after restart.
Do not copy a database during writes as a substitute for a consistent backup.
The additive schema supports old readers, but old writers do not enable foreign
keys; do not run old and new writers concurrently against the upgraded store.

## Verification

Python integration tests launch a fresh interpreter to reopen/replay a saved run
with the provider explicitly forbidden. Additional tests cover daylight-saving
offsets, transaction rollback, legacy migration, payload retention, corrupted
inputs, changed outputs, unavailable storage and replay rate limits.

The browser integration suite uses real FastAPI routes and a temporary SQLite
database; only the data provider is replaced with deterministic synthetic data.
No browser network interception is used. It saves, reloads, reopens, replays,
exports and reconciles trades, then clones settings into a new experiment.

From `frontend`, build and run on Windows:

```powershell
$env:NEXT_PUBLIC_API_BASE_URL='http://127.0.0.1:18001'
npm run build
$env:PW_CHANNEL='msedge'
npm run e2e:integration
```

The build-time API URL must match `PW_API_PORT` (default 18001). This test build
is for local verification; rebuild with the intended API URL before deployment.
CI runs both the mocked desktop/mobile suite and this real local integration.

Remaining work: durable hosted storage, personal ownership/authentication,
instrument metadata enforcement, session/partial-bar policies, and experiment
comparison with held-out evaluation.
