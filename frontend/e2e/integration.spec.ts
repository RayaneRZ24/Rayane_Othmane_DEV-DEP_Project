import { expect, test } from "@playwright/test";

test("les machines se rejouent par observation avec pause et reprise", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Vue d’ensemble" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Lancer", exact: true })).toBeEnabled();
  const scenarios = (await (await page.request.get("/api/backend/api/v1/scenarios")).json()).items;
  expect(scenarios.length).toBeGreaterThan(0);
  await page.getByLabel("Machine", { exact: true }).selectOption(scenarios[0].id);
  await page.getByLabel("Méthode d’analyse", { exact: true }).selectOption("robust-mad-v1");
  await page.getByLabel("Cadence", { exact: true }).selectOption("60");
  const started = page.waitForResponse(r => r.url().endsWith("/commands") && r.request().method() === "POST");
  await page.getByRole("button", { name: "Lancer", exact: true }).click();
  const run = await (await started).json() as { id: string };
  const endpoint = `/api/backend/api/v1/runs/${run.id}`;
  try {
    await expect(page.locator(".observations-scroll tbody tr").first()).toBeVisible();
    await expect(page.locator(".alert-entry").first()).toBeVisible({ timeout: 15000 });
    await page.getByRole("button", { name: "Pause", exact: true }).click();
    await expect(page.getByRole("button", { name: "Reprendre" })).toBeEnabled();
    const paused = await (await page.request.get(endpoint)).json();
    await page.waitForTimeout(1100);
    expect((await (await page.request.get(endpoint)).json()).cursor_index).toBe(paused.cursor_index);
    const alerts = await (await page.request.get(`${endpoint}/alerts`)).json();
    expect(alerts.total).toBeGreaterThan(0);
    expect(alerts.analyzed_index).toBe(paused.cursor_index);
    expect(alerts.items.every((a: { detected_index: number; evidence: { sample_index: number } }) => a.detected_index <= paused.cursor_index && a.evidence.sample_index <= paused.cursor_index)).toBe(true);
    expect(JSON.stringify(alerts)).not.toMatch(/test_label|interpretation_label|is_anomaly/);
    await page.getByRole("button", { name: "Voir les mesures", exact: true }).first().click();
    await expect(page.locator(".alert-evidence").first()).toBeVisible();
    await expect(page.getByLabel("Machine", { exact: true })).toBeDisabled();
    await page.screenshot({ path: "../reports/interface_smd.png", fullPage: true });
    const memory = page.getByRole("group", { name: "Ressources" }).getByRole("button", { name: /Mémoire/ });
    await memory.click();
    await expect(memory).toHaveAttribute("aria-pressed", "true");
    const feature = scenarios.find((s: { id: string }) => s.id === paused.scenario_id).features.find((f: { group: string }) => f.group === "memory");
    await expect(page.getByLabel("Indicateur", { exact: true })).toHaveValue(feature.id);
    await expect(page.locator(".observations-scroll tbody tr").first()).toBeVisible();
    const data = await (await page.request.get(`${endpoint}/metrics?feature=${feature.id}&to_index=999999`)).json();
    expect(data.items.every((p: { sample_index: number }) => p.sample_index <= paused.cursor_index)).toBe(true);
    await page.getByRole("button", { name: "Reprendre" }).click();
    await expect.poll(async () => (await (await page.request.get(endpoint)).json()).cursor_index).toBeGreaterThan(paused.cursor_index);
    await page.getByRole("button", { name: "Arrêter", exact: true }).click();
    await expect(page.getByLabel("Machine", { exact: true })).toBeEnabled();
    if (scenarios.length > 1) {
      await page.getByLabel("Machine", { exact: true }).selectOption(scenarios[1].id);
      await expect(page.getByTestId("replay-position")).toHaveText("—");
      await expect(page.locator(".observations-scroll tbody tr")).toHaveCount(0);
    }
    await expect(page.locator("body")).not.toContainText(/Rayane|Othmane|SMD|PostgreSQL|FastAPI|Next\.js|Données du projet|UTC|Heure UTC|Événements/i);
    expect(errors).toEqual([]);
  } finally {
    const current = await (await page.request.get(endpoint)).json();
    if (["created", "running", "paused"].includes(current.status))
      await page.request.post(`${endpoint}/commands`, { data: { command_id: crypto.randomUUID(), action: "stop" } });
  }
});

test("un registre vide ne propose aucune lecture", async ({ page }) => {
  await page.route("**/api/backend/api/v1/scenarios", route => route.fulfill({ json: { items: [] } }));
  await page.route("**/api/backend/api/v1/runs", route => route.fulfill({ json: { items: [] } }));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Aucune machine disponible" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Lancer", exact: true })).toHaveCount(0);
});

test("la méthode combinée est choisie explicitement et analysée jusqu’au curseur", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Lancer", exact: true })).toBeEnabled();
  await page.getByLabel("Méthode d’analyse", { exact: true }).selectOption("pca-joint-v1");
  await page.getByLabel("Cadence", { exact: true }).selectOption("60");
  const started = page.waitForResponse(r => r.url().endsWith("/commands") && r.request().method() === "POST");
  await page.getByRole("button", { name: "Lancer", exact: true }).click();
  const run = await (await started).json();
  const endpoint = `/api/backend/api/v1/runs/${run.id}`;
  try {
    expect(run.detector_name).toBe("pca-joint-v1");
    expect(run.detector_version).toBe("pca-joint-v1");
    await expect.poll(async () => (await (await page.request.get(endpoint)).json()).analyzed_index).toBeGreaterThan(10);
    await page.getByRole("button", { name: "Pause", exact: true }).click();
    await expect(page.getByLabel("Méthode d’analyse", { exact: true })).toBeDisabled();
    const paused = await (await page.request.get(endpoint)).json();
    expect(paused.analyzed_index).toBe(paused.cursor_index);
    const alerts = await (await page.request.get(endpoint + "/alerts")).json();
    expect(alerts.detector_version).toBe("pca-joint-v1");
    expect(alerts.items.every((a: { evidence: { method: string } }) => a.evidence.method === "pca-joint-v1")).toBe(true);
  } finally {
    await page.request.post(endpoint + "/commands", { data: { command_id: crypto.randomUUID(), action: "stop" } });
  }
});

test("la supervision reste utilisable sur un petit écran", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Vue d’ensemble" })).toBeVisible();
  await expect(page.getByLabel("Machine", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});


test("une alerte ancienne ouvre sa période et les filtres distinguent les composants", async ({ page }) => {
  const features = [
    { id: "cpu_r", label: "Charge CPU", group: "cpu", unit: "normalized" },
    { id: "disk_q", label: "File disque", group: "disk", unit: "normalized" },
    { id: "disk_r", label: "Lectures disque", group: "disk", unit: "normalized" },
  ];
  const run = { id: "history", scenario_id: "machine", machine_id: "machine", status: "completed", cursor_index: 20000, speed: 60, detector_name: "robust-mad-v1" };
  const alert = { id: "old-alert", feature_id: "disk_r", feature_label: "Lectures disque", resource: "disk", status: "recovered", start_index: 998, detected_index: 1000, last_anomalous_index: 1005, closed_index: 1010, evidence: {} };
  const resource_counts = { cpu: { total: 51, active: 0 }, memory: { total: 0, active: 0 }, disk: { total: 1, active: 0 }, network: { total: 0, active: 0 } };
  await page.route("**/api/backend/api/v1/**", async route => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/scenarios")) return route.fulfill({ json: { items: [{ id: "machine", display_name: "Machine", sample_count: 20001, features }] } });
    if (url.pathname.endsWith("/runs")) return route.fulfill({ json: { items: [run] } });
    if (url.pathname.endsWith("/events")) return route.fulfill({ contentType: "text/event-stream", body: "" });
    if (url.pathname.endsWith("/alerts")) {
      const component = url.searchParams.get("resource");
      return route.fulfill({ json: { items: component === "disk" || !component ? [alert] : [], total: component === "memory" ? 0 : component === "disk" ? 1 : 52, active_count: 0, resource_counts, feature_counts: { cpu_r: 51, disk_r: 1 }, analyzed_index: 20000, detector_version: "robust-mad-v1" } });
    }
    if (url.pathname.endsWith("/metrics")) {
      const end = Number(url.searchParams.get("to_index"));
      const begin = Number(url.searchParams.get("from_index") ?? end - 499);
      return route.fulfill({ json: { items: Array.from({ length: end - begin + 1 }, (_, i) => ({ sample_index: begin + i, value: .2 })), effective_to_index: end, next_cursor: null } });
    }
    return route.fulfill({ json: run });
  });
  await page.goto("/");
  const filters = page.getByRole("group", { name: "Filtrer les alertes par composant" });
  await filters.getByRole("button", { name: /Disque/ }).click();
  await expect(page.locator(".alert-entry")).toHaveCount(1);
  await page.getByRole("group", { name: "Ressources" }).getByRole("button", { name: /Disque/ }).click();
  await expect(page.locator(".chart-context")).toContainText("0 alertes sur cet indicateur · 1 sur le composant Disque");
  const historical = page.waitForResponse(response => response.url().includes("/metrics?") && response.url().includes("from_index=800"));
  await page.getByRole("button", { name: "Afficher sur le graphique" }).click();
  await historical;
  await expect(page.getByLabel("Indicateur", { exact: true })).toHaveValue("disk_r");
  await expect(page.locator(".chart-context")).toContainText(/Alerte sélectionnée.*1.000/);
  const indices = await page.locator(".observations-scroll tbody tr td:first-child").allTextContents();
  expect(indices.every(index => Number(index.replace(/[^0-9]/g, "")) <= 1100)).toBe(true);
  await page.getByRole("button", { name: "Revenir aux dernières observations" }).click();
  await expect(page.locator(".observations-scroll tbody tr").first()).toContainText(/20.000/);
  await filters.getByRole("button", { name: /Mémoire/ }).click();
  await expect(page.locator(".alerts-empty")).toContainText("Aucune alerte détectée pour le composant Mémoire");
  await filters.getByRole("button", { name: /Tous/ }).click();
  await page.getByRole("button", { name: "Plus anciennes" }).click();
  await filters.getByRole("button", { name: /Disque/ }).click();
  await expect(page.getByRole("button", { name: "Plus récentes" })).toBeDisabled();
});
