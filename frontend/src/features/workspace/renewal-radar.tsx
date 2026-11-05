"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertCircle, ArrowRight, ChevronLeft, ChevronRight, Download, Gavel, Hourglass, Inbox, MousePointerClick, Search, ShieldAlert, Sparkles, Target, X } from "lucide-react";
import { OpportunityDetail } from "./opportunity-detail";
import { EmptyState, Pill } from "./ds";
import {
  CATEGORY, CATEGORY_ORDER, NATIONS, SOURCE_NAMES, compactPounds, radarBase, relative, shortValue, signalsOf, titleCase, urgencyTone,
  type Item, type Page, type Summary,
} from "./radar-model";
import type { SharedProps } from "./types";

export { valueLine } from "./radar-model";

const PAGE = 30;

function useWide() {
  const [wide, setWide] = useState(true);
  useEffect(() => {
    const query = window.matchMedia("(min-width: 1180px)");
    const update = () => setWide(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  return wide;
}

export function RenewalRadar({ notify, navigate }: SharedProps) {
  const base = radarBase();
  const wide = useWide();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [page, setPage] = useState<Page | null>(null);
  const [category, setCategory] = useState("");
  const [nation, setNation] = useState("");
  const [tier, setTier] = useState("");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const url = new URL(window.location.href);
    const lead = Number(url.searchParams.get("lead"));
    if (lead > 0) setSelected(lead);
    const preset = url.searchParams.get("category");
    if (preset && CATEGORY[preset]) setCategory(preset);
    if (url.searchParams.get("tier") === "1") setTier("1");
  }, []);
  useEffect(() => {
    fetch(`${base}/summary`, { cache: "no-store" }).then((r) => (r.ok ? r.json() : Promise.reject())).then(setSummary).catch(() => setError("The opportunity summary is unavailable."));
  }, [base]);
  useEffect(() => {
    const timer = setTimeout(() => { setQuery(search.trim()); setOffset(0); }, 220);
    return () => clearTimeout(timer);
  }, [search]);
  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams({ limit: String(PAGE), offset: String(offset) });
    if (category) params.set("category", category);
    if (nation) params.set("nation", nation);
    if (tier) params.set("tier", tier);
    if (query) params.set("q", query);
    setLoading(true);
    fetch(`${base}?${params}`, { cache: "no-store", signal: controller.signal }).then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data: Page) => { setPage(data); setError(""); setLoading(false); })
      .catch(() => { if (!controller.signal.aborted) { setError("Opportunities are unavailable. Check the SalesIntel API is running, then try again."); setLoading(false); } });
    return () => controller.abort();
  }, [base, category, nation, tier, query, offset]);

  // On a wide screen the first lead opens automatically, so the page is never empty.
  useEffect(() => {
    if (wide && page?.items.length && !page.items.some((i) => i.id === selected)) setSelected(page.items[0].id);
  }, [wide, page, selected]);

  const select = useCallback((id: number | null) => {
    setSelected(id);
    const url = new URL(window.location.href);
    if (id) url.searchParams.set("lead", String(id)); else url.searchParams.delete("lead");
    window.history.replaceState({}, "", url);
  }, []);

  async function review(id: number, state: string) {
    const response = await fetch(`${base}/${id}/review`, { method: "PATCH", headers: { "content-type": "application/json" }, body: JSON.stringify({ review_state: state }) });
    if (!response.ok) return notify("Could not save your review.", true);
    setPage((p) => p && { ...p, items: p.items.map((i) => (i.id === id ? { ...i, review_state: state } : i)) });
    notify(state === "dismiss" ? "Dismissed. It stays out of your way unless the evidence changes." : "Saved for later.");
  }
  async function promote(id: number) {
    const response = await fetch(`${base}/${id}/promote`, { method: "POST" });
    if (!response.ok) return notify("Could not add this to your pipeline.", true);
    const result = (await response.json()) as { created: boolean };
    notify(result.created ? "Added to your pipeline for qualification." : "This is already in your pipeline.");
    setPage((p) => p && { ...p, items: p.items.map((i) => (i.id === id ? { ...i, review_state: "investigate" } : i)) });
  }
  function filter(update: () => void) { update(); setOffset(0); }
  function clearAll() { setCategory(""); setNation(""); setTier(""); setSearch(""); setQuery(""); setOffset(0); }
  function toggle(nextCategory: string, nextTier = "") {
    const same = category === nextCategory && tier === nextTier;
    filter(() => { setCategory(same ? "" : nextCategory); setTier(same ? "" : nextTier); });
  }

  const current = page?.items.find((i) => i.id === selected) || null;
  const failing = summary?.health.filter((x) => x.status !== "fresh") || [];
  const filtered = !!(category || nation || tier || query);
  const kpis = summary && [
    { id: "tier1", icon: Target, label: "Ready to work", value: summary.by_tier["1"] || 0, detail: "Tier 1, highest priority", active: tier === "1" && !category, onClick: () => toggle("", "1") },
    { id: "live", icon: Gavel, label: "Live tenders", value: summary.by_category.live_procurement || 0, detail: "Open with a deadline", active: category === "live_procurement" && !tier, onClick: () => toggle("live_procurement") },
    { id: "ending", icon: Hourglass, label: "Ending in 12 months", value: summary.renewals_within_months["12"] || 0, detail: `${summary.renewals_within_months["6"] || 0} within 6 months`, active: category === "pre_tender" && !tier, onClick: () => toggle("pre_tender") },
    { id: "defence", icon: ShieldAlert, label: "Contracts to defend", value: summary.by_category.contract_defence || 0, detail: "Held by the Mitie group", active: category === "contract_defence" && !tier, onClick: () => toggle("contract_defence") },
  ];

  return (
    <div className="ds-root">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-[13px] font-semibold text-ds-brand">UK public sector · fire and security</p>
          <h1 className="mt-1 text-[28px] font-semibold leading-tight tracking-[-0.03em] text-ds-ink">Opportunity Finder</h1>
          <p className="mt-1.5 max-w-2xl text-[15px] leading-6 text-ds-muted">Contracts nearing renewal, early notices, live tenders and AI-inferred signals, ranked by when you need to act.</p>
        </div>
        <div className="flex gap-2">
          <a className="ds-btn" href={`${base}/export.csv`}><Download size={16} /> Export</a>
          <button className="ds-btn primary" onClick={() => navigate("discover")}><Sparkles size={16} /> Find more with AI</button>
        </div>
      </header>

      {failing.length > 0 && <div role="status" className="mt-5 flex items-start gap-2.5 rounded-xl border border-ds-amber-line bg-ds-amber-soft px-4 py-3 text-[13px] text-ds-ink-2">
        <AlertCircle size={16} className="mt-0.5 flex-none text-ds-amber" />
        <span><strong className="font-semibold text-ds-amber">Needs attention: </strong>{failing.map((x) => `${SOURCE_NAMES[x.source_key] || x.source_key} is ${x.status.replace("_", " ")}`).join("; ")}. Results from it may be out of date.</span>
      </div>}

      <section aria-label="Totals" className="mt-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {kpis ? kpis.map((k) => (
          <button key={k.id} onClick={k.onClick} aria-pressed={k.active} className={`group rounded-xl border bg-white p-4 text-left shadow-ds-xs transition hover:border-ds-brand-line hover:shadow-ds-sm ${k.active ? "border-ds-brand ring-4 ring-[rgba(59,79,216,.12)]" : "border-ds-border"}`}>
            <span className="flex items-center justify-between gap-2"><span className="text-[13px] font-medium text-ds-muted">{k.label}</span><k.icon size={16} className={k.active ? "text-ds-brand" : "text-ds-faint group-hover:text-ds-brand"} /></span>
            <span className="ds-num mt-2 block text-[28px] font-semibold leading-none tracking-[-0.02em] text-ds-ink">{k.value}</span>
            <span className="mt-2 block text-[12px] text-ds-muted">{k.detail}</span>
          </button>
        )) : [0, 1, 2, 3].map((i) => <div key={i} className="ds-skeleton h-[106px] rounded-xl" />)}
      </section>
      {summary && summary.value.estimated_annualised_core_only > 0 && <p className="mt-3 text-[12px] text-ds-muted">
        About <strong className="font-semibold text-ds-ink-2">{compactPounds(summary.value.estimated_annualised_core_only)} a year</strong> of core work is coming up for renewal (published value over published term; not guaranteed spend). {summary.value.unknown_value_renewals} renewals publish no value.
      </p>}

      <section aria-label="Filters" className="z-10 -mx-1 mt-6 bg-ds-canvas px-1 pb-3 pt-2 md:sticky md:top-[60px]">
        <div className="flex flex-wrap items-center gap-2.5">
          <div className="relative w-full sm:w-auto sm:min-w-[220px] sm:flex-1">
            <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ds-faint" />
            <input className="ds-input" aria-label="Search customer, contract or supplier" placeholder="Search customer, contract or incumbent" value={search} onChange={(e) => setSearch(e.target.value)} maxLength={100} />
            {search && <button aria-label="Clear search" className="absolute right-2 top-1/2 grid h-6 w-6 -translate-y-1/2 place-items-center rounded-md text-ds-muted hover:bg-ds-subtle" onClick={() => setSearch("")}><X size={14} /></button>}
          </div>
          <select className="ds-select min-w-0 flex-1 sm:flex-none" aria-label="Nation" value={nation} onChange={(e) => filter(() => setNation(e.target.value))}><option value="">All of the UK</option>{NATIONS.map((n) => <option key={n} value={n}>{n}</option>)}</select>
          <select className="ds-select min-w-0 flex-1 sm:flex-none" aria-label="Priority" value={tier} onChange={(e) => filter(() => setTier(e.target.value))}><option value="">Any priority</option><option value="1">Tier 1 · act now</option><option value="2">Tier 2</option><option value="3">Tier 3</option></select>
          {filtered && <button className="ds-btn ghost sm" onClick={clearAll}>Clear filters</button>}
        </div>
        <div className="ds-tabs mt-3" role="group" aria-label="Opportunity type">
          <button aria-pressed={category === ""} onClick={() => filter(() => setCategory(""))}>All <span>{summary?.opportunities ?? ""}</span></button>
          {CATEGORY_ORDER.map((id) => (
            <button key={id} aria-pressed={category === id} onClick={() => filter(() => setCategory(id))} title={CATEGORY[id].help}>
              {CATEGORY[id].label} <span>{summary?.by_category[id] ?? 0}</span>
            </button>
          ))}
        </div>
      </section>

      {error && <div role="alert" className="mt-4 rounded-xl border border-ds-red-line bg-ds-red-soft px-4 py-3 text-[13px] text-ds-red">{error}</div>}

      <div className="mt-2 grid items-start gap-5 xl:grid-cols-[minmax(320px,400px)_minmax(0,1fr)]">
        <section aria-label="Opportunities" className="min-w-0">
          <p className="mb-2 px-1 text-[12px] font-medium text-ds-muted" aria-live="polite">
            {page ? `${page.total.toLocaleString("en-GB")} ${page.total === 1 ? "opportunity" : "opportunities"}, most urgent first` : "Loading…"}
          </p>
          {!page && loading && <div className="space-y-2">{[0, 1, 2, 3, 4].map((i) => <div key={i} className="ds-skeleton h-[118px] rounded-xl" />)}</div>}
          {page && !page.items.length && <div className="ds-card"><EmptyState icon={<Inbox size={20} />} title="Nothing matches these filters" action={filtered ? <button className="ds-btn" onClick={clearAll}>Clear filters</button> : undefined}>SalesIntel only covers captured public records, so this does not mean no opportunity exists. Try AI Research to look further.</EmptyState></div>}
          {page && !!page.items.length && <ul className={`space-y-2 transition-opacity ${loading ? "opacity-60" : ""}`}>
            {page.items.map((item) => <li key={item.id}><LeadRow item={item} active={item.id === selected} onClick={() => select(item.id)} /></li>)}
          </ul>}
          {page && page.total > PAGE && <div className="mt-3 flex items-center justify-between px-1">
            <span className="text-[12px] text-ds-muted">{offset + 1}–{Math.min(offset + PAGE, page.total)} of {page.total}</span>
            <div className="flex gap-1.5">
              <button className="ds-btn sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}><ChevronLeft size={15} /> Previous</button>
              <button className="ds-btn sm" disabled={offset + PAGE >= page.total} onClick={() => setOffset(offset + PAGE)}>Next <ChevronRight size={15} /></button>
            </div>
          </div>}
        </section>

        {wide ? (
          <aside aria-label="Selected opportunity" className="ds-card sticky top-[176px] h-[calc(100vh-196px)] min-h-[520px] overflow-hidden">
            {current ? <OpportunityDetail key={current.id} item={current} onPromote={promote} onReview={review} />
              : <EmptyState icon={<MousePointerClick size={20} />} title="Select an opportunity">See why it matters, the evidence behind it and the next step, then run deep research before you engage.</EmptyState>}
          </aside>
        ) : current && (
          <div className="fixed inset-0 z-50 flex bg-[rgba(16,24,40,.35)]" role="dialog" aria-modal="true" aria-label="Opportunity detail">
            <div className="ds-fade ml-auto h-full w-full max-w-[720px] bg-white shadow-ds-lg">
              <OpportunityDetail key={current.id} item={current} onPromote={promote} onReview={review} onClose={() => select(null)} />
            </div>
          </div>
        )}
      </div>

      {summary && <details className="mt-10 rounded-xl border border-ds-border bg-white px-5 py-4 text-[13px] text-ds-muted">
        <summary className="cursor-pointer font-semibold text-ds-ink-2">Coverage and limits</summary>
        <ul className="mt-2 list-disc space-y-1 pl-5 leading-5">{summary.limits.map((t) => <li key={t}>{t}</li>)}</ul>
        <button className="mt-3 inline-flex items-center gap-1 font-semibold text-ds-brand" onClick={() => navigate("discover")}>Use AI Research for private-sector leads <ArrowRight size={14} /></button>
      </details>}
    </div>
  );
}

function LeadRow({ item, active, onClick }: { item: Item; active: boolean; onClick: () => void }) {
  const x = item.suggestion;
  const meta = CATEGORY[x.category] || { short: x.category_label, tone: "neutral" as const };
  const when = relative(x.timing);
  const value = shortValue(x.value);
  const signals = signalsOf(x).length;
  const urgency = urgencyTone(x.timing);
  const done = item.review_state === "dismiss" || item.review_state === "defer";
  return (
    <button onClick={onClick} aria-current={active ? "true" : undefined}
      className={`w-full rounded-xl border bg-white px-4 py-3.5 text-left transition ${active ? "border-ds-brand shadow-ds-sm ring-4 ring-[rgba(59,79,216,.10)]" : "border-ds-border shadow-ds-xs hover:border-ds-border-strong hover:shadow-ds-sm"} ${done ? "opacity-60" : ""}`}>
      <span className="flex items-center justify-between gap-2">
        <span className="flex min-w-0 items-center gap-1.5">
          <Pill tone={meta.tone} dot>{meta.short}</Pill>
          {x.priority.tier === 1 && <Pill tone="brand">Tier 1</Pill>}
          {item.review_state === "investigate" && <Pill tone="green">In pipeline</Pill>}
          {item.researched && <Pill tone="violet" title="A deep research dossier is saved">Researched</Pill>}
          {signals > 0 && <Sparkles size={13} className="text-ds-violet" aria-label="Has inferred signals" />}
        </span>
        {when && <span className={`ds-num flex-none text-[12px] font-semibold ${urgency === "red" ? "text-ds-red" : urgency === "amber" ? "text-ds-amber" : "text-ds-muted"}`}>{when}</span>}
      </span>
      <span className="mt-2 block truncate text-[14px] font-semibold text-ds-ink">{titleCase(x.customer)}</span>
      <span className="mt-0.5 line-clamp-2 block text-[13px] leading-5 text-ds-muted">{x.title}</span>
      <span className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-ds-muted">
        {value && <span className="ds-num font-semibold text-ds-ink-2">{value}</span>}
        {x.supplier && <span className="max-w-[220px] truncate">Incumbent: {x.supplier}</span>}
        <span>{x.nation}</span>
      </span>
    </button>
  );
}
