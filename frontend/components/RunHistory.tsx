import { percent, sqliteTimestampLabel } from "../lib/format";
import { STRATEGY_LABELS, type RunSummary } from "../lib/types";
import { DataTable } from "./DataTable";

type Props = {
  runs: RunSummary[];
  error: string;
  onRefresh: () => void;
  onOpen: (id: number) => void;
  onClone: (id: number) => void;
  busy: boolean;
};

export function RunHistory({ runs, error, onRefresh, onOpen, onClone, busy }: Props) {
  const rows = runs.map((run) => ({
    ran_at: sqliteTimestampLabel(run.created_at),
    ticker: run.ticker,
    strategy: STRATEGY_LABELS[run.strategy] ?? run.strategy,
    window: `${run.start_date} → ${run.end_date} (${run.interval})`,
    return: percent(run.total_return),
    buy_and_hold: percent(run.benchmark_return),
    sharpe: run.sharpe_ratio.toFixed(2),
    max_drawdown: percent(run.max_drawdown),
    round_trips: run.trade_count,
  }));

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h3>Run History</h3>
          <span className="muted">Shared history, newest first. Export important experiments; older runs can expire.</span>
        </div>
        <button className="secondary-button" onClick={onRefresh}>
          Refresh
        </button>
      </div>
      {error ? <p className="error">{error}</p> : null}
      <DataTable rows={rows} emptyMessage="No saved runs yet." actions={(index) => {
        const run = runs[index];
        return run.has_snapshot ? (
          <div className="export-actions">
            <button className="secondary-button" disabled={busy} onClick={() => onOpen(run.id)} aria-label={`Open run ${run.id}`}>
              Open
            </button>
            <button className="secondary-button" disabled={busy} onClick={() => onClone(run.id)} aria-label={`Clone run ${run.id}`}>
              Clone settings
            </button>
          </div>
        ) : <span className="muted">Summary only</span>;
      }} />
    </section>
  );
}
