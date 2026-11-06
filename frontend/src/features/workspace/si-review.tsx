"use client";
/**
 * Blind opportunity review, and the controls to run it.
 *
 * A reviewer sees one item at a time, exactly as its source records describe it. They never see which method found it,
 * its rank or SalesIntel's reasons, and they record their own judgement.
 *
 * Whoever runs the evaluation (an administrator) works through these steps:
 * 1. Send each salesperson an offline review pack.
 * 2. Import their answers.
 * 3. Adjudicate every disagreement, with a recorded method and reason.
 * 4. Lock the review.
 * 5. Reveal the private key, which the server accepts only if it matches the published commitment.
 *
 * The server refuses to show results before that, whatever this screen does.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, ArrowRight, ArrowUpRight, Check, Download, EyeOff, Lock, ShieldCheck, Upload } from "lucide-react";
import { getApiBaseUrl } from "@/lib/api";
import { authHeaders } from "@/lib/session";
import { Pill } from "./ds";
import { safeUrl } from "./radar-model";
import { si } from "./si-api";

type Fact = { text: string; date: string; url: string; basis: string };
type Item = { id: string; organisation: string; site: string | null; location: string | null; title: string; record_type: string; facts: Fact[] };
type Question = { key: string; question: string; options: [string, string][] };
type Mine = Record<string, { answers: Record<string, string>; minutes: number | null; note: string }>;
type SetT = { set_key: string; as_of: string; rubric: Question[]; items: Item[]; instructions: string; mine: Mine; progress: { done: number; total: number };
  state: "open" | "locked" | "revealed"; fingerprint: string };
type Dis = { item_id: string; question: string; answers: Record<string, string>; reviewers: string[] };
type Ruling = { item_id: string; question: string; answer: string; method: string; adjudicator: string; rationale: string };
type Agree = Record<string, { items: number; percent_agreement: number | null; kappa: number | null }>;
type StatusT = { items: number; reviews: number; reviewers: number; items_with_two_reviews: number; missing: string[]; disagreements: Dis[]; pending: Dis[];
  adjudicated: number; complete: boolean; agreement: Agree; state: "open" | "locked" | "revealed"; ready_to_lock: boolean; fingerprint: string; rulings: Ruling[] };
type Rate = { hits: number; n: number; rate: number | null; interval: number[] | null };
type Arm = { label: string; n: number; pool: number; frame: number; relevant: Rate; relevant_or_possible: Rate; actionable: Rate; worth_investigating: Rate; noise: Rate;
  route_available: number | null; identity_correct: number | null; minutes_per_item: number | null; objective: { median_evidence_age_days: number | null } };
type Comparison = { family: string; arms: [string, string]; measure: string; difference: number | null; adjusted_interval: number[] | null; supported: boolean; overlap: number };
type Share = { n: number; score: number; rate: number | null; interval: number[] | null };
type DiagnosisT = { registered: string; purpose: string; measures: { otherwise_missed: string; chain: string }; statistics: string; rule: string;
  steps: { key: string; label: string }[]; otherwise_missed: Record<string, Record<"relevant" | "relevant_or_possible", Share & { label: string }>>;
  chain: Record<string, { n: number; steps: (Share & { key: string; label: string; drop: number | null })[] }> };
export type ResultsT = { items: number; reviewers: number; reviews: number; arms: Record<string, Arm>; comparisons: Comparison[]; verdicts: string[];
  exploratory: { rule: string; worth_investigating: Rate; met: boolean }; agreement: Agree;
  disagreements: { item_id: string; questions: { question: string; answers: Record<string, string>; final: string; method: string; adjudicator: string; rationale: string }[] }[];
  missed_by_qualified: string[]; missed_by_salesintel: string[]; note: string; statistics: string; diagnosis?: DiagnosisT };

const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${Math.round(v * 100)}%`);
const MEASURE: Record<string, string> = { relevant: "Genuine opportunity", actionable: "Worth pursuing this week or month", worth_investigating: "Worth investigating",
  noise: "Noise (not relevant, or not worth pursuing)", relevant_or_possible: "Genuine or possible" };
const METHOD: Record<string, string> = { consensus: "Consensus of the reviewers", third_reviewer: "An independent third reviewer" };

async function readJson(file: File): Promise<unknown> { return JSON.parse(await file.text()); }

export function SiReview({ notify, admin }: { notify: (m: string, e?: boolean) => void; admin: boolean }) {
  const [sets, setSets] = useState<string[] | null>(null);
  const [data, setData] = useState<SetT | null>(null);
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [minutes, setMinutes] = useState("");
  const [note, setNote] = useState("");
  const load = useCallback(async (key: string, jump = false) => {
    const d = await si<SetT>(`/review/${key}`);
    setData(d);
    if (jump) setIndex(Math.max(0, d.items.findIndex((i) => !d.mine[i.id])));
  }, []);
  useEffect(() => { si<{ items: string[] }>("/review").then((r) => { setSets(r.items); if (r.items[0]) void load(r.items[0], true); }).catch((e) => notify((e as Error).message, true)); }, [load, notify]);
  const item = data?.items[index];
  useEffect(() => {
    if (!data || !item) return;
    const mine = data.mine[item.id];
    setAnswers(mine?.answers || {}); setMinutes(mine?.minutes != null ? String(mine.minutes) : ""); setNote(mine?.note || "");
  }, [data, item]);
  const complete = useMemo(() => data ? data.rubric.every((q) => answers[q.key]) : false, [data, answers]);
  const closed = data?.state !== "open";

  async function save() {
    if (!data || !item) return;
    try {
      await si(`/review/${data.set_key}/${item.id}`, { method: "PUT", json: { answers, minutes: minutes ? Number(minutes) : null, note } });
      notify(`Saved ${item.id}.`);
      await load(data.set_key);
      if (index < data.items.length - 1) setIndex(index + 1);
    } catch (e) { notify((e as Error).message, true); }
  }

  if (sets && !sets.length) return <p className="ds-root text-[13px] text-ds-muted">No review set is available.</p>;
  if (!data || !item) return <div className="ds-root space-y-3"><div className="ds-skeleton h-20 rounded-xl" /><div className="ds-skeleton h-80 rounded-xl" /></div>;
  return (
    <div className="ds-root space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0"><p className="si-eyebrow mb-1.5">Evaluation · as of {new Date(data.as_of).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })} · fingerprint {data.fingerprint}</p>
          <h1 className="text-[26px] font-semibold leading-tight tracking-[-0.025em] text-ds-ink">Blind opportunity review</h1>
          <p className="mt-1.5 max-w-3xl text-[14px] text-ds-muted">{data.instructions}</p></div>
        <div className="text-right"><p className="si-mono text-[22px] leading-none text-ds-ink">{data.progress.done}/{data.progress.total}</p><p className="mt-1 text-[12px] text-ds-muted">judged by you</p></div>
      </header>
      {closed && <p role="status" className="ds-card flex items-center gap-2 px-4 py-3 text-[13px] text-ds-ink-2"><Lock size={14} aria-hidden="true" />This review is closed: answers can no longer change.</p>}

      <nav aria-label="Review items" className="flex flex-wrap gap-1">
        {data.items.map((i, n) => <button key={i.id} aria-current={n === index ? "true" : undefined} onClick={() => setIndex(n)}
          className={`si-mono relative h-7 min-w-[52px] rounded-[6px] border px-1.5 text-[11px] ${n === index ? "border-ds-ink bg-white text-ds-ink" : data.mine[i.id] ? "border-transparent bg-ds-green-soft text-ds-green" : "border-ds-border bg-white text-ds-muted"}`}>
          {data.mine[i.id] && <Check size={10} className="mr-0.5 inline" aria-hidden="true" />}{i.id}<span className="sr-only">{data.mine[i.id] ? " (judged)" : ""}</span></button>)}
      </nav>

      <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
        <ItemCard item={item} />
        <form className="ds-card space-y-4 p-5" aria-label="Your judgement" onSubmit={(e) => { e.preventDefault(); void save(); }}>
          {data.rubric.map((q) => (
            <fieldset key={q.key} disabled={closed}>
              <legend className="text-[13px] font-semibold text-ds-ink">{q.question}</legend>
              <div className="mt-1.5 flex flex-wrap gap-1.5">{q.options.map(([v, label]) => (
                <label key={v} className={`relative cursor-pointer rounded-[6px] border px-2.5 py-1 text-[12.5px] focus-within:ring-2 focus-within:ring-[#c2410c] ${answers[q.key] === v ? "border-ds-ink bg-ds-ink text-white" : "border-ds-border bg-white text-ds-ink-2 hover:border-ds-border-strong"}`}>
                  <input type="radio" className="sr-only" name={q.key} value={v} checked={answers[q.key] === v} onChange={() => setAnswers({ ...answers, [q.key]: v })} />{label}</label>))}</div>
            </fieldset>
          ))}
          <div className="grid grid-cols-[110px_minmax(0,1fr)] gap-3">
            <label className="block"><span className="ds-label">Minutes spent</span><input className="ds-input mt-1 !pl-3" inputMode="numeric" value={minutes} disabled={closed} onChange={(e) => setMinutes(e.target.value.replace(/\D/g, ""))} /></label>
            <label className="block"><span className="ds-label">Note (optional)</span><input className="ds-input mt-1 !pl-3" value={note} disabled={closed} onChange={(e) => setNote(e.target.value)} /></label>
          </div>
          <div className="flex items-center justify-between gap-2">
            <button type="button" className="ds-btn ghost sm" disabled={index === 0} onClick={() => setIndex(index - 1)}><ArrowLeft size={14} /> Previous</button>
            <button className="ds-btn primary" disabled={!complete || closed}>Save and next <ArrowRight size={14} /></button>
          </div>
          {!complete && !closed && <p className="text-[12px] text-ds-muted">Answer every question to save.</p>}
        </form>
      </div>

      {admin && <EvaluationControl set={data} notify={notify} onView={(id) => setIndex(Math.max(0, data.items.findIndex((i) => i.id === id)))} onChanged={() => load(data.set_key)} />}
    </div>
  );
}

function ItemCard({ item }: { item: Item }) {
  return (
    <article aria-label={`Item ${item.id}`} className="ds-card p-5">
      <p className="flex flex-wrap items-center gap-2"><span className="si-mono text-[12px] text-ds-muted">{item.id}</span><Pill>{item.record_type}</Pill>
        <span className="inline-flex items-center gap-1 text-[12px] text-ds-muted"><EyeOff size={12} aria-hidden="true" />Source method hidden</span></p>
      <h2 className="si-serif mt-2 text-[28px] leading-[1.1] text-ds-ink">{item.organisation}</h2>
      {item.site && <p className="text-[14px] text-ds-ink-2">{item.site}</p>}
      {item.location && <p className="text-[13px] text-ds-muted">{item.location}</p>}
      <p className="mt-2 text-[14px] text-ds-ink-2">{item.title}</p>
      <section aria-label="Evidence" className="mt-4 border-t border-ds-border pt-3">
        <p className="si-eyebrow">Evidence</p>
        <ul className="mt-2 space-y-2.5">{item.facts.map((f, i) => {
          const href = safeUrl(f.url);
          return <li key={i} className="text-[13px] leading-5 text-ds-ink-2">{f.text}{f.date && <span className="si-mono text-ds-muted"> · {f.date}</span>}
            {href && <> · <a className="inline-flex items-center gap-0.5 font-medium text-ds-ink underline decoration-ds-border-strong underline-offset-2" href={href} target="_blank" rel="noopener noreferrer">source<ArrowUpRight size={11} /></a></>}
            <span className="block text-[11.5px] text-ds-muted">{f.basis}</span></li>;
        })}</ul>
      </section>
    </article>
  );
}

function EvaluationControl({ set, notify, onView, onChanged }: { set: SetT; notify: (m: string, e?: boolean) => void; onView: (id: string) => void; onChanged: () => Promise<void> }) {
  const [status, setStatus] = useState<StatusT | null>(null);
  const [results, setResults] = useState<ResultsT | null>(null);
  const [label, setLabel] = useState("Reviewer A");
  const [busy, setBusy] = useState(false);
  const refresh = useCallback(async () => {
    const s = await si<StatusT>(`/review/${set.set_key}/status`);
    setStatus(s);
    if (s.state === "revealed") setResults(await si<ResultsT>(`/review/${set.set_key}/results`));
  }, [set.set_key]);
  const done = set.progress.done;
  useEffect(() => { refresh().catch((e) => notify((e as Error).message, true)); }, [refresh, notify, done]);  // also after this reviewer saves
  const question = (key: string) => set.rubric.find((q) => q.key === key);

  async function act(fn: () => Promise<unknown>, done: string) {
    setBusy(true);
    try { await fn(); notify(done); await refresh(); await onChanged(); } catch (e) { notify((e as Error).message, true); } finally { setBusy(false); }
  }
  async function downloadPack() {
    await act(async () => {
      const r = await fetch(`${getApiBaseUrl()}/api/si/review/${set.set_key}/pack?reviewer=${encodeURIComponent(label)}`, { headers: authHeaders() });
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || "The pack could not be made.");
      const a = document.createElement("a");
      a.href = URL.createObjectURL(await r.blob());
      a.download = `opportunity-review-${set.set_key}-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}.html`;
      document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 0);
    }, `Pack for ${label} downloaded. Send it to that salesperson only.`);
  }
  if (!status) return <div className="ds-skeleton h-40 rounded-xl" />;
  const agreement = status.agreement.relevance;
  return (
    <section aria-label="Run the evaluation" className="space-y-4 border-t border-ds-border pt-5">
      <div><p className="si-eyebrow">For whoever runs the evaluation</p><h2 className="text-[20px] font-semibold tracking-[-0.01em] text-ds-ink">Run the evaluation</h2>
        <p className="mt-1 max-w-3xl text-[13px] text-ds-muted">Results stay sealed on the server until every item has two independent reviews, every disagreement is resolved,
          the review is locked, and the private key matches the commitment published before anyone judged an item.</p></div>

      <div role="region" aria-label="Review progress" className="ds-card grid gap-3 p-4 text-[13px] text-ds-ink-2 sm:grid-cols-4">
        <p><span className="si-mono block text-[20px] text-ds-ink">{status.items_with_two_reviews}/{status.items}</span>items with two complete reviews</p>
        <p><span className="si-mono block text-[20px] text-ds-ink">{status.reviewers}</span>reviewer{status.reviewers === 1 ? "" : "s"}</p>
        <p><span className="si-mono block text-[20px] text-ds-ink">{status.pending.length}</span>disagreement{status.pending.length === 1 ? "" : "s"} to resolve</p>
        <p><span className="si-mono block text-[20px] text-ds-ink">{agreement?.items ? pct(agreement.percent_agreement) : "—"}</span>
          agreement on relevance{agreement?.kappa != null ? `, kappa ${agreement.kappa}` : agreement?.items ? "" : " (needs two reviewers)"}</p>
      </div>

      <ol className="grid gap-3 lg:grid-cols-2">
        <li className="ds-card p-4"><p className="text-[13px] font-semibold text-ds-ink">1 · Send each salesperson their own review pack</p>
          <p className="mt-1 text-[12.5px] text-ds-muted">One file per reviewer. It holds only the evidence shown above, makes no network requests and contains no key. They open it in a browser,
            judge every item and send back one answers file.</p>
          <div className="mt-3 flex flex-wrap items-end gap-2"><label className="block"><span className="ds-label">Reviewer label</span>
            <input className="ds-input mt-1 !pl-3" value={label} maxLength={40} onChange={(e) => setLabel(e.target.value.replace(/[^A-Za-z0-9 ._-]/g, ""))} /></label>
            <button className="ds-btn" disabled={busy || !label.trim() || status.state !== "open"} onClick={() => void downloadPack()}><Download size={14} /> Download pack</button></div></li>
        <li className="ds-card p-4"><p className="text-[13px] font-semibold text-ds-ink">2 · Import their answers</p>
          <p className="mt-1 text-[12.5px] text-ds-muted">The file is checked against this set&apos;s fingerprint and every answer against the rubric before anything is stored. Importing the same file again changes nothing.</p>
          <label className="mt-3 inline-flex cursor-pointer items-center gap-2 text-[13px] font-medium text-ds-ink"><Upload size={14} aria-hidden="true" />Import a reviewer&apos;s answers file
            <input type="file" accept="application/json,.json" className="sr-only" disabled={busy || status.state !== "open"} onChange={(e) => {
              const f = e.target.files?.[0]; e.target.value = "";
              if (f) void act(async () => si(`/review/${set.set_key}/import`, { method: "POST", json: await readJson(f) }), `Imported ${f.name}.`);
            }} /></label></li>
      </ol>

      <section aria-label="Disagreements" className="ds-card p-4">
        <p className="text-[13px] font-semibold text-ds-ink">3 · Resolve each disagreement, and record how</p>
        <p className="mt-1 text-[12.5px] text-ds-muted">Where two reviewers gave different answers to a primary question, hold a short discussion between them (consensus), or ask an independent third salesperson.
          Record the final answer and why. The methods stay hidden throughout.</p>
        {!status.disagreements.length && <p className="mt-3 text-[13px] text-ds-muted">{status.items_with_two_reviews ? "No disagreements so far." : "Disagreements appear once two reviewers have judged the same items."}</p>}
        <ul className="mt-3 space-y-3">{status.disagreements.map((d) => {
          const ruled = status.rulings.find((r) => r.item_id === d.item_id && r.question === d.question);
          return <li key={`${d.item_id}-${d.question}`} className="rounded-[10px] border border-ds-border p-3">
            <p className="flex flex-wrap items-center gap-2 text-[13px]"><button className="si-mono font-medium text-ds-ink underline decoration-ds-border-strong underline-offset-2" onClick={() => onView(d.item_id)}>{d.item_id}</button>
              <span className="text-ds-ink-2">{question(d.question)?.question}</span></p>
            <p className="mt-1 text-[12.5px] text-ds-muted">{Object.entries(d.answers).map(([who, a]) => `${who}: ${question(d.question)?.options.find((o) => o[0] === a)?.[1] || a}`).join(" · ")}</p>
            {ruled ? <p className="mt-1.5 text-[12.5px] text-ds-ink-2"><Check size={12} className="mr-1 inline text-ds-green" aria-hidden="true" />Final: {question(d.question)?.options.find((o) => o[0] === ruled.answer)?.[1]} · {METHOD[ruled.method]} ({ruled.adjudicator}): {ruled.rationale}</p>
              : <Adjudicate d={d} q={question(d.question)!} disabled={busy || status.state !== "open"} onSave={(r) => act(() => si(`/review/${set.set_key}/adjudications`, { method: "POST", json: r }), `Recorded the decision for ${d.item_id}.`)} />}
          </li>;
        })}</ul>
      </section>

      <ol className="grid gap-3 lg:grid-cols-2">
        <li className="ds-card p-4"><p className="text-[13px] font-semibold text-ds-ink">4 · Lock the review</p>
          <p className="mt-1 text-[12.5px] text-ds-muted">Possible once every item has two complete reviews and every disagreement is resolved. After this, no answer can change.</p>
          <button className="ds-btn mt-3" disabled={busy || !status.ready_to_lock} onClick={() => { if (window.confirm("Lock the review? Answers can no longer change.")) void act(() => si(`/review/${set.set_key}/lock`, { method: "POST" }), "The review is locked."); }}>
            <Lock size={14} /> Lock the review</button>
          {status.state !== "open" && <p className="mt-2 text-[12.5px] text-ds-green">Locked.</p>}</li>
        <li className="ds-card p-4"><p className="text-[13px] font-semibold text-ds-ink">5 · Reveal with the private key</p>
          <p className="mt-1 text-[12.5px] text-ds-muted">The key was kept outside the repository. It is accepted only if it matches the commitment published before the review.</p>
          <label className={`mt-3 inline-flex items-center gap-2 text-[13px] font-medium ${status.state === "locked" ? "cursor-pointer text-ds-ink" : "text-ds-muted"}`}><ShieldCheck size={14} aria-hidden="true" />Reveal with the private key file
            <input type="file" accept="application/json,.json" className="sr-only" disabled={busy || status.state !== "locked"} onChange={(e) => {
              const f = e.target.files?.[0]; e.target.value = "";
              if (f) void act(async () => si(`/review/${set.set_key}/reveal`, { method: "POST", json: await readJson(f) }), "The key matched its commitment. Results are unsealed.");
            }} /></label></li>
      </ol>

      <section aria-label="Review results">
        {!results ? <p className="ds-card px-4 py-3 text-[13px] text-ds-muted"><Lock size={13} className="mr-1.5 inline" aria-hidden="true" />Results are sealed until the review is complete, locked and its key is revealed.</p>
          : <Results r={results} />}
      </section>
    </section>
  );
}

function Adjudicate({ d, q, disabled, onSave }: { d: Dis; q: Question; disabled: boolean; onSave: (r: Ruling) => Promise<void> }) {
  const [answer, setAnswer] = useState("");
  const [method, setMethod] = useState("consensus");
  const [who, setWho] = useState(d.reviewers.join(" and "));
  const [why, setWhy] = useState("");
  return (
    <form className="mt-2 grid gap-2 sm:grid-cols-[150px_210px_minmax(0,1fr)]" aria-label={`Resolve ${d.item_id}: ${q.key}`}
      onSubmit={(e) => { e.preventDefault(); void onSave({ item_id: d.item_id, question: d.question, answer, method, adjudicator: who, rationale: why }); }}>
      <label className="block"><span className="ds-label">Final answer</span><select className="ds-input mt-1 !pl-3" value={answer} onChange={(e) => setAnswer(e.target.value)}>
        <option value="">Choose…</option>{q.options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
      <label className="block"><span className="ds-label">How it was resolved</span><select className="ds-input mt-1 !pl-3" value={method} onChange={(e) => setMethod(e.target.value)}>
        {Object.entries(METHOD).map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
      <label className="block"><span className="ds-label">Resolved by</span><input className="ds-input mt-1 !pl-3" value={who} onChange={(e) => setWho(e.target.value)} /></label>
      <label className="block sm:col-span-3"><span className="ds-label">Why (recorded with the result)</span><input className="ds-input mt-1 !pl-3" value={why} onChange={(e) => setWhy(e.target.value)} /></label>
      <div className="sm:col-span-3"><button className="ds-btn sm" disabled={disabled || !answer || why.trim().length < 10 || who.trim().length < 2}>Record the decision</button></div>
    </form>
  );
}

export function Results({ r }: { r: ResultsT }) {
  const arms = Object.entries(r.arms);
  const cell = (x: Rate) => (x.n ? `${x.hits}/${x.n} · ${pct(x.rate)}${x.interval ? ` (${pct(x.interval[0])}–${pct(x.interval[1])})` : ""}` : "—");
  return (
    <div className="space-y-4">
      <div className="ds-card overflow-x-auto">
        <table className="w-full min-w-[860px] text-left text-[13px]">
          <caption className="px-4 pt-3 text-left text-[12.5px] text-ds-muted">Final labels from {r.reviewers} reviewers over {r.items} items; 95% Wilson intervals. A lead sampled by two methods counts in both.</caption>
          <thead><tr className="border-b border-ds-border text-[12px] text-ds-muted"><th className="px-4 py-2.5 font-medium">Measure</th>
            {arms.map(([k, a]) => <th key={k} className="px-3 py-2.5 text-right font-medium">{a.label}<span className="block font-normal">n {a.n} of {a.frame} (list {a.pool})</span></th>)}</tr></thead>
          <tbody>{(["relevant", "actionable", "worth_investigating", "noise", "relevant_or_possible"] as const).map((m) => (
            <tr key={m} className="border-b border-ds-border last:border-0"><td className="px-4 py-2 text-ds-ink-2">{MEASURE[m]}</td>
              {arms.map(([k, a]) => <td key={k} className="si-mono px-3 py-2 text-right text-ds-ink">{cell(a[m])}</td>)}</tr>))}
            <tr className="border-b border-ds-border"><td className="px-4 py-2 text-ds-ink-2">Contact route available</td>{arms.map(([k, a]) => <td key={k} className="si-mono px-3 py-2 text-right">{pct(a.route_available)}</td>)}</tr>
            <tr><td className="px-4 py-2 text-ds-ink-2">Minutes per item</td>{arms.map(([k, a]) => <td key={k} className="si-mono px-3 py-2 text-right">{a.minutes_per_item ?? "—"}</td>)}</tr></tbody>
        </table>
      </div>
      <div className="ds-card p-4">
        <p className="text-[13px] font-semibold text-ds-ink">Comparisons, decided before the review</p>
        <ul className="mt-2 space-y-1 text-[13px] text-ds-ink-2">{r.verdicts.map((v) => <li key={v}>{v}</li>)}</ul>
        <p className="mt-2 text-[12px] text-ds-muted">{r.statistics}</p>
        <p className="mt-2 text-[13px] text-ds-ink-2">Exploratory pathway: {r.exploratory.rule} Result: {cell(r.exploratory.worth_investigating)}, so the rule is {r.exploratory.met ? "met" : "not met"}.</p>
      </div>
      {r.diagnosis && <Diagnosis d={r.diagnosis} arms={arms} />}
      <div className="ds-card p-4 text-[13px] text-ds-ink-2">
        <p className="font-semibold text-ds-ink">Agreement and disagreements</p>
        <p className="mt-1">{Object.entries(r.agreement).map(([q, a]) => `${q}: ${pct(a.percent_agreement)} over ${a.items} items, kappa ${a.kappa ?? "—"}`).join(" · ")}</p>
        {r.disagreements.map((d) => <p key={d.item_id} className="mt-1"><span className="si-mono">{d.item_id}</span>: {d.questions.map((q) => `${q.question} → ${q.final} (${METHOD[q.method]}, ${q.adjudicator}: ${q.rationale})`).join("; ")}</p>)}
        <p className="mt-2">Judged genuine but on neither SalesIntel list: {r.missed_by_salesintel.join(", ") || "none"}. Not on the qualified list: {r.missed_by_qualified.join(", ") || "none"}.</p>
        <p className="mt-2 text-[12px] text-ds-muted">{r.note}</p>
      </div>
    </div>
  );
}

const share = (x: Share | undefined) => (!x || x.rate === null ? "—" : `${pct(x.rate)}${x.interval ? ` (${pct(x.interval[0])}–${pct(x.interval[1])})` : ""}`);

/** Where discovery is weak, as registered before any answer was seen. It sits beside the pre-specified comparisons and decides nothing. */
function Diagnosis({ d, arms }: { d: DiagnosisT; arms: [string, Arm][] }) {
  const registered = new Date(`${d.registered}T12:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
  const label = (m: "relevant" | "relevant_or_possible") => Object.values(d.otherwise_missed)[0]?.[m]?.label ?? m;
  const head = (first: string) => (
    <thead><tr className="border-b border-ds-border text-[12px] text-ds-muted"><th scope="col" className="px-4 py-2.5 font-medium">{first}</th>
      {arms.map(([k, a]) => <th key={k} scope="col" className="px-3 py-2.5 text-right font-medium">{a.label}<span className="block font-normal">n {d.chain[k]?.n ?? 0}</span></th>)}</tr></thead>
  );
  return (
    <section aria-label="Diagnosis" className="ds-card space-y-4 p-4">
      <div><p className="text-[13px] font-semibold text-ds-ink">Diagnosis, registered before any answer ({registered})</p>
        <p className="mt-1 max-w-3xl text-[13px] text-ds-ink-2">{d.purpose}</p></div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[860px] text-left text-[13px]">
          <caption className="pb-1 text-left text-[13px] font-medium text-ds-ink">Otherwise missed</caption>
          {head("Not yet advertised")}
          <tbody>{(["relevant", "relevant_or_possible"] as const).map((m) => (
            <tr key={m} className="border-b border-ds-border last:border-0"><th scope="row" className="px-4 py-2 font-normal text-ds-ink-2">{label(m)}</th>
              {arms.map(([k]) => <td key={k} className="si-mono px-3 py-2 text-right text-ds-ink">{share(d.otherwise_missed[k]?.[m])}</td>)}</tr>))}</tbody>
        </table>
        <p className="mt-1.5 max-w-3xl text-[12px] text-ds-muted">{d.measures.otherwise_missed}</p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[860px] text-left text-[13px]">
          <caption className="pb-1 text-left text-[13px] font-medium text-ds-ink">Where leads drop out</caption>
          {head("Still standing after")}
          <tbody>{d.steps.map((s, n) => (
            <tr key={s.key} className="border-b border-ds-border last:border-0"><th scope="row" className="px-4 py-2 font-normal text-ds-ink-2">{n + 1} · {s.label}</th>
              {arms.map(([k]) => <td key={k} className="si-mono px-3 py-2 text-right text-ds-ink">{share(d.chain[k]?.steps[n])}</td>)}</tr>))}</tbody>
        </table>
        <p className="mt-1.5 max-w-3xl text-[12px] text-ds-muted">{d.measures.chain}</p>
      </div>
      <p className="max-w-3xl text-[12px] text-ds-muted">{d.statistics} {d.rule}</p>
    </section>
  );
}
