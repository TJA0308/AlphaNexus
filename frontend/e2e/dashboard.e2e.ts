import { expect, test, type Page, type Route } from "@playwright/test";
import { readFile } from "node:fs/promises";

import rsiResult from "./fixtures/backtest-rsi.json";
import smaResult from "./fixtures/backtest-sma.json";
import runs from "./fixtures/runs.json";

type Stub = { status?: number; body: unknown; delayMs?: number };

// Answer every API call from fixtures. POSTs are recorded so tests can check
// what the dashboard sent.
async function stubApi(page: Page, backtest: Stub | ((body: Record<string, unknown>) => Stub)) {
  const posts: { url: string; body: Record<string, unknown> }[] = [];

  await page.route("**/backtests**", async (route: Route) => {
    const request = route.request();
    if (request.method() === "GET") {
      return route.fulfill({ json: runs });
    }
    const body = request.postDataJSON() as Record<string, unknown>;
    posts.push({ url: request.url(), body });
    const reply = typeof backtest === "function" ? backtest(body) : backtest;
    if (reply.delayMs) await new Promise((resolve) => setTimeout(resolve, reply.delayMs));
    return route.fulfill({ status: reply.status ?? 200, json: reply.body });
  });

  return posts;
}

test("first visit runs the example backtest without saving it and renders every chart", async ({ page }) => {
  const posts = await stubApi(page, { body: smaResult });

  await page.goto("/");

  await expect(page.locator(".badge").first()).toHaveText("AAPL");
  expect(posts).toHaveLength(1);
  expect(posts[0].url).toContain("save=false");
  expect(posts[0].body.strategy).toBe("sma_crossover");

  // Metrics come from the response, formatted.
  const metrics = page.locator(".metric");
  await expect(metrics).toHaveCount(8);
  await expect(metrics.filter({ hasText: "Round Trips" })).toContainText(String(smaResult.metrics.trade_count));

  // Both charts must actually draw a series, not just axes. The drawdown
  // chart once rendered empty because its <Area> sat inside a <LineChart>.
  await expect(page.locator(".recharts-line-curve").first()).toHaveAttribute("d", /.{50,}/);
  await expect(page.locator(".recharts-area-area")).toHaveAttribute("d", /.{50,}/);
});

test("running a different strategy sends it, saves it, and relabels the result", async ({ page }) => {
  const posts = await stubApi(page, (body) => ({ body: body.strategy === "rsi_mean_reversion" ? rsiResult : smaResult }));
  await page.goto("/");
  await expect(page.locator(".badge").first()).toHaveText("AAPL");

  await page.selectOption("#strategy", "rsi_mean_reversion");
  await page.locator(".top-actions .primary-button").click();

  await expect(page.locator(".badge-row")).toContainText("RSI Mean Reversion");
  const manual = posts.at(-1)!;
  expect(manual.url).not.toContain("save=false");
  expect(manual.body.strategy).toBe("rsi_mean_reversion");
});

test("the trade ledger and run history tabs show their data", async ({ page }) => {
  await stubApi(page, { body: smaResult });
  await page.goto("/");
  await expect(page.locator(".badge").first()).toHaveText("AAPL");

  await page.getByRole("tab", { name: "Trades" }).click();
  await expect(page.locator(".scroll-table tbody tr")).toHaveCount(smaResult.trades.length);

  await page.getByRole("tab", { name: "History" }).click();
  await expect(page.getByRole("tabpanel")).toContainText("SMA Crossover");
  await expect(page.getByRole("tabpanel").locator("tbody tr")).toHaveCount(runs.length);
});

test("a validation error from the API is shown as a message instead of crashing the page", async ({ page }) => {
  // FastAPI reports schema errors as a list of objects. Rendering that list
  // directly once crashed the dashboard.
  await stubApi(page, {
    status: 422,
    body: { detail: [{ loc: ["body", "oversold"], msg: "Input should be greater than 0" }] },
  });

  await page.goto("/");

  await expect(page.getByRole("status")).toContainText("oversold: Input should be greater than 0");
  await expect(page.getByRole("heading", { name: "Performance Dashboard" })).toBeVisible();
});

test("a slow API is explained as a cold start", async ({ page }) => {
  await stubApi(page, { body: smaResult, delayMs: 7_000 });

  await page.goto("/");

  await expect(page.getByRole("status")).toContainText("waking up", { timeout: 6_500 });
  await expect(page.locator(".badge").first()).toHaveText("AAPL", { timeout: 10_000 });
});

test("an invalid date range disables Run and says why", async ({ page }) => {
  await stubApi(page, { body: smaResult });
  await page.goto("/");
  await expect(page.locator(".badge").first()).toHaveText("AAPL");

  await page.fill("#end", "2000-01-01");

  await expect(page.locator(".top-actions .primary-button")).toBeDisabled();
  await expect(page.getByRole("status")).toContainText("Start date must be before end date");
});

test("multiple tickers are blocked before another request is sent", async ({ page }) => {
  const posts = await stubApi(page, { body: smaResult });
  await page.goto("/");
  await expect(page.locator(".badge").first()).toHaveText("AAPL");

  await page.fill("#ticker", "AAPL MSFT");
  await expect(page.locator(".top-actions .primary-button")).toBeDisabled();
  await expect(page.getByRole("status")).toContainText("Enter one ticker");
  expect(posts).toHaveLength(1);

  await page.fill("#ticker", "BRK-B");
  await expect(page.locator(".top-actions .primary-button")).toBeEnabled();
});

test("a cleared fee field shows an inline error", async ({ page }) => {
  const posts = await stubApi(page, { body: smaResult });
  await page.goto("/");
  await expect(page.locator(".badge").first()).toHaveText("AAPL");

  await page.fill("#fees", "");
  await expect(page.locator(".top-actions .primary-button")).toBeDisabled();
  await expect(page.getByRole("status")).toContainText("Fees and slippage cannot be negative");
  expect(posts).toHaveLength(1);
});

test("a rate-limited request explains when to retry", async ({ page }) => {
  const message = "Too many backtests. Try again in 60 seconds.";
  await stubApi(page, { status: 429, body: { detail: message } });
  await page.goto("/");
  await expect(page.getByRole("status")).toContainText(message);
  await expect(page.getByRole("heading", { name: "Performance Dashboard" })).toBeVisible();
});

test("both CSV buttons download the displayed result", async ({ page }) => {
  await stubApi(page, { body: smaResult });
  await page.goto("/");
  await expect(page.locator(".badge").first()).toHaveText("AAPL");
  await page.getByRole("tab", { name: "Exports" }).click();

  for (const [label, rows] of [
    ["Equity Curve CSV", smaResult.equity_curve],
    ["Trade Ledger CSV", smaResult.trades],
  ] as const) {
    const pendingDownload = page.waitForEvent("download");
    await page.getByRole("button", { name: label }).click();
    const download = await pendingDownload;
    expect(download.suggestedFilename()).toMatch(/^aapl_sma_crossover_.*\.csv$/);
    const path = await download.path();
    expect(path).not.toBeNull();
    const csv = await readFile(path!, "utf8");
    const lines = csv.trim().split(/\r?\n/);
    expect(lines).toHaveLength(rows.length + 1);
    expect(lines[0]).toContain(label === "Equity Curve CSV" ? '"date","close"' : '"date","side","signal_date"');
    expect(lines[1]).toContain(String(rows[0].close));
    if (label === "Trade Ledger CSV") {
      expect(lines[0]).toContain('"fill_price","fee","shares","cash_before","cash_after"');
      expect(lines[1]).toContain(String(smaResult.trades[0].fill_price));
      // Reconcile a downloaded trade, not just the response fixture.
      const fields = lines[1].split(",").map((field) => field.slice(1, -1));
      const [fill, fee, shares, before, after] = fields.slice(4, 9).map(Number);
      expect(after).toBeCloseTo(before - fill * shares - fee, 7);
    }
  }
});

test("ledger displays fill prices and fees separately from reference closes", async ({ page }) => {
  await stubApi(page, { body: smaResult });
  await page.goto("/");
  await expect(page.locator(".badge").first()).toHaveText("AAPL");
  await page.getByRole("tab", { name: "Trades" }).click();
  const table = page.locator(".scroll-table");
  await expect(table).toContainText("fill price");
  await expect(table).toContainText("reference close");
  await expect(table).toContainText("cash after");
});

test("excessive costs are rejected before submitting", async ({ page }) => {
  const posts = await stubApi(page, { body: smaResult });
  await page.goto("/");
  await expect(page.locator(".badge").first()).toHaveText("AAPL");
  await page.fill("#slippage", "20000");
  await expect(page.locator(".top-actions .primary-button")).toBeDisabled();
  await expect(page.getByRole("status")).toContainText("1,000 bps");
  expect(posts).toHaveLength(1);
});

test("the page never scrolls sideways", async ({ page }) => {
  // On phones a `1fr` grid track once let the form widen the page past the
  // screen. The mobile project runs this at a phone viewport.
  await stubApi(page, { body: smaResult });
  await page.goto("/");
  await expect(page.locator(".badge").first()).toHaveText("AAPL");

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});
