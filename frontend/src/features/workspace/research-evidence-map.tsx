"use client";

import { useEffect, useState } from "react";
import { ArrowUpRight, Loader2 } from "lucide-react";
import { getApiBaseUrl } from "@/lib/api";
import { safeSource } from "./api";

type MapNode = {
  id: string;
  type: "hypothesis" | "organisation" | "location" | "stakeholder_role" | "observation" | "source";
  label: string;
  source_title?: string;
  published_date?: string;
  retrieved_at?: string;
  url?: string;
};
type MapEdge = { source: string; target: string; relation: string; label: string; observation_id?: string | null };
type EvidenceMap = {
  lead_id: number;
  nodes: MapNode[];
  edges: MapEdge[];
  missing_references: { id: string; relation: string; reason: string }[];
  unknowns: string[];
  limitations: string[];
};

/** Displays only links saved in the dossier; it performs no entity resolution. */
export function ResearchEvidenceMap({ leadId }: { leadId: number }) {
  const [open, setOpen] = useState(false);
  const [map, setMap] = useState<EvidenceMap | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    if (!open || map) return;
    const controller = new AbortController();
    setLoading(true); setError("");
    void fetch(`${getApiBaseUrl()}/api/research-dossiers/leads/${leadId}/evidence-map`, { cache: "no-store", signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error("Evidence connections are unavailable. Try again.");
        const data: EvidenceMap = await response.json();
        if (data.lead_id !== leadId || !Array.isArray(data.nodes) || !Array.isArray(data.edges)) throw new Error("Evidence connections could not be read. Try again.");
        setMap(data);
      })
      .catch((reason) => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Evidence connections are unavailable."); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [leadId, map, open, retry]);

  const nodes = new Map((map?.nodes || []).map((node) => [node.id, node]));
  const context = (map?.nodes || []).filter((node) => ["organisation", "location", "stakeholder_role"].includes(node.type));
  const links = (map?.edges || []).filter((edge) => ["supports_hypothesis", "counter_context", "contact_context"].includes(edge.relation));
  const sectionLabel: Record<string, string> = { organisation: "Organisation", location: "Location", stakeholder_role: "Role to verify" };
  const relationLabel: Record<string, string> = { supports_hypothesis: "Supporting context", counter_context: "Alternative context", contact_context: "Contact context" };

  return <details className="mt-5 border-t border-[var(--misi-border)] pt-5" onToggle={(event) => setOpen(event.currentTarget.open)}>
    <summary className="cursor-pointer text-sm font-semibold text-[var(--misi-ink)]">Map the evidence connections</summary>
    <p className="mt-2 text-xs leading-5 text-[var(--misi-muted)]">Explore how this saved lead links observations, sources and proposed context. These are unverified dossier references, not established relationships.</p>
    {loading && <p className="mt-4 flex items-center gap-2 text-sm text-[var(--misi-muted)]" role="status"><Loader2 size={14} className="animate-spin motion-reduce:animate-none" /> Loading evidence connections…</p>}
    {error && <div className="mt-3"><p role="alert" className="text-sm text-[#825929]">{error}</p><button type="button" className="mt-2 text-sm font-semibold text-[var(--misi-accent)] underline" onClick={() => setRetry((value) => value + 1)}>Try again</button></div>}
    {map && <div className="mt-4">
      {context.length > 0 && <dl className="grid gap-3 border-y border-[var(--misi-border)] py-4 sm:grid-cols-3">{context.map((node) => <div key={node.id}><dt className="text-[11px] font-semibold uppercase tracking-wide text-[var(--misi-muted)]">{sectionLabel[node.type]}</dt><dd className="mt-1 text-sm leading-5 text-[var(--misi-ink)]">{node.label}</dd></div>)}</dl>}
      <div className="mt-4"><h4 className="text-xs font-semibold uppercase tracking-wide text-[var(--misi-muted)]">How the evidence connects</h4>
        {links.length === 0 ? <p className="mt-2 text-sm text-[var(--misi-muted)]">No cited observation links are available for this lead.</p> : <ul className="mt-2 divide-y divide-[var(--misi-border)] border-y border-[var(--misi-border)]">{links.map((edge, index) => {
          const observation = nodes.get(edge.source);
          if (!observation || observation.type !== "observation") return null;
          const attributed = (map.edges || []).find((item) => item.target === observation.id && item.relation === "attributed_to");
          const source = attributed && nodes.get(attributed.source);
          const url = source?.url ? safeSource(source.url) : null;
          return <li key={`${edge.relation}-${edge.source}-${index}`} className="py-3"><p className="text-[11px] font-semibold uppercase tracking-wide text-[var(--misi-muted)]">{relationLabel[edge.relation]}</p><p className="mt-1 text-sm leading-6 text-[var(--misi-ink)]">{observation.label || "Observation text unavailable."}</p><p className="mt-1 text-xs leading-5 text-[var(--misi-muted)]">{observation.source_title || "Source not named"} · {observation.published_date || "Date not provided"}{observation.retrieved_at ? ` · Retrieved ${observation.retrieved_at}` : ""}</p>{url && <a href={url} target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-[var(--misi-accent)] underline underline-offset-4">Review source <ArrowUpRight size={12} aria-hidden="true" /></a>}</li>;
        })}</ul>}
      </div>
      {(map.missing_references || []).length > 0 && <p className="mt-3 text-xs leading-5 text-[#825929]" role="status">{map.missing_references.length} cited {map.missing_references.length === 1 ? "reference is" : "references are"} missing, ambiguous or outside the map limit. Do not treat them as evidence.</p>}
      {(map.unknowns || []).length > 0 && <div className="mt-4"><h4 className="text-xs font-semibold uppercase tracking-wide text-[var(--misi-muted)]">Questions still open</h4><ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-[var(--misi-ink)]">{map.unknowns.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul></div>}
      {(map.limitations || []).length > 0 && <details className="mt-4 text-xs leading-5 text-[var(--misi-muted)]"><summary className="cursor-pointer font-semibold text-[var(--misi-ink)]">What this map can and cannot show</summary><ul className="mt-2 list-disc space-y-1 pl-5">{map.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul></details>}
    </div>}
  </details>;
}
