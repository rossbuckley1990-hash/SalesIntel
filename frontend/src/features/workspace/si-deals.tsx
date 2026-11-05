"use client";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, ArrowRight, ArrowUpRight, Briefcase, Calculator, CheckCircle2, ClipboardList, Package, Trophy, XCircle } from "lucide-react";
import { EmptyState, Pill } from "./ds";
import { safeUrl } from "./radar-model";
import { SERVICES, SERVICE_NAME, STAGE_LABEL, goto, param, pounds, si, type DealCard, type DealT } from "./si-api";
import { ActivityForm, Basis, PageHeader, Panel, TaskRow, Timeline, useUrl } from "./si-shared";
import { WinAssessment } from "./si-assessment";
import type { SharedProps } from "./types";
import { ResultsView } from "./si-intel";

const money = pounds;
const OPEN = ["qualify", "engage", "survey", "proposal", "bid_review", "negotiation", "approval"];

export function SiDeals(props: SharedProps) {
  useUrl();
  const id = Number(param("deal"));
  return id > 0 ? <DealRecordView key={id} id={id} {...props} /> : <Board {...props} />;
}

const DAY_MS = 86400000;
const ageOf = (iso: string) => Math.max(0, Math.floor((Date.now() - Date.parse(iso)) / DAY_MS));
const QUIET_AFTER = 14;

/** A pipeline you can drag. Stage rules stay on the server: a move it refuses is undone and its reason shown. */
function Board({ notify }: SharedProps) {
  const [items, setItems] = useState<DealCard[] | null>(null);
  const [dragging, setDragging] = useState<number | null>(null);
  const [over, setOver] = useState<string | null>(null);
  const [moved, setMoved] = useState<number | null>(null);
  const [closing, setClosing] = useState<{ deal: DealCard; stage: "won" | "lost" } | null>(null);
  const [reason, setReason] = useState("");
  const [tab, setTab] = useState<"pipeline" | "results">(param("tab") === "results" ? "results" : "pipeline");
  const load = useCallback(async () => {
    try { setItems((await si<{ items: DealCard[] }>("/deals")).items); } catch (e) { notify((e as Error).message, true); }
  }, [notify]);
  useEffect(() => { void load(); }, [load]);

  async function move(deal: DealCard, stage: string, why = "") {
    if (deal.stage === stage) return;
    if ((stage === "won" || stage === "lost") && !why.trim()) { setClosing({ deal, stage }); setReason(""); return; }
    const before = items;
    setItems((xs) => xs && xs.map((x) => (x.id === deal.id ? { ...x, stage, updated_at: new Date().toISOString() } : x)));
    setMoved(deal.id);
    try {
      await si(`/deals/${deal.id}`, { method: "PATCH", json: { stage, ...(why ? { reason: why } : {}) } });
      notify(stage === "won" ? `${deal.title} marked won. Handover recorded.` : stage === "lost" ? `${deal.title} marked lost.` : `${deal.title} moved to ${STAGE_LABEL[stage]}.`);
      setClosing(null);
      void load();
    } catch (e) { setItems(before); notify((e as Error).message, true); }
  }
  const drop = (stage: string) => (e: React.DragEvent) => {
    e.preventDefault(); setOver(null);
    const deal = items?.find((d) => d.id === Number(e.dataTransfer.getData("text/plain")));
    if (deal) void move(deal, stage);
  };
  const target = (stage: string) => ({
    onDragOver: (e: React.DragEvent) => { if (dragging !== null) { e.preventDefault(); e.dataTransfer.dropEffect = "move"; if (over !== stage) setOver(stage); } },
    onDragLeave: (e: React.DragEvent) => { if (!(e.currentTarget as HTMLElement).contains(e.relatedTarget as Node)) setOver((o) => (o === stage ? null : o)); },
    onDrop: drop(stage),
  });

  const open = (items || []).filter((d) => OPEN.includes(d.stage));
  const closed = (items || []).filter((d) => !OPEN.includes(d.stage));
  const priced = open.filter((d) => d.value_total !== null);
  const total = priced.reduce((sum, d) => sum + Number(d.value_total), 0);
  return (
    <div className="ds-root space-y-5">
      <PageHeader eyebrow="Pipeline" title="Deals" actions={items && !!open.length ? <div className="text-right">
        <p className="si-mono text-[22px] leading-none text-ds-ink">{priced.length ? money(total) : "—"}</p>
        <p className="mt-1 text-[12px] text-ds-muted">Total contract value of {priced.length} priced of {open.length} open deal{open.length === 1 ? "" : "s"}</p></div> : undefined}>
        Drag a deal to move it on. Stage rules still apply: approval needs a quotation, and won needs an approved one.
      </PageHeader>
      <div className="ds-tabs w-fit" role="group" aria-label="Deals view">
        <button aria-pressed={tab === "pipeline"} onClick={() => setTab("pipeline")}>Pipeline</button>
        <button aria-pressed={tab === "results"} onClick={() => setTab("results")}>Results from discovery</button>
      </div>
      {tab === "results" && <ResultsView />}
      {tab === "pipeline" && <>
      {!items && <div className="ds-skeleton h-72 rounded-xl" />}
      {items && !items.length && <div className="ds-card"><EmptyState icon={<Briefcase size={20} />} title="No deals yet" action={<button className="ds-btn primary" onClick={() => goto("clients")}>Open Accounts</button>}>Qualify an account into a deal once you have confirmed what the customer needs.</EmptyState></div>}
      {items && !!items.length && <>
        <div className="si-board" role="list" aria-label="Pipeline by stage">
          {OPEN.map((stage) => {
            const cards = items.filter((d) => d.stage === stage);
            const stagePriced = cards.filter((d) => d.value_total !== null);
            return (
              <section key={stage} role="listitem" aria-label={STAGE_LABEL[stage]} className={`si-col ${over === stage ? "over" : ""}`} {...target(stage)}>
                <div className="si-col-head"><h2>{STAGE_LABEL[stage]}</h2><span className="n">{cards.length}</span></div>
                <p className="si-col-sum">{stagePriced.length ? <>{money(stagePriced.reduce((s, d) => s + Number(d.value_total), 0))} <small>TCV{stagePriced.length < cards.length ? `, ${cards.length - stagePriced.length} unpriced` : ""}</small></> : cards.length ? <small>Not priced yet</small> : ""}</p>
                <ul>{cards.map((d) => {
                  const age = ageOf(d.updated_at);
                  return (
                    <li key={d.id} className={`si-deal ${dragging === d.id ? "dragging" : ""} ${moved === d.id ? "moved" : ""}`} draggable
                      onDragStart={(e) => { e.dataTransfer.setData("text/plain", String(d.id)); e.dataTransfer.effectAllowed = "move"; setDragging(d.id); }}
                      onDragEnd={() => { setDragging(null); setOver(null); }}>
                      <button className="block w-full text-left" onClick={() => goto("deals", { deal: d.id })}>
                        <span className="t">{d.title}</span><span className="a">{d.account}</span>
                        {d.next_step && <span className="mt-1.5 line-clamp-2 block text-[12px] leading-[17px] text-ds-ink-2">Next: {d.next_step}</span>}
                      </button>
                      <span className="f">
                        <span>{d.value_total !== null ? money(d.value_total) : d.value_annual !== null ? `${money(d.value_annual)}/yr` : "Unpriced"}</span>
                        <span className={age >= QUIET_AFTER ? "quiet" : ""} title={`Last updated ${age} day${age === 1 ? "" : "s"} ago`}>{age >= QUIET_AFTER ? `quiet ${age}d` : `${age}d`}</span>
                      </span>
                      <label className="mt-2 flex items-center gap-1.5 text-[11.5px] text-ds-muted"><span className="sr-only">Move {d.title} to</span>
                        <select className="!h-7 flex-1 cursor-pointer rounded-[6px] border border-transparent bg-[#f7f6f3] !py-0 !pl-2 !pr-6 text-[12px] text-ds-ink-2 hover:border-ds-border" value={d.stage} onChange={(e) => void move(d, e.target.value)}>
                          {[...OPEN, "won", "lost"].map((st) => <option key={st} value={st}>{st === d.stage ? `In ${STAGE_LABEL[st]}` : `Move to ${STAGE_LABEL[st]}`}</option>)}</select></label>
                    </li>
                  );
                })}</ul>
              </section>
            );
          })}
        </div>
        {dragging !== null && <div className="si-drop-close" aria-hidden="true">
          <div className={over === "won" ? "over" : ""} {...target("won")}><Trophy size={15} /> Drop to mark won</div>
          <div className={over === "lost" ? "over" : ""} {...target("lost")}><XCircle size={15} /> Drop to mark lost</div>
        </div>}
        {closing && <form className="ds-card space-y-3 p-4" aria-label={`Mark ${closing.deal.title} ${closing.stage}`} onSubmit={(e) => { e.preventDefault(); void move(closing.deal, closing.stage, reason); }}>
          <p className="text-[14px] font-semibold text-ds-ink">{closing.stage === "won" ? "Why did we win" : "Why did we lose"} {closing.deal.title}?</p>
          <textarea className="w-full rounded-lg border border-ds-border-strong p-2.5 text-[14px]" rows={2} aria-label={closing.stage === "won" ? "Why did we win?" : "Why did we lose?"} value={reason} onChange={(e) => setReason(e.target.value)} required autoFocus />
          <div className="flex gap-2"><button className="ds-btn primary" disabled={!reason.trim()}>{closing.stage === "won" ? "Mark won" : "Mark lost"}</button><button type="button" className="ds-btn ghost" onClick={() => setClosing(null)}>Cancel</button></div>
        </form>}
        {!!closed.length && <Panel title="Closed"><ul className="divide-y divide-ds-border">{closed.map((d) => <li key={d.id}><button className="flex w-full items-center justify-between gap-2 py-2 text-left" onClick={() => goto("deals", { deal: d.id })}>
          <span className="text-[13px] font-semibold text-ds-ink">{d.title} <span className="font-normal text-ds-muted">· {d.account}</span></span><Pill tone={d.stage === "won" ? "green" : "neutral"}>{STAGE_LABEL[d.stage]}</Pill></button></li>)}</ul></Panel>}
      </>}
      </>}
    </div>
  );
}

function DealRecordView({ id, notify }: SharedProps & { id: number }) {
  const [d, setD] = useState<DealT | null>(null);
  const [scope, setScope] = useState<Record<string, { value: string; basis: string }>>({});
  const [rates, setRates] = useState<Record<string, string>>({});
  const [reviewer, setReviewer] = useState("");
  const [closing, setClosing] = useState<"" | "won" | "lost">("");
  const [reason, setReason] = useState("");
  const load = useCallback(async () => {
    const deal = await si<DealT>(`/deals/${id}`);
    setD(deal);
    setScope(Object.fromEntries(deal.scope.map((s) => [`${s.service}.${s.field}`, { value: s.value === null ? "" : String(s.value), basis: s.basis || "customer_stated" }])));
    setRates(Object.fromEntries(Object.entries(deal.quote?.rates || {}).map(([k, v]) => [k, String(v)])));
  }, [id]);
  useEffect(() => { load().catch((e) => notify(e.message, true)); }, [load, notify]);
  if (!d) return <div className="ds-root space-y-3"><div className="ds-skeleton h-24 rounded-xl" /><div className="ds-skeleton h-72 rounded-xl" /></div>;
  const won = d.stage === "won";

  async function patch(json: Record<string, unknown>, done?: string) {
    try { setD(await si<DealT>(`/deals/${id}`, { method: "PATCH", json })); if (done) notify(done); return true; } catch (e) { notify((e as Error).message, true); return false; }
  }
  async function saveScope() {
    const entries = Object.entries(scope).map(([k, v]) => { const [service, field] = k.split("."); return { service, field, value: v.value === "" ? null : v.value, basis: v.value === "" ? null : v.basis }; });
    try { setD(await si<DealT>(`/deals/${id}/scope`, { method: "PUT", json: { entries } })); notify("Scope saved."); } catch (e) { notify((e as Error).message, true); }
  }
  async function buildQuote() {
    await saveScope();
    // Rates go to the server exactly as typed; it validates them as decimals.
    const entered = Object.fromEntries(Object.entries(rates).filter(([, v]) => v.trim() !== "").map(([k, v]) => [k, v.trim()]));
    try { setD(await si<DealT>(`/deals/${id}/quote`, { method: "POST", json: { rates: entered } })); notify("Quotation draft updated."); } catch (e) { notify((e as Error).message, true); }
  }
  async function approveQuote() {
    try { setD(await si<DealT>(`/deals/${id}/quote/approve`, { method: "POST", json: { reviewer } })); notify("Quotation approved for issue."); } catch (e) { notify((e as Error).message, true); }
  }
  const index = d.stages.indexOf(d.stage);
  const next = OPEN.includes(d.stage) ? OPEN[index + 1] : null;
  const origin = d.origin || {};
  const handover = d.handover as { captured_at?: string; contacts?: { name: string | null; role: string; email: string | null; phone: string | null }[]; requirements?: string[]; commitments?: string[]; still_unconfirmed?: string[] };

  return (
    <div className="ds-root space-y-5">
      <button className="ds-btn ghost sm -ml-2" onClick={() => goto("deals")}><ArrowLeft size={14} /> Deals</button>
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <button className="text-[13px] font-semibold text-ds-brand hover:underline" onClick={() => goto("clients", { account: d.account_id })}>{d.account}</button>
          <h1 className="mt-0.5 text-[24px] font-semibold leading-tight tracking-[-0.02em] text-ds-ink">{d.title}</h1>
          <p className="mt-1 flex flex-wrap items-center gap-2 text-[13px] text-ds-muted">Value: <strong className="text-ds-ink">{d.value_total !== null ? money(d.value_total) : d.value_annual !== null ? `${money(d.value_annual)} a year` : "Unknown"}</strong> <Basis basis={d.value_basis} /></p>
        </div>
        {d.stage === "won" ? <Pill tone="green">Won</Pill> : d.stage === "lost" ? <Pill>Lost</Pill> : <div className="flex flex-wrap gap-2">
          {next && <button className="ds-btn primary" onClick={() => void patch({ stage: next }, `Moved to ${STAGE_LABEL[next]}.`)}>Move to {STAGE_LABEL[next]} <ArrowRight size={15} /></button>}
          <button className="ds-btn" onClick={() => setClosing("won")}><Trophy size={15} /> Won</button>
          <button className="ds-btn ghost" onClick={() => setClosing("lost")}><XCircle size={15} /> Lost</button>
        </div>}
      </header>

      <ol className="flex flex-wrap gap-1" aria-label="Stage">{OPEN.map((s, i) => <li key={s} className={`rounded-full px-3 py-1 text-[12px] font-semibold ${s === d.stage ? "bg-ds-brand text-white" : i < index || d.stage === "won" ? "bg-ds-brand-soft text-ds-brand" : "bg-ds-subtle text-ds-muted"}`}>{STAGE_LABEL[s]}</li>)}</ol>

      {closing && <form className="ds-card space-y-2 p-4" onSubmit={async (e) => { e.preventDefault(); if (await patch({ stage: closing, reason }, closing === "won" ? "Marked won. Handover recorded." : "Marked lost.")) { setClosing(""); setReason(""); } }}>
        <label className="block"><span className="ds-label">{closing === "won" ? "Why did we win?" : "Why did we lose?"}</span><textarea className="mt-1 w-full rounded-lg border border-ds-border-strong p-2.5 text-[14px]" rows={2} value={reason} onChange={(e) => setReason(e.target.value)} required /></label>
        {closing === "won" && d.quote?.status !== "approved" && <p className="text-[12px] text-ds-amber">The current quotation must be approved before a deal can be marked won.</p>}
        <div className="flex gap-2"><button className="ds-btn primary">Confirm {closing}</button><button type="button" className="ds-btn ghost" onClick={() => setClosing("")}>Cancel</button></div>
      </form>}

      <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0 space-y-5">
          <Panel title={<span className="flex items-center gap-2"><ClipboardList size={15} className="text-ds-muted" /> Scope</span>} action={!won && <button className="ds-btn sm" onClick={() => void saveScope()}>Save scope</button>}>
            {won && <p className="mb-3 text-[13px] text-ds-muted">Won and handed over. Scope and quotation are locked; record a change as a new deal.</p>}
            <fieldset disabled={won} className="contents">
            <div className="mb-3 flex flex-wrap gap-1.5">{SERVICES.map(([v, l]) => <button key={v} aria-pressed={d.services.includes(v)} onClick={() => void patch({ services: d.services.includes(v) ? d.services.filter((x) => x !== v) : [...d.services, v] })}
              className={`rounded-full border px-3 py-1 text-[12px] font-medium ${d.services.includes(v) ? "border-ds-brand bg-ds-brand-soft text-ds-brand" : "border-ds-border bg-white text-ds-ink-2"}`}>{l}</button>)}
              <select className="ds-select !h-8 text-[12px]" aria-label="Type of work" value={d.work_type} onChange={(e) => void patch({ work_type: e.target.value })}><option value="">Type of work</option>{Object.entries(d.work_types).map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
            <div className="overflow-x-auto"><table className="w-full min-w-[560px] text-[13px]"><thead><tr className="text-left text-[12px] text-ds-muted"><th className="pb-2 font-semibold">What we need to know</th><th className="pb-2 font-semibold">Answer</th><th className="pb-2 font-semibold">Basis</th></tr></thead>
              <tbody>{d.scope.map((s) => { const k = `${s.service}.${s.field}`; const v = scope[k] || { value: "", basis: "customer_stated" }; return <tr key={k} className="border-t border-ds-border">
                <td className="py-2 pr-3 text-ds-ink-2"><span className="text-[11px] font-semibold uppercase text-ds-muted">{s.service === "common" ? "All" : SERVICE_NAME[s.service]}</span><br />{s.question}</td>
                <td className="py-2 pr-3"><input aria-label={s.question} className="h-9 w-full rounded-md border border-ds-border-strong px-2" value={v.value} placeholder="Unknown" onChange={(e) => setScope({ ...scope, [k]: { ...v, value: e.target.value } })} /></td>
                <td className="py-2"><select aria-label={`Basis for ${s.question}`} className="h-9 rounded-md border border-ds-border-strong px-2" value={v.basis} onChange={(e) => setScope({ ...scope, [k]: { ...v, basis: e.target.value } })}><option value="surveyed">Surveyed</option><option value="customer_stated">Customer stated</option><option value="estimate">Estimate</option></select></td>
              </tr>; })}</tbody></table></div>
          </fieldset></Panel>

          <Panel title={<span className="flex items-center gap-2"><Calculator size={15} className="text-ds-muted" /> Quotation draft</span>} action={d.quote?.status && <Pill tone={d.quote.status === "approved" ? "green" : d.quote.status === "superseded" ? "red" : "amber"}>{d.quote.status === "approved" ? `Version ${d.quote.version} approved by ${d.quote.approved_by}` : d.quote.status === "superseded" ? "Approval superseded" : "Draft"}</Pill>}>
            <fieldset disabled={won} className="contents">
            {d.quote?.status === "superseded" && <p role="alert" className="mb-3 rounded-lg border border-ds-red-line bg-ds-red-soft px-3 py-2 text-[13px] text-ds-red">{d.quote.superseded_reason || "Inputs changed after approval."} Rebuild and approve the quotation again before this deal can be won.</p>}
            {!d.services.length ? <p className="text-[13px] text-ds-muted">Choose the services in scope first.</p> : <>
              <div className="grid gap-2 sm:grid-cols-2">{d.scope.filter((s) => s.service !== "common" && s.unit).map((s) => { const k = `${s.service}.${s.field}`; return <label key={k} className="block"><span className="ds-label">Rate per {s.unit} ({SERVICE_NAME[s.service]})</span>
                <input inputMode="decimal" className="mt-1 block h-9 w-full rounded-md border border-ds-border-strong px-2 text-[13px]" placeholder="£ not set" value={rates[k] || ""} onChange={(e) => setRates({ ...rates, [k]: e.target.value })} /></label>; })}</div>
              <button className="ds-btn mt-3" onClick={() => void buildQuote()}><Calculator size={15} /> Build quotation draft</button>
              {!!d.quote?.lines?.length && <div className="mt-4 overflow-x-auto"><table className="w-full min-w-[520px] text-[13px]"><thead><tr className="text-left text-[12px] text-ds-muted"><th className="pb-2 font-semibold">Line</th><th className="pb-2 text-right font-semibold">Qty</th><th className="pb-2 text-right font-semibold">Rate</th><th className="pb-2 text-right font-semibold">Total</th></tr></thead>
                <tbody>{d.quote.lines.map((l) => <tr key={l.key} className="border-t border-ds-border"><td className="py-2 pr-2 text-ds-ink-2">{l.description}{l.warning && <span className="block text-[12px] text-ds-amber">{l.warning}</span>}</td>
                  <td className="py-2 text-right">{l.quantity ?? "?"}</td><td className="py-2 text-right">{l.rate !== null ? money(l.rate) : "?"}</td><td className="py-2 text-right font-semibold">{l.total !== null ? money(l.total) : "?"}</td></tr>)}
                  <tr className="border-t-2 border-ds-border-strong"><td className="py-2 font-semibold" colSpan={3}>Total</td><td className="py-2 text-right font-semibold">{d.quote.subtotal !== null && d.quote.subtotal !== undefined ? money(d.quote.subtotal) : "Incomplete"}</td></tr></tbody></table></div>}
              {!!d.quote?.missing?.length && <div className="mt-3 rounded-lg border border-ds-amber-line bg-ds-amber-soft p-3"><p className="text-[13px] font-semibold text-ds-amber">Missing before approval</p><ul className="mt-1 list-disc pl-5 text-[12px] text-ds-ink-2">{d.quote.missing.map((m) => <li key={m}>{m}</li>)}</ul></div>}
              {d.quote?.terms_note && <p className="mt-2 text-[12px] text-ds-muted">{d.quote.terms_note}</p>}
              {!!d.quote?.approvals?.length && <details className="mt-3 text-[12px] text-ds-muted"><summary className="cursor-pointer font-semibold">Approval history ({d.quote.approvals.length})</summary>
                <ul className="mt-1 space-y-1">{d.quote.approvals.map((a) => <li key={a.version}>Version {a.version}: {pounds(a.subtotal)} approved by {a.reviewer}, {new Date(a.approved_at).toLocaleString("en-GB")}{a.superseded_at ? `; superseded: ${a.superseded_reason}` : ""}</li>)}</ul></details>}
              {d.quote?.status !== "approved" && !!d.quote?.lines && <div className="mt-3 flex flex-wrap items-end gap-2"><label><span className="ds-label">Approved by</span><input className="mt-1 block h-9 rounded-md border border-ds-border-strong px-2 text-[13px]" value={reviewer} onChange={(e) => setReviewer(e.target.value)} /></label>
                <button className="ds-btn primary" disabled={reviewer.trim().length < 2} onClick={() => void approveQuote()}><CheckCircle2 size={15} /> Approve quotation</button></div>}
            </>}
          </fieldset></Panel>

          {d.stage === "won" && handover.captured_at && <Panel title={<span className="flex items-center gap-2"><Package size={15} className="text-ds-green" /> Handover record</span>}>
            <p className="text-[13px] text-ds-ink-2">Captured {new Date(handover.captured_at).toLocaleString("en-GB")}. Won because: {d.outcome_reason}</p>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <div><p className="ds-label">Requirements heard</p><ul className="mt-1 list-disc pl-5 text-[13px]">{(handover.requirements || []).map((r) => <li key={r}>{r}</li>)}</ul></div>
              <div><p className="ds-label">Commitments made</p><ul className="mt-1 list-disc pl-5 text-[13px]">{(handover.commitments || []).map((r) => <li key={r}>{r}</li>)}</ul></div>
              <div><p className="ds-label">Contacts</p><ul className="mt-1 text-[13px]">{(handover.contacts || []).map((c, i) => <li key={i}>{c.name || c.role} {c.email || c.phone}</li>)}</ul></div>
              <div><p className="ds-label">Still to confirm</p><ul className="mt-1 list-disc pl-5 text-[13px] text-ds-amber">{(handover.still_unconfirmed || []).map((r) => <li key={r}>{r}</li>)}</ul></div>
            </div>
          </Panel>}

          <Panel title="Log an interaction"><ActivityForm accountId={d.account_id} dealId={d.id} notify={notify} onSaved={() => void load()} /></Panel>
          <Panel title="History"><Timeline items={d.activities} /></Panel>
        </div>
        <div className="space-y-5">
          <WinAssessment dealId={d.id} version={`${d.stage}|${d.quote?.status}|${d.quote?.version}|${d.activities.length}|${d.tasks.length}|${JSON.stringify(d.qualification)}`} notify={notify} />
          <Panel title="Qualification">
            <dl className="space-y-2 text-[13px]">{[["requirement", "Requirement"], ["decision_maker", "Decision maker"], ["timing", "Timing"], ["budget", "Budget"], ["incumbent", "Current provider"]].map(([k, l]) => <div key={k}>
              <dt className="text-[12px] text-ds-muted">{l}</dt><dd className={d.qualification[k] ? "text-ds-ink" : "text-ds-amber"}>{d.qualification[k] || "Not confirmed"}</dd></div>)}</dl>
          </Panel>
          <Panel title="Where it came from">
            {!origin.key ? <p className="text-[13px] text-ds-muted">Created from your own conversations.</p> : <>
              <p className="text-[14px] font-medium leading-6 text-ds-ink">{origin.why_now}</p>
              <ul className="mt-2 space-y-1">{(origin.evidence || []).map((e, i) => { const href = safeUrl(e.url); return <li key={i} className="text-[13px]">{href ? <a className="inline-flex items-center gap-1 font-medium text-ds-brand hover:underline" href={href} target="_blank" rel="noreferrer">{e.label}<ArrowUpRight size={12} /></a> : e.label}</li>; })}</ul>
              {origin.captured_at && <p className="mt-2 text-[12px] text-ds-muted">Evidence kept as it was on {new Date(origin.captured_at).toLocaleDateString("en-GB")}.</p>}
              {origin.dossier && <p className="mt-2 rounded-lg bg-ds-canvas px-3 py-2 text-[13px] text-ds-ink-2" aria-label="Investigation carried into this deal">
                Investigation version {origin.dossier.version}: {origin.dossier.verdict === "weakened" ? "evidence was found against the original hypothesis" : origin.dossier.verdict === "strengthened" ? "the evidence supports the original hypothesis" : "the hypothesis was not settled"}. {origin.dossier.findings.length} sourced finding(s) kept.</p>}
            </>}
          </Panel>
          <Panel title="Follow-ups">{!d.tasks.length ? <p className="text-[13px] text-ds-muted">None for this deal.</p> : <ul className="divide-y divide-ds-border">{d.tasks.map((t) => <TaskRow key={t.id} t={t} onDone={async () => { await si(`/tasks/${t.id}/complete`, { method: "POST" }); void load(); }} />)}</ul>}</Panel>
        </div>
      </div>
    </div>
  );
}
