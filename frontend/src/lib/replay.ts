export type Feature = { id: string; label: string; group: string; unit: "normalized" };
export type Scenario = { id: string; machine_id: string; display_name: string; start_index: number; end_index: number; sample_count: number; reference_samples: number; features: Feature[] };
export type DetectorName = "robust-mad-v1" | "pca-joint-v1";
export type Run = { detector_name: DetectorName; id: string; scenario_id: string; machine_id: string; status: string; cursor_index: number | null; speed: number; start_index: number; end_index: number };
export type Alert = { id: string; feature_id: string; feature_label: string; resource: string; status: string; start_index: number; detected_index: number; last_anomalous_index: number; closed_index: number | null; peak_score: number; evidence: { method?: string; contributors?: { feature_id: string; label: string; value: number; resource: string; contribution: number }[]; sample_index: number; value: number; reference_median: number; expected_lower: number; expected_upper: number } };
export type AlertPage = { items: Alert[]; total: number; active_count: number; resource_counts: Record<string, { total: number; active: number }>; feature_counts: Record<string, number>; cursor_index: number | null; analyzed_index: number | null; detector_version: string | null };
export type MetricPoint = { sample_index: number; value: number | null; observed: boolean };
export type Page<T> = { items: T[]; effective_to_index: number | null; next_cursor: string | null };
export async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api/backend/api/v1${path}`, {
    method: body ? "POST" : "GET", headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined, signal: AbortSignal.timeout(15000),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.error === "string" ? data.error : data.error?.message ?? "Le service est momentanément indisponible.");
  return data;
}
export const states: Record<string, string> = { created: "Prêt", running: "En cours", paused: "En pause", stopped: "Arrêté", completed: "Terminé", interrupted: "Interrompu", failed: "Erreur" };
export const groups: Record<string, string> = { cpu: "CPU", memory: "Mémoire", disk: "Disque", network: "Réseau" };
export const number = (value: number) => new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 5 }).format(value);
