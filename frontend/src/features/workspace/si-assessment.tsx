"use client";
/** Can we win this? Four separate answers: fit, readiness, the seller's view, and a win rate only when history supports one. */
import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, CircleDashed, HelpCircle, XCircle } from "lucide-react";
import { si } from "./si-api";
import { Panel } from "./si-shared";

type Criterion = { key: string; label: string; status: "met" | "gap" | "unknown" | "done" | "missing"; evidence: string; action: string };
export type AssessmentT = {
  commercial_fit: { criteria: Criterion[]; met: number; gaps: number; unknown: number };
  win_readiness: { items: Criterion[]; done: number; total: number };
  seller_confidence: { value: string | null; label: string | null; basis: string };
  win_probability: { available: boolean; message?: string; reason?: string; estimate?: number; interval?: [number, number]; comparable_outcomes: number; wins: number; losses: number;
    required?: number; validation?: { holdout_deals: number; brier: number; baseline_brier: number }; method?: string; limitations?: string[]; comparable_rule?: string };
};

const ICON = { met: CheckCircle2, done: CheckCircle2, gap: XCircle, missing: CircleDashed, unknown: HelpCircle };
const TONE = { met: "text-ds-green", done: "text-ds-green", gap: "text-ds-red", missing: "text-ds-amber", unknown: "text-ds-muted" };
const WORD = { met: "Met", done: "Done", gap: "Gap", missing: "To do", unknown: "Unknown" };

function Row({ c }: { c: Criterion }) {
  const Icon = ICON[c.status];
  return <li className="flex gap-2 py-1.5"><Icon size={15} className={`mt-0.5 shrink-0 ${TONE[c.status]}`} aria-hidden="true" />
    <div className="min-w-0 text-[13px]"><p className="font-medium text-ds-ink">{c.label} <span className={`text-[11px] font-semibold uppercase ${TONE[c.status]}`}>{WORD[c.status]}</span></p>
      {c.evidence && <p className="text-ds-ink-2">{c.evidence}</p>}{c.action && <p className="text-ds-brand">{c.action}</p>}</div></li>;
}

export function WinAssessment({ dealId, version, notify }: { dealId: number; version: string; notify: (m: string, e?: boolean) => void }) {
  const [a, setA] = useState<AssessmentT | null>(null);
  const load = useCallback(async () => { try { setA(await si<AssessmentT>(`/deals/${dealId}/assessment`)); } catch (e) { notify((e as Error).message, true); } }, [dealId, notify]);
  useEffect(() => { void load(); }, [load, version]);
  async function confidence(value: string) {
    try { await si(`/deals/${dealId}`, { method: "PATCH", json: { seller_confidence: value } }); void load(); } catch (e) { notify((e as Error).message, true); }
  }
  if (!a) return <Panel title="Can we win this?"><div className="ds-skeleton h-24 rounded-lg" /></Panel>;
  const p = a.win_probability;
  return (
    <Panel title="Can we win this?">
      <section aria-label="Commercial fit">
        <p className="ds-label">Commercial fit · {a.commercial_fit.met} met, {a.commercial_fit.gaps} gaps, {a.commercial_fit.unknown} unknown</p>
        <ul className="divide-y divide-ds-border">{a.commercial_fit.criteria.map((c) => <Row key={c.key} c={c} />)}</ul>
      </section>
      <section aria-label="Win readiness" className="mt-4">
        <p className="ds-label">Win readiness · {a.win_readiness.done} of {a.win_readiness.total} in place</p>
        <ul className="divide-y divide-ds-border">{a.win_readiness.items.map((c) => <Row key={c.key} c={c} />)}</ul>
      </section>
      <section aria-label="Seller confidence" className="mt-4">
        <label className="block"><span className="ds-label">Your confidence</span>
          <select className="ds-select mt-1 w-full" aria-label="Your confidence" value={a.seller_confidence.value || ""} onChange={(e) => void confidence(e.target.value)}>
            <option value="" disabled>Not recorded</option><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option></select></label>
        <p className="mt-1 text-[12px] text-ds-muted">Your own judgement, kept separate from everything SalesIntel calculates.</p>
      </section>
      <section aria-label="Win probability" className="mt-4 rounded-lg border border-ds-border bg-ds-canvas p-3">
        <p className="ds-label">Win probability</p>
        {p.available ? <>
          <p className="text-[20px] font-semibold text-ds-ink">{Math.round((p.estimate || 0) * 100)}% <span className="text-[13px] font-normal text-ds-muted">({Math.round((p.interval?.[0] || 0) * 100)}–{Math.round((p.interval?.[1] || 0) * 100)}% range)</span></p>
          <p className="text-[12px] text-ds-ink-2">{p.wins} won of {p.comparable_outcomes} comparable deals. Tested on {p.validation?.holdout_deals} recent outcomes: error {p.validation?.brier} against {p.validation?.baseline_brier} for your overall win rate.</p>
          <ul className="mt-1 list-disc pl-5 text-[12px] text-ds-muted">{(p.limitations || []).map((l) => <li key={l}>{l}</li>)}</ul>
        </> : <>
          <p className="text-[14px] font-semibold text-ds-ink">{p.message}</p>
          <p className="text-[12px] text-ds-muted">{p.reason} {p.comparable_rule}</p>
        </>}
      </section>
    </Panel>
  );
}
