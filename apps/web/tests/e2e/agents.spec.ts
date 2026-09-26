import { expect, test, type Page } from "@playwright/test";

// T025 — agents in the console (003): consent, the linked agents and their revocation, an agent's
// rollback request decided by the person, and the public privacy page; French and English.

const CONSOLE = "http://localhost:3100";
const CONSENT = "/oauth/consent?request=consent-handle-0123456789";
const VESTIO = "01990000-0000-7000-8000-000000000002";

test.describe.configure({ timeout: 120_000 });

async function signIn(page: Page, locale: "fr" | "en" = "fr", session = true) {
  await page.context().addCookies([
    { name: "pono_locale", value: locale, url: CONSOLE },
    ...(session ? [{ name: "pono_session", value: "healthy", url: CONSOLE }] : []),
  ]);
}

async function noHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth,
  );
  expect(overflow).toBe(false);
}

test("a person grants an agent read-only access, and it goes back to the agent", async ({
  page,
}, info) => {
  await signIn(page);
  await page.goto(CONSENT);
  await page.waitForLoadState("networkidle");
  await expect(
    page.getByRole("heading", { name: "Claude veut accéder à ton atelier", level: 1 }),
  ).toBeVisible();
  await expect(page.getByText("Organisation : alice")).toBeVisible();
  await expect(page.getByText(/Jamais, quel que soit l’accès : valider une mise en ligne/)).toBeVisible();
  await expect(page.getByRole("radio", { name: /Lecture et actions/ })).toBeChecked();
  await info.attach("consent", { body: await page.screenshot({ fullPage: true }), contentType: "image/png" });

  await page.getByRole("radio", { name: /Lecture seule/ }).check();
  await page.getByRole("button", { name: "Autoriser" }).click();
  await page.waitForURL(/\/privacy\?decision=approve&access=read/);
});

test("a refusal goes back to the agent too", async ({ page }) => {
  await signIn(page);
  await page.goto(CONSENT);
  await page.waitForLoadState("networkidle");
  await page.getByRole("button", { name: "Refuser" }).click();
  await page.waitForURL(/\/privacy\?decision=deny/);
});

test("signed out, the consent page sends to sign-in and back to the same request", async ({
  page,
}) => {
  await signIn(page, "fr", false);
  await page.goto(CONSENT);
  await page.waitForLoadState("networkidle");
  await expect(page.getByText("Connecte-toi pour décider.", { exact: false })).toBeVisible();
  await expect(page.getByRole("link", { name: "Se connecter" })).toHaveAttribute(
    "href",
    `/api/v1/auth/login?next=${encodeURIComponent(CONSENT)}`,
  );
});

test("an unknown or expired request says so", async ({ page }) => {
  await signIn(page);
  await page.goto("/oauth/consent?request=not-a-known-request");
  await expect(page.getByRole("alert")).toContainText("inconnue, déjà traitée ou expirée");
});

test("the linked agents are listed and one is cut at once", async ({ page }, info) => {
  await signIn(page);
  await page.goto("/workshop/connections");
  await page.waitForLoadState("networkidle");
  const rows = page.locator("tr", { hasText: /Claude|Codex/ });
  await expect(rows).toHaveCount(2);
  await expect(page.locator("#agents-address")).toHaveText(`${CONSOLE}/mcp`);
  await noHorizontalScroll(page);
  await info.attach("agents", { body: await page.screenshot({ fullPage: true }), contentType: "image/png" });

  await page.locator("tr", { hasText: "Codex" }).getByRole("button", { name: "Couper l’accès" }).click();
  await expect(page.locator("tr", { hasText: "Codex" })).toHaveCount(0);
  await expect(page.locator("tr", { hasText: "Claude" })).toHaveCount(1);
});

test("an agent's rollback request waits for the person, who decides", async ({ page }, info) => {
  await signIn(page);
  await page.goto(`/workshop/projects/${VESTIO}`);
  await page.waitForLoadState("networkidle");
  const request = page.getByRole("alertdialog");
  await expect(request).toContainText("Claude demande un retour arrière");
  await expect(request).toContainText("La production n’a pas bougé");
  await info.attach("rollback-request", { body: await page.screenshot({ fullPage: true }), contentType: "image/png" });

  await request.getByRole("button", { name: "Écarter" }).click();
  await expect(page.getByText("Claude demande un retour arrière")).toHaveCount(0);
});

test("the privacy page is public, in French and in English, without horizontal scroll", async ({
  page,
}, info) => {
  await signIn(page, "fr", false);
  await page.goto("/privacy");
  await expect(
    page.getByRole("heading", { name: "Ce que Pono lit, garde, et ne fait jamais", level: 1 }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Tout retirer" })).toBeVisible();
  await page.setViewportSize({ width: 375, height: 812 });
  await noHorizontalScroll(page);
  await info.attach("privacy-mobile", { body: await page.screenshot({ fullPage: true }), contentType: "image/png" });

  await page.context().clearCookies();
  await signIn(page, "en", false);
  await page.goto("/privacy");
  await expect(
    page.getByRole("heading", { name: "What Pono reads, keeps, and never does", level: 1 }),
  ).toBeVisible();
});

test("agents' protocol paths reach the service through the console's address", async ({
  request,
}) => {
  const metadata = await request.get("/.well-known/oauth-authorization-server");
  const tools = await request.post("/mcp", { data: { jsonrpc: "2.0", id: 1, method: "tools/list" } });

  expect(await metadata.json()).toEqual({
    relayed: "/.well-known/oauth-authorization-server",
    method: "GET",
  });
  expect(await tools.json()).toEqual({ relayed: "/mcp", method: "POST" });
});

test("consent speaks English too, and fits a phone", async ({ page }) => {
  await signIn(page, "en");
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto(CONSENT);
  await page.waitForLoadState("networkidle");
  await expect(
    page.getByRole("heading", { name: "Claude wants access to your workshop", level: 1 }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Allow" })).toBeVisible();
  await noHorizontalScroll(page);
});
