"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowUpRight, Bookmark, Building2, CalendarRange, ChevronDown, Eye, Globe, Inbox, Info, Landmark, Layers, MousePointerClick, Network, Radar, Rows3, Search, Sparkles, X, XCircle } from "lucide-react";
import { EmptyState, Pill } from "./ds";
import { NATIONS, relative, safeUrl, valueLine } from "./radar-model";
import { BASIS_LABEL, SERVICES, SERVICE_NAME, dayLabel, goto, param, si, type DiscoverResult, type Lead } from "./si-api";
import { useUrl } from "./si-shared";
import type { SharedProps } from "./types";
import { authMode } from "@/lib/session";
import { JobStatus, newKey, useJob, type JobT } from "./si-people";
import { ShadowCard } from "./si-shadow";
import { Runway } from "./si-runway";
import { SiAtlas } from "./si-atlas";
import { ActionDock, OpportunityBrief, useOpportunity, useWide, type Opportunity } from "./si-living";

const KIND_SHORT: Record<string, string> = { published_procurement: "Live tender", contract_ending: "Contract ending", private_signal: "Signal", customer_expansion: "Customer", unverified_candidate: "Unverified" };
const KIND_TONE: Record<string, "green" | "blue" | "amber" | "violet" | "neutral" | "brand"> = { published_procurement: "green", contract_ending: "blue", private_signal: "violet", customer_expansion: "brand", unverified_candidate: "amber" };

function ResearchRow({ job, onDone }: { job: JobT & { params?: { query?: string } }; onDone: () => void }) {
  const [live] = useJob(job, onDone) as [(JobT & { params?: { query?: string } }) | null, unknown];
  if (!live) return null;
  const done = !["queued", "running"].includes(live.status);
  return <li className="si-research-run"><p className="truncate text-[12.5px] text-ds-ink-2"><Globe size={12} className="mr-1 inline text-ds-muted" aria-hidden="true" />Web research: “{live.params?.query || job.params?.query}”</p>
    <JobStatus job={live} />{done && live.result?.message && <p className="text-[12px] text-ds-muted">{live.result.message}</p>}</li>;
}

function BriefView({ lead }: { lead: Lead }) {
  const b = lead.brief;
  const Q = ({ q, children }: { q: string; children: React.ReactNode }) => <section className="border-t border-ds-border pt-3 first:border-0 first:pt-0" aria-label={q}>
    <h3 className="si-eyebrow">{q}</h3><div className="mt-1 text-[14px] leading-6 text-ds-ink">{children}</div></section>;
  return (
    <div className="mt-3 space-y-3 rounded-xl border border-ds-border p-4">
      <Q q="Why this customer?"><ul className="space-y-0.5">{b.why_customer.map((x) => <li key={x}>{x}</li>)}{b.fit.gaps.map((x) => <li key={x} className="text-ds-amber">{x}</li>)}</ul>
        {!!b.fit.unknown.length && <p className="text-[12px] text-ds-muted">Not yet known: {b.fit.unknown.join("; ")}</p>}</Q>
      <Q q="Why now?"><p className="font-medium">{b.why_now} <span className={`text-[11px] font-semibold uppercase ${b.why_now_basis === "Published" ? "text-ds-green" : "text-ds-amber"}`}>{b.why_now_basis}</span></p>
        {b.inferred_timing && <p className="text-[12px] text-ds-muted">Inferred timing: {b.inferred_timing}</p>}</Q>
      <Q q="What do we know?"><ul className="space-y-1">{b.known.map((k, i) => { const href = safeUrl(k.source_url || ""); return <li key={i} className="text-[13px]">{k.text}{k.date && <span className="text-ds-muted"> · {k.date}</span>}
        {href && <> · <a className="font-medium text-ds-brand hover:underline" href={href} target="_blank" rel="noreferrer">source</a></>}{k.basis !== "published" && k.basis !== "stated" && <span className="text-ds-amber"> (inferred)</span>}</li>; })}</ul></Q>
      <Q q="What remains unknown?"><ul className="list-disc space-y-0.5 pl-5 text-[13px] text-ds-ink-2">{b.unknown.map((u) => <li key={u}>{u}</li>)}</ul></Q>
      <Q q="Who should we contact?"><p className="text-[13px]">{b.who.roles.join(" · ")}</p><p className="text-[12px] text-ds-muted">{b.who.summary}{b.who.people_in_research ? ` · ${b.who.people_in_research} named in research` : ""}</p></Q>
      <Q q="What should we do next?"><p className="font-semibold text-ds-brand">{b.next}</p></Q>
    </div>
  );
}

type View = { id: number; name: string; filters: Record<string, string> };
const STATUS: [string, string][] = [["active", "Active"], ["new", "New"], ["watching", "Watching"], ["investigating", "Investigating"], ["dismissed", "Dismissed"]];

/** Discover has two modes: the opportunities list, and the Contract Atlas of who holds the work today. */
export function SiDiscover(props: SharedProps) {
  const [mode, setMode] = useState<"opportunities" | "atlas">(() => (param("mode") === "atlas" ? "atlas" : "opportunities"));
  useEffect(() => {
    const sync = () => setMode(param("mode") === "atlas" ? "atlas" : "opportunities");
    window.addEventListener("popstate", sync);
    return () => window.removeEventListener("popstate", sync);
  }, []);
  function choose(next: "opportunities" | "atlas") {
    setMode(next);
    const url = new URL(window.location.href);
    for (const k of ["mode", "q", "contractor", "customer", "lead", "source", "layout"]) url.searchParams.delete(k);
    if (next === "atlas") url.searchParams.set("mode", "atlas");
    window.history.pushState({}, "", url);
  }
  return (
    <div>
      <div className="ds-tabs mb-4" role="group" aria-label="Discover mode">
        <button aria-pressed={mode === "opportunities"} onClick={() => choose("opportunities")}><Layers size={14} aria-hidden="true" />Opportunities</button>
        <button aria-pressed={mode === "atlas"} onClick={() => choose("atlas")}><Network size={14} aria-hidden="true" />Contract Atlas</button>
      </div>
      {mode === "atlas" ? <SiAtlas notify={props.notify} /> : <DiscoverOpportunities {...props} />}
    </div>
  );
}

function DiscoverOpportunities({ notify }: SharedProps) {
  useUrl();
  const [q, setQ] = useState(param("q") || "");
  const [applied, setApplied] = useState(param("q") || "");
  const [source, setSource] = useState<"all" | "public" | "private" | "shadow">(() => (["public", "private", "shadow"].includes(param("source") || "") ? param("source") as "public" | "private" | "shadow" : "all"));
  const [nation, setNation] = useState("");
  const [service, setService] = useState("");
  const [status, setStatus] = useState("active");
  const [layout, setLayout] = useState<"list" | "runway">(() => (param("layout") === "runway" ? "runway" : "list"));
  const [result, setResult] = useState<DiscoverResult | null>(null);
  const [selected, setSelected] = useState<string | null>(param("lead"));
  const [views, setViews] = useState<View[]>([]);
  const [jobs, setJobs] = useState<(JobT & { params?: { query?: string } })[]>([]);
  const loadJobs = useCallback(async () => {
    try { setJobs((await si<{ items: (JobT & { kind: string; params?: { query?: string } })[] }>("/research-jobs")).items.filter((j) => j.kind === "prospect_search").slice(0, 3)); } catch { /* optional */ }
  }, []);
  useEffect(() => { void loadJobs(); }, [loadJobs]);
  const [loading, setLoading] = useState(true);
  const search = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams({ q: applied, source, nation, service, status, limit: "100" });
    try { setResult(await si<DiscoverResult>(`/discover?${params}`)); } catch (e) { notify((e as Error).message, true); } finally { setLoading(false); }
  }, [applied, source, nation, service, status, notify]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    si<{ items: View[] }>("/saved-views").then((d) => {
      setViews(d.items);
      const chosen = d.items.find((v) => v.id === Number(param("saved"))); // opened from the sidebar
      if (chosen) applyView(chosen);
    }).catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    // On a wide screen the first result opens beside the list. On a phone the detail is a sheet over the page, so it opens only when chosen.
    const wide = typeof window !== "undefined" && window.matchMedia("(min-width: 1280px)").matches;
    if (wide && result?.items.length && !result.items.some((x) => x.key === selected)) setSelected(result.items[0].key);
  }, [result, selected]);

  // Keyboard: / to search, j and k to move, o to open the account.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = ["INPUT", "TEXTAREA", "SELECT"].includes((e.target as HTMLElement).tagName);
      if (e.key === "/" && !typing) { e.preventDefault(); search.current?.focus(); return; }
      if (typing || !result?.items.length || e.metaKey || e.ctrlKey) return;
      const index = result.items.findIndex((x) => x.key === selected);
      if (e.key === "j" || e.key === "ArrowDown") { e.preventDefault(); setSelected(result.items[Math.min(index + 1, result.items.length - 1)].key); }
      if (e.key === "k" || e.key === "ArrowUp") { e.preventDefault(); setSelected(result.items[Math.max(index - 1, 0)].key); }
      if (e.key === "o" && current) void openAccount(current);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const current = useMemo(() => result?.items.find((x) => x.key === selected) || null, [result, selected]);
  const op = useOpportunity(current?.key ?? null, notify, { onChanged: () => void load() });

  async function setLeadStatus(lead: Lead, next: Lead["status"]) {
    setResult((r) => r && { ...r, items: r.items.map((x) => (x.key === lead.key ? { ...x, status: next } : x)) });
    try {
      await si(`/discover/${lead.key}/status`, { method: "POST", json: { status: next } });
      notify(next === "dismissed" ? "Dismissed." : next === "watching" ? "Watching." : "Updated.");
      if (next === "dismissed" && status === "active") setResult((r) => r && { ...r, items: r.items.filter((x) => x.key !== lead.key), total: r.total - 1 });
    } catch (e) { notify((e as Error).message, true); void load(); }
  }
  async function openAccount(lead: Lead, then: "clients" | "engage" = "clients") {
    try {
      const linked = await si<{ account_id: number; created: boolean; basis: string }>(`/discover/${lead.key}/account`, { method: "POST", json: {} });
      if (linked.created) notify(`Account created for ${lead.organisation}.`);
      else if (linked.basis === "same_name") notify(`Linked to the existing ${lead.organisation} account by name. Confirm it is the same organisation.`);
      goto(then, { account: linked.account_id, source: lead.key });
    } catch (e) { notify((e as Error).message, true); }
  }
  async function webResearch() {
    const text = applied || q;
    if (text.trim().length < 3) return notify("Describe what to look for first.", true);
    try {
      const job = await si<JobT>("/discover/research", { method: "POST", json: { query: text }, headers: { "Idempotency-Key": newKey() } });
      setJobs((j) => [{ ...job, params: { query: text } } as JobT & { params: { query: string } }, ...j]);
      notify("Web research started. It keeps running if you leave or refresh this page.");
    } catch (e) { notify((e as Error).message, true); }
  }
  async function saveView() {
    const name = window.prompt("Name this view", applied || "My territory");
    if (!name) return;
    try {
      const view = await si<View>("/saved-views", { method: "POST", json: { name, filters: { q: applied, source, nation, service, status } } });
      setViews((v) => [...v, view]);
      notify("View saved.");
    } catch (e) { notify((e as Error).message, true); }
  }
  function applyView(v: View) {
    setQ(v.filters.q || ""); setApplied(v.filters.q || ""); setSource((v.filters.source as typeof source) || "all");
    setNation(v.filters.nation || ""); setService(v.filters.service || ""); setStatus(v.filters.status || "active");
  }
  const filtered = !!(applied || nation || service || source !== "all" || status !== "active");

  return (
    <div className="ds-root">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="si-eyebrow mb-1.5">Opportunities</p>
          <h1 className="text-[26px] font-semibold leading-tight tracking-[-0.025em] text-ds-ink">Discover</h1>
          <p className="mt-1.5 text-[14px] text-ds-muted">Public tenders, contract renewals and private-sector research in one list, most time-sensitive first.</p>
        </div>
        <div className="ds-tabs" role="group" aria-label="Layout">
          <button aria-pressed={layout === "list"} onClick={() => setLayout("list")}><Rows3 size={14} aria-hidden="true" />List</button>
          <button aria-pressed={layout === "runway"} onClick={() => setLayout("runway")}><CalendarRange size={14} aria-hidden="true" />Runway</button>
        </div>
        {!!views.length && <div className="flex w-full flex-wrap items-center gap-1.5"><Bookmark size={14} className="text-ds-muted" />{views.map((v) => <button key={v.id} className="rounded-full border border-ds-border bg-white px-2.5 py-1 text-[12px] font-medium text-ds-ink-2 hover:border-ds-brand-line hover:text-ds-brand" onClick={() => applyView(v)}>{v.name}</button>)}</div>}
      </header>

      <section aria-label="Search and filters" className="mt-4 space-y-2.5">
        <form className="flex flex-col gap-2 sm:flex-row" onSubmit={(e) => { e.preventDefault(); setApplied(q.trim()); }} role="search">
          <div className="si-hero-search relative flex-1">
            <Search size={17} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-ds-muted" />
            <input ref={search} className="ds-input !h-11 !pl-10 !pr-9" aria-label="Search opportunities" value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. care homes in Yorkshire with fire alarm maintenance    ( / )" />
            {q && <button type="button" aria-label="Clear search" className="absolute right-2 top-1/2 grid h-7 w-7 -translate-y-1/2 place-items-center rounded-md text-ds-faint hover:bg-ds-subtle" onClick={() => { setQ(""); setApplied(""); }}><X size={15} /></button>}
          </div>
          <button className="ds-btn primary !h-11">Search</button>
          <button type="button" className="ds-btn !h-11" onClick={() => void webResearch()} title="Ask Claude to search the web for private-sector companies. Uses API credit."><Globe size={15} /> Research the web</button>
        </form>
        <div className="flex flex-wrap items-center gap-2">
          <div className="ds-tabs" role="group" aria-label="Source">
            {([["all", "All", Layers], ["shadow", "Shadow Radar", Radar], ["public", "Public procurement", Landmark], ["private", "Private research", Building2]] as const).map(([id, label, Icon]) => (
              <button key={id} aria-pressed={source === id} onClick={() => setSource(id)}><Icon size={14} aria-hidden="true" />{label}{result && id !== "all" && <span>{result.counts[id]}</span>}</button>))}
          </div>
          <select className="ds-select !h-9" aria-label="Nation" value={nation} onChange={(e) => setNation(e.target.value)}><option value="">All of the UK</option>{NATIONS.map((n) => <option key={n} value={n}>{n}</option>)}</select>
          <select className="ds-select !h-9" aria-label="Service" value={service} onChange={(e) => setService(e.target.value)}><option value="">Any service</option>{SERVICES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
          <select className="ds-select !h-9" aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value)}>{STATUS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
          {filtered && <><button className="ds-btn ghost sm" onClick={() => { setQ(""); setApplied(""); setSource("all"); setNation(""); setService(""); setStatus("active"); }}>Clear</button>
            <button className="ds-btn ghost sm" onClick={() => void saveView()}><Bookmark size={14} /> Save view</button></>}
        </div>
        {result && applied && (result.interpreted.nations.length + result.interpreted.services.length + result.interpreted.regions.length > 0) && <p className="text-[12px] text-ds-muted">
          Understood: {[...result.interpreted.nations, ...result.interpreted.services.map((s) => SERVICE_NAME[s] || s), ...result.interpreted.regions].join(", ")}{result.interpreted.keywords.length ? `; matching “${result.interpreted.keywords.join(" ")}”` : ""}.</p>}
        {result?.gaps.map((g) => <p key={g} className="flex items-start gap-2 rounded-xl border border-ds-amber-line bg-ds-amber-soft px-3 py-2 text-[12px] leading-[18px] text-ds-ink-2"><Info size={14} className="mt-px flex-none text-ds-amber" aria-hidden="true" />{g}</p>)}
        {!!jobs.length && <section aria-label="Web research runs" className="si-research-runs"><p className="si-eyebrow">Your latest web research</p>
          <ul>{jobs.map((j) => <ResearchRow key={j.id} job={j} onDone={() => { void load(); void loadJobs(); }} />)}</ul></section>}
      </section>

      {layout === "runway" && <div className="mt-5 space-y-4">
        {!result ? <div className="ds-skeleton h-72 rounded-xl" /> : <Runway items={result.items} selected={selected} onSelect={setSelected} />}
        {current && <aside aria-label="Selected opportunity" className="lo-detail !static !max-h-none"><Detail key={current.key} lead={current} op={op} notify={notify} onStatus={setLeadStatus} onChanged={() => void load()} /></aside>}
      </div>}

      {layout === "list" && <div className="lo-cockpit">
        <section aria-label="Results" className="min-w-0">
          <p className="mb-2 px-1 text-[12px] font-medium text-ds-muted" aria-live="polite">{result ? `${result.total} result${result.total === 1 ? "" : "s"}` : "Loading…"}{result && result.total > 0 && " · j/k to move, o to open"}</p>
          {!result && loading && <div className="space-y-2">{[0, 1, 2, 3].map((i) => <div key={i} className="ds-skeleton h-[104px] rounded-xl" />)}</div>}
          {result && !result.items.length && <div className="ds-card"><EmptyState icon={<Inbox size={20} />} title="No matches">{result.gaps[result.gaps.length - 1]}</EmptyState></div>}
          <ul className={`si-stagger si-results space-y-2 ${loading ? "opacity-60" : ""}`}>
            {result?.items.map((lead) => <li key={lead.key}><LeadRow lead={lead} active={lead.key === selected} onClick={() => setSelected(lead.key)} /></li>)}
          </ul>
        </section>
        <aside aria-label="Selected opportunity" className="lo-detail hidden xl:block">
          {current ? <Detail key={current.key} lead={current} op={op} notify={notify} onStatus={setLeadStatus} onChanged={() => void load()} />
            : <EmptyState icon={<MousePointerClick size={20} />} title="Select a result">See what happened, why it could matter, what could disprove it and the one thing to do next.</EmptyState>}
        </aside>
        {current && <button className="si-sheet-backdrop xl:hidden" aria-label="Close details" tabIndex={-1} onClick={() => setSelected(null)} />}
        {current && <div key={current.key} className="si-sheet fixed inset-x-0 bottom-0 z-40 max-h-[82vh] overflow-y-auto rounded-t-[20px] border-t border-ds-border bg-white shadow-ds-lg xl:hidden" role="region" aria-label="Selected opportunity details">
          <span className="si-sheet-handle" aria-hidden="true" />
          <button className="ds-btn ghost sm m-3 mb-0" onClick={() => setSelected(null)}><X size={14} /> Close</button>
          <Detail lead={current} op={op} notify={notify} onStatus={setLeadStatus} onChanged={() => void load()} />
        </div>}
      </div>}
    </div>
  );
}

/** The middle and right panels of the cockpit: the Living Opportunity and its Action Dock, with the lead's own record kept below. */
function Detail({ lead, op, notify, onStatus, onChanged }: { lead: Lead; op: Opportunity; notify: SharedProps["notify"]; onStatus: (l: Lead, s: Lead["status"]) => void; onChanged: () => void }) {
  const legacy = lead.type === "public" ? { view: "radar", key: "lead", id: lead.key.slice(3) } : lead.type === "private" ? { view: "prospects", key: "prospect", id: lead.key.slice(3) } : null;
  const [frame, wide] = useWide(760); // wide: the dock is the third panel; narrow: it follows the reveal, so what happened is read first
  return (
    <div ref={frame} className={`lo-detail-inner ${wide ? "wide" : ""}`}>
      <div className="min-w-0 space-y-4">
        <div className="lo-lead-bar">
          <Pill tone={lead.type === "public" ? "blue" : lead.type === "shadow" ? "amber" : "violet"}>{lead.source_label}</Pill>
          <Pill tone={lead.basis === "published" ? "green" : "amber"}>{lead.basis === "published" ? "Published evidence" : "Inferred: verify"}</Pill>
          {lead.account_id && <Pill tone="green">{BASIS_LABEL[lead.link_basis || ""] || "Account"}</Pill>}
          <span className="ml-auto flex gap-1">
            {lead.status !== "watching" && <button className="ds-btn ghost sm" onClick={() => onStatus(lead, "watching")}><Eye size={14} /> Watch</button>}
            {lead.status !== "dismissed" ? <button className="ds-btn ghost sm" onClick={() => onStatus(lead, "dismissed")}><XCircle size={14} /> Dismiss</button>
              : <button className="ds-btn ghost sm" onClick={() => onStatus(lead, "new")}>Restore</button>}
          </span>
        </div>
        <OpportunityBrief op={op} afterReveal={wide ? null : <ActionDock op={op} />}>
          <details className="lo-source-record" aria-label="Source record">
            <summary><ChevronDown size={14} aria-hidden="true" />Source record<span className="lo-meta ml-1 font-normal">{lead.type === "shadow" ? "the Shadow Radar card" : "the six questions, as first found"}</span></summary>
            <div className="mt-3">{lead.type === "shadow" ? <ShadowCard lead={lead} notify={notify} onChanged={onChanged} /> : <LeadRecord lead={lead} />}</div>
            {authMode === "local" && legacy && <button className="mt-3 inline-flex items-center gap-1 text-[13px] font-semibold text-ds-brand hover:underline" onClick={() => goto(legacy.view, { [legacy.key]: legacy.id })}>
              {lead.type === "public" ? "Full record, evidence and deep research" : "Full research: signals, timing, people"} <ArrowUpRight size={13} /></button>}
          </details>
        </OpportunityBrief>
      </div>
      {wide && <div className="lo-dock-col"><ActionDock op={op} /></div>}
    </div>
  );
}

function LeadRow({ lead, active, onClick }: { lead: Lead; active: boolean; onClick: () => void }) {
  const urgent = lead.days !== null && lead.days >= 0 && lead.days <= 30;
  const rid = `lead-${lead.key.replace(/[^a-z0-9]/gi, "-")}`;
  return (
    // Named organisation first, so a screen reader hears who before what (and the row is never confused with a source tab).
    <button onClick={onClick} aria-current={active ? "true" : undefined} aria-labelledby={`${rid}-org ${rid}-meta ${rid}-why`}
      className={`si-lead w-full rounded-xl border bg-white px-4 py-3 text-left transition duration-200 ${active ? "border-ds-brand" : "border-ds-border shadow-ds-xs hover:border-ds-border-strong"} ${lead.status === "dismissed" ? "opacity-60" : ""}`}>
      <span id={`${rid}-meta`} className="flex items-center justify-between gap-2">
        <span className="flex min-w-0 flex-wrap items-center gap-1.5">
          <span className="si-type mr-1" style={{ ["--c" as string]: lead.type === "public" ? (lead.kind === "contract_ending" ? "#1baf7a" : "#2a78d6") : lead.type === "shadow" ? "#eb6834" : "#8e8b93" }}><i aria-hidden="true" />{lead.type === "public" ? "Public" : lead.type === "shadow" ? "Shadow Radar" : "Private"}</span>
          {lead.type === "shadow" && lead.shadow ? <><Pill>{lead.shadow.state_label}</Pill><Pill tone="violet">{lead.shadow.sensor_name}{lead.shadow.competing?.length ? ` +${lead.shadow.competing.length}` : ""}</Pill></>
            : <Pill tone={KIND_TONE[lead.kind] || "neutral"}>{KIND_SHORT[lead.kind] || lead.kind_label}</Pill>}
          {lead.type === "private" && lead.light && <Pill tone={lead.light === "green" ? "green" : lead.light === "amber" ? "amber" : lead.light === "red" ? "red" : "neutral"} dot>{lead.category_label}</Pill>}
          {lead.basis === "inferred" && lead.type !== "shadow" && <Pill tone="amber">Inferred</Pill>}
          {lead.account_id && <Pill tone="green">Account</Pill>}
          {lead.status === "watching" && <Pill>Watching</Pill>}
        </span>
        {lead.timing && lead.type === "public" && <span className={`flex-none text-[12px] font-semibold ${urgent ? "text-ds-red" : "text-ds-muted"}`}>{lead.days !== null && lead.days < 0 ? relative(lead.timing) : dayLabel(lead.timing)}</span>}
      </span>
      <span id={`${rid}-org`} className="mt-1.5 block truncate text-[14px] font-semibold text-ds-ink">{lead.organisation}</span>
      {lead.type === "shadow" && lead.shadow?.site && <span className="mt-0.5 block truncate text-[13px] text-ds-ink-2">{lead.shadow.site}</span>}
      <span id={`${rid}-why`} className="mt-0.5 line-clamp-2 block text-[13px] leading-5 text-ds-ink-2"><strong className="font-semibold">Why now: </strong>{lead.type === "shadow" ? lead.shadow?.timeline.find((e) => e.role === "anchor")?.statement : lead.why_now}</span>
    </button>
  );
}

function LeadRecord({ lead }: { lead: Lead }) {
  const value = lead.value ? valueLine(lead.value) : "Not published";
  return (
    <div aria-label={lead.organisation}>
      <Pill tone={KIND_TONE[lead.kind] || "neutral"}>{lead.kind_label}</Pill>
      <p className="mt-2 text-[14px] font-semibold text-ds-ink">{lead.organisation}</p>
      <p className="mt-0.5 text-[13px] leading-5 text-ds-ink-2">{lead.title}</p>
      <BriefView lead={lead} />
      <dl className="mt-3 grid gap-2.5 sm:grid-cols-2">
        <div className="rounded-lg bg-ds-canvas px-3 py-2.5"><dt className="text-[12px] text-ds-muted">{lead.type === "public" ? (lead.timing_label ? lead.timing_label[0].toUpperCase() + lead.timing_label.slice(1) : "Timing") : "Timing"}</dt><dd className="text-[14px] font-semibold text-ds-ink">{lead.type === "public" ? (lead.timing ? new Date(lead.timing).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" }) : "Not published") : lead.category_label}</dd></div>
        <div className="rounded-lg bg-ds-canvas px-3 py-2.5"><dt className="text-[12px] text-ds-muted">Value</dt><dd className="text-[14px] font-semibold text-ds-ink">{value}</dd></div>
        <div className="rounded-lg bg-ds-canvas px-3 py-2.5"><dt className="text-[12px] text-ds-muted">Supplier named</dt><dd className="text-[14px] font-semibold text-ds-ink">{lead.supplier || "Unknown"}</dd>{lead.supplier && <dd className="text-[12px] text-ds-muted">Reported, not necessarily today&apos;s incumbent</dd>}</div>
        <div className="rounded-lg bg-ds-canvas px-3 py-2.5"><dt className="text-[12px] text-ds-muted">Where</dt><dd className="text-[14px] font-semibold text-ds-ink">{lead.nation || lead.region || "Not stated"}</dd></div>
      </dl>
      {!!lead.services.length && <div className="mt-3 flex flex-wrap gap-1.5">{lead.services.map((s) => <Pill key={s} tone="brand">{SERVICE_NAME[s] || s}</Pill>)}</div>}
      {lead.type === "private" && <p className="mt-3 text-[13px] text-ds-muted">{lead.people || 0} named people and {lead.contact_routes || 0} published contact routes found by research.</p>}
      {lead.type === "private" && <p className="mt-3 flex items-center gap-1.5 text-[12px] text-ds-muted"><Sparkles size={12} /> Found by AI web research. Check the sources before relying on it.</p>}
    </div>
  );
}
