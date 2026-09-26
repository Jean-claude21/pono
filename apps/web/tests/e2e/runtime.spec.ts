import { expect, test, type Page } from "@playwright/test";

// T031 — the development runtime in the console (004): its state and limits, the errors, the
// conflicts, the console's own way to write a file, and the open link; French and English.

const CONSOLE = "http://localhost:3100";
const LECTIO = "01990000-0000-7000-8000-000000000001";
const VESTIO = "01990000-0000-7000-8000-000000000002";

test.describe.configure({ timeout: 120_000 });

async function open(page: Page, project = LECTIO, locale: "fr" | "en" = "fr") {
  await page.context().addCookies([
    { name: "pono_session", value: "healthy", url: CONSOLE },
    { name: "pono_locale", value: locale, url: CONSOLE },
  ]);
  await page.goto(`/workshop/projects/${project}`);
  await page.waitForLoadState("networkidle");
}

async function noHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth,
  );
  expect(overflow).toBe(false);
}

test("a ready runtime shows its state, limits, last save, conflicts and errors", async ({ page }, info) => {
  await open(page);
  const panel = page.locator("section", { has: page.getByRole("heading", { name: "Runtime de développement" }) });
  await expect(panel.getByText("Prêt", { exact: true })).toBeVisible();
  await expect(panel.getByText("1 sur 3 runtimes démarrés · 1 Gio chacun · veille après 15 min")).toBeVisible();
  await expect(panel.getByText("Base de développement, jamais la production")).toBeVisible();
  await expect(panel.getByText("c0ffee1")).toBeVisible();
  await expect(panel.getByText("src/styles.css")).toBeVisible();
  await expect(panel.getByText("Unexpected token (3:14)")).toBeVisible();
  await expect(panel.getByText("src/routes/index.tsx, ligne 3")).toBeVisible();
  await expect(panel.getByRole("link", { name: "Ouvrir" })).toHaveAttribute(
    "href",
    `/runtime/open?project=${LECTIO}`,
  );
  await noHorizontalScroll(page);
  await info.attach("runtime", { body: await page.screenshot({ fullPage: true }), contentType: "image/png" });
});

test("the console writes a file like an agent, and says why a path is refused", async ({ page }) => {
  await open(page);
  await page.getByLabel("Chemin dans le projet").fill("src/title.ts");
  await page.getByLabel("Contenu").fill("export const title = 'Lectio';");
  await page.getByRole("button", { name: "Écrire", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("src/title.ts écrit : l’écran se met à jour.");

  await page.getByLabel("Chemin dans le projet").fill(".env");
  await page.getByRole("button", { name: "Écrire", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Ce chemin est hors du projet ou protégé.");
});

test("a project without a runtime offers to start one, and says when the limit is reached", async ({ page }) => {
  await open(page, VESTIO);
  const start = page.getByRole("button", { name: "Démarrer le runtime" });
  await expect(start).toBeVisible();
  await start.click();
  await expect(page.getByRole("alert")).toContainText("Trois runtimes sont déjà démarrés.");
});

test("opening goes through a one-time ticket", async ({ page }) => {
  await page.context().addCookies([{ name: "pono_session", value: "healthy", url: CONSOLE }]);
  await page.goto(`/runtime/open?project=${LECTIO}&return=/`);
  await page.waitForURL(/\/privacy\?runtime=opened/);
});

// The console on a phone is a known gap (docs/EXPLOITATION.md): the rail does not fold yet.
test("the runtime speaks English too", async ({ page }) => {
  await open(page, LECTIO, "en");
  await expect(page.getByRole("heading", { name: "Development runtime" })).toBeVisible();
  await expect(page.getByText("Development database, never production")).toBeVisible();
  await noHorizontalScroll(page);
});
