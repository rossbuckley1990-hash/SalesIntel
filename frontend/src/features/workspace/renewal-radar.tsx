"use client";

import { useEffect, useState } from "react";
import { getApiBaseUrl } from "@/lib/api";
import { safeSource } from "./api";
import { Badge, Button, Empty, Heading, Loading, Metric, SectionHeading } from "./ui";
import type { SharedProps } from "./types";

type Evidence = { source_revision_id: number; source_url: string; source: string; record_key: string; published_at: string | null };
type Value = { published_total: number | null; estimated_annualised: number | null; framework_ceiling: number | null; type: string; basis: string; scope_note: string };
type Brief = { customer: string; service_requirement: string; incumbent: string; commercial_value: string; contract_lifecycle: string; procurement_route: string; timing: string; why_it_matters: string; missing_information: string[]; next_action: string };
type Suggestion = {
  category: string; category_label: string; customer: string; title: string; supplier: string | null; timing: string | null; timing_basis: string; end_estimated: boolean; latest_end: string | null;
  nation: string; fit: string; value: Value; priority: { tier: number; reasons: string[] }; counter_evidence: string[]; next_actions: string[]; extension: string;
  link: { confidence: string; records: number; sources: string[] }; brief: Brief; evidence: Evidence[];
};
type Item = { id: number; review_state: string; suggestion: Suggestion };
type Page = { items: Item[]; total: number };
type Health = { source_key: string; status: string; last_success_at: string | null };
type Summary = {
  opportunities: number; by_category: Record<string, number>; by_tier: Record<string, number>; renewals_within_months: Record<string, number>;
  value: { estimated_annualised: number; estimated_annualised_core_only: number; unknown_value_renewals: number }; find_a_tender_unbroken_from: string | null; health: Health[]; limits: string[];
};

const PAGE = 25;
const CATEGORIES = [["", "All"], ["contract_defence", "Contract defence"], ["live_procurement", "Live procurement"], ["official_early_signal", "Official early signals"], ["pre_tender", "Pre-tender"], ["verify_first", "Verify first"]];
const NATIONS = ["", "England", "Scotland", "Wales", "Northern Ireland", "Not stated"];
const SOURCE_NAMES: Record<string, string> = { find_a_tender: "Find a Tender", contracts_finder: "Contracts Finder", public_contracts_scotland: "Public Contracts Scotland", renewal_radar: "Radar evaluation" };
const pounds = (value: number | null | undefined) => (value ? `£${Math.round(value).toLocaleString("en-GB")}` : "Not published");

export function valueLine(value: Value) {
  if (value.type === "estimated_annualised") return `${pounds(value.estimated_annualised)} a year (estimated)`;
  if (value.type === "published_total") return `${pounds(value.published_total)} published total`;
  if (value.type === "framework_ceiling") return `${pounds(value.framework_ceiling)} framework ceiling`;
  return "Value not published";
}

export function RenewalRadar({ notify }: SharedProps) {
  const base = `${getApiBaseUrl()}/api/market-network/opportunities`;
  const [summary, setSummary] = useState<Summary | null>(null);
  const [page, setPage] = useState<Page | null>(null);
  const [category, setCategory] = useState("");
  const [nation, setNation] = useState("");
  const [tier, setTier] = useState("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");
  useEffect(() => {
    fetch(`${base}/summary`, { cache: "no-store" }).then(response => (response.ok ? response.json() : Promise.reject())).then(setSummary).catch(() => setError("The radar summary is unavailable."));
  }, [base]);
  useEffect(() => {
    const controller = new AbortController();
    const query = new URLSearchParams({ limit: String(PAGE), offset: String(offset) });
    if (category) query.set("category", category);
    if (nation) query.set("nation", nation);
    if (tier) query.set("tier", tier);
    if (search.trim()) query.set("q", search.trim());
    fetch(`${base}?${query}`, { cache: "no-store", signal: controller.signal }).then(response => (response.ok ? response.json() : Promise.reject())).then((data: Page) => { setPage(data); setError(""); })
      .catch(() => { if (!controller.signal.aborted) setError("Opportunities are unavailable. Try again."); });
    return () => controller.abort();
  }, [base, category, nation, tier, search, offset]);
  async function review(id: number, state: string) {
    const response = await fetch(`${base}/${id}/review`, { method: "PATCH", headers: { "content-type": "application/json" }, body: JSON.stringify({ review_state: state }) });
    if (!response.ok) return notify("Could not save your review.", true);
    setPage(previous => previous && { ...previous, items: previous.items.map(item => (item.id === id ? { ...item, review_state: state } : item)) });
  }
  async function promote(id: number) {
    const response = await fetch(`${base}/${id}/promote`, { method: "POST" });
    if (!response.ok) return notify("Could not add this to pursuits.", true);
    const result = await response.json() as { created: boolean };
    notify(result.created ? "Added to pursuits for qualification." : "This is already in pursuits.");
    setPage(previous => previous && { ...previous, items: previous.items.map(item => (item.id === id ? { ...item, review_state: "investigate" } : item)) });
  }
  function filter(update: () => void) { update(); setOffset(0); }
  const failing = summary?.health.filter(x => x.status !== "fresh") || [];
  return <div>
    <Heading eyebrow="UK fire and security" title="Renewal Radar" description="Published contracts nearing their end, official early signals and live tenders across the UK. Every line is a record to check, not a confirmed requirement.">
      <a className="m-button secondary" href={`${base}/export.csv`}>Export CSV</a>
    </Heading>
    {error && <p role="alert">{error}</p>}
    {!summary && !error && <Loading />}
    {summary && <>
      <section aria-label="Radar totals" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Metric label="Ready to work" value={String(summary.by_tier["1"] || 0)} detail="Tier 1 opportunities" />
        <Metric label="Contract defence" value={String(summary.by_category.contract_defence || 0)} detail="Held by the Mitie group" />
        <Metric label="Live tenders" value={String(summary.by_category.live_procurement || 0)} detail="Open deadlines" />
        <Metric label="Ending within 12 months" value={String(summary.renewals_within_months["12"] || 0)} detail={`${summary.renewals_within_months["6"] || 0} within 6 months`} />
      </section>
      <p className="m-description">{pounds(summary.value.estimated_annualised_core_only)} a year estimated on core contracts in the renewal list. This is published value over published term, not guaranteed or fully addressable spend. {summary.value.unknown_value_renewals} renewals publish no value.</p>
      {failing.length > 0 && <p role="status">Needs attention: {failing.map(x => `${SOURCE_NAMES[x.source_key] || x.source_key} is ${x.status.replace("_", " ")}`).join("; ")}.</p>}
    </>}
    <section aria-label="Opportunities">
      <SectionHeading title="Opportunities" detail={page ? `${page.total.toLocaleString("en-GB")} matching, highest priority first` : undefined} />
      <div className="flex flex-wrap items-center gap-3 py-3">
        {CATEGORIES.map(([id, label]) => <Button key={id} kind={category === id ? "primary" : "secondary"} onClick={() => filter(() => setCategory(id))}>{label}</Button>)}
      </div>
      <div className="flex flex-wrap items-center gap-3 pb-3">
        <label className="text-sm">Search <input aria-label="Search customer, contract or supplier" value={search} onChange={event => filter(() => setSearch(event.target.value))} className="ml-1 rounded border border-[var(--misi-border)] bg-transparent px-2 py-1" maxLength={100} /></label>
        <label className="text-sm">Nation <select value={nation} onChange={event => filter(() => setNation(event.target.value))}>{NATIONS.map(x => <option key={x} value={x}>{x || "All UK"}</option>)}</select></label>
        <label className="text-sm">Priority <select value={tier} onChange={event => filter(() => setTier(event.target.value))}><option value="">All</option><option value="1">Tier 1</option><option value="2">Tier 2</option><option value="3">Tier 3</option></select></label>
      </div>
      {page && !page.items.length && <Empty title="No opportunities match">This does not mean none exist; it only covers captured records.</Empty>}
      {page && !!page.items.length && <ul className="divide-y divide-[var(--misi-border)]">{page.items.map(({ id, review_state, suggestion: x }) => <li key={id} className="py-3"><details>
        <summary className="cursor-pointer">
          <strong>{x.customer}</strong> · {x.title}
          <span className="mt-1 flex flex-wrap items-center gap-2 text-sm">
            <Badge>Tier {x.priority.tier}</Badge><Badge>{x.category_label}</Badge><span>{x.nation}</span>
            <span>{x.timing ? `${x.timing}${x.end_estimated ? " (estimated)" : ""}` : "No date published"}</span><span>{valueLine(x.value)}</span>{x.supplier && <span>Supplier: {x.supplier}</span>}
          </span>
        </summary>
        <div className="mt-3 text-sm leading-6">
          <p><strong>Next:</strong> {x.next_actions[0]}</p>
          {x.next_actions.length > 1 && <ul className="list-disc pl-5">{x.next_actions.slice(1).map(text => <li key={text}>{text}</li>)}</ul>}
          {x.counter_evidence.length > 0 && <><p className="mt-2"><strong>Check first</strong></p><ul className="list-disc pl-5">{x.counter_evidence.map(text => <li key={text}>{text}</li>)}</ul></>}
          <dl className="mt-2 grid gap-x-4 gap-y-1 sm:grid-cols-[12rem_1fr]">
            <dt>Why it matters</dt><dd>{x.brief.why_it_matters}</dd>
            <dt>Contract term</dt><dd>{x.brief.contract_lifecycle}</dd>
            <dt>Date basis</dt><dd>{x.timing_basis}</dd>
            <dt>Value basis</dt><dd>{x.value.basis} {x.value.scope_note}</dd>
            <dt>Procurement route</dt><dd>{x.brief.procurement_route}</dd>
            {x.extension && <><dt>Extension wording</dt><dd>{x.extension}</dd></>}
            <dt>Missing</dt><dd>{x.brief.missing_information.join(" ")}</dd>
            <dt>Records</dt><dd>{x.link.records} from {x.link.sources.join(" and ")}; link confidence {x.link.confidence}</dd>
            <dt>Priority reasons</dt><dd>{x.priority.reasons.join("; ")}</dd>
          </dl>
          <p className="mt-2"><strong>Evidence</strong></p>
          {x.evidence.slice(0, 4).map(source => <p key={source.source_revision_id}><a className="underline" href={safeSource(source.source_url) || undefined} target="_blank" rel="noreferrer">{source.source} {source.record_key}</a>{source.published_at ? ` · ${source.published_at.slice(0, 10)}` : ""}</p>)}
          <div className="mt-3 flex flex-wrap gap-2"><Button kind="primary" onClick={() => promote(id)}>Add to pursuits</Button><Button onClick={() => review(id, "defer")}>Defer</Button><Button onClick={() => review(id, "dismiss")}>Dismiss</Button></div>
          <p className="mt-2 text-xs">Your review: {review_state}. Nothing here contacts anyone.</p>
        </div>
      </details></li>)}</ul>}
      {page && page.total > PAGE && <div className="flex items-center gap-3 py-3"><Button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>Previous</Button><span className="text-sm">{offset + 1} to {Math.min(offset + PAGE, page.total)} of {page.total}</span><Button disabled={offset + PAGE >= page.total} onClick={() => setOffset(offset + PAGE)}>Next</Button></div>}
    </section>
    {summary && <section aria-label="Coverage" className="mt-6"><SectionHeading title="Coverage and limits" /><ul className="list-disc pl-5 text-sm leading-6">{summary.limits.map(text => <li key={text}>{text}</li>)}</ul></section>}
  </div>;
}
