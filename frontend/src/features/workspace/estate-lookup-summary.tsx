"use client";

import { safeSource } from "./api";
import { publicSourceLabel } from "./public-source-labels";

export type EstateLookup = {
  status: string;
  message: string;
  postcode: string;
  records: { id: string | number; name: string; business_type: string; address: string; postcode: string; source_url: string }[];
  retrieved_at: string | null;
  limitations: string[];
};

export function EstateLookupSummary({ lookup }: { lookup: EstateLookup }) {
  return <details className="mt-4 rounded-xl border border-[var(--misi-border)] bg-[var(--misi-surface-secondary)] p-4">
    <summary className="cursor-pointer text-sm font-semibold text-[var(--misi-accent)]">Food establishment register · {lookup.status}</summary>
    <p className="mt-2 text-sm leading-6 text-[var(--misi-ink)]">{publicSourceLabel(lookup.message)}</p>
    <p className="mt-2 text-xs leading-5 text-[#825929]">Unverified site context for {lookup.postcode}; it does not establish a customer match, maintenance need or compliance position. No records does not mean no establishments.</p>
    <ul className="mt-3 grid gap-2">{(lookup.records || []).map((item, index) => {
      const url = safeSource(item.source_url);
      return <li key={`${item.id}-${index}`} className="rounded-lg border border-[var(--misi-border)] bg-[var(--misi-surface-secondary)] p-3"><p className="text-sm font-medium text-[var(--misi-ink)]">{item.name}</p><p className="mt-1 text-xs leading-5 text-[var(--misi-muted)]">{[item.business_type, item.address, item.postcode].filter(Boolean).join(" · ")}</p>{url && <a href={url} target="_blank" rel="noreferrer" className="mt-2 inline-block text-xs text-[var(--misi-accent)] underline underline-offset-4">View public record</a>}</li>;
    })}</ul>
    {!!lookup.limitations?.length && <ul className="mt-3 list-disc space-y-1 pl-5 text-xs leading-5 text-[var(--misi-muted)]">{lookup.limitations.map((item, index) => <li key={index}>{publicSourceLabel(item)}</li>)}</ul>}
    {lookup.retrieved_at && <p className="mt-2 text-xs text-[var(--misi-muted)]">Retrieved {lookup.retrieved_at}</p>}
  </details>;
}
