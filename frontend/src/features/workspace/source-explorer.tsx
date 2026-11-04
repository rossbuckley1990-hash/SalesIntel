"use client";

import { useState, type FormEvent } from "react";
import { ArrowRight, ArrowUpRight, CircleHelp, Database, Loader2, Search } from "lucide-react";
import { getApiBaseUrl } from "@/lib/api";
import { safeSource } from "./api";
import { Badge, Button } from "./ui";
import { publicResearchExport, publicSourceLabel } from "./public-source-labels";

type SourceStatus = { available: boolean; configured: boolean; version: string | null; capabilities: number | null; message: string };
type Capability = { id: string; title: string; provider: string; source: string };
type SearchResults = { items: Capability[]; message: string };
type CapabilityDetail = { id: string; title: string; provider: string; risk: string; method: string; origin: string; inputs: { name: string; type: string; required: boolean }[]; limitations: string[]; message: string };
type PlanningResult = { source: string; source_contract: string; dataset: string; query: string; entities: Record<string, unknown>[]; receipt: Record<string, unknown> | null; verification: string; limitations: string[] };
type CandidateResult = { topic: string; candidates: { title: string; description: string; directory: string; kind: string }[]; directories: { id: string; reachable: boolean }[]; message: string };

async function sourceRequest<T>(path: string): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}/api/rightclick${path}`, { cache: "no-store" });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(typeof data?.detail === "string" ? data.detail : `Source discovery is unavailable (${response.status}).`);
  }
  return response.json() as Promise<T>;
}

/** Read-only inspection: capability descriptions are not evidence of demand. */
export function SourceExplorer() {
  const [status, setStatus] = useState<SourceStatus | null>(null);
  const [results, setResults] = useState<SearchResults | null>(null);
  const [detail, setDetail] = useState<CapabilityDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [opening, setOpening] = useState(false);
  const [error, setError] = useState("");
  const [identifier, setIdentifier] = useState("");
  const [dataset, setDataset] = useState("planning-application");
  const [planning, setPlanning] = useState<PlanningResult | null>(null);
  const [planningLoading, setPlanningLoading] = useState(false);
  const [planningError, setPlanningError] = useState("");
  const [candidateTopic, setCandidateTopic] = useState("fire safety");
  const [candidates, setCandidates] = useState<CandidateResult | null>(null);
  const [candidatesLoading, setCandidatesLoading] = useState(false);
  const [candidatesError, setCandidatesError] = useState("");

  async function refreshStatus() {
    setOpening(true); setError("");
    try { setStatus(await sourceRequest<SourceStatus>("/status")); }
    catch (e) { setStatus(null); setError(e instanceof Error ? e.message : "Source discovery is unavailable."); }
    finally { setOpening(false); }
  }

  async function search() {
    if (loading) return;
    setLoading(true); setError(""); setDetail(null); setResults(null);
    try { setResults(await sourceRequest<SearchResults>("/capabilities?query=planning")); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not search available sources."); }
    finally { setLoading(false); }
  }

  async function explain(item: Capability) {
    setLoading(true); setError(""); setDetail(null);
    try { setDetail(await sourceRequest<CapabilityDetail>(`/capabilities/explain?id=${encodeURIComponent(item.id)}`)); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not inspect this source."); }
    finally { setLoading(false); }
  }

  async function queryPlanning(event: FormEvent) {
    event.preventDefault();
    if (!identifier.trim() || planningLoading) return;
    setPlanningLoading(true); setPlanningError(""); setPlanning(null);
    try {
      const response = await fetch(`${getApiBaseUrl()}/api/rightclick/planning-query`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ identifier: identifier.trim(), dataset, limit: 10 }) });
      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(typeof data?.detail === "string" ? data.detail : `Public-source query failed (${response.status}).`);
      }
      setPlanning(await response.json() as PlanningResult);
    } catch (e) { setPlanningError(e instanceof Error ? e.message : "Could not query this source."); }
    finally { setPlanningLoading(false); }
  }

  async function findCandidates() {
    if (candidatesLoading) return;
    setCandidatesLoading(true); setCandidatesError(""); setCandidates(null);
    try { setCandidates(await sourceRequest<CandidateResult>(`/candidates?topic=${encodeURIComponent(candidateTopic)}`)); }
    catch (e) { setCandidatesError(e instanceof Error ? e.message : "Could not discover source candidates."); }
    finally { setCandidatesLoading(false); }
  }

  // The public response is untrusted. Display only records explicitly tagged
  // with the dataset requested; never present a different dataset as a match.
  const displayRecords = planning?.entities.filter((item) => item && typeof item === "object" && !Array.isArray(item) && item.dataset === planning.dataset) ?? [];

  return <section className="mt-8" aria-label="Public source explorer">
    <details className="overflow-hidden rounded-2xl border border-[var(--misi-border)] bg-white" onToggle={(event) => { if (event.currentTarget.open && !status && !opening) void refreshStatus(); }}>
      <summary className="cursor-pointer list-none px-5 py-5 sm:px-7 [&::-webkit-details-marker]:hidden">
        <div className="flex flex-wrap items-start justify-between gap-4"><div><p className="m-eyebrow"><Database size={14} /> Public source discovery</p><h2 className="mt-2 text-xl font-semibold text-[var(--misi-ink)]">Find the public sources behind the signals</h2><p className="mt-1 max-w-2xl text-sm leading-6 text-[var(--misi-muted)]">Explore approved capabilities, see what each source accepts, and understand its limits before using it in research.</p></div><span className="rounded-full border border-[var(--misi-border)] px-3 py-1 text-xs font-medium text-[var(--misi-accent)]">Explore sources <ArrowRight className="ml-1 inline" size={13} aria-hidden="true" /></span></div>
      </summary>
      <div className="border-t border-[var(--misi-border)] px-5 py-5 sm:px-7">
        <p className="text-xs leading-5 text-[var(--misi-muted)]">A capability describes how to access a source. It does not establish that the source has relevant data, that records are current, or that a buyer has a requirement.</p>
        {opening && <p className="mt-4 flex items-center gap-2 text-sm text-[var(--misi-muted)]" role="status"><Loader2 className="animate-spin" size={15} /> Checking source discovery…</p>}
        {status && <div className="mt-4 flex flex-wrap items-center gap-2"><Badge tone={status.available ? "green" : "amber"}>{status.available ? "Discovery available" : status.configured ? "Discovery unavailable" : "Not configured"}</Badge><span className="text-sm text-[var(--misi-ink)]">{publicSourceLabel(status.message)}</span>{status.available && status.version && <span className="text-xs text-[var(--misi-muted)]">Runtime {status.version}</span>}{!status.available && <Button disabled={opening} onClick={() => void refreshStatus()}>Check connection again</Button>}</div>}
        {error && <div className="mt-4 flex flex-wrap items-center gap-3"><p className="text-sm text-[#825929]" role="alert">{publicSourceLabel(error)}</p><Button onClick={() => void refreshStatus()} disabled={opening}>Try again</Button></div>}
        {status?.available && <>
          <div className="mt-5 rounded-xl border border-[var(--misi-border)] bg-[var(--misi-surface-secondary)] p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="text-base font-semibold text-[var(--misi-ink)]">Discover more source candidates</h3><p className="mt-1 max-w-2xl text-xs leading-5 text-[var(--misi-muted)]">Search public API directories for a research area. Candidates are unreviewed suggestions: they are not approved for MiSi research, and their coverage, access and relevance have not been checked.</p></div><Badge tone="amber">Unreviewed</Badge></div><div className="mt-4 flex flex-wrap items-end gap-3"><label htmlFor="source-candidate-topic" className="min-w-[12rem] text-xs font-semibold text-[var(--misi-ink)]">Research area<select id="source-candidate-topic" value={candidateTopic} onChange={(event) => setCandidateTopic(event.target.value)} className="mt-2 block w-full rounded-lg border border-[var(--misi-border)] bg-[var(--misi-surface-secondary)] px-3 py-2 text-sm text-[var(--misi-ink)]"><option value="fire safety">Fire safety</option><option value="building">Buildings</option><option value="procurement">Procurement</option><option value="planning">Planning</option></select></label><Button disabled={candidatesLoading} onClick={() => void findCandidates()}>{candidatesLoading ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />} {candidatesLoading ? "Discovering candidates" : "Find source candidates"}</Button></div>{candidatesError && <p className="mt-3 text-sm text-[#825929]" role="alert">{publicSourceLabel(candidatesError)}</p>}{candidates && <div className="mt-4"><p className="text-xs leading-5 text-[var(--misi-muted)]" role="status">{publicSourceLabel(candidates.message)}</p>{candidates.candidates.length ? <ul className="mt-3 grid gap-2 md:grid-cols-2">{candidates.candidates.map((item, index) => <li key={`${item.title}-${index}`} className="rounded-lg border border-[var(--misi-border)] bg-white p-3"><p className="text-sm font-semibold text-[var(--misi-ink)]">{item.title}</p><p className="mt-1 text-xs leading-5 text-[var(--misi-muted)]">{item.description}</p><p className="mt-2 text-xs text-[#825929]">Unreviewed · {item.directory} · {item.kind}</p></li>)}</ul> : <p className="mt-3 text-sm text-[var(--misi-ink)]">No candidates returned for this area. Directory coverage is limited.</p>}{candidates.directories.length > 0 && <p className="mt-3 text-xs text-[var(--misi-muted)]">Directories: {candidates.directories.map((item) => `${item.id} (${item.reachable ? "reachable" : "unavailable"})`).join(" · ")}</p>}</div>}</div>
          <div className="mt-5"><p className="text-sm font-semibold text-[var(--misi-ink)]">Approved public source</p><p className="mt-1 text-xs leading-5 text-[var(--misi-muted)]">This pilot currently checks only the approved Planning Data England operation. Other discovered capabilities are not available here.</p><Button className="mt-3" disabled={loading} onClick={() => void search()}>{loading ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />} Show approved capability</Button></div>
          {results && <div className="mt-4"><p className="text-xs leading-5 text-[var(--misi-muted)]" role="status">{publicSourceLabel(results.message)}</p>{results.items.length ? <div className="mt-3 grid gap-2 md:grid-cols-2">{results.items.map(item => <button key={item.id} type="button" onClick={() => void explain(item)} disabled={loading} className="rounded-xl border border-[var(--misi-border)] bg-white p-4 text-left transition hover:border-[var(--misi-border)] hover:bg-[var(--misi-surface-secondary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-200 disabled:opacity-50"><span className="flex items-start justify-between gap-3"><span className="text-sm font-semibold text-[var(--misi-ink)]">{item.title}</span><ArrowUpRight size={15} className="shrink-0 text-[var(--misi-accent)]" aria-hidden="true" /></span><span className="mt-2 block break-words text-xs text-[var(--misi-muted)]">{publicSourceLabel(item.provider)}</span><span className="mt-2 block text-xs text-[var(--misi-accent)]">Inspect capability</span></button>)}</div> : <p className="mt-3 flex items-center gap-2 text-sm text-[var(--misi-ink)]"><CircleHelp size={16} /> The approved planning capability was not found in this runtime.</p>}</div>}
          {detail && <article className="mt-4 rounded-xl border border-[var(--misi-border)] bg-[var(--misi-surface-secondary)] p-4" aria-label="Capability details"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-widest text-[var(--misi-accent)]">Capability details</p><h3 className="mt-2 font-semibold text-[var(--misi-ink)]">{detail.title}</h3></div><Badge tone="neutral">{detail.method || "Method unknown"} · {detail.risk || "Risk unknown"}</Badge></div><p className="mt-2 break-words text-xs text-[var(--misi-muted)]">{publicSourceLabel(detail.provider)}{detail.origin ? ` · ${detail.origin}` : ""}</p>{detail.message && <p className="mt-3 text-sm leading-6 text-[var(--misi-ink)]">{publicSourceLabel(detail.message)}</p>}{detail.inputs.length > 0 && <div className="mt-4"><h4 className="text-xs font-bold uppercase tracking-widest text-[var(--misi-muted)]">Inputs</h4><ul className="mt-2 grid gap-1">{detail.inputs.map((input, index) => <li key={`${input.name}-${index}`} className="text-sm text-[var(--misi-ink)]"><strong>{input.name}</strong> · {input.type}{input.required ? " · required" : " · optional"}</li>)}</ul></div>}{detail.limitations.length > 0 && <ul className="mt-4 list-disc space-y-1 pl-5 text-xs leading-5 text-[#825929]">{detail.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul>}{safeSource(detail.origin) && <a href={safeSource(detail.origin) || "#"} target="_blank" rel="noreferrer" className="mt-3 inline-block break-all text-xs font-semibold text-[var(--misi-accent)] underline underline-offset-4">Visit source <ArrowUpRight size={12} className="inline" aria-hidden="true" /></a>}</article>}
          <div className="mt-6 border-t border-[var(--misi-border)] pt-5"><h3 className="text-base font-semibold text-[var(--misi-ink)]">Check planning context for a property</h3><p className="mt-1 text-xs leading-5 text-[var(--misi-muted)]">Query a bounded selection from Planning Data England through an approved public source. The identifier is sent to the public source; the result is context for research, not evidence of buying intent.</p><form onSubmit={queryPlanning} className="mt-3 grid gap-3 sm:grid-cols-2"><label htmlFor="source-planning-identifier" className="text-xs font-semibold text-[var(--misi-ink)]">UPRN or postcode<input id="source-planning-identifier" value={identifier} onChange={(event) => setIdentifier(event.target.value)} required maxLength={20} placeholder="For example 10008315764" className="mt-2 block w-full rounded-lg border border-[var(--misi-border)] bg-[var(--misi-surface-secondary)] px-3 py-2 text-sm text-[var(--misi-ink)]" /></label><label htmlFor="source-planning-dataset" className="text-xs font-semibold text-[var(--misi-ink)]">Public dataset<select id="source-planning-dataset" value={dataset} onChange={(event) => setDataset(event.target.value)} className="mt-2 block w-full rounded-lg border border-[var(--misi-border)] bg-[var(--misi-surface-secondary)] px-3 py-2 text-sm text-[var(--misi-ink)]"><option value="planning-application">Planning applications</option><option value="brownfield-land">Brownfield land</option><option value="conservation-area">Conservation areas</option></select></label><div className="sm:col-span-2"><Button type="submit" disabled={planningLoading || !identifier.trim()}>{planningLoading ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />} {planningLoading ? "Checking public data" : "Check public planning data"}</Button></div></form>
            {planningError && <p className="mt-3 text-sm text-[#825929]" role="alert">{publicSourceLabel(planningError)}</p>}
            {planning && <div className="mt-4" role="status"><p className="text-sm text-[var(--misi-ink)]">{displayRecords.length} {displayRecords.length === 1 ? "record" : "records"} returned for {planning.dataset} · {planning.query}</p><p className="mt-1 text-xs leading-5 text-[#825929]">Unverified source context. Data coverage varies; no results does not mean no activity or requirement.</p>{displayRecords.length !== planning.entities.length && <p className="mt-1 text-xs text-[#825929]">Some returned records were omitted because their dataset did not match the request.</p>}{displayRecords.length > 0 && <ul className="mt-3 grid gap-2">{displayRecords.map((item, index) => {
              const entityId = String(item.entity ?? "");
              const entityUrl = /^\d{1,18}$/.test(entityId) ? `https://www.planning.data.gov.uk/entity/${entityId}` : null;
              const title = typeof item.name === "string" && item.name.trim() ? item.name.slice(0, 255) : entityId ? `Record ${entityId}` : "Public record";
              const dateValue = typeof item["start-date"] === "string" ? item["start-date"] : typeof item["entry-date"] === "string" ? item["entry-date"] : "";
              const date = /^\d{4}-\d{2}-\d{2}$/.test(dateValue) ? dateValue : "";
              return <li key={`${entityId}-${index}`} className="rounded-lg border border-[var(--misi-border)] bg-[var(--misi-surface-secondary)] p-3"><p className="text-sm font-semibold text-[var(--misi-ink)]">{title}</p><p className="mt-1 text-xs text-[var(--misi-muted)]">{[entityId && `Record ${entityId}`, date && `Date ${date}`].filter(Boolean).join(" · ") || "Record details unavailable"}</p>{entityUrl && <a href={entityUrl} target="_blank" rel="noreferrer" className="mt-2 inline-block text-xs text-[var(--misi-accent)] underline underline-offset-4">View official record <ArrowUpRight size={12} className="inline" aria-hidden="true" /></a>}</li>;
            })}</ul>}{planning.limitations.length > 0 && <ul className="mt-3 list-disc space-y-1 pl-5 text-xs leading-5 text-[var(--misi-muted)]">{planning.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul>}{planning.receipt && <details className="mt-3 rounded-lg border border-[var(--misi-border)] p-3"><summary className="cursor-pointer text-xs font-semibold text-[var(--misi-accent)]">View execution receipt</summary><pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap break-all text-xs text-[var(--misi-muted)]">{JSON.stringify(publicResearchExport(planning.receipt), null, 2).slice(0, 4000)}</pre><p className="mt-2 text-xs text-[var(--misi-muted)]">A receipt records execution; it does not verify the source claim or sales opportunity.</p></details>}</div>}
          </div>
        </>}
      </div>
    </details>
  </section>;
}
