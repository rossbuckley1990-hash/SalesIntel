"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowUpRight, Check, CircleHelp, Copy, FileSearch, Loader2, Search, UserRound } from "lucide-react";
import { getApiBaseUrl } from "@/lib/api";
import { safeSource } from "./api";
import { Button } from "./ui";
import { ImportedObservationDetails, type ObservationOrigin } from "./observation-origin";
import { SourceDiscoverySummary, type SourceDiscovery } from "./source-discovery-summary";
import { publicResearchExport } from "./public-source-labels";
import { EstateLookupSummary, type EstateLookup } from "./estate-lookup-summary";
import { LeadActions, type LeadAction } from "./lead-actions";
import { ConversationPrep } from "./conversation-prep";
import { ResearchEvidenceMap } from "./research-evidence-map";
import { LeadInvestigations } from "./lead-investigations";

type Observation = ObservationOrigin & { id: string; source_url: string; source_title: string; published_date: string | null; fact: string };
type Opportunity = { organisation: string; location: string; headline: string; thesis: string; potential_solution?: string; supporting_observation_ids: string[]; counter_observation_ids: string[]; unknowns: string[]; contact_name: string; contact_role: string; contact_observation_ids: string[]; engagement: string; verification_action: string };
type RelatedObservation = { id: number; organisation_name: string; site: string; observed_statement: string; source_title: string; source_url: string | null; published_at: string | null; retrieved_at: string };
type Lead = { actions?: LeadAction[]; estate_lookup?: EstateLookup | null; source_discovery?: SourceDiscovery | null; contact_research?: { result: ContactResult; researched_at: string } | null; related_observations?: RelatedObservation[]; related_observations_note?: string; id: number; run_id: number; organisation: string; location: string; headline: string; status: string; notes: string; updated_at: string; opportunity: Opportunity; brief: string; model: string; observations: Observation[]; feedback: unknown[] };
type SavedRun = { id: number; brief: string; model: string; completed_at: string; result: { searches: unknown[]; observations: unknown[]; opportunities: unknown[]; limitations: string[] } };
type Contact = { name: string; role: string; kind: string; value: string; source_url: string; source_title: string; source_date: string | null; evidence_quote: string };
type ContactResult = { organisation: string; contacts: Contact[]; limitations: string[] };
const statuses = [ ["new", "New"], ["investigate", "Investigating"], ["ready", "Ready to approach"], ["contacted", "Contacted"], ["qualified", "Qualified"], ["not_now", "Not now"], ["not_relevant", "Not relevant"] ] as const;
const feedbackOptions = [ ["useful", "Useful"], ["needs_research", "Needs research"], ["not_useful", "Not useful"], ["incorrect", "Incorrect"] ] as const;
const statusLabel = (value: string) => statuses.find(([key]) => key === value)?.[1] || value;
const linkedCount = (ids: string[], observations: Observation[]) =>
  new Set(ids.filter((id) => observations.some((item) => item.id === id && safeSource(item.source_url)))).size;

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, { ...init, cache: "no-store" });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(typeof payload?.detail === "string" ? payload.detail : `Request failed (${response.status}).`);
  }
  return response.json();
}

function Sources({ title, ids, observations }: { title: string; ids: string[]; observations: Observation[] }) {
  if (!ids.length) return null;
  return <div className="mt-5"><h4 className="text-xs font-bold uppercase tracking-widest text-[var(--misi-muted)]">{title}</h4><div className="mt-2 grid gap-2">{ids.map((id) => {
    const item = observations.find((observation) => observation.id === id);
    if (!item) return <p key={id} className="text-sm text-[#825929]">Source {id} unavailable. Verify before use.</p>;
    const url = safeSource(item.source_url);
    return <div key={id} className="rounded-xl border border-[var(--misi-border)] bg-[var(--misi-surface-secondary)] p-4"><p className="text-sm leading-6 text-[var(--misi-ink)]">{item.fact}</p><p className="mt-2 text-xs text-[var(--misi-muted)]">{item.source_title || "Source"} · {item.published_date || "Date not provided"}</p><ImportedObservationDetails observation={item} />{url ? <a href={url} target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-[var(--misi-accent)] underline underline-offset-4">Read source <ArrowUpRight size={12} aria-hidden="true" /></a> : <p className="mt-2 text-xs text-[#825929]">Source link unavailable</p>}</div>;
  })}</div></div>;
}

export function ResearchLibrary({ revision, onResearchSaved }: { revision: number; onResearchSaved: () => void }) {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [runs, setRuns] = useState<SavedRun[]>([]);
  const [total, setTotal] = useState(0);
  const [selected, setSelected] = useState<Lead | null>(null);
  const [filter, setFilter] = useState("all");
  const [searchInput, setSearchInput] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const selectedId = useRef<number | null>(null);
  const requestedLead = useRef(false);
  const detailRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [notes, setNotes] = useState("");
  const [message, setMessage] = useState("");
  const [contacts, setContacts] = useState<ContactResult | null>(null);
  const [contactsBusy, setContactsBusy] = useState(false);
  const [contactError, setContactError] = useState("");
  const [contactSavedAt, setContactSavedAt] = useState("");
  const [copyMessage, setCopyMessage] = useState("");
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api<{ items: Lead[]; total: number }>(`/api/research-dossiers/leads?limit=25&offset=${offset}${filter === "all" ? "" : `&status=${encodeURIComponent(filter)}`}${searchQuery ? `&q=${encodeURIComponent(searchQuery)}` : ""}`);
      setLeads(data.items); setTotal(data.total); setError("");
    } catch (e) { setError(e instanceof Error ? e.message : "Could not load saved research."); }
    finally { setLoading(false); }
  }, [filter, offset, searchQuery]);
  useEffect(() => { void load(); }, [load, revision]);
  useEffect(() => {
    let active = true;
    void api<{ items: SavedRun[] }>("/api/research-dossiers/runs?limit=5&offset=0").then((data) => { if (active && Array.isArray(data.items)) setRuns(data.items); }).catch(() => { if (active) setRuns([]); });
    return () => { active = false; };
  }, [revision]);
  async function openLead(lead: Lead) {
    selectedId.current = lead.id; setSelected(lead); setNotes(lead.notes || ""); setMessage(""); setCopyMessage(""); setContacts(lead.contact_research?.result || null); setContactSavedAt(lead.contact_research?.researched_at || ""); setContactError("");
    try { const detail = await api<Lead>(`/api/research-dossiers/leads/${lead.id}`); if (selectedId.current === lead.id) { setSelected(detail); setNotes((current) => current === (lead.notes || "") ? (detail.notes || "") : current); setContacts(detail.contact_research?.result || null); setContactSavedAt(detail.contact_research?.researched_at || ""); } }
    catch (e) { if (selectedId.current === lead.id) setMessage(e instanceof Error ? e.message : "Could not refresh this dossier."); }
  }
  async function openLeadById(id: number) {
    try { const lead = await api<Lead>(`/api/research-dossiers/leads/${id}`); requestedLead.current = true; await openLead(lead); }
    catch (e) { setMessage(e instanceof Error ? e.message : "Could not open the saved lead."); }
  }
  useEffect(() => {
    const requested = sessionStorage.getItem("misi-open-lead");
    if (!requested || !/^\d+$/.test(requested)) return;
    sessionStorage.removeItem("misi-open-lead");
    requestedLead.current = true;
    void api<Lead>(`/api/research-dossiers/leads/${requested}`).then((lead) => openLead(lead)).catch(() => setError("Could not open the saved lead."));
    // The session request is consumed once on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    if (!requestedLead.current || !selected || !detailRef.current) return;
    requestedLead.current = false;
    detailRef.current.scrollIntoView({ block: "start", behavior: "auto" });
    detailRef.current.focus({ preventScroll: true });
  }, [selected, loading, error, leads.length]);
  async function updateLead(change: { status?: string; notes?: string; feedback?: string }) {
    if (!selected || busy) return;
    setBusy(true); setMessage("");
    try {
      const updated = await api<Lead>(`/api/research-dossiers/leads/${selected.id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(change) });
      if (selectedId.current === updated.id) { setSelected(updated); if (change.notes !== undefined) setNotes((current) => current === change.notes ? (updated.notes || "") : current); setMessage(change.feedback ? "Feedback saved." : "Changes saved."); }
      setLeads((items) => items.map((item) => item.id === updated.id ? updated : item));
    } catch (e) { setMessage(e instanceof Error ? e.message : "Could not save changes."); }
    finally { setBusy(false); }
  }
  async function findContacts() {
    if (!selected || contactsBusy) return;
    setContactsBusy(true); setContactError("");
    const leadId = selected.id;
    try { const snapshot = await api<{ result: ContactResult; researched_at: string; saved: boolean; save_error: string | null }>(`/api/research-dossiers/leads/${leadId}/contact-research`, { method: "POST" }); if (selectedId.current === leadId) { setContacts(snapshot.result); setContactSavedAt(snapshot.saved ? snapshot.researched_at : ""); if (!snapshot.saved) setContactError(snapshot.save_error || "The contact search could not be saved."); } if (snapshot.saved) void load(); }
    catch (e) { if (selectedId.current === leadId) setContactError(e instanceof Error ? e.message : "Contact research failed."); }
    finally { setContactsBusy(false); }
  }
  async function copyApproach() {
    if (!selected?.opportunity.engagement) return;
    try {
      await navigator.clipboard.writeText(selected.opportunity.engagement);
      setCopyMessage("Approach copied. Review and tailor it before use.");
    } catch {
      setCopyMessage("Copy unavailable. You can select and copy the approach above.");
    }
  }
  return <section aria-label="Saved research workspace" className="mt-10 min-w-0 border-t border-[var(--misi-border)] bg-[var(--misi-canvas)] text-[var(--misi-ink)]">
    <header className="grid gap-4 py-6 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
      <div><p className="text-[11px] font-semibold uppercase tracking-[0.09em] text-[var(--misi-muted)]">Research workspace</p><h2 className="mt-2 max-w-xl text-[20px] font-semibold leading-[1.3] tracking-[-0.02em] text-[var(--misi-ink)]">Your opportunity stream</h2><p className="mt-1 max-w-lg text-sm leading-6 text-[var(--misi-muted)]">A considered view of your research, evidence and next conversation.</p></div>
      <div className="flex flex-wrap items-end gap-2"><form className="flex items-center gap-2" onSubmit={(event) => { event.preventDefault(); setOffset(0); setSearchQuery(searchInput.trim()); }}><label htmlFor="research-lead-search" className="sr-only">Search saved leads</label><input id="research-lead-search" value={searchInput} onChange={(event) => setSearchInput(event.target.value)} maxLength={120} placeholder="Organisation, place or lead" className="w-44 border border-[var(--misi-border)] bg-white px-3 py-2.5 text-sm text-[var(--misi-ink)] placeholder:text-[var(--misi-tertiary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--misi-accent)] sm:w-56" /><Button type="submit"><Search size={15} /> Search</Button></form><div className="flex items-center gap-2"><label htmlFor="research-status-filter" className="sr-only">Show</label><select id="research-status-filter" value={filter} onChange={(e) => { setFilter(e.target.value); setOffset(0); }} className="border border-[var(--misi-border)] bg-white px-3 py-2.5 text-sm text-[var(--misi-ink)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--misi-accent)]"><option value="all">All leads</option>{statuses.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div></div>
    </header>
    {loading && !leads.length ? <p className="px-8 py-8 text-sm text-[var(--misi-muted)]" role="status">Loading saved research…</p> : error ? <div className="px-8 py-8"><p role="alert" className="text-sm text-[#895b28]">Saved research is unavailable: {error}</p><Button className="mt-3" onClick={() => void load()}>Try again</Button></div> : !leads.length && !selected ? <div className="px-8 py-12"><FileSearch className="text-[var(--misi-accent)]" size={24} /><p className="mt-4 text-xl font-semibold text-[var(--misi-ink)]">{searchQuery ? "No matching leads" : filter === "all" ? "Your first lead starts with a question" : "No leads in this stage"}</p><p className="mt-2 text-sm text-[var(--misi-muted)]">{searchQuery ? "Try a different organisation, place or keyword." : filter === "all" ? "Run public research above. Supported opportunities will appear here for review." : "Try another stage to see more of your research."}</p></div> : <div className="min-w-0">
      <div className="border-y border-[var(--misi-border)] py-3">
        <p className="mb-3 flex justify-between text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--misi-muted)]"><span>Saved intelligence</span><span>{total} {total === 1 ? "lead" : "leads"}{total > 25 ? ` · ${offset + 1}–${Math.min(offset + 25, total)}` : ""}</span></p>
        <div className="flex snap-x overflow-x-auto border-b border-[var(--misi-border)]" aria-label="Saved leads">{leads.map((lead) => <button key={lead.id} type="button" onClick={() => { if (window.matchMedia("(max-width: 1023px)").matches) requestedLead.current = true; void openLead(lead); }} aria-pressed={selected?.id === lead.id} className={`group min-w-[220px] max-w-[270px] flex-1 snap-start border-b-2 px-4 py-3 text-left transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--misi-accent)] motion-reduce:transition-none ${selected?.id === lead.id ? "border-[var(--misi-accent)] bg-[var(--misi-soft)] text-[var(--misi-ink)]" : "border-transparent bg-transparent text-[var(--misi-ink)] hover:bg-[var(--misi-surface-secondary)]"}`}><span className="flex items-start justify-between gap-3"><span className="text-[13px] font-semibold leading-5">{lead.organisation}</span><ArrowUpRight size={15} className="shrink-0 opacity-50" /></span><span className="mt-1.5 block text-[13px] leading-5 text-[var(--misi-muted)]">{lead.headline}</span><span className="mt-3 block text-[11px] font-medium text-[var(--misi-muted)]">{statusLabel(lead.status)}{lead.location ? ` · ${lead.location}` : ""}</span></button>)}</div>
        {leads.length > 3 && <p className="mt-2 text-xs text-[var(--misi-muted)]">Scroll across to explore more saved leads.</p>}
        {total > 25 && <div className="mt-3 flex gap-2"><Button disabled={offset === 0 || loading} onClick={() => setOffset(Math.max(0, offset - 25))}>Previous</Button><Button disabled={offset + 25 >= total || loading} onClick={() => setOffset(offset + 25)}>Next</Button></div>}
      </div>
      {!selected ? <div className="flex min-h-[210px] flex-col justify-between bg-[var(--misi-surface-secondary)] px-6 py-6 text-[var(--misi-ink)] sm:px-8"><p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--misi-muted)]">Intelligence briefing / 01</p><div className="max-w-md py-10"><CircleHelp size={21} className="text-[var(--misi-accent)]" /><h3 style={{ fontSize: "20px", lineHeight: 1.35, fontWeight: 600 }} className="mt-5 tracking-[-0.02em]">Choose a lead to explore</h3><p className="mt-4 text-sm leading-6 text-[var(--misi-muted)]">See the signals, what they could mean, what is still unknown and how to start a useful conversation.</p></div><p className="border-t border-[var(--misi-border)] pt-4 text-xs text-[var(--misi-muted)]">Evidence, interpretation and a practical next move — together in one place.</p></div> : <article ref={detailRef} tabIndex={-1} role="region" aria-label={`Research brief for ${selected.organisation}`} className="mt-5 grid min-w-0 overflow-hidden rounded-xl border border-[var(--misi-border)] bg-[var(--misi-surface)] text-[var(--misi-ink)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--misi-accent)] xl:grid-cols-[minmax(0,1.75fr)_minmax(280px,1fr)]" key={selected.id}>
        <div className="px-6 pb-8 pt-7 sm:px-8"><div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--misi-border)] pb-5"><p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--misi-muted)]">Intelligence briefing / {selected.organisation}</p><span className="inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--misi-muted)]"><span className="h-1.5 w-1.5 rounded-full bg-[#a66430]" />Hypothesis to verify</span></div>
          <p className="mt-7 text-xs font-semibold uppercase tracking-[0.14em] text-[var(--misi-muted)]">{selected.organisation}{selected.location ? ` · ${selected.location}` : ""}</p><h3 style={{ fontSize: "22px", lineHeight: 1.3, fontWeight: 600 }} className="mt-3 max-w-3xl tracking-[-0.02em] text-[var(--misi-ink)]">{selected.headline}</h3>
          <div className="mt-6 border-l-2 border-[var(--misi-border)] pl-4"><p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--misi-muted)]">Why this may matter</p><p className="mt-3 max-w-3xl text-[15px] leading-7 text-[var(--misi-ink)]">{selected.opportunity.thesis}</p></div>
          <div className="mt-6 grid grid-cols-3 gap-3 border-y border-[var(--misi-border)] py-4" aria-label="Evidence overview"><div><span className="block text-[11px] leading-4 text-[var(--misi-muted)]">Linked observations: </span><span className="mt-2 block text-base font-semibold leading-none">{linkedCount(selected.opportunity.supporting_observation_ids, selected.observations)}</span></div><div><span className="block text-[11px] leading-4 text-[var(--misi-muted)]">Alternative context: </span><span className="mt-2 block text-base font-semibold leading-none">{linkedCount(selected.opportunity.counter_observation_ids, selected.observations)}</span></div><div><span className="block text-[11px] leading-4 text-[var(--misi-muted)]">Unanswered questions: </span><span className="mt-2 block text-base font-semibold leading-none">{selected.opportunity.unknowns.length}</span></div><p className="col-span-3 mt-1 text-xs leading-5 text-[var(--misi-muted)]">Counts are a review aid, not a measure of source independence, confidence or buying intent.</p></div>
          <div className="mt-7 grid gap-6 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]"><div><p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--misi-muted)]">Your next conversation</p><p className="mt-3 text-sm leading-6 text-[var(--misi-ink)]">{selected.opportunity.engagement || "Approach not established."}</p>{selected.opportunity.engagement && <Button className="mt-4" onClick={() => void copyApproach()}><Copy size={14} aria-hidden="true" /> Copy approach</Button>}{copyMessage && <p role="status" className="mt-2 text-xs leading-5 text-[var(--misi-muted)]">{copyMessage}</p>}</div><div className="border-t border-[var(--misi-border)] pt-4 sm:border-l sm:border-t-0 sm:pl-6 sm:pt-0"><p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--misi-muted)]">Next thing to verify</p><p className="mt-3 text-sm leading-6 text-[var(--misi-ink)]">{selected.opportunity.verification_action || "Confirm current arrangements."}</p></div></div>
          {selected.opportunity.unknowns.length > 0 && <div className="mt-8 border-t border-[var(--misi-border)] pt-6"><h4 className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--misi-muted)]">What we still need to know</h4><ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-6 text-[var(--misi-ink)]">{selected.opportunity.unknowns.map((item, index) => <li key={index}>{item}</li>)}</ul></div>}
          {selected.opportunity.potential_solution && <div className="mt-7 bg-[var(--misi-surface-secondary)] px-5 py-5"><p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--misi-muted)]">Potential solution to explore</p><p className="mt-2 text-sm leading-6 text-[var(--misi-ink)]">{selected.opportunity.potential_solution}</p><p className="mt-2 text-xs leading-5 text-[var(--misi-muted)]">A suggestion to test with the customer, not a confirmed requirement or delivery capability.</p></div>}
        </div>
        <div className="border-t border-[var(--misi-border)] bg-[var(--misi-surface-secondary)] px-6 pb-8 pt-3 text-[var(--misi-ink)] xl:border-l xl:border-t-0"><LeadActions key={selected.id} leadId={selected.id} suggestion={selected.opportunity.verification_action || ""} initialActions={selected.actions || []} />
        <LeadInvestigations key={`investigations-${selected.id}`} leadId={selected.id} organisation={selected.organisation} onOpenLead={(id) => void openLeadById(id)} onResearchSaved={onResearchSaved} />
        <ConversationPrep opportunity={selected.opportunity} observations={selected.observations} />
        <ResearchEvidenceMap key={`map-${selected.id}`} leadId={selected.id} />
        <details className="mt-5 border-t border-[var(--misi-border)] pt-5"><summary className="cursor-pointer text-sm font-semibold text-[var(--misi-ink)]">Evidence and public sources</summary>
        {selected.source_discovery && <SourceDiscoverySummary discovery={selected.source_discovery} />}
        {selected.estate_lookup && <EstateLookupSummary lookup={selected.estate_lookup} />}
        <Sources title="Signals behind the idea" ids={selected.opportunity.supporting_observation_ids} observations={selected.observations} />
        <Sources title="Alternative context" ids={selected.opportunity.counter_observation_ids} observations={selected.observations} />
        </details>
        {!!selected.related_observations?.length && <details className="mt-5 border-t border-[var(--misi-border)] pt-5"><summary className="cursor-pointer text-sm font-semibold text-[var(--misi-ink)]">Related evidence from your inbox · {selected.related_observations.length}</summary><p className="mt-2 text-xs leading-5 text-[#825929]">Matched by organisation name. Confirm the organisation, site and relevance; this is not proof of demand.</p><div className="mt-3 grid gap-2">{selected.related_observations.map((item) => { const url = item.source_url ? safeSource(item.source_url) : null; return <div key={item.id} className="border-l border-[var(--misi-border)] pl-4"><p className="text-sm leading-6 text-[var(--misi-ink)]">{item.observed_statement}</p><p className="mt-1 text-xs text-[var(--misi-muted)]">{item.organisation_name} · {item.site} · {item.published_at || "Date not provided"}</p>{url && <a href={url} target="_blank" rel="noreferrer" className="mt-2 inline-block text-xs text-[var(--misi-accent)] underline underline-offset-4">{item.source_title || "Read source"}</a>}</div>; })}</div>{selected.related_observations_note && <p className="mt-3 text-xs leading-5 text-[var(--misi-muted)]">{selected.related_observations_note}</p>}</details>}
        <div className="mt-6 border-t border-[var(--misi-border)] pt-6"><p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--misi-muted)]"><UserRound size={14} /> Who to approach</p><p className="mt-3 text-base font-semibold text-[var(--misi-ink)]">{[selected.opportunity.contact_name, selected.opportunity.contact_role].filter(Boolean).join(" · ") || "Contact not established"}</p><Sources title="Contact evidence" ids={selected.opportunity.contact_observation_ids} observations={selected.observations} /><p className="mt-2 text-xs leading-5 text-[var(--misi-muted)]">Verify the person and their role before contacting them.</p><Button className="mt-4" disabled={contactsBusy} onClick={() => void findContacts()}>{contactsBusy ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />} {contactsBusy ? "Researching contacts" : "Find public contact details"}</Button>{contactError && <p role="alert" className="mt-3 text-xs text-[#825929]">{contactError}</p>}{contacts && <div className="mt-4 space-y-3"><p className="text-xs leading-5 text-[var(--misi-muted)]">Published source; details are automatically extracted and need independent checking.{contactSavedAt ? ` Saved ${new Date(contactSavedAt).toLocaleString("en-GB")}.` : ""}</p>{contacts.contacts.length === 0 && <p className="text-sm text-[var(--misi-ink)]">No public contact details found in this search.</p>}{contacts.contacts.map((contact, i) => { const url = safeSource(contact.source_url); return <div key={i} className="border-l border-[var(--misi-border)] pl-4"><p className="break-all text-sm font-semibold text-[var(--misi-ink)]">{contact.value}</p><p className="mt-1 text-xs text-[var(--misi-muted)]">{[contact.name, contact.role, contact.kind].filter(Boolean).join(" · ")}</p><p className="mt-2 text-xs leading-5 text-[var(--misi-ink)]">“{contact.evidence_quote}”</p>{url && <a href={url} target="_blank" rel="noreferrer" className="mt-2 inline-block text-xs text-[var(--misi-accent)] underline underline-offset-4">{contact.source_title || "View source"}{contact.source_date ? ` · ${contact.source_date}` : ""}</a>}</div>; })}{contacts.limitations.map((item, i) => <p key={i} className="text-xs leading-5 text-[#825929]">{item}</p>)}</div>}</div>
        <div className="mt-6 border-t border-[var(--misi-border)] pt-6"><div className="flex flex-wrap items-center gap-3"><label htmlFor="lead-stage" className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--misi-muted)]">Sales stage</label><select id="lead-stage" value={selected.status} disabled={busy} onChange={(e) => void updateLead({ status: e.target.value })} className="border border-[var(--misi-border)] bg-white px-3 py-2 text-sm text-[var(--misi-ink)]">{statuses.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div><label htmlFor="lead-notes" className="mt-5 block text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--misi-muted)]">Your notes</label><textarea id="lead-notes" rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Add context from your review or conversation…" className="mt-2 w-full border border-[var(--misi-border)] bg-white p-3 text-sm text-[var(--misi-ink)]" /><Button className="mt-2" disabled={busy || notes === (selected.notes || "")} onClick={() => void updateLead({ notes })}><Check size={15} /> Save notes</Button><p className="mt-5 text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--misi-muted)]">Was this lead useful?</p><div className="mt-2 flex flex-wrap gap-2">{feedbackOptions.map(([value, label]) => <Button key={value} disabled={busy} onClick={() => void updateLead({ feedback: value })}>{label}</Button>)}</div>{message && <p role="status" className="mt-3 text-sm text-[var(--misi-accent)]">{message}</p>}<p className="mt-4 text-xs leading-5 text-[var(--misi-muted)]">From research: {selected.brief} · {selected.model}. Verify sources and current arrangements before engagement.</p></div>
        </div>
      </article>}
    </div>}
    {runs.length > 0 && <details className="border-t border-[var(--misi-border)] px-5 py-5 sm:px-6"><summary className="cursor-pointer text-sm font-semibold text-[var(--misi-ink)]">Recent research runs <span className="text-xs font-normal text-[var(--misi-muted)]">· latest {runs.length}</span></summary><p className="mt-2 text-sm text-[var(--misi-muted)]">Return to the original research, including searches that found no supported leads.</p><div className="mt-3 divide-y divide-[var(--misi-border)] border-t border-[var(--misi-border)]">{runs.map((run) => <div key={run.id} className="flex flex-wrap items-center justify-between gap-4 py-4"><div><p className="text-sm font-medium text-[var(--misi-ink)]">{run.brief}</p><p className="mt-1 text-xs text-[var(--misi-muted)]">{run.model} · {run.result.opportunities.length} leads · {run.result.observations.length} observations · {run.result.searches.length} passes</p></div><Button onClick={() => { const url = URL.createObjectURL(new Blob([JSON.stringify(publicResearchExport(run.result), null, 2)], { type: "application/json" })); const link = document.createElement("a"); link.href = url; link.download = `misi-research-${run.id}.json`; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }}>Download research</Button></div>)}</div></details>}
  </section>;
}
