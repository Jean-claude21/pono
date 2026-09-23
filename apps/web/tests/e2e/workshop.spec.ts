import { expect, test, type Page } from "@playwright/test";

// T054 — the workshop renders at 1440 px with no data, healthy data and failing data.

async function open(page: Page, scenario: string) {
  await page.context().addCookies([
    { name: "pono_session", value: scenario, url: "http://localhost:3100" },
    { name: "pono_locale", value: "fr", url: "http://localhost:3100" },
  ]);
  await page.goto("/workshop");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "console");
}

async function noHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth,
  );
  expect(overflow).toBe(false);
}

test("an empty workshop invites to connect the providers", async ({ page }, info) => {
  await open(page, "empty");
  await expect(page.getByRole("heading", { name: "Projets", level: 1 })).toBeVisible();
  await expect(page.getByText("Ton atelier est vide.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Relier mes fournisseurs" })).toBeVisible();
  await expect(page.locator("table.table")).toHaveCount(0);
  await noHorizontalScroll(page);
  await info.attach("empty", { body: await page.screenshot(), contentType: "image/png" });
});

test("a healthy workshop lists every project without a verdict", async ({ page }, info) => {
  await open(page, "healthy");
  await expect(page.locator("tbody tr")).toHaveCount(3);
  await expect(page.locator(".verdict")).toHaveCount(0);
  await expect(page.locator("tbody .state-healthy")).toHaveCount(2);
  await expect(page.locator("tbody .state-idle")).toHaveCount(1);
  await expect(page.locator(".filters [aria-pressed='true']")).toContainText("Tous");
  await noHorizontalScroll(page);
  await info.attach("healthy", { body: await page.screenshot(), contentType: "image/png" });
});

test("a failing project comes first, in a verdict, and the filter keeps it alone", async ({
  page,
}, info) => {
  await open(page, "failing");
  const verdict = page.locator(".verdict").first();
  await expect(verdict).toContainText("La production de nyatefe ne répond pas.");
  await expect(verdict).toContainText("+ 2 à décider");
  await expect(page.locator(".env .down")).toHaveCount(1);
  await expect(page.locator(".meter.crit")).toHaveCount(1);
  await expect(page.locator(".meter.warn")).toHaveCount(1);
  await noHorizontalScroll(page);
  await info.attach("failing", { body: await page.screenshot(), contentType: "image/png" });

  await page.getByRole("button", { name: /En panne/ }).click();
  await expect(page).toHaveURL(/state=failing/);
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await expect(page.locator("tbody tr")).toContainText("nyatefe");

  await verdict.getByRole("link", { name: "Ouvrir" }).click();
  await expect(page.getByRole("heading", { name: "nyatefe", level: 1 })).toBeVisible();
  await expect(page.getByText("ne répond pas").first()).toBeVisible();
});

test("without a session the console sends the person back to sign in", async ({ page }) => {
  await page.goto("/workshop");
  await expect(page).toHaveURL(/\/\?error=auth.session_required/);
  await expect(page.getByRole("alert")).toBeVisible();
});

test("the person links and unlinks the chat for quota alerts", async ({ page }, info) => {
  await open(page, "healthy");
  await page.goto("/workshop/connections");
  await page.waitForLoadState("networkidle");

  await page.getByRole("button", { name: "Relier Telegram" }).click();
  const open_ = page.getByRole("link", { name: "Ouvrir Telegram" });
  await expect(open_).toHaveAttribute("href", /start=one-time-code$/);
  await page.getByRole("button", { name: "C’est fait" }).click();
  await expect(page.getByText("Relié : tes alertes arrivent sur Telegram")).toBeVisible();
  await noHorizontalScroll(page);
  await info.attach("chat-linked", { body: await page.screenshot(), contentType: "image/png" });

  await page.getByRole("button", { name: "Délier" }).click();
  await expect(page.getByRole("button", { name: "Relier Telegram" })).toBeVisible();
});
