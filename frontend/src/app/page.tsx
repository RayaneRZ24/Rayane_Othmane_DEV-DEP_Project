"use client";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, Layers3, RefreshCw, Play, Pause, Square, Cpu, MemoryStick, HardDrive, Network, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { AlertsPanel } from "@/components/alerts-panel";
import { MetricChart } from "@/components/metric-chart";
import { api, groups, number, states, type Scenario, type Run, type Page, type MetricPoint, type AlertPage, type DetectorName, type Alert } from "@/lib/replay";

export default function Home() {
  const cache = useQueryClient();
  const scenarios = useQuery({ queryKey: ["scenarios"], queryFn: () => api<{ items: Scenario[] }>("/scenarios") });
  const runs = useQuery({ queryKey: ["runs"], queryFn: () => api<{ items: Run[] }>("/runs") });
  const [initialized, setInitialized] = useState(false);
  const [scenarioChoice, setScenario] = useState("");
  const [runId, setRunId] = useState<string | null>(null);
  const [group, setGroup] = useState("cpu");
  const [featureChoice, setFeature] = useState("");
  const [speed, setSpeed] = useState(10);
  const [detector, setDetector] = useState<DetectorName>("robust-mad-v1");
  const [search, setSearch] = useState("");
  const [connected, setConnected] = useState(false);
  const [alertOffset, setAlertOffset] = useState(0);
  const [alertResource, setAlertResource] = useState("");
  const [focusedAlert, setFocusedAlert] = useState<Alert | null>(null);
  useEffect(() => {
    if (!runs.data || initialized) return;
    const existing = runs.data.items.find(r => ["running", "paused"].includes(r.status)) ?? runs.data.items[0];
    if (existing) { setRunId(existing.id); setScenario(existing.scenario_id); setSpeed(existing.speed); setDetector(existing.detector_name ?? "robust-mad-v1"); }
    setInitialized(true);
  }, [runs.data, initialized]);
  const runQuery = useQuery({ queryKey: ["run", runId], queryFn: () => api<Run>(`/runs/${runId}`), enabled: !!runId, refetchInterval: 1000 });
  const run = runQuery.data;
  const scenario = scenarios.data?.items.find(s => s.id === scenarioChoice) ?? scenarios.data?.items[0];
  const features = scenario?.features.filter(f => f.group === group) ?? [];
  const feature = features.find(f => f.id === featureChoice) ?? features[0];
  const active = !!run && ["running", "paused"].includes(run.status);
  useEffect(() => {
    if (!runId) return;
    let last = 0;
    const source = new EventSource(`/api/backend/api/v1/runs/${runId}/events`);
    source.addEventListener("run.updated", (event: MessageEvent) => {
      try {
        const next = JSON.parse(event.data) as Run;
        if (next.id !== runId) return;
        setConnected(true);
        if (Date.now() - last > 750 || next.status !== "running") { cache.setQueryData(["run", runId], next); last = Date.now(); }
        if (["stopped", "completed", "interrupted", "failed"].includes(next.status)) { source.close(); setConnected(false); }
      } catch { setConnected(false); }
    });
    source.onerror = () => setConnected(false);
    source.addEventListener("run.unavailable", () => setConnected(false));
    return () => { source.close(); setConnected(false); };
  }, [runId, cache]);
  const cursor = run?.cursor_index ?? null;
  const chartEnd = focusedAlert ? Math.min(cursor ?? 0, focusedAlert.detected_index + 100) : cursor;
  const metrics = useQuery({
    queryKey: ["metrics", runId, feature?.id, focusedAlert ? focusedAlert.id : cursor, chartEnd],
    queryFn: () => api<Page<MetricPoint>>(`/runs/${runId}/metrics?${new URLSearchParams({ feature: feature!.id, to_index: String(chartEnd), ...(focusedAlert ? { from_index: String(Math.max(0, focusedAlert.detected_index - 200)) } : {}) })}`),
    enabled: cursor !== null && !!feature,
    placeholderData: (previous, query) => query?.queryKey[1] === runId && query?.queryKey[2] === feature?.id && typeof query?.queryKey[3] === "number" && !focusedAlert ? previous : undefined,
    gcTime: 10000,
  });
  const alerts = useQuery({
    queryKey: ["alerts", runId, cursor, alertOffset, run?.status, alertResource],
    queryFn: () => api<AlertPage>(`/runs/${runId}/alerts?offset=${alertOffset}&limit=50${alertResource ? `&resource=${alertResource}` : ""}`),
    enabled: !!runId, gcTime: 10000,
    placeholderData: (previous, query) => query?.queryKey[1] === runId && query?.queryKey[3] === alertOffset && query?.queryKey[5] === alertResource ? previous : undefined,
  });
  const action = useMutation({ mutationFn: async (stop: boolean) => {
    let current = run;
    if (!stop && (!current || !["created", "running", "paused"].includes(current.status))) {
      if (!scenario) throw new Error("Aucune machine disponible.");
      current = await api<Run>("/runs", { request_id: crypto.randomUUID(), scenario_id: scenario.id, speed, detector_name: detector });
      setRunId(current.id); setAlertOffset(0); setFocusedAlert(null); cache.setQueryData(["run", current.id], current);
    }
    if (!current) throw new Error("Aucune lecture en cours.");
    return api<Run>(`/runs/${current.id}/commands`, { command_id: crypto.randomUUID(), action: stop ? "stop" : current.status === "running" ? "pause" : current.status === "paused" ? "resume" : "start" });
  }, onSuccess: next => { cache.setQueryData(["run", next.id], next); void cache.invalidateQueries({ queryKey: ["runs"] }); }, onError: () => { void runQuery.refetch(); } });
  function chooseMachine(id: string) { setScenario(id); setRunId(null); setAlertOffset(0); setFocusedAlert(null); action.reset(); }
  const points = metrics.data?.items ?? [];
  const count = cursor === null ? 0 : cursor + 1;
  const total = scenario?.sample_count ?? 1;
  const error = action.error ?? scenarios.error ?? runs.error ?? runQuery.error ?? metrics.error ?? alerts.error;
  const icons = { cpu: Cpu, memory: MemoryStick, disk: HardDrive, network: Network };
  return <div className="app-shell">
    <aside className="sidebar"><a className="brand" href="/"><span className="brand-mark"><Activity size={22} /></span><span>smartops<span className="brand-dot">.</span></span></a><p className="nav-label product-nav-label">SUPERVISION</p><nav aria-label="Navigation principale"><a className="nav-item selected" href="/" aria-current="page"><Layers3 size={17} /> Vue d’ensemble<span className="nav-indicator" /></a></nav></aside>
    <div className="main-shell"><header className="topbar"><div><span className="muted">SmartOps</span><span className="breadcrumb-slash">/</span><span>Infrastructure</span></div><span className={`environment ${connected ? "is-connected" : ""}`}><span className="tiny-dot" />{active ? connected ? "Synchronisé" : "Synchronisation…" : "Relecture"}</span></header>
      <main><section className="page-heading"><h1>Vue d’ensemble</h1><Button variant="outline" className="refresh-button" onClick={() => void cache.invalidateQueries()}><RefreshCw size={14} />Actualiser</Button></section>
        {error && <p role="alert" className="error-banner">{error.message}</p>}
        {scenarios.isSuccess && !scenarios.data.items.length ? <section className="panel empty-state"><Activity size={28} /><h2>Aucune machine disponible</h2></section> : <>
          <section className="panel replay-controls" aria-label="Commandes de lecture">
            <label>Machine<select aria-label="Machine" value={scenario?.id ?? ""} disabled={active || action.isPending || !initialized} onChange={e => chooseMachine(e.target.value)}>{scenarios.data?.items.map(s => <option key={s.id} value={s.id}>{s.display_name}</option>)}</select></label>
            <label>Cadence<select aria-label="Cadence" value={speed} disabled={active || action.isPending} onChange={e => { setSpeed(Number(e.target.value)); setRunId(null); setFocusedAlert(null); }}>{[1, 10, 30, 60].map(s => <option key={s} value={s}>{s} obs/s</option>)}</select></label>
            <label>Méthode<select aria-label="Méthode d’analyse" value={detector} disabled={active || action.isPending} onChange={e => { setDetector(e.target.value as DetectorName); setRunId(null); setAlertOffset(0); setFocusedAlert(null); action.reset(); }}><option value="robust-mad-v1">Par indicateur</option><option value="pca-joint-v1">Indicateurs combinés</option></select></label>
            <div className="playback-buttons"><Button disabled={!scenario || !initialized || action.isPending} onClick={() => action.mutate(false)}>{run?.status === "running" ? <Pause size={15} /> : <Play size={15} />}{run?.status === "running" ? "Pause" : run?.status === "paused" ? "Reprendre" : "Lancer"}</Button><Button variant="outline" aria-label="Arrêter" disabled={!active || action.isPending} onClick={() => action.mutate(true)}><Square size={14} /></Button></div>
            <div className="replay-time"><strong data-testid="replay-position">{cursor === null ? "—" : `#${number(cursor)}`}</strong><span>{number(count)} / {number(total)} observations</span></div>
            <progress aria-label="Progression de la lecture" max={total} value={count} />
          </section>
          <section className="stats-grid" aria-label="État de la surveillance"><Stat label="MACHINES" value={String(scenarios.data?.items.length ?? "—")} /><Stat label="ALERTES ACTIVES" value={alerts.data?.detector_version ? String(alerts.data.active_count) : "—"} /><Stat label="OBSERVATIONS LUES" value={number(count)} /><Stat label="ÉTAT DE LECTURE" value={run ? states[run.status] ?? run.status : "Prêt"} /></section>
          <div className="resource-tabs" role="group" aria-label="Ressources">{Object.entries(groups).map(([key, name]) => { const Icon = icons[key as keyof typeof icons]; return <button key={key} aria-pressed={group === key} className={group === key ? "selected" : ""} onClick={() => { setGroup(key); setFeature(""); setFocusedAlert(null); }}><Icon size={17} />{name}<small>{alerts.data?.resource_counts?.[key]?.total ?? 0} alertes</small></button>; })}</div>
          <div className="content-grid"><section className="panel" id="indicators-panel"><div className="panel-heading"><div><h2>{feature?.label ?? "Indicateurs"}</h2><p>{scenario?.display_name} · {feature?.id}</p></div><select aria-label="Indicateur" value={feature?.id ?? ""} onChange={e => { setFeature(e.target.value); setFocusedAlert(null); }}>{features.map(f => <option key={f.id} value={f.id}>{f.label}</option>)}</select></div>{focusedAlert ? <div className="chart-context" role="status"><span>Alerte sélectionnée · Détection #{number(focusedAlert.detected_index)}</span><button onClick={() => setFocusedAlert(null)}>Revenir aux dernières observations</button></div> : <div className="chart-context" role="status"><span>{!alerts.data?.detector_version ? "Analyse non démarrée." : `${alerts.data.feature_counts?.[feature?.id ?? ""] ?? 0} alertes sur cet indicateur · ${alerts.data.resource_counts?.[group]?.total ?? 0} sur le composant ${groups[group]}.`}</span></div>}<MetricChart points={points} label={feature?.label ?? "Indicateur"} cursor={chartEnd} detections={focusedAlert ? [focusedAlert.detected_index] : alerts.data?.items.filter(a => a.feature_id === feature?.id).map(a => a.detected_index) ?? []} /><div className="panel-foot"><span>Valeur normalisée · 0–1</span><span>{points.length} observations affichées · {focusedAlert ? "repère de l’alerte sélectionnée" : "repères des alertes de la page courante"}</span></div></section>
            <section className="panel"><div className="panel-heading"><h2>Machines</h2></div><label className="machine-search"><Search size={14} /><input aria-label="Rechercher une machine" placeholder="Rechercher une machine…" value={search} onChange={e => setSearch(e.target.value)} /></label><div className="service-selector machine-list">{scenarios.data?.items.filter(s => s.display_name.toLowerCase().includes(search.toLowerCase())).map(s => <button key={s.id} className={scenario?.id === s.id ? "selected" : ""} disabled={active || action.isPending} onClick={() => chooseMachine(s.id)}><span>{s.display_name}</span><small>{s.features.length} indicateurs</small></button>)}</div></section></div>
          <AlertsPanel resource={alertResource} onResource={value => { setAlertResource(value); setAlertOffset(0); }} data={alerts.data} loading={alerts.isFetching} offset={alertOffset} onPage={setAlertOffset} onSelect={alert => { setGroup(alert.resource); setFeature(alert.feature_id); setFocusedAlert(alert); document.getElementById("indicators-panel")?.scrollIntoView({ behavior: "smooth", block: "center" }); }} />
          <section className="panel observations-panel"><div className="panel-heading"><h2>{focusedAlert ? "Observations autour de l’alerte" : "Dernières observations"}</h2><span className="muted">{feature?.label}</span></div><div className="observations-scroll"><table><thead><tr><th>Index d’observation</th><th>Valeur normalisée</th></tr></thead><tbody>{points.slice(-8).reverse().map(p => <tr key={p.sample_index}><td>#{number(p.sample_index)}</td><td>{p.value === null ? "Indisponible" : number(p.value)}</td></tr>)}</tbody></table>{!points.length && <p className="empty-logs">Aucune observation disponible.</p>}</div></section>
        </>}
      </main></div></div>;
}
function Stat({ label, value }: { label: string; value: string }) { return <article className="status-card"><div className="status-card-top"><span>{label}</span><Activity size={16} /></div><div className="status-value">{value}</div></article>; }
