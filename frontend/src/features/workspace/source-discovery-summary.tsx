"use client";

import { safeSource } from "./api";
import { publicSourceLabel } from "./public-source-labels";

export type SourceDiscovery = {
  status: string;
  message: string;
  capabilities: { id: string; title: string; provider: string; source: string }[];
  topics?: string[];
  candidates?: { title: string; description: string; directory: string; kind: string }[];
  directories?: { id: string; reachable: boolean }[];
  query: { identifier: string; dataset: string; records: { entity_id: string; title: string; source_url: string; description: string; date: string }[]; receipt: string | null } | null;
};

function officialRecord(value: string): string | null {
  const url = safeSource(value);
  if (!url) return null;
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== "https:" || parsed.hostname !== "www.planning.data.gov.uk" || parsed.port || parsed.search || parsed.hash || !/^\/entity\/\d{1,18}\/?$/.test(parsed.pathname)) return null;
    return url;
  } catch { return null; }
}

export function SourceDiscoverySummary({ discovery }: { discovery: SourceDiscovery }) {
  return <details className="mt-4 rounded-xl border border-[var(--misi-border)] bg-[var(--misi-surface-secondary)] p-4">
    <summary className="cursor-pointer text-sm font-semibold text-[var(--misi-accent)]">Public source discovery · {discovery.status}</summary>
    <p className="mt-2 text-sm leading-6 text-[var(--misi-ink)]">{publicSourceLabel(discovery.message)}</p>
    {discovery.capabilities.length > 0 && <ul className="mt-3 grid gap-1 text-xs text-[var(--misi-muted)]">{discovery.capabilities.map((item, index) => <li key={`${item.id}-${index}`}>{publicSourceLabel(item.title)} · {publicSourceLabel(item.provider)}</li>)}</ul>}
    {!!discovery.topics?.length && <p className="mt-3 text-xs text-[var(--misi-muted)]">Research areas: {discovery.topics.join(" · ")}</p>}
    {!!discovery.candidates?.length && <div className="mt-3"><p className="text-xs leading-5 text-[#825929]">Directory suggestions are unreviewed leads to sources, not evidence and not automatically used in research.</p><ul className="mt-2 grid gap-2">{discovery.candidates.map((item, index) => <li key={index} className="rounded-lg border border-[var(--misi-border)] p-3"><p className="text-sm text-[var(--misi-ink)]">{publicSourceLabel(item.title)}</p><p className="mt-1 text-xs leading-5 text-[var(--misi-muted)]">{publicSourceLabel(item.description)} · {publicSourceLabel(item.directory)}</p></li>)}</ul></div>}
    {!!discovery.directories?.length && <p className="mt-3 text-xs text-[var(--misi-muted)]">Directories: {discovery.directories.map((item) => `${publicSourceLabel(item.id)} (${item.reachable ? "reachable" : "unavailable"})`).join(" · ")}</p>}
    {discovery.query && <div className="mt-3">
      <p className="text-xs text-[var(--misi-muted)]">{discovery.query.dataset} · {discovery.query.identifier} · {discovery.query.records.length} returned records</p>
      <p className="mt-1 text-xs leading-5 text-[#825929]">Unverified contextual records, not proof of a buying need. Coverage can be incomplete; an empty result does not mean no activity. Confirm the identifier and location before associating records with an account.</p>
      <ul className="mt-2 grid gap-2">{discovery.query.records.map((item, index) => {
        const url = officialRecord(item.source_url);
        return <li key={`${item.entity_id}-${index}`} className="rounded-lg border border-[var(--misi-border)] bg-[var(--misi-surface-secondary)] p-3 text-sm"><p className="font-medium text-[var(--misi-ink)]">{item.title || `Record ${item.entity_id}`}</p>{item.description && <p className="mt-1 text-[var(--misi-ink)]">{item.description}</p>}<p className="mt-1 text-xs text-[var(--misi-muted)]">{item.date || "Date not provided"} · Record {item.entity_id}</p>{url && <a href={url} target="_blank" rel="noreferrer" className="mt-2 inline-block text-xs text-[var(--misi-accent)] underline underline-offset-4">View public record</a>}</li>;
      })}</ul>
      {discovery.query.receipt && <p className="mt-2 break-all text-xs text-[var(--misi-muted)]">Execution receipt: {discovery.query.receipt}</p>}
    </div>}
  </details>;
}
