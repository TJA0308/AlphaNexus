import { dollars, percent } from "../lib/format";
import type { Metrics } from "../lib/types";

type Tone = "positive" | "negative" | undefined;

function tone(value: number): Tone {
  if (value > 0) return "positive";
  if (value < 0) return "negative";
  return undefined;
}

export function MetricsGrid({ metrics }: { metrics: Metrics | null }) {
  const cards: { label: string; value: string; tone?: Tone }[] = metrics
    ? [
        { label: "Ending Equity", value: dollars(metrics.ending_equity) },
        { label: "Strategy Return", value: percent(metrics.total_return), tone: tone(metrics.total_return) },
        { label: "Buy & Hold", value: percent(metrics.benchmark_return), tone: tone(metrics.benchmark_return) },
        {
          label: "Excess vs B&H",
          value: percent(metrics.excess_return_vs_benchmark),
          tone: tone(metrics.excess_return_vs_benchmark),
        },
        { label: "Max Drawdown", value: percent(metrics.max_drawdown), tone: tone(metrics.max_drawdown) },
        { label: "Sharpe Ratio", value: metrics.sharpe_ratio.toFixed(2) },
        { label: "Round Trips", value: String(metrics.trade_count) },
        { label: "Win Rate", value: metrics.trade_count ? percent(metrics.win_rate) : "n/a" },
      ]
    : ["Ending Equity", "Strategy Return", "Buy & Hold", "Excess vs B&H", "Max Drawdown", "Sharpe Ratio", "Round Trips", "Win Rate"].map(
        (label) => ({ label, value: "—" }),
      );

  return (
    <div className="metrics">
      {cards.map((card) => (
        <div className="metric" key={card.label}>
          <span>{card.label}</span>
          <strong className={card.tone}>{card.value}</strong>
        </div>
      ))}
    </div>
  );
}
