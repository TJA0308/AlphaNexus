import { expect, test, type Page, type Route } from "@playwright/test";

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

test("the page never scrolls sideways", async ({ page }) => {
  // On phones a `1fr` grid track once let the form widen the page past the
  // screen. The mobile project runs this at a phone viewport.
  await stubApi(page, { body: smaResult });
  await page.goto("/");
  await expect(page.locator(".badge").first()).toHaveText("AAPL");

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});
