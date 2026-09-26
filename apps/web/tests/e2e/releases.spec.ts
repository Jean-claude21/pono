import { expect, test, type Page } from "@playwright/test";

// T036 — the guarded release in the console: verdicts, guards, approval, protection, rollback,
// evidence log. The mock service plays lectio with one refused and one waiting change.

const LECTIO = "01990000-0000-7000-8000-000000000001";

// The project page compiles on its first visit in the dev server; running beside the other files,
// that first compilation alone can take most of the default minute.
test.describe.configure({ timeout: 120_000 });

async function open(page: Page, locale: "fr" | "en" = "fr") {
  await page.context().addCookies([
    { name: "pono_session", value: "healthy", url: "http://localhost:3100" },
    { name: "pono_locale", value: locale, url: "http://localhost:3100" },
  ]);
  await page.goto(`/workshop/projects/${LECTIO}`);
  await page.waitForLoadState("networkidle");
}

async function noHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth,
  );
  expect(overflow).toBe(false);
}

test("a refused change shows why, and offers nothing to approve", async ({ page }, info) => {
  await open(page);
  const refused = page.locator("article.release", { hasText: "Proposition n° 12" });
  await expect(refused.getByText("Refusée")).toBeVisible();
  await expect(refused.getByText("Une migration détruit des données.")).toBeVisible();
  await expect(refused.getByText(/drizzle\/0003_drop_notes\.sql · ligne 2 · suppression de colonne/)).toBeVisible();
  await expect(refused.getByRole("button", { name: /Valider/ })).toHaveCount(0);
  await noHorizontalScroll(page);
  await info.attach("releases", { body: await page.screenshot({ fullPage: true }), contentType: "image/png" });
});

test("a waiting change is approved on its exact version", async ({ page }) => {
  await open(page);
  const waiting = page.locator("article.release", { hasText: "Proposition n° 13" });
  await waiting.getByRole("button", { name: "Valider la version a1b2c3d" }).click();
  await expect(waiting.getByText("Validée par alice")).toBeVisible();
});

test("production is protected on a click and rolled back after a confirmation", async ({ page }) => {
  await open(page);
  await page.getByRole("button", { name: "Protéger la production" }).click();
  await expect(page.getByText("Protégée · main")).toBeVisible();

  await page.getByRole("button", { name: "Revenir à la version précédente" }).click();
  await expect(page.getByRole("alertdialog")).toContainText("La base n’est pas modifiée.");
  await page.getByRole("button", { name: "Confirmer le retour arrière" }).click();
  await expect(page.getByText("Retour arrière demandé.")).toBeVisible();
});

test("the evidence log lists what happened, newest first", async ({ page }, info) => {
  await open(page);
  await page.getByRole("link", { name: "Journal de preuves" }).click();
  await expect(page.getByRole("heading", { name: "Journal de preuves", level: 1 })).toBeVisible();
  const rows = page.locator("tbody tr");
  await expect(rows).toHaveCount(4);
  await expect(rows.first()).toContainText("En attente de validation");
  await expect(rows.nth(2)).toContainText("coding-agent[bot]");
  await noHorizontalScroll(page);
  await info.attach("journal", { body: await page.screenshot({ fullPage: true }), contentType: "image/png" });
});

test("the guarded release speaks English too", async ({ page }) => {
  await open(page, "en");
  await expect(page.getByRole("heading", { name: "Releases" })).toBeVisible();
  await expect(page.getByText("A migration destroys data.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Evidence log" })).toBeVisible();
});
