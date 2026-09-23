import { expect, test } from "@playwright/test";

// T066 — language from the browser, an explicit choice that sticks, and no mixed-language screen.

const FRENCH_ONLY = ["Projets", "Importer", "Connexions", "il y a", "Se déconnecter"];
const ENGLISH_ONLY = ["Projects", "Import a project", "Connections", " ago", "Sign out"];

test.describe("browser language", () => {
  test.use({ locale: "en-US" });
  test("an English browser gets English", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("html")).toHaveAttribute("lang", "en");
    await expect(page.getByRole("link", { name: "Sign in" })).toBeVisible();
  });
});

test.describe("unsupported language", () => {
  test.use({ locale: "de-DE" });
  test("falls back to French", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("html")).toHaveAttribute("lang", "fr");
    await expect(page.getByRole("link", { name: "Se connecter" })).toBeVisible();
  });
});

test.describe("explicit choice", () => {
  test.use({ locale: "en-US" });
  test("wins over the browser and survives a reload", async ({ page, context }) => {
    await page.goto("/", { waitUntil: "networkidle" });
    await expect(page.locator("html")).toHaveAttribute("lang", "en");

    await page.locator(".locale-switch button[lang='fr']").click();
    await expect(page.locator("html")).toHaveAttribute("lang", "fr");
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("lang", "fr");
    const cookies = await context.cookies();
    expect(cookies.find((cookie) => cookie.name === "pono_locale")?.value).toBe("fr");
  });
});

for (const [locale, foreign] of [
  ["en", FRENCH_ONLY],
  ["fr", ENGLISH_ONLY],
] as const) {
  test(`the ${locale} workshop holds no word of the other language`, async ({ page, context }) => {
    await context.addCookies([
      { name: "pono_session", value: "failing", url: "http://localhost:3100" },
      { name: "pono_locale", value: locale, url: "http://localhost:3100" },
    ]);
    for (const path of ["/workshop", "/workshop/connections"]) {
      await page.goto(path);
      await expect(page.locator("html")).toHaveAttribute("lang", locale);
      const text = await page.locator("body").innerText();
      for (const word of foreign) expect(text, `${path} shows "${word}"`).not.toContain(word);
    }
  });
}
