import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

test("save, reload, open, replay, clone and export through the real API", async ({ page }) => {
  const initial = page.waitForResponse((response) => response.url().endsWith("/backtests?save=false"));
  await page.goto("/");
  await initial;
  // Automatic trailing-year example may be outside the fixed fixture window.
  // Wait until it finishes before entering the reproducible test range.
  await expect(page.locator(".top-actions .primary-button")).not.toHaveText("Running...", { timeout: 20_000 });
  await page.fill("#start", "2024-01-01");
  await page.fill("#end", "2024-12-31");
  await page.fill("#fees", "83");
  await page.locator(".top-actions .primary-button").click();
  await expect(page.getByText(/Saved experiment #1\./)).toBeVisible();

  const reloaded = page.waitForResponse((response) => response.url().endsWith("/backtests?save=false"));
  await page.reload();
  await reloaded;
  await expect(page.locator(".top-actions .primary-button")).not.toHaveText("Running...", { timeout: 20_000 });
  await page.getByRole("tab", { name: "History" }).click();
  await page.getByRole("button", { name: "Open run 1", exact: true }).click();
  await expect(page.getByText("Opened saved run #1 using its original results.")).toBeVisible();
  await expect(page.locator("#fees")).toHaveValue("83");
  await page.getByRole("button", { name: "Verify replay" }).click();
  await expect(page.getByText(/Replay verified for run #1/)).toBeVisible();

  const pending = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export experiment JSON" }).click();
  const download = await pending;
  const manifest = JSON.parse(await readFile((await download.path())!, "utf8"));
  expect(manifest.snapshot.request.fee_bps).toBe(83);
  expect(manifest.snapshot.dataset.source).toBe("synthetic-integration-fixture");
  expect(manifest.snapshot.dataset.rows.length).toBeGreaterThan(200);
  expect(manifest.snapshot.dataset.sha256).toMatch(/^[a-f0-9]{64}$/);
  for (const trade of manifest.snapshot.result.trades) {
    expect(trade.cash).toBeCloseTo(trade.cash_before - trade.trade_signal * trade.shares * trade.fill_price - trade.fee, 7);
  }

  await page.getByRole("tab", { name: "History" }).click();
  await page.getByRole("button", { name: "Clone run 1", exact: true }).click();
  await expect(page.getByText(/Settings copied from run #1/)).toBeVisible();
  await page.fill("#fees", "84");
  await page.locator(".top-actions .primary-button").click();
  await expect(page.getByText(/Saved experiment #2\./)).toBeVisible();
});
