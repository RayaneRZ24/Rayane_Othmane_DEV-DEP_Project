"use client";
import { useState } from "react";
import { AlertTriangle, ArrowUpRight } from "lucide-react";
import { groups, number, type AlertPage, type Alert } from "@/lib/replay";

const statuses: Record<string, string> = { active: "À examiner", recovered: "Retour sous le seuil", stopped: "Lecture arrêtée", completed: "Fin de lecture", interrupted: "Lecture interrompue" };

export function AlertsPanel({ data, loading, onSelect, onPage, offset, resource, onResource }: {
  resource: string; onResource: (value: string) => void; data?: AlertPage; loading: boolean; offset: number; onPage: (offset: number) => void; onSelect: (alert: Alert) => void;
}) {
  const [expanded, setExpanded] = useState<string | null>(null);
  return <section className="panel alerts-panel" aria-label="Alertes de surveillance">
    <div className="panel-heading"><div><h2>Alertes de surveillance</h2><p>Alertes de la lecture · tous les indicateurs du composant sélectionné.</p></div><span className="alert-count">{data?.active_count ?? 0} à examiner au total</span></div>
    <div className="alert-filters" role="group" aria-label="Filtrer les alertes par composant">{[["", "Tous"], ...Object.entries(groups)].map(([key, label]) => <button key={key} aria-pressed={resource === key} onClick={() => onResource(key)}>{label}<span>{key ? data?.resource_counts?.[key]?.total ?? 0 : Object.values(data?.resource_counts ?? {}).reduce((sum, counts) => sum + counts.total, 0)}</span></button>)}</div>
    {data?.detector_version === "pca-joint-v1" && <p className="alert-scope">Une alerte combinée est classée selon son indicateur principal ; plusieurs composants peuvent contribuer à cet écart.</p>}
    {!data?.items.length ? <div className="alerts-empty">{loading ? "Analyse en cours…" : !data?.detector_version ? "Lancez la lecture pour analyser cette machine." : `Aucune alerte détectée ${resource ? `pour le composant ${groups[resource]}` : "sur cette machine"} jusqu’à l’observation #${number(data.analyzed_index ?? 0)}.`}</div> : <div className="alert-list">{data.items.map(alert => <article className={`alert-entry ${alert.status === "active" ? "is-active" : ""}`} key={alert.id}>
      <div className="alert-entry-heading"><AlertTriangle size={17} /><div><strong>{alert.feature_label}{alert.evidence.method === "pca-joint-v1" ? " · écart combiné" : ""}</strong><span>{groups[alert.resource]} · Détection #{number(alert.detected_index)}</span></div><span className={`alert-status ${alert.status}`}>{statuses[alert.status] ?? alert.status}</span></div>
      <div className="alert-actions"><button aria-expanded={expanded === alert.id} onClick={() => setExpanded(expanded === alert.id ? null : alert.id)}>{expanded === alert.id ? "Masquer les mesures" : "Voir les mesures"}</button><button onClick={() => onSelect(alert)}>Afficher sur le graphique<ArrowUpRight size={12} /></button></div>
      {expanded === alert.id && <dl className="alert-evidence"><div><dt>Valeur à la détection</dt><dd>{number(alert.evidence.value)}</dd></div><div><dt>Référence médiane</dt><dd>{number(alert.evidence.reference_median)}</dd></div><div><dt>{alert.evidence.method === "pca-joint-v1" ? "Plage descriptive de cet indicateur" : "Plage de référence"}</dt><dd>{number(alert.evidence.expected_lower)} – {number(alert.evidence.expected_upper)}</dd></div><div><dt>Première observation de l’écart</dt><dd>#{number(alert.start_index)}</dd></div><div><dt>Dernier écart observé</dt><dd>#{number(alert.last_anomalous_index)}</dd></div>{alert.closed_index !== null && <div><dt>Fin du suivi</dt><dd>#{number(alert.closed_index)}</dd></div>}</dl>}
      {expanded === alert.id && alert.evidence.contributors && <div className="joint-evidence"><p>Détection fondée sur les indicateurs combinés. Signaux principalement associés à cet écart :</p><ul>{alert.evidence.contributors.map(c => <li key={c.feature_id}><span>{c.label}</span><strong>{number(c.value)}</strong></li>)}</ul><small>Ces associations ne prouvent pas une cause de panne.</small></div>}
    </article>)}</div>}
    <div className="panel-foot"><span>{data?.total ?? 0} alertes {resource ? `· ${groups[resource]}` : "· Tous les composants"} · {number((data?.analyzed_index ?? -1) + 1)} observations analysées</span><div className="alert-pagination"><button disabled={offset === 0} onClick={() => onPage(Math.max(0, offset - 50))}>Plus récentes</button><button disabled={!data || offset + 50 >= data.total} onClick={() => onPage(offset + 50)}>Plus anciennes</button></div></div>
  </section>;
}
