import { expect, test } from "@playwright/test";

test("la supervision affiche les états réels sans détails internes", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Vue d’ensemble" })).toBeVisible();
  await expect(page.locator(".status-card").filter({ hasText: "STOCKAGE" })).toContainText("Connecté");
  await expect(page.locator(".status-card").filter({ hasText: "CONNEXION LIVE" })).toContainText("Connectée");
  await expect(page.locator("body")).not.toContainText(/Rayane|Othmane|RCAEval|Online Boutique|socle|persistance|PostgreSQL|FastAPI|Next\.js|Développement|Projet intelligent|Données du projet|migration/i);
  expect(errors).toEqual([]);
  await page.screenshot({ path: "../reports/socle-integration.png", fullPage: true });
});

test("la supervision reste utilisable sur un petit écran", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Vue d’ensemble" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
