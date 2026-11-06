"use client";
/**
 * Contract Atlas: who holds the fire and security work, for whom, until when, and which accounts are worth investigating.
 *
 * Published contracts come from the Market Network and say where each fact comes from. Relationships reported by case
 * studies and announcements are researched on request, inside the research budget, and show the page's own words.
 * Nothing here estimates a probability: an account is worth investigating for a stated reason, with what would disprove it.
 */
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { AlertTriangle, ArrowUpRight, BadgeCheck, Building2, CircleHelp, Landmark, Link2, Search, ShieldCheck, Telescope, X } from "lucide-react";
import { Pill } from "./ds";
import { safeUrl, type Tone } from "./radar-model";
import { goto, param, si } from "./si-api";
import { JobStatus, newKey, useJob, type JobT } from "./si-people";

type Service = { family: string; label: string; contracts?: number };
type Reason = { kind: string; title: string; facts: string[]; mechanism: string; alternatives: string[]; disconfirming: string[]; missing: string[];
  action: string; next_step: string; key?: string };
type Status = { code: string; label: string; detail: string; end?: string; latest_end?: string };
export type AtlasContract = { key: string; id: number; customer: string; customer_key: string; title: string; supplier: string; supplier_name_seen: string;
  contractor_id?: number; match: { basis: string; label: string }; services: Service[]; scope: { code: string; label: string };
  route: { code: string; label: string }; nation: string; region: string; region_approximate: boolean;
  value: { amount: number; kind: string; label: string; basis: string; annual_estimate?: number } | null;
  status: Status; sources: { label: string; url: string; published: string }[]; checks: string[];
  timeline: { date: string; event: string; basis: string }[]; reasons: Reason[] };
type Relationship = { id: number; kind: string; supplier: string; contractor_id: number | null; customer: string; customer_key: string; intermediary: string;
  services: Service[]; sites_mentioned: string; published_on: string; duration_stated: string; currency: string;
  source: { url: string; title: string; type: string }; quote: string; quote_verified: boolean; status: string; unknowns: string[]; caveat: string };
type Research = { id: number; status: string; when: string; cost_cents: number; result: { message?: string; searched_for?: string[]; not_found?: string[];
  sources_reviewed?: number } } | null;
type Contractor = { id: number; name: string; yours: boolean;
  identity: { company_number: string | null; basis: string; basis_label: string; aliases: { name: string; source: string }[];
    group: { parent_name: string; parent_number: string | null; basis: string; note: string } | null;
    conflicts: { kind: string; names: string[]; company_numbers: string[]; note: string }[] };
  services: Service[]; contracts: AtlasContract[]; relationships: Relationship[]; unsupported_relationships: number; worth_investigating: AtlasContract[];
  coverage: Record<string, string>; research: Research };
type Customer = { key: string; name: string; incumbent: { state: string; label: string }; contracts: AtlasContract[]; relationships: Relationship[];
  signals: Reason[]; research: Research; coverage: string };
type Row = { id?: number; key?: string; name: string; company_number?: string | null; identity_basis?: string; contracts: number; live?: number;
  ending_soon: number; customers?: number; suppliers?: string[]; services: Service[]; region?: string; nation?: string };
type Found = { contractors: Row[]; customers: Row[]; totals: { contractors: number; customers: number };
  options: { disciplines: { family: string; label: string }[]; regions: string[]; nations: string[] } };

const STATUS_TONE: Record<string, Tone> = { end_approaching: "amber", extension_possible: "amber", extension_window: "amber", replacement_identified: "violet",
  end_passed_unknown: "neutral", in_term: "green", term_not_published: "neutral", framework: "blue", historical: "neutral" };
const KIND_LABEL: Record<string, string> = { direct_customer: "Customer", subcontract: "Subcontract", fm_delivery: "Through an FM provider", partnership: "Partnership" };
const SOURCE_LABEL: Record<string, string> = { supplier_case_study: "Supplier case study", supplier_customer_page: "Supplier's customer page", press_release: "Press release",
  trade_press: "Trade press", customer_report: "Customer's own report", fm_announcement: "FM announcement", other: "Public page" };
const money = (n: number) => `£${Math.round(n).toLocaleString("en-GB")}`;

function setUrl(next: Record<string, string | null>) {
  const url = new URL(window.location.href);
  for (const [k, v] of Object.entries(next)) if (v) url.searchParams.set(k, v); else url.searchParams.delete(k);
  window.history.replaceState({}, "", url);
}

export function SiAtlas({ notify }: { notify: (m: string, e?: boolean) => void }) {
  const [q, setQ] = useState(param("q") || "");
  const [applied, setApplied] = useState(param("q") || "");
  const [discipline, setDiscipline] = useState("");
  const [region, setRegion] = useState("");
  const [ending, setEnding] = useState("");
  const [found, setFound] = useState<Found | null>(null);
  const [selected, setSelected] = useState<{ type: "contractor"; id: number } | { type: "customer"; key: string } | null>(() => {
    const c = Number(param("contractor")); const k = param("customer");
    return c > 0 ? { type: "contractor", id: c } : k ? { type: "customer", key: k } : null;
  });
  useEffect(() => {
    const p = new URLSearchParams();
    if (applied) p.set("q", applied);
    if (discipline) p.set("discipline", discipline);
    if (region) p.set("region", region);
    if (ending) p.set("ending_months", ending);
    si<Found>(`/atlas/search?${p}`).then(setFound).catch((e) => notify((e as Error).message, true));
  }, [applied, discipline, region, ending, notify]);
  function open(next: { type: "contractor"; id: number } | { type: "customer"; key: string }) {
    setSelected(next);
    setUrl({ contractor: next.type === "contractor" ? String(next.id) : null, customer: next.type === "customer" ? next.key : null });
    document.getElementById("atlas-record")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  return (
    <div className="ds-root">
      <header>
        <p className="si-eyebrow mb-1.5">Contract Atlas</p>
        <h1 className="text-[26px] font-semibold leading-tight tracking-[-0.025em] text-ds-ink">Who holds the work</h1>
        <p className="mt-1.5 max-w-3xl text-[14px] text-ds-muted">Which contractors hold fire and security contracts, for whom and until when, from published records, and what public
          sources report about private customers when you research them. Every fact says where it comes from.</p>
      </header>
      <section aria-label="Search the Atlas" className="mt-4 space-y-2.5">
        <form role="search" className="flex flex-col gap-2 sm:flex-row" onSubmit={(e) => { e.preventDefault(); setApplied(q.trim()); setUrl({ q: q.trim() || null }); }}>
          <div className="si-hero-search relative flex-1">
            <Search size={17} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-ds-muted" />
            <input className="ds-input !h-11 !pl-10 !pr-9" aria-label="Contractor or customer" value={q} onChange={(e) => setQ(e.target.value)}
              placeholder="A contractor or a customer, e.g. Chubb, Churches, a housing association" />
            {q && <button type="button" aria-label="Clear search" className="absolute right-2 top-1/2 grid h-7 w-7 -translate-y-1/2 place-items-center rounded-md text-ds-faint hover:bg-ds-subtle"
              onClick={() => { setQ(""); setApplied(""); setUrl({ q: null }); }}><X size={15} /></button>}
          </div>
          <button className="ds-btn primary !h-11">Search</button>
        </form>
        <div className="flex flex-wrap items-center gap-2">
          <select className="ds-select !h-9" aria-label="Service" value={discipline} onChange={(e) => setDiscipline(e.target.value)}>
            <option value="">Any service</option>{found?.options.disciplines.map((d) => <option key={d.family} value={d.family}>{d.label}</option>)}</select>
          <select className="ds-select !h-9" aria-label="Region" value={region} onChange={(e) => setRegion(e.target.value)}>
            <option value="">All regions</option>{found?.options.regions.map((r) => <option key={r} value={r}>{r}</option>)}</select>
          <select className="ds-select !h-9" aria-label="Published end" value={ending} onChange={(e) => setEnding(e.target.value)}>
            <option value="">Any end date</option><option value="6">Ending within 6 months</option><option value="12">Ending within 12 months</option>
            <option value="18">Ending within 18 months</option><option value="24">Ending within 24 months</option></select>
          {found && <span className="text-[12.5px] text-ds-muted">{found.totals.contractors} contractors · {found.totals.customers} customers</span>}
        </div>
      </section>

      <div className="mt-5 grid items-start gap-5 xl:grid-cols-[minmax(0,380px)_minmax(0,1fr)]">
        <div className="space-y-5">
          <Results title="Contractors" icon={<Building2 size={15} aria-hidden="true" />} rows={found?.contractors} empty="No contractor matches."
            render={(r) => <button className="w-full text-left" onClick={() => r.id && open({ type: "contractor", id: r.id })} aria-current={selected?.type === "contractor" && selected.id === r.id ? "true" : undefined}>
              <span className="block truncate text-[14px] font-semibold text-ds-ink">{r.name}</span>
              <span className="mt-0.5 block text-[12px] text-ds-muted">{r.company_number ? `Companies House ${r.company_number}` : "Name only"} · {r.contracts} contract{r.contracts === 1 ? "" : "s"} · {r.customers} customer{r.customers === 1 ? "" : "s"}</span>
              <Chips row={r} /></button>} />
          <Results title="Customers" icon={<Landmark size={15} aria-hidden="true" />} rows={found?.customers} empty="No customer matches."
            render={(r) => <button className="w-full text-left" onClick={() => r.key && open({ type: "customer", key: r.key })} aria-current={selected?.type === "customer" && selected.key === r.key ? "true" : undefined}>
              <span className="block truncate text-[14px] font-semibold text-ds-ink">{r.name}</span>
              <span className="mt-0.5 block text-[12px] text-ds-muted">{[r.region || r.nation, `${r.contracts} contract${r.contracts === 1 ? "" : "s"}`, (r.suppliers || []).slice(0, 2).join(", ")].filter(Boolean).join(" · ")}</span>
              <Chips row={r} /></button>} />
        </div>
        <div id="atlas-record" className="min-w-0 scroll-mt-4">
          {!selected ? <div className="ds-card p-6 text-[14px] text-ds-muted">Choose a contractor to see who it works for, or a customer to see who supplies it.</div>
            : selected.type === "contractor" ? <ContractorRecord key={selected.id} id={selected.id} notify={notify} onCustomer={(key) => open({ type: "customer", key })} />
              : <CustomerRecord key={selected.key} customerKey={selected.key} notify={notify} onContractor={(id) => open({ type: "contractor", id })} />}
        </div>
      </div>
    </div>
  );
}

function Results({ title, icon, rows, empty, render }: { title: string; icon: ReactNode; rows: Row[] | undefined; empty: string; render: (r: Row) => ReactNode }) {
  return (
    <section aria-label={title} className="ds-card overflow-hidden">
      <h2 className="flex items-center gap-2 border-b border-ds-border px-4 py-2.5 text-[13px] font-semibold text-ds-ink">{icon}{title}</h2>
      {!rows ? <div className="ds-skeleton m-4 h-24 rounded-lg" /> : !rows.length ? <p className="px-4 py-3 text-[13px] text-ds-muted">{empty}</p>
        : <ul className="max-h-[420px] divide-y divide-ds-border overflow-y-auto">{rows.map((r) => <li key={r.id ?? r.key} className="px-4 py-2.5 hover:bg-ds-subtle">{render(r)}</li>)}</ul>}
    </section>
  );
}

function Chips({ row }: { row: Row }) {
  return <span className="mt-1.5 flex flex-wrap gap-1">{row.ending_soon > 0 && <Pill tone="amber">{row.ending_soon} ending within 18 months</Pill>}
    {row.services.slice(0, 2).map((s) => <Pill key={s.family}>{s.label}</Pill>)}</span>;
}

/** Turn a competitor-held contract into an account, linked to the contract and its evidence, without retyping anything. */
async function investigate(contract: AtlasContract, notify: (m: string, e?: boolean) => void) {
  try {
    const linked = await si<{ account_id: number; created: boolean }>(`/discover/${contract.key}/account`, { method: "POST", json: {} });
    notify(linked.created ? `Account created for ${contract.customer}, linked to the published contract.` : `Opened ${contract.customer}, already an account.`);
    goto("clients", { account: linked.account_id, source: contract.key });
  } catch (e) { notify((e as Error).message, true); }
}

function ReasonDetail({ r }: { r: Reason }) {
  const list = (label: string, items: string[]) => !!items.length && <div><dt className="text-[12px] font-semibold text-ds-ink-2">{label}</dt>
    <dd><ul className="mt-0.5 list-disc space-y-0.5 pl-4">{items.map((x) => <li key={x}>{x}</li>)}</ul></dd></div>;
  return (
    <dl className="mt-2 grid gap-2 text-[12.5px] leading-5 text-ds-ink-2 md:grid-cols-2">
      {list("What the records show", r.facts)}
      <div><dt className="text-[12px] font-semibold text-ds-ink-2">Why it can matter</dt><dd>{r.mechanism}</dd></div>
      {list("Other explanations", r.alternatives)}
      {list("What would rule it out", r.disconfirming)}
      {list("Still unknown", r.missing)}
      <div><dt className="text-[12px] font-semibold text-ds-ink-2">Next check</dt><dd>{r.next_step}</dd></div>
    </dl>
  );
}

function ContractCard({ c, notify, showSupplier, onOpen }: { c: AtlasContract; notify: (m: string, e?: boolean) => void; showSupplier?: boolean; onOpen?: () => void }) {
  const [open, setOpen] = useState(false);
  const reason = c.reasons[0];
  return (
    <li className="rounded-[10px] border border-ds-border bg-white p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[14px] font-semibold text-ds-ink">{showSupplier
            ? <button className="underline decoration-ds-border-strong underline-offset-2" onClick={onOpen}>{c.supplier}</button>
            : <button className="underline decoration-ds-border-strong underline-offset-2" onClick={onOpen}>{c.customer}</button>}</p>
          <p className="text-[13px] text-ds-ink-2">{c.title}</p>
          <p className="mt-0.5 text-[12px] text-ds-muted">{[c.scope.label, c.route.code !== "direct_award" ? c.route.label : "", c.region || c.nation,
            c.value ? `${c.value.label} ${money(c.value.amount)}${c.value.annual_estimate ? ` (about ${money(c.value.annual_estimate)} a year)` : ""}` : "Value not published"].filter(Boolean).join(" · ")}</p>
        </div>
        <Pill tone={STATUS_TONE[c.status.code] || "neutral"} title={c.status.detail}>{c.status.label}</Pill>
      </div>
      <div className="mt-1.5 flex flex-wrap gap-1">{c.services.map((s) => <Pill key={s.family}>{s.label}</Pill>)}</div>
      {reason && <p className="mt-2 text-[13px] text-ds-ink"><strong className="font-semibold">Worth investigating:</strong> {reason.title}.</p>}
      <div className="mt-2 flex flex-wrap items-center gap-2">
        {reason && <button className="ds-btn primary sm" onClick={() => void investigate(c, notify)}><Telescope size={13} /> Investigate {c.customer}</button>}
        <button className="ds-btn ghost sm" aria-expanded={open} onClick={() => setOpen(!open)}>{open ? "Hide" : "Show"} evidence and timeline</button>
        {c.sources[0] && safeUrl(c.sources[0].url) && <a className="inline-flex items-center gap-1 text-[12.5px] font-medium text-ds-ink underline decoration-ds-border-strong underline-offset-2"
          href={safeUrl(c.sources[0].url)!} target="_blank" rel="noopener noreferrer">Published notice<ArrowUpRight size={12} /></a>}
      </div>
      {open && <div className="mt-2 border-t border-ds-border pt-2">
        {reason && <ReasonDetail r={reason} />}
        <p className="mt-2 text-[12px] font-semibold text-ds-ink-2">Timeline</p>
        <ul className="mt-1 space-y-0.5 text-[12.5px] text-ds-ink-2">{c.timeline.map((t, i) => <li key={i}><span className="si-mono text-ds-muted">{t.date}</span> {t.event} <span className="text-ds-muted">({t.basis})</span></li>)}</ul>
        <p className="mt-2 text-[12px] text-ds-muted">Supplier as published: {c.supplier_name_seen} · {c.match.label}.{c.value ? ` ${c.value.basis}` : ""}</p>
        {!!c.checks.length && <ul className="mt-1 text-[12px] text-ds-amber">{c.checks.map((x) => <li key={x}>{x}</li>)}</ul>}
      </div>}
    </li>
  );
}

function RelationshipCard({ r, onContractor, onCustomer }: { r: Relationship; onContractor?: (id: number) => void; onCustomer?: (key: string) => void }) {
  const href = safeUrl(r.source.url);
  return (
    <li className="rounded-[10px] border border-ds-border bg-white p-3">
      <p className="flex flex-wrap items-center gap-2 text-[14px] font-semibold text-ds-ink">
        {onCustomer ? <button className="underline decoration-ds-border-strong underline-offset-2" onClick={() => onCustomer(r.customer_key)}>{r.customer}</button>
          : r.contractor_id && onContractor ? <button className="underline decoration-ds-border-strong underline-offset-2" onClick={() => onContractor(r.contractor_id!)}>{r.supplier}</button> : r.supplier}
        <Pill tone="violet">{KIND_LABEL[r.kind] || r.kind}{r.intermediary ? ` via ${r.intermediary}` : ""}</Pill>
        {r.currency === "historical" && <Pill>Historical</Pill>}
      </p>
      <blockquote className="mt-1.5 border-l-2 border-ds-border-strong pl-3 text-[13px] italic leading-5 text-ds-ink-2">“{r.quote}”</blockquote>
      <p className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[12px] text-ds-muted">
        {r.quote_verified ? <Pill tone="green"><BadgeCheck size={12} aria-hidden="true" /> Quote found on the page</Pill> : <Pill tone="amber">Quote not found word for word on the page</Pill>}
        {href ? <a className="inline-flex items-center gap-1 font-medium text-ds-ink underline decoration-ds-border-strong underline-offset-2" href={href} target="_blank" rel="noopener noreferrer">{SOURCE_LABEL[r.source.type] || "Source"}<ArrowUpRight size={11} /></a> : SOURCE_LABEL[r.source.type]}
        {r.published_on ? <span>published {r.published_on}</span> : <span>publication date not shown</span>}
        {r.sites_mentioned && <span>· {r.sites_mentioned}</span>}
      </p>
      {!!r.services.length && <div className="mt-1 flex flex-wrap gap-1">{r.services.map((s) => <Pill key={s.family}>{s.label}</Pill>)}</div>}
      <p className="mt-1.5 text-[12px] text-ds-muted">{r.caveat}</p>
    </li>
  );
}

function ResearchControl({ body, research, label, notify, onDone }: { body: Record<string, unknown>; research: Research; label: string; notify: (m: string, e?: boolean) => void; onDone: () => void }) {
  const [job, setJob] = useJob(null, onDone);
  const key = useRef(newKey());
  async function start() {
    try { setJob(await si<JobT>("/atlas/research", { method: "POST", json: body, headers: { "Idempotency-Key": key.current } })); key.current = newKey(); }
    catch (e) { notify((e as Error).message, true); }
  }
  return (
    <div className="space-y-2">
      {job ? <JobStatus job={job} /> : <button className="ds-btn sm" onClick={() => void start()}><Search size={13} /> {label}</button>}
      {research && !job && <p className="text-[12px] text-ds-muted">Last researched {research.when}: {research.result.message || research.status}
        {research.result.sources_reviewed ? ` · ${research.result.sources_reviewed} pages reviewed` : ""}{research.cost_cents ? ` · $${(research.cost_cents / 100).toFixed(2)}` : ""}</p>}
      {research?.result.not_found?.length ? <p className="text-[12px] text-ds-muted">Not found: {research.result.not_found.join("; ")}</p> : null}
      <p className="text-[12px] text-ds-muted">Uses live web research within your research budget. Private contracts are rarely published, so finding nothing is a common and honest answer.</p>
    </div>
  );
}

function Section({ title, detail, children, label }: { title: string; detail?: string; children: ReactNode; label?: string }) {
  return (
    <section aria-label={label || title} className="ds-card p-4">
      <h3 className="text-[14px] font-semibold text-ds-ink">{title}</h3>
      {detail && <p className="mt-0.5 text-[12.5px] text-ds-muted">{detail}</p>}
      <div className="mt-3">{children}</div>
    </section>
  );
}

export function ContractorRecord({ id, notify, onCustomer }: { id: number; notify: (m: string, e?: boolean) => void; onCustomer: (key: string) => void }) {
  const [c, setC] = useState<Contractor | null>(null);
  const load = useCallback(() => si<Contractor>(`/atlas/contractors/${id}`).then(setC).catch((e) => notify((e as Error).message, true)), [id, notify]);
  useEffect(() => { void load(); }, [load]);
  if (!c) return <div className="ds-skeleton h-96 rounded-xl" />;
  const live = c.contracts.filter((x) => ["in_term", "end_approaching", "extension_possible"].includes(x.status.code)).length;
  const others = c.contracts.filter((x) => !c.worth_investigating.some((w) => w.key === x.key));
  return (
    <article aria-label={`Contractor ${c.name}`} className="space-y-4">
      <header className="ds-card p-5">
        <p className="si-eyebrow">Contractor</p>
        <h2 className="mt-1 text-[24px] font-semibold leading-tight tracking-[-0.02em] text-ds-ink">{c.name}</h2>
        <p className="mt-1 flex flex-wrap items-center gap-2 text-[13px] text-ds-ink-2">
          {c.identity.company_number ? <Pill tone="green"><ShieldCheck size={12} aria-hidden="true" /> Companies House {c.identity.company_number}</Pill> : <Pill>Name only</Pill>}
          <span className="text-ds-muted">{c.identity.basis_label}</span></p>
        {c.identity.group && <p className="mt-1.5 text-[12.5px] text-ds-ink-2"><Link2 size={12} className="mr-1 inline" aria-hidden="true" />Controlled by {c.identity.group.parent_name}
          {c.identity.group.parent_number ? ` (${c.identity.group.parent_number})` : ""}. <span className="text-ds-muted">{c.identity.group.note}</span></p>}
        {c.identity.conflicts.map((x) => <p key={x.names.join()} role="note" className="mt-2 rounded-lg border border-ds-amber-line bg-ds-amber-soft px-3 py-2 text-[12.5px] text-ds-ink-2">
          <AlertTriangle size={13} className="mr-1 inline text-ds-amber" aria-hidden="true" />{x.note} {x.names.join(" · ")}{x.company_numbers.length ? ` (${x.company_numbers.join(", ")})` : ""}</p>)}
        {c.yours && <p className="mt-2 text-[13px] font-medium text-ds-green">This is your own company: its contracts are not shown as opportunities.</p>}
        <dl className="mt-3 grid grid-cols-2 gap-3 text-[13px] sm:grid-cols-4">
          {[["Published contracts", c.contracts.length], ["In term", live], ["Worth investigating", c.worth_investigating.length], ["Reported customers", c.relationships.length]].map(([k, v]) =>
            <div key={k as string}><dt className="text-[12px] text-ds-muted">{k}</dt><dd className="si-mono text-[18px] text-ds-ink">{v}</dd></div>)}
        </dl>
        {!!c.services.length && <div className="mt-3 flex flex-wrap gap-1">{c.services.map((s) => <Pill key={s.family}>{s.label} · {s.contracts}</Pill>)}</div>}
      </header>
      {!!c.worth_investigating.length && <Section title="Worth investigating" detail="Contracts in your services and territory where a published date gives a reason to engage. Never a probability: each says what would rule it out.">
        <ul className="space-y-2">{c.worth_investigating.map((x) => <ContractCard key={x.key} c={x} notify={notify} onOpen={() => onCustomer(x.customer_key)} />)}</ul></Section>}
      <Section title="Published contracts" detail="Awarded by the buyer and published on Find a Tender, Contracts Finder or Public Contracts Scotland.">
        {!others.length ? <p className="text-[13px] text-ds-muted">No other published contracts.</p>
          : <ul className="space-y-2">{others.map((x) => <ContractCard key={x.key} c={x} notify={notify} onOpen={() => onCustomer(x.customer_key)} />)}</ul>}
      </Section>
      <Section title="Reported by public sources" label="Reported customers" detail="Customers named in this contractor's case studies, customer pages, press releases and FM announcements. Contract terms are not published.">
        {!c.relationships.length ? <p className="mb-3 text-[13px] text-ds-muted">None recorded yet.</p>
          : <ul className="mb-3 space-y-2">{c.relationships.map((r) => <RelationshipCard key={r.id} r={r} onCustomer={onCustomer} />)}</ul>}
        {c.unsupported_relationships > 0 && <p className="mb-2 text-[12px] text-ds-muted">{c.unsupported_relationships} claim{c.unsupported_relationships === 1 ? " was" : "s were"} not supported by the pages retrieved and {c.unsupported_relationships === 1 ? "is" : "are"} not shown.</p>}
        <ResearchControl body={{ direction: "contractor", subject: c.name, contractor_id: c.id }} research={c.research} label="Research published customers" notify={notify} onDone={() => void load()} />
      </Section>
      <Section title="What this covers, and what it does not">
        <ul className="space-y-1 text-[12.5px] text-ds-ink-2">{Object.values(c.coverage).map((x) => <li key={x} className="flex gap-2"><CircleHelp size={13} className="mt-0.5 flex-none text-ds-muted" aria-hidden="true" />{x}</li>)}</ul>
        {c.identity.aliases.length > 1 && <p className="mt-2 text-[12px] text-ds-muted">Published as: {c.identity.aliases.map((a) => a.name).join(" · ")}</p>}
      </Section>
    </article>
  );
}

export function CustomerRecord({ customerKey, notify, onContractor, compact }: { customerKey: string; notify: (m: string, e?: boolean) => void; onContractor: (id: number) => void; compact?: boolean }) {
  const [c, setC] = useState<Customer | null>(null);
  const load = useCallback(() => si<Customer>(`/atlas/customers/${encodeURIComponent(customerKey)}`).then(setC).catch((e) => notify((e as Error).message, true)), [customerKey, notify]);
  useEffect(() => { void load(); }, [load]);
  if (!c) return <div className="ds-skeleton h-72 rounded-xl" />;
  const tone: Tone = c.incumbent.state === "published" ? "green" : c.incumbent.state === "reported" ? "blue" : "neutral";
  return (
    <article aria-label={`Customer ${c.name}`} className="space-y-4">
      <header className="ds-card p-5">
        <p className="si-eyebrow">Customer</p>
        <h2 className="mt-1 text-[24px] font-semibold leading-tight tracking-[-0.02em] text-ds-ink">{c.name}</h2>
        <p className="mt-2"><Pill tone={tone}>{c.incumbent.label}</Pill></p>
        <p className="mt-2 text-[12.5px] text-ds-muted">{c.coverage}</p>
      </header>
      <Section title="Published contracts" detail="Who the buyer named as supplier, with the published term.">
        {!c.contracts.length ? <p className="text-[13px] text-ds-muted">None published in the sources collected.</p>
          : <ul className="space-y-2">{c.contracts.slice(0, compact ? 4 : 50).map((x) => <ContractCard key={x.key} c={x} notify={notify} showSupplier onOpen={() => x.contractor_id && onContractor(x.contractor_id)} />)}</ul>}
      </Section>
      <Section title="Reported by public sources" label="Reported suppliers" detail="Suppliers named by case studies, press releases and announcements.">
        {!c.relationships.length ? <p className="mb-3 text-[13px] text-ds-muted">None recorded yet.</p>
          : <ul className="mb-3 space-y-2">{c.relationships.map((r) => <RelationshipCard key={r.id} r={r} onContractor={onContractor} />)}</ul>}
        <ResearchControl body={{ direction: "customer", subject: c.name }} research={c.research} label="Research who supplies them" notify={notify} onDone={() => void load()} />
      </Section>
      {!!c.signals.length && <Section title="Signals from Shadow Radar" detail="Indirect evidence about the same organisation. It suggests a change; it does not prove one.">
        <ul className="space-y-2">{c.signals.map((r) => <li key={r.title} className="rounded-[10px] border border-ds-border bg-white p-3"><p className="text-[13px] font-semibold text-ds-ink">{r.title}</p><ReasonDetail r={r} /></li>)}</ul>
      </Section>}
    </article>
  );
}

/** For the Account workspace: who supplies this account, by its exact name. */
export function AccountSuppliers({ accountId }: { accountId: number }) {
  const [c, setC] = useState<Customer | null>(null);
  useEffect(() => { si<Customer>(`/atlas/account/${accountId}`).then(setC).catch(() => setC(null)); }, [accountId]);
  if (!c) return null;
  const suppliers = [...new Set([...c.contracts.filter((x) => x.status.code !== "historical").map((x) => x.supplier), ...c.relationships.map((r) => r.supplier)])];
  return (
    <section aria-label="Who supplies them" className="ds-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="text-[14px] font-semibold text-ds-ink">Who supplies them</h3>
        <button className="text-[12.5px] font-semibold text-ds-brand hover:underline" onClick={() => goto("find", { mode: "atlas", customer: c.key })}>Open in Contract Atlas</button></div>
      <p className="mt-1.5"><Pill tone={c.incumbent.state === "published" ? "green" : c.incumbent.state === "reported" ? "blue" : "neutral"}>{c.incumbent.label}</Pill></p>
      {suppliers.some((s) => !c.incumbent.label.includes(s)) && <p className="mt-1.5 text-[12.5px] text-ds-ink-2">Also named: {suppliers.filter((s) => !c.incumbent.label.includes(s)).slice(0, 5).join(" · ")}</p>}
      {!suppliers.length && <p className="mt-1.5 text-[12.5px] text-ds-muted">Nothing published names a current supplier. Research it from Contract Atlas, within your research budget.</p>}
    </section>
  );
}
