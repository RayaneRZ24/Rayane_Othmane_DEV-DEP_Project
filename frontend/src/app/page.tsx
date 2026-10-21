"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, Database, Layers3, Radio, RefreshCw, Server } from "lucide-react";
import { Button } from "@/components/ui/button";
import { LatencyChart, type LatencyPoint } from "@/components/latency-chart";

type Health = { status: string; api: string; database: string; version: string; checked_at: string };
const backend = "/api/backend";

async function fetchHealth() {
  const start = performance.now();
  const response = await fetch(`${backend}/health`, { signal: AbortSignal.timeout(10000) });
  if (![200, 503].includes(response.status)) throw new Error("Le service applicatif est injoignable.");
  const health = await response.json() as Health;
  if (!health.checked_at || !health.database) throw new Error("La réponse du service est invalide.");
  return { ...health, latency: Math.round(performance.now() - start), receivedAt: Date.now() };
}

export default function Home() {
  const health = useQuery({ queryKey: ["system", "health"], queryFn: fetchHealth, refetchInterval: 5000 });
  const [stream, setStream] = useState<"connecting" | "connected" | "disconnected">("connecting");
  const [lastEventAt, setLastEventAt] = useState<string | null>(null);
  const [points, setPoints] = useState<LatencyPoint[]>([]);

  useEffect(() => {
    const data = health.data;
    if (!data) return;
    setPoints((previous) => [...previous, { time: data.receivedAt, latency: data.latency }].slice(-40));
  }, [health.data]);

  useEffect(() => {
    const source = new EventSource(`${backend}/api/v1/system/events`);
    source.addEventListener("system.snapshot", (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data) as { emitted_at: string };
        if (typeof data.emitted_at !== "string") throw new Error("Invalid event");
        setLastEventAt(data.emitted_at); setStream("connected");
      } catch { setStream("disconnected"); }
    });
    source.addEventListener("system.unavailable", () => setStream("disconnected"));
    source.onerror = () => setStream("disconnected");
    return () => source.close();
  }, []);

  const available = health.isSuccess && !health.isRefetchError;
  const databaseReady = available && health.data?.database === "available";
  const connected = databaseReady && stream === "connected";
  const initializing = health.isPending || stream === "connecting";
  const formatTime = (value?: string) => value ? new Date(value).toLocaleTimeString("fr-FR") : "—";

  return <div className="app-shell">
    <aside className="sidebar">
      <a className="brand" href="/"><span className="brand-mark"><Activity size={22} /></span><span>smartops<span className="brand-dot">.</span></span></a>
      <p className="nav-label product-nav-label">SUPERVISION</p>
      <nav aria-label="Navigation principale">
        <a className="nav-item selected" href="/" aria-current="page"><Layers3 size={17} /> Vue d’ensemble <span className="nav-indicator" /></a>
      </nav>
    </aside>

    <div className="main-shell">
      <header className="topbar"><div><span className="muted">SmartOps</span><span className="breadcrumb-slash">/</span><span>Supervision</span></div><span className={`environment ${connected ? "is-connected" : ""}`}><span className="tiny-dot" /> {connected ? "Services connectés" : initializing ? "Connexion en cours" : "Attention requise"}</span></header>
      <main>
        <section className="page-heading"><h1>Vue d’ensemble</h1><Button variant="outline" className="refresh-button" onClick={() => void health.refetch()} disabled={health.isFetching}><RefreshCw size={14} className={health.isFetching ? "spinning" : ""} /> Actualiser</Button></section>

        <section className="stats-grid" aria-label="État des composants">
          <StatusCard icon={<Server size={18} />} label="SERVICE APPLICATIF" value={health.isPending ? "Connexion…" : available ? "Disponible" : "Injoignable"} healthy={available} />
          <StatusCard icon={<Database size={18} />} label="STOCKAGE" value={health.isPending ? "Vérification…" : databaseReady ? "Connecté" : "Indisponible"} healthy={databaseReady} />
          <StatusCard icon={<Radio size={18} />} label="CONNEXION LIVE" value={stream === "connected" ? "Connectée" : stream === "connecting" ? "Connexion…" : "Déconnectée"} healthy={stream === "connected"} />
          <StatusCard icon={<Activity size={18} />} label="LATENCE DU SERVICE" value={available ? `${health.data?.latency} ms` : "—"} healthy={available} />
        </section>

        <div className="content-grid">
          <section className="panel latency-panel"><div className="panel-heading"><h2>Temps de réponse</h2><span className="chart-legend"><span /> Service · ms</span></div><LatencyChart points={points} /><div className="panel-foot"><span><span className="tiny-dot" /> Actualisation automatique · 5 s</span><span>{points.length} {points.length === 1 ? "mesure" : "mesures"}</span></div></section>

          <section className="panel service-panel"><div className="panel-heading"><h2>État des services</h2></div>
            <div className="service-list">
              <ServiceRow label="Service applicatif" connected={available} pending={health.isPending} />
              <ServiceRow label="Stockage" connected={databaseReady} pending={health.isPending} />
              <ServiceRow label="Connexion live" connected={stream === "connected"} pending={stream === "connecting"} />
            </div>
            <dl className="update-list"><div><dt>Dernière vérification</dt><dd>{formatTime(health.data?.checked_at)}</dd></div><div><dt>Dernière synchronisation</dt><dd>{formatTime(lastEventAt ?? undefined)}</dd></div></dl>
          </section>
        </div>

      </main>
    </div>
  </div>;
}

function StatusCard({ icon, label, value, healthy }: { icon: React.ReactNode; label: string; value: string; healthy: boolean }) {
  return <article className="status-card"><div className="status-card-top"><span>{label}</span>{icon}</div><div className="status-value"><span className={`status-dot ${healthy ? "ok" : "waiting"}`} />{value}</div></article>;
}

function ServiceRow({ label, connected, pending }: { label: string; connected: boolean; pending: boolean }) {
  return <div className="service-row"><span>{label}</span><span className={`service-state ${connected ? "ready" : ""}`}><span className={`status-dot ${connected ? "ok" : "waiting"}`} />{pending ? "Connexion…" : connected ? "Disponible" : "Indisponible"}</span></div>;
}
