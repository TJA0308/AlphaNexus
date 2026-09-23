"use client";

import * as Slider from "@radix-ui/react-slider";

import type { BacktestRequest, BarInterval, Strategy } from "../lib/types";

type Props = {
  form: BacktestRequest;
  onChange: (patch: Partial<BacktestRequest>) => void;
};

type NumberFieldProps = {
  id: string;
  label: string;
  value: number;
  onChange: (value: number) => void;
  min?: number;
  step?: number;
};

function NumberField({ id, label, value, onChange, min, step = 1 }: NumberFieldProps) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        type="number"
        min={min}
        step={step}
        // An emptied box reads as NaN; show it empty rather than as "NaN".
        value={Number.isNaN(value) ? "" : value}
        onChange={(event) => onChange(event.target.valueAsNumber)}
      />
    </div>
  );
}

export function ControlsPanel({ form, onChange }: Props) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <span>Research Workbench</span>
        <h1>AlphaNexus</h1>
        <p>Configure market data, strategy rules, and cost assumptions.</p>
      </div>

      <section className="section">
        <h2>Market</h2>
        <div className="field">
          <label htmlFor="ticker">Ticker</label>
          <input id="ticker" value={form.ticker} onChange={(event) => onChange({ ticker: event.target.value.toUpperCase() })} />
        </div>
        <div className="field-grid">
          <div className="field">
            <label htmlFor="start">Start</label>
            <input id="start" type="date" value={form.start} onChange={(event) => onChange({ start: event.target.value })} />
          </div>
          <div className="field">
            <label htmlFor="end">End</label>
            <input id="end" type="date" value={form.end} onChange={(event) => onChange({ end: event.target.value })} />
          </div>
        </div>
        <div className="field">
          <label htmlFor="interval">Interval</label>
          <select
            id="interval"
            value={form.interval}
            onChange={(event) => onChange({ interval: event.target.value as BarInterval })}
          >
            <option value="1d">1d (daily)</option>
            <option value="1h">1h (hourly, last ~2 years only)</option>
          </select>
        </div>
      </section>

      <section className="section">
        <h2>Strategy</h2>
        <div className="field">
          <label htmlFor="strategy">Strategy</label>
          <select id="strategy" value={form.strategy} onChange={(event) => onChange({ strategy: event.target.value as Strategy })}>
            <option value="sma_crossover">SMA Crossover</option>
            <option value="rsi_mean_reversion">RSI Mean Reversion</option>
            <option value="bollinger_breakout">Bollinger Breakout</option>
          </select>
        </div>

        {form.strategy === "sma_crossover" ? (
          <div className="field">
            <div className="range-label">
              <label id="sma-label">SMA Windows</label>
              <span>
                {form.fast_window} / {form.slow_window} bars
              </span>
            </div>
            <Slider.Root
              className="range-slider"
              aria-labelledby="sma-label"
              min={5}
              max={200}
              minStepsBetweenThumbs={5}
              step={1}
              value={[form.fast_window, form.slow_window]}
              onValueChange={([fast, slow]) => onChange({ fast_window: fast, slow_window: slow })}
            >
              <Slider.Track className="range-track">
                <Slider.Range className="range-fill" />
              </Slider.Track>
              <Slider.Thumb className="range-thumb" aria-label="Fast SMA window" />
              <Slider.Thumb className="range-thumb" aria-label="Slow SMA window" />
            </Slider.Root>
          </div>
        ) : null}

        {form.strategy === "rsi_mean_reversion" ? (
          <>
            <NumberField id="rsiWindow" label="RSI Window" min={2} value={form.rsi_window} onChange={(rsi_window) => onChange({ rsi_window })} />
            <div className="field-grid">
              <NumberField id="oversold" label="Oversold" min={1} value={form.oversold} onChange={(oversold) => onChange({ oversold })} />
              <NumberField id="overbought" label="Overbought" min={1} value={form.overbought} onChange={(overbought) => onChange({ overbought })} />
            </div>
          </>
        ) : null}

        {form.strategy === "bollinger_breakout" ? (
          <div className="field-grid">
            <NumberField id="bandWindow" label="Band Window" min={2} value={form.band_window} onChange={(band_window) => onChange({ band_window })} />
            <NumberField id="bandStd" label="Band Width (σ)" min={0.1} step={0.1} value={form.band_std} onChange={(band_std) => onChange({ band_std })} />
          </div>
        ) : null}
      </section>

      <section className="section">
        <h2>Portfolio</h2>
        <div className="field-grid">
          <NumberField id="cash" label="Starting Cash" min={1} step={100} value={form.starting_cash} onChange={(starting_cash) => onChange({ starting_cash })} />
          <NumberField
            id="allocation"
            label="Allocation %"
            min={1}
            value={Math.round(form.allocation * 100)}
            onChange={(value) => onChange({ allocation: value / 100 })}
          />
        </div>
        <div className="field-grid">
          <NumberField id="fees" label="Fee bps" min={0} value={form.fee_bps} onChange={(fee_bps) => onChange({ fee_bps })} />
          <NumberField id="slippage" label="Slip bps" min={0} value={form.slippage_bps} onChange={(slippage_bps) => onChange({ slippage_bps })} />
        </div>
      </section>
    </aside>
  );
}
