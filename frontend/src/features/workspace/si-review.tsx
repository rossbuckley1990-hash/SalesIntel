"use client";
/**
 * Blind opportunity review. A reviewer sees one discovered opportunity at a time, with neutral evidence only (never which
 * method found it, its rank or SalesIntel's reasons), and records their own judgement. Results unblind the methods, so
 * they are for administrators, after reviewers have finished.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, ArrowRight, ArrowUpRight, Check, EyeOff } from "lucide-react";
import { Pill } from "./ds";
import { safeUrl } from "./radar-model";
import { SERVICE_NAME, si } from "./si-api";

type Item = { id: string; organisation: string; site: string | null; title: string; source_kind: string; summary: string;
  evidence: { text: string; date: string; url: string; basis: string }[]; services_mentioned: string[] };
type Question = { key: string; question: string; options: [string, string][] };
type SetT = { set_key: string; as_of: string; rubric: Question[]; items: Item[]; instructions: string;
  mine: Record<string, { answers: Record<string, string>; minutes: number | null; note: string }>; progress: { done: number; total: number } };
type Arm = { items: number; judged: number; precision: number | null; precision_interval: number[] | null; precision_lenient: number | null; actionable_yield: number | null;
  actionable_interval: number[] | null; reason_to_contact: number | null; identity_correct: number | null; requirement_confirmed: number | null; route_available: number | null;
  stakeholders_identifiable: number | null; minutes_per_item: number | null; objective: { median_evidence_age_days: number | null; advertised_share: number | null; with_route_on_record: number | null } };
type ResultsT = { items: number; judged: number; reviewers: number; complete: boolean; arms: Record<string, Arm>; agreement: { items_with_two_reviews: number; relevance_kappa: number | null; percent_agreement: number | null };
  disagreements: { item_id: string }[]; missed_by_salesintel: string[]; note: string };

const ARM_LABEL: Record<string, string> = { salesintel: "SalesIntel (this PR)", salesintel_pr8: "SalesIntel (PR #8 rules)", renewal: "Renewal dates", keyword: "Keywords" };
const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${Math.round(v * 100)}`);

export function SiReview({ notify, admin }: { notify: (m: string, e?: boolean) => void; admin: boolean }) {
  const [sets, setSets] = useState<string[] | null>(null);
  const [data, setData] = useState<SetT | null>(null);
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [minutes, setMinutes] = useState("");
  const [note, setNote] = useState("");
  const [results, setResults] = useState<ResultsT | null>(null);
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

  async function save() {
    if (!data || !item) return;
    try {
      await si(`/review/${data.set_key}/${item.id}`, { method: "PUT", json: { answers, minutes: minutes ? Number(minutes) : null, note } });
      notify(`Saved ${item.id}.`);
      await load(data.set_key);
      if (index < data.items.length - 1) setIndex(index + 1);
    } catch (e) { notify((e as Error).message, true); }
  }
  async function unblind() {
    if (!data || !window.confirm("Results show which method found each item. Only look once every reviewer has finished. Continue?")) return;
    try { setResults(await si<ResultsT>(`/review/${data.set_key}/results`)); } catch (e) { notify((e as Error).message, true); }
  }

  if (sets && !sets.length) return <p className="ds-root text-[13px] text-ds-muted">No review set is available.</p>;
  if (!data || !item) return <div className="ds-root space-y-3"><div className="ds-skeleton h-20 rounded-xl" /><div className="ds-skeleton h-80 rounded-xl" /></div>;
  return (
    <div className="ds-root space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0"><p className="si-eyebrow mb-1.5">Evaluation · as of {new Date(data.as_of).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })}</p>
          <h1 className="text-[26px] font-semibold leading-tight tracking-[-0.025em] text-ds-ink">Blind opportunity review</h1>
          <p className="mt-1.5 max-w-3xl text-[14px] text-ds-muted">{data.instructions}</p></div>
        <div className="text-right"><p className="si-mono text-[22px] leading-none text-ds-ink">{data.progress.done}/{data.progress.total}</p><p className="mt-1 text-[12px] text-ds-muted">judged by you</p></div>
      </header>

      <nav aria-label="Review items" className="flex flex-wrap gap-1">
        {data.items.map((i, n) => <button key={i.id} aria-current={n === index ? "true" : undefined} onClick={() => setIndex(n)}
          className={`si-mono relative h-7 min-w-[52px] rounded-[6px] border px-1.5 text-[11px] ${n === index ? "border-ds-ink bg-white text-ds-ink" : data.mine[i.id] ? "border-transparent bg-ds-green-soft text-ds-green" : "border-ds-border bg-white text-ds-muted"}`}>
          {data.mine[i.id] && <Check size={10} className="mr-0.5 inline" aria-hidden="true" />}{i.id}<span className="sr-only">{data.mine[i.id] ? " (judged)" : ""}</span></button>)}
      </nav>

      <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
        <article aria-label={`Item ${item.id}`} className="ds-card p-5">
          <p className="flex flex-wrap items-center gap-2"><span className="si-mono text-[12px] text-ds-muted">{item.id}</span><Pill>{item.source_kind}</Pill>
            <span className="inline-flex items-center gap-1 text-[12px] text-ds-muted"><EyeOff size={12} aria-hidden="true" />Source method hidden</span></p>
          <h2 className="si-serif mt-2 text-[28px] leading-[1.1] text-ds-ink">{item.organisation}</h2>
          {item.site && <p className="text-[14px] text-ds-ink-2">{item.site}</p>}
          <p className="mt-1 text-[14px] text-ds-ink-2">{item.title}</p>
          {item.summary && <p className="mt-3 text-[14px] leading-6 text-ds-ink">{item.summary}</p>}
          {!!item.services_mentioned.length && <p className="mt-2 flex flex-wrap gap-1.5">{item.services_mentioned.map((s) => <Pill key={s}>{SERVICE_NAME[s] || s.replace(/_/g, " ")}</Pill>)}</p>}
          <section aria-label="Evidence" className="mt-4 border-t border-ds-border pt-3">
            <p className="si-eyebrow">Evidence</p>
            {!item.evidence.length ? <p className="mt-1 text-[13px] text-ds-muted">Only the summary above.</p> : <ul className="mt-2 space-y-2">{item.evidence.map((e, i) => {
              const href = safeUrl(e.url);
              return <li key={i} className="text-[13px] leading-5 text-ds-ink-2">{e.text}{e.date && <span className="si-mono text-ds-muted"> · {e.date}</span>}
                {href && <> · <a className="inline-flex items-center gap-0.5 font-medium text-ds-ink underline decoration-ds-border-strong underline-offset-2" href={href} target="_blank" rel="noreferrer">source<ArrowUpRight size={11} /></a></>}</li>;
            })}</ul>}
          </section>
        </article>

        <form className="ds-card space-y-4 p-5" aria-label="Your judgement" onSubmit={(e) => { e.preventDefault(); void save(); }}>
          {data.rubric.map((q) => (
            <fieldset key={q.key}>
              <legend className="text-[13px] font-semibold text-ds-ink">{q.question}</legend>
              <div className="mt-1.5 flex flex-wrap gap-1.5">{q.options.map(([v, label]) => (
                <label key={v} className={`relative cursor-pointer rounded-[6px] border px-2.5 py-1 text-[12.5px] focus-within:ring-2 focus-within:ring-[#c2410c] ${answers[q.key] === v ? "border-ds-ink bg-ds-ink text-white" : "border-ds-border bg-white text-ds-ink-2 hover:border-ds-border-strong"}`}>
                  <input type="radio" className="sr-only" name={q.key} value={v} checked={answers[q.key] === v} onChange={() => setAnswers({ ...answers, [q.key]: v })} />{label}</label>))}</div>
            </fieldset>
          ))}
          <div className="grid grid-cols-[110px_minmax(0,1fr)] gap-3">
            <label className="block"><span className="ds-label">Minutes spent</span><input className="ds-input mt-1 !pl-3" inputMode="numeric" value={minutes} onChange={(e) => setMinutes(e.target.value.replace(/\D/g, ""))} /></label>
            <label className="block"><span className="ds-label">Note (optional)</span><input className="ds-input mt-1 !pl-3" value={note} onChange={(e) => setNote(e.target.value)} /></label>
          </div>
          <div className="flex items-center justify-between gap-2">
            <button type="button" className="ds-btn ghost sm" disabled={index === 0} onClick={() => setIndex(index - 1)}><ArrowLeft size={14} /> Previous</button>
            <button className="ds-btn primary" disabled={!complete}>Save and next <ArrowRight size={14} /></button>
          </div>
          {!complete && <p className="text-[12px] text-ds-muted">Answer every question to save.</p>}
        </form>
      </div>

      {admin && <section aria-label="Review results" className="space-y-3">
        {!results ? <button className="ds-btn" onClick={() => void unblind()}>See results (unblinds the methods)</button> : <>
          <div className="ds-card overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-[13px]">
              <thead><tr className="border-b border-ds-border text-[12px] text-ds-muted"><th className="px-4 py-2.5 font-medium">Measure (judged items only)</th>
                {Object.keys(results.arms).map((a) => <th key={a} className="px-3 py-2.5 text-right font-medium">{ARM_LABEL[a] || a}</th>)}</tr></thead>
              <tbody>{([["Judged / items", (a: Arm) => `${a.judged} / ${a.items}`], ["Relevant, %", (a: Arm) => `${pct(a.precision)}${a.precision_interval ? ` (${pct(a.precision_interval[0])}–${pct(a.precision_interval[1])})` : ""}`],
                ["Worth pursuing now, %", (a: Arm) => `${pct(a.actionable_yield)}${a.actionable_interval ? ` (${pct(a.actionable_interval[0])}–${pct(a.actionable_interval[1])})` : ""}`],
                ["Reason to contact, %", (a: Arm) => pct(a.reason_to_contact)], ["Identity correct, %", (a: Arm) => pct(a.identity_correct)], ["Requirement confirmed, %", (a: Arm) => pct(a.requirement_confirmed)],
                ["Who to speak to, %", (a: Arm) => pct(a.stakeholders_identifiable)], ["Contact route available, %", (a: Arm) => pct(a.route_available)], ["Minutes per item", (a: Arm) => String(a.minutes_per_item ?? "—")],
                ["Median evidence age, days", (a: Arm) => String(a.objective.median_evidence_age_days ?? "—")], ["Already advertised, %", (a: Arm) => pct(a.objective.advertised_share)]] as [string, (a: Arm) => string][])
                .map(([label, f]) => <tr key={label} className="border-b border-ds-border last:border-0"><td className="px-4 py-2 text-ds-ink-2">{label}</td>
                  {Object.values(results.arms).map((a, i) => <td key={i} className="si-mono px-3 py-2 text-right text-ds-ink">{f(a)}</td>)}</tr>)}</tbody>
            </table>
          </div>
          <p className="text-[12.5px] text-ds-ink-2">{results.judged} of {results.items} items judged by {results.reviewers} reviewer{results.reviewers === 1 ? "" : "s"}{results.complete ? "" : " (not complete)"}.
            Agreement on relevance: {results.agreement.items_with_two_reviews ? `${pct(results.agreement.percent_agreement)}% over ${results.agreement.items_with_two_reviews} items, kappa ${results.agreement.relevance_kappa ?? "—"}` : "needs two reviewers per item"}.
            {results.disagreements.length ? ` Disagreements: ${results.disagreements.map((d) => d.item_id).join(", ")}.` : ""}
            {results.missed_by_salesintel.length ? ` Judged relevant but not on SalesIntel's list: ${results.missed_by_salesintel.join(", ")}.` : ""}</p>
          <p className="text-[12px] text-ds-muted">{results.note}</p>
        </>}
      </section>}
    </div>
  );
}
