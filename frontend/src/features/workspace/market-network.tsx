"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { ArrowUpRight, Building2, ChevronRight, Database, FileText, RefreshCw } from "lucide-react";
import { getApiBaseUrl } from "@/lib/api";
import { safeSource } from "./api";
import { Button } from "./ui";
import { MarketSuggestions } from "./market-suggestions";

type SourceHealth = { source_key: string; last_checked_at: string | null; last_success_at: string | null; last_new_at: string | null; last_error: string | null; failure_count: number };
type Summary = { companies: number; verified_companies: number; awards: number; source_records: number; source_revisions: number; sources: SourceHealth[]; limitations: string[] };
type Company = { id: number; name: string; identifier_scheme: string | null; identifier_value: string | null; first_seen: string | null; last_seen: string | null; identity_status: string; award_count: number };
type Award = { id: number; ocid: string | null; award_id: string | null; title: string | null; buyer: string | null; supplier: string | null; status: string | null; award_date: string | null; amount: number | string | null; currency: string | null; classification: string | null; source_url: string | null; source_revision_id: number | null; relevance?: { level: string; reason: string } };
type Page<T> = { items: T[]; total: number };
type SourceRevision = { id: number; source_key: string; record_key: string; ocid: string | null; source_url: string | null; content_hash: string; published_at: string | null; retrieved_at: string; last_seen: string; superseded_at: string | null };
type Relationship = { id: number; subject: string; object: string; relation_type: string; effective_from: string | null; effective_to: string | null; observed_at: string | null; assertion_status: string; evidence_excerpt: string; source_url: string | null; source_revision_id: number };
type Relationships = { items: Relationship[]; limitations: string[] };
type AwardContext = { award_id: number; title: string; buyer: string | null; supplier: string | null; supplier_company_number: string; award_date: string | null; timing: string; notice: { source_url: string | null; source_revision_id: number }; control: { controller: string; controller_company_number: string; notified_on: string | null; ceased_on: string | null; assertion_status: string; source_url: string | null; source_revision_id: number }; unknowns: string[] };

const PAGE_SIZE = 20;

async function get<T>(path: string, signal: AbortSignal): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}/api/market-network${path}`, { cache: "no-store", signal });
  if (!response.ok) throw new Error(`Market intelligence is unavailable (${response.status}).`);
  return response.json() as Promise<T>;
}

function readableDate(value: string | null) {
  if (!value) return "Not recorded";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? "Not recorded" : new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeZone: "Europe/London" }).format(date);
}
function readableDateTime(value: string | null) {
  if (!value) return "Not recorded";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? "Not recorded" : new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: "Europe/London" }).format(date);
}
function human(value: string | null) { return value ? value.replaceAll("_", " ").replace(/^./, letter => letter.toUpperCase()) : "Unknown"; }
function relevanceLabel(level?: string) { return level === "relevant" ? "Sector terms identified" : level === "ambiguous" ? "Needs scope review" : level === "excluded" ? "Outside sector filter" : "Scope not assessed"; }
function amountLabel(amount: number | string | null, currency: string | null) {
  if (amount == null || (typeof amount === "string" && !amount.trim())) return "Value not published";
  const value = Number(amount);
  if (!Number.isFinite(value)) return "Value not published";
  if (!currency) return `${value.toLocaleString("en-GB")} · currency not recorded`;
  try { return new Intl.NumberFormat("en-GB", { style: "currency", currency, maximumFractionDigits: 0 }).format(value); }
  catch { return `${value.toLocaleString("en-GB")} ${currency || "currency unspecified"}`; }
}

function SourceEvidence({ revisionId }: { revisionId: number }) {
  const [open, setOpen] = useState(false);
  const [source, setSource] = useState<SourceRevision | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    get<SourceRevision>(`/sources/${revisionId}`, controller.signal).then(setSource).catch(() => { if (!controller.signal.aborted) setError("Source version details are unavailable."); });
    return () => controller.abort();
  }, [open, revisionId]);
  return <details className="mt-3" onToggle={event => setOpen(event.currentTarget.open)}><summary className="cursor-pointer text-xs font-semibold text-[var(--misi-accent)]">Source version {revisionId}</summary>{error && <p role="alert" className="mt-2 text-xs text-[#825929]">{error}</p>}{open && !source && !error && <p className="mt-2 text-xs" role="status">Loading source details…</p>}{source && <div className="mt-2 text-xs leading-5 text-[var(--misi-muted)]"><p>{human(source.source_key)} · Record {source.record_key}</p><p>Published: {readableDate(source.published_at)} · Retrieved: {readableDateTime(source.retrieved_at)} · Last seen: {readableDateTime(source.last_seen)}</p><p>{source.superseded_at ? `Superseded: ${readableDateTime(source.superseded_at)}` : "Latest captured version"}</p><p className="break-all">Content fingerprint: {source.content_hash}</p>{source.source_url && safeSource(source.source_url) && <a className="text-[var(--misi-accent)] underline underline-offset-4" href={safeSource(source.source_url) || "#"} target="_blank" rel="noreferrer">Review public record <ArrowUpRight className="inline" size={12} /></a>}</div>}</details>;
}

function CompanyEvidence({ companyId }: { companyId: number }) {
  const [open, setOpen] = useState(false);
  const [ids, setIds] = useState<number[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    get<{ source_revision_ids: number[] }>(`/companies/${companyId}/sources`, controller.signal).then(data => setIds(data.source_revision_ids)).catch(() => { if (!controller.signal.aborted) setError("Organisation sources are unavailable."); });
    return () => controller.abort();
  }, [open, companyId]);
  return <details className="mt-3" onToggle={event => setOpen(event.currentTarget.open)}><summary className="cursor-pointer text-xs font-semibold text-[var(--misi-accent)]">Review linked source versions</summary>{error && <p role="alert" className="mt-2 text-xs text-[#825929]">{error}</p>}{open && !ids && !error && <p className="mt-2 text-xs" role="status">Loading source references…</p>}{ids && (ids.length ? <><p className="mt-2 text-xs text-[var(--misi-muted)]">Showing up to 20 of {ids.length} linked versions, including historical versions.</p>{ids.slice(0, 20).map(id => <SourceEvidence key={id} revisionId={id} />)}</> : <p className="mt-2 text-xs text-[var(--misi-muted)]">No source versions are linked.</p>)}</details>;
}

function CompanyRelationships({ companyId }: { companyId: number }) {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<Relationships | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    setError("");
    get<Relationships>(`/relationships?entity_id=${companyId}&limit=50`, controller.signal).then(setData).catch(() => { if (!controller.signal.aborted) setError("Relationship evidence is unavailable."); });
    return () => controller.abort();
  }, [open, companyId]);
  return <details className="mt-3" onToggle={event => setOpen(event.currentTarget.open)}><summary className="cursor-pointer text-xs font-semibold text-[var(--misi-accent)]">Review corporate relationships</summary>
    {error && <p role="alert" className="mt-2 text-xs text-[#825929]">{error}</p>}
    {open && !data && !error && <p role="status" className="mt-2 text-xs">Loading relationship evidence…</p>}
    {data && <div className="mt-2 text-xs leading-5 text-[var(--misi-muted)]">
      <p>Registry filings report submitted information; they are not independent verification of ownership. Cached filings may be out of date. Confirm the current register before relying on them.</p>
      {data.items.length ? <ul className="mt-2 divide-y divide-[var(--misi-border)]">{data.items.map(item => <li key={item.id} className="py-2"><p className="font-semibold text-[var(--misi-ink)]">{item.subject} · {item.relation_type === "SIGNIFICANT_CONTROL_BY" ? "reported significant control by" : human(item.relation_type)} · {item.object}</p><p>Reported from: {readableDate(item.effective_from)} · Reported until: {item.effective_to ? readableDate(item.effective_to) : "Not recorded"}</p><p>{item.assertion_status === "reviewed_cached_registry_filing" ? "Reviewed cached registry filing" : human(item.assertion_status)} · Captured: {readableDate(item.observed_at)}</p>{item.evidence_excerpt && <p>{item.evidence_excerpt}</p>}{item.source_url && safeSource(item.source_url) && <a className="text-[var(--misi-accent)] underline underline-offset-4" href={safeSource(item.source_url) || "#"} target="_blank" rel="noreferrer">Review registry filing <ArrowUpRight className="inline" size={12} /></a>}</li>)}</ul> : <p className="mt-2">No captured relationship filings for this organisation. This does not mean no relationship exists.</p>}
      {data.items.length === 50 && <p className="mt-2">Showing the first 50 captured relationships.</p>}
    </div>}
  </details>;
}

function CompanyAwardContext({ companyId }: { companyId: number }) {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<AwardContext[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    setError("");
    get<{items: AwardContext[]}>(`/companies/${companyId}/award-context`, controller.signal).then(result => setData(result.items)).catch(() => { if (!controller.signal.aborted) setError("Connected evidence is unavailable."); });
    return () => controller.abort();
  }, [open, companyId]);
  return <details className="mt-3" onToggle={event => setOpen(event.currentTarget.open)}><summary className="cursor-pointer text-xs font-semibold text-[var(--misi-accent)]">Connect awards and corporate filings</summary>
    {error && <p role="alert" className="mt-2 text-xs text-[#825929]">{error}</p>}{open && !data && !error && <p role="status" className="mt-2 text-xs">Loading connected evidence…</p>}
    {data && <div className="mt-2 text-xs leading-5 text-[var(--misi-muted)]"><p>These sources describe different facts joined by the supplier's exact company number. This is not independent corroboration, proof of current delivery or an award to its controller. Registry filings may be cached and are not independently verified.</p>
      {data.length ? <ul className="mt-2 divide-y divide-[var(--misi-border)]">{data.map((item, index) => <li key={`${item.award_id}-${item.control.source_revision_id}-${index}`} className="py-3"><p className="font-semibold text-[var(--misi-ink)]">{item.title} · {item.buyer || "Buyer not recorded"}</p><p>Awarded supplier: {item.supplier || "Not recorded"} · GB-COH {item.supplier_company_number} · Award date: {readableDate(item.award_date)}</p><p>Reported controller: {item.control.controller} · GB-COH {item.control.controller_company_number} · Notified: {readableDate(item.control.notified_on)}{item.control.ceased_on ? ` · Ceased: ${readableDate(item.control.ceased_on)}` : " · Cessation not recorded"}</p><p className="mt-1">{item.timing}</p><div className="mt-1 flex flex-wrap gap-x-4">{item.notice.source_url && safeSource(item.notice.source_url) && <a className="text-[var(--misi-accent)] underline underline-offset-4" href={safeSource(item.notice.source_url) || "#"} target="_blank" rel="noreferrer">Review award source <ArrowUpRight className="inline" size={12} /></a>}{item.control.source_url && safeSource(item.control.source_url) && <a className="text-[var(--misi-accent)] underline underline-offset-4" href={safeSource(item.control.source_url) || "#"} target="_blank" rel="noreferrer">Review control filing <ArrowUpRight className="inline" size={12} /></a>}</div></li>)}</ul> : <p className="mt-2">No exact-number links found in captured award and control records. This is not evidence that none exist.</p>}
      {data.length === 50 && <p className="mt-2">Showing the first 50 captured links.</p>}
    </div>}
  </details>;
}

/** Evidence here is reported procurement data, not a confirmed current contract or buying intent. */
export function MarketNetwork() {
  const [open, setOpen] = useState(false);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [companies, setCompanies] = useState<Page<Company> | null>(null);
  const [awards, setAwards] = useState<Page<Award> | null>(null);
  const [view, setView] = useState<"companies" | "awards">("companies");
  const [query, setQuery] = useState("");
  const [appliedQuery, setAppliedQuery] = useState("");
  const [supplier, setSupplier] = useState<Company | null>(null);
  const [companyOffset, setCompanyOffset] = useState(0);
  const [awardOffset, setAwardOffset] = useState(0);
  const [selectedCompany, setSelectedCompany] = useState<Company | null>(null);
  const [selectedAward, setSelectedAward] = useState<Award | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  const refresh = useCallback(() => setReload(value => value + 1), []);

  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    setLoading(true); setError("");
    const companyParams = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(companyOffset) });
    const awardParams = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(awardOffset) });
    if (appliedQuery) { companyParams.set("q", appliedQuery); awardParams.set("q", appliedQuery); }
    if (supplier) awardParams.set("supplier_id", String(supplier.id));
    Promise.all([
      get<Summary>("/summary", controller.signal),
      get<Page<Company>>(`/companies?${companyParams}`, controller.signal),
      get<Page<Award>>(`/awards?${awardParams}`, controller.signal),
    ]).then(([nextSummary, nextCompanies, nextAwards]) => {
      setSummary(nextSummary); setCompanies(nextCompanies); setAwards(nextAwards);
    }).catch((reason: unknown) => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Could not load market intelligence.");
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [open, companyOffset, awardOffset, reload, appliedQuery, supplier]);
  function applySearch(event: FormEvent) {
    event.preventDefault();
    setCompanyOffset(0); setAwardOffset(0); setSelectedCompany(null); setSelectedAward(null);
    setAppliedQuery(query.trim());
  }

  return <section className="mt-6" aria-label="Fire and security market intelligence">
    <details className="overflow-hidden rounded-2xl border border-[var(--misi-border)] bg-white" onToggle={event => setOpen(event.currentTarget.open)}>
      <summary className="cursor-pointer list-none px-5 py-5 sm:px-7 [&::-webkit-details-marker]:hidden">
        <div className="flex flex-wrap items-start justify-between gap-4"><div><p className="m-eyebrow"><Database size={14} /> Market intelligence</p><h2 className="mt-2 text-xl font-semibold text-[var(--misi-ink)]">Explore the market network</h2><p className="mt-1 max-w-2xl text-sm leading-6 text-[var(--misi-muted)]">Explore organisations and published awards captured from connected public sources.</p></div><span className="rounded-full border border-[var(--misi-border)] px-3 py-1 text-xs font-medium text-[var(--misi-accent)]">Open network <ChevronRight className="ml-1 inline" size={13} aria-hidden="true" /></span></div>
      </summary>
      {open && <div className="border-t border-[var(--misi-border)] px-5 py-5 sm:px-7">
        <p className="max-w-3xl text-sm leading-6 text-[var(--misi-muted)]">A published award is evidence of an announcement, not proof that a contract remains active or that a supplier is bidding. Company names and identifiers reflect source records and may need independent verification.</p>
        {loading && <p className="mt-4 text-sm text-[var(--misi-muted)]" role="status">Loading market records…</p>}
        {error && <div className="mt-4 flex flex-wrap items-center gap-3"><p className="text-sm text-[#825929]" role="alert">{error}</p><Button onClick={refresh}>Try again</Button></div>}
        {summary && !error && <>
          <div className="mt-5 flex flex-wrap gap-x-8 gap-y-3 border-b border-[var(--misi-border)] pb-5" aria-label="Market network totals">
            <p><strong className="block text-2xl font-semibold tracking-tight">{summary.companies.toLocaleString("en-GB")}</strong><span className="text-xs text-[var(--misi-muted)]">Supplier identity records</span></p>
            <p><strong className="block text-2xl font-semibold tracking-tight">{(summary.verified_companies ?? 0).toLocaleString("en-GB")}</strong><span className="text-xs text-[var(--misi-muted)]">Registry profiles</span></p>
            <p><strong className="block text-2xl font-semibold tracking-tight">{summary.awards.toLocaleString("en-GB")}</strong><span className="text-xs text-[var(--misi-muted)]">Published award records</span></p>
            <p><strong className="block text-2xl font-semibold tracking-tight">{summary.source_records.toLocaleString("en-GB")}</strong><span className="text-xs text-[var(--misi-muted)]">Source records captured</span></p>
            <p><strong className="block text-2xl font-semibold tracking-tight">{summary.source_revisions.toLocaleString("en-GB")}</strong><span className="text-xs text-[var(--misi-muted)]">Source versions retained</span></p>
          </div>
          <MarketSuggestions />
          <div className="mt-5 flex flex-wrap items-center gap-2" role="group" aria-label="Market record type">
            <button type="button" aria-pressed={view === "companies"} onClick={() => setView("companies")} className={`rounded-md px-3 py-2 text-sm font-semibold ${view === "companies" ? "bg-[var(--misi-accent-soft)] text-[var(--misi-accent)]" : "text-[var(--misi-muted)] hover:bg-[var(--misi-surface-secondary)]"}`}><Building2 className="mr-2 inline" size={15} />Organisations</button>
            <button type="button" aria-pressed={view === "awards"} onClick={() => setView("awards")} className={`rounded-md px-3 py-2 text-sm font-semibold ${view === "awards" ? "bg-[var(--misi-accent-soft)] text-[var(--misi-accent)]" : "text-[var(--misi-muted)] hover:bg-[var(--misi-surface-secondary)]"}`}><FileText className="mr-2 inline" size={15} />Published awards</button>
            <button type="button" className="ml-auto flex items-center gap-1 text-xs font-semibold text-[var(--misi-accent)]" onClick={refresh} disabled={loading}><RefreshCw size={13} /> Refresh view</button>
          </div>
          <form onSubmit={applySearch} className="mt-4 flex flex-wrap items-end gap-2"><label htmlFor="market-network-search" className="min-w-0 flex-1 text-xs font-semibold text-[var(--misi-ink)]">Search captured records<input id="market-network-search" value={query} onChange={event => setQuery(event.target.value)} maxLength={100} placeholder="Organisation, buyer or award title" className="mt-2 block w-full rounded-md border border-[var(--misi-border)] bg-white px-3 py-2 text-sm font-normal text-[var(--misi-ink)]" /></label><Button type="submit" disabled={loading}>Search</Button>{appliedQuery && <Button onClick={() => { setQuery(""); setAppliedQuery(""); setCompanyOffset(0); setAwardOffset(0); }}>Clear search</Button>}</form>
          {supplier && view === "awards" && <p className="mt-3 text-xs text-[var(--misi-muted)]">Showing awards linked to {supplier.name}. <button type="button" className="font-semibold text-[var(--misi-accent)] underline underline-offset-4" onClick={() => { setSupplier(null); setAwardOffset(0); }}>Show all suppliers</button></p>}
          {view === "companies" && companies && <div className="mt-3">
            {companies.items.length === 0 ? <p className="py-5 text-sm text-[var(--misi-muted)]">No matching organisation records were found in the captured data. This is not evidence that no contractors exist.</p> : <ul className="divide-y divide-[var(--misi-border)]">{companies.items.map(company => <li key={company.id}><button type="button" className="flex w-full items-center justify-between gap-4 py-4 text-left hover:text-[var(--misi-accent)]" aria-expanded={selectedCompany?.id === company.id} onClick={() => setSelectedCompany(selectedCompany?.id === company.id ? null : company)}><span><strong className="block text-sm font-semibold">{company.name}</strong><span className="mt-1 block text-xs text-[var(--misi-muted)]">{human(company.identity_status)} · {company.award_count} linked {company.award_count === 1 ? "award" : "awards"}</span></span><ChevronRight className={`shrink-0 transition-transform ${selectedCompany?.id === company.id ? "rotate-90" : ""}`} size={16} /></button>{selectedCompany?.id === company.id && <div className="mb-4 bg-[var(--misi-surface-secondary)] px-4 py-3 text-sm leading-6"><p>Identifier: {company.identifier_scheme && company.identifier_value ? `${company.identifier_scheme} · ${company.identifier_value}` : "Not established"}</p><p>First observed: {readableDate(company.first_seen)} · Last observed: {readableDate(company.last_seen)}</p><p className="mt-1 text-xs text-[var(--misi-muted)]">A source identity does not by itself establish a corporate group, service capability or a current customer relationship.</p><CompanyRelationships companyId={company.id} /><CompanyAwardContext companyId={company.id} /><CompanyEvidence companyId={company.id} /><button type="button" onClick={() => { setSupplier(company); setQuery(""); setAppliedQuery(""); setAwardOffset(0); setSelectedAward(null); setView("awards"); }} className="mt-3 text-xs font-semibold text-[var(--misi-accent)] underline underline-offset-4">See linked published awards</button></div>}</li>)}</ul>}
            <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-[var(--misi-muted)]"><span>Showing {companies.items.length ? companyOffset + 1 : 0}–{companyOffset + companies.items.length} of {companies.total}</span><Button disabled={loading || companyOffset === 0} onClick={() => { setSelectedCompany(null); setCompanyOffset(Math.max(0, companyOffset - PAGE_SIZE)); }}>Previous</Button><Button disabled={loading || companyOffset + PAGE_SIZE >= companies.total} onClick={() => { setSelectedCompany(null); setCompanyOffset(companyOffset + PAGE_SIZE); }}>Next</Button></div>
          </div>}
          {view === "awards" && awards && <div className="mt-3">
            {awards.items.length === 0 ? <p className="py-5 text-sm text-[var(--misi-muted)]">No matching awards were found in the captured data. This does not establish that none were published.</p> : <ul className="divide-y divide-[var(--misi-border)]">{awards.items.map(award => <li key={award.id}><button type="button" className="flex w-full items-center justify-between gap-4 py-4 text-left hover:text-[var(--misi-accent)]" aria-expanded={selectedAward?.id === award.id} onClick={() => setSelectedAward(selectedAward?.id === award.id ? null : award)}><span><strong className="block text-sm font-semibold">{award.title || "Published award"}</strong><span className="mt-1 block text-xs text-[var(--misi-muted)]">{award.buyer || "Buyer unknown"} · {award.supplier || "Supplier not identified"} · {readableDate(award.award_date)} · {relevanceLabel(award.relevance?.level)}</span></span><ChevronRight className={`shrink-0 transition-transform ${selectedAward?.id === award.id ? "rotate-90" : ""}`} size={16} /></button>{selectedAward?.id === award.id && <div className="mb-4 bg-[var(--misi-surface-secondary)] px-4 py-3 text-sm leading-6"><p>Published award status: {human(award.status)} · Classification: {human(award.classification)} · Published value: {amountLabel(award.amount, award.currency)}</p><p>Sector filter: {relevanceLabel(award.relevance?.level)}{award.relevance?.reason ? ` · ${award.relevance.reason}` : ""}</p><p>Procurement ID: {award.ocid || "Not recorded"} · Award ID: {award.award_id || "Not recorded"}</p><p className="mt-1 text-xs text-[var(--misi-muted)]">Published value is not necessarily realised revenue or the value attributable to this supplier. Check the notice for framework and lot details.</p>{award.source_url && safeSource(award.source_url) && <a className="mt-2 inline-block text-xs font-semibold text-[var(--misi-accent)] underline underline-offset-4" href={safeSource(award.source_url) || "#"} target="_blank" rel="noreferrer">Review source <ArrowUpRight className="inline" size={12} /></a>}{award.source_revision_id != null && <SourceEvidence revisionId={award.source_revision_id} />}</div>}</li>)}</ul>}
            <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-[var(--misi-muted)]"><span>Showing {awards.items.length ? awardOffset + 1 : 0}–{awardOffset + awards.items.length} of {awards.total}</span><Button disabled={loading || awardOffset === 0} onClick={() => { setSelectedAward(null); setAwardOffset(Math.max(0, awardOffset - PAGE_SIZE)); }}>Previous</Button><Button disabled={loading || awardOffset + PAGE_SIZE >= awards.total} onClick={() => { setSelectedAward(null); setAwardOffset(awardOffset + PAGE_SIZE); }}>Next</Button></div>
          </div>}
          <details className="mt-6 border-t border-[var(--misi-border)] pt-4"><summary className="cursor-pointer text-sm font-semibold text-[var(--misi-ink)]">Source health and coverage</summary><div className="mt-3 text-xs leading-5 text-[var(--misi-muted)]"><p>Totals describe records collected, not unique businesses or market coverage. Supplier identities without authoritative identifiers may appear more than once. Source checks do not guarantee that a publication is current or complete.</p>{summary.sources.length ? <ul className="mt-3 space-y-3">{summary.sources.map(source => <li key={source.source_key}><strong className="text-[var(--misi-ink)]">{human(source.source_key)}</strong><p>Last checked: {readableDateTime(source.last_checked_at)} · Last successful: {readableDateTime(source.last_success_at)} · Last new data: {readableDateTime(source.last_new_at)}</p>{source.last_error && <p className="text-[#825929]">A source check failed. Failures: {source.failure_count}</p>}</li>)}</ul> : <p className="mt-3">No source checks recorded yet.</p>}{summary.limitations.length > 0 && <ul className="mt-3 list-disc space-y-1 pl-4">{summary.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul>}</div></details>
        </>}
      </div>}
    </details>
  </section>;
}
