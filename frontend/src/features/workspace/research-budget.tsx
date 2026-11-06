"use client";
/**
 * The research budget: live, paid web research runs only against a budget someone approved, as a hard ceiling the
 * server enforces before anything starts. A team's administrator approves it on the Team page; the owner of a local
 * install, who has no Team page, approves it from the menu.
 */
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { si } from "./si-api";

type BudgetT = { approved_cents: number; reserved_cents: number; spent_cents: number; remaining_cents: number; approved: boolean; live_provider: boolean };

export function ResearchBudget({ manage, notify }: { manage: boolean; notify: (m: string, e?: boolean) => void }) {
  const [b, setB] = useState<BudgetT | null>(null);
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const load = useCallback(async () => { try { setB(await si<BudgetT>("/research-budget")); } catch { /* optional */ } }, []);
  useEffect(() => { void load(); }, [load]);
  const money = (c: number) => "$" + (c / 100).toFixed(2);
  async function approve(e: FormEvent) {
    e.preventDefault();
    try {
      await si("/research-budget", { method: "POST", json: { amount_cents: Math.round(Number(amount) * 100), note } });
      notify("Research budget approved. Live research stops when it is used up."); setAmount(""); setNote(""); void load();
    } catch (err) { notify((err as Error).message, true); }
  }
  if (!b) return null;
  const figures: [string, number][] = [["Approved", b.approved_cents], ["Spent", b.spent_cents], ["Committed", b.reserved_cents], ["Remaining", b.remaining_cents]];
  return (
    <section className="ds-card p-4" aria-label="Research budget">
      <div className="flex flex-wrap items-baseline justify-between gap-2"><p className="text-[14px] font-semibold text-ds-ink">Research budget</p>
        <p className="text-[12px] text-ds-muted">{b.live_provider ? "Live, paid web research is configured." : "Live research is not configured here; nothing is charged."}</p></div>
      <dl className="mt-3 grid grid-cols-2 gap-3 text-[13px] sm:grid-cols-4">
        {figures.map(([k, v]) => <div key={k}><dt className="text-[12px] text-ds-muted">{k}</dt><dd className="si-mono text-ds-ink">{money(v)}</dd></div>)}
      </dl>
      {!b.approved && <p className="mt-2 text-[12.5px] text-ds-ink-2">No budget approved: investigations and gap research that would call a paid provider are refused, and nothing is charged.</p>}
      {manage && <form className="mt-3 flex flex-wrap items-end gap-2" onSubmit={approve} aria-label="Approve research budget">
        <label className="block"><span className="ds-label">Add (US$)</span><input className="ds-input mt-1 !w-28 !pl-3" inputMode="decimal" aria-label="Budget to add" value={amount} onChange={(e) => setAmount(e.target.value)} required /></label>
        <label className="block min-w-[200px] flex-1"><span className="ds-label">Purpose</span><input className="ds-input mt-1 !pl-3" aria-label="Budget purpose" value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Pilot evaluation, 20 investigations" /></label>
        <button className="ds-btn primary">Approve</button>
      </form>}
    </section>
  );
}

/** The local install's own page for it, reached from the foot of the menu. */
export function ResearchBudgetView({ notify }: { notify: (m: string, e?: boolean) => void }) {
  return (
    <div className="ds-root max-w-3xl space-y-4">
      <header>
        <p className="si-eyebrow mb-1.5">Research</p>
        <h1 className="text-[26px] font-semibold leading-tight tracking-[-0.025em] text-ds-ink">Research budget</h1>
        <p className="mt-1.5 text-[14px] text-ds-muted">Deep investigations and gap research can use live, paid web research. They run only against the budget you approve here,
          a hard ceiling checked before anything starts. When it is used up, research stops and nothing more is charged.</p>
      </header>
      <ResearchBudget manage notify={notify} />
    </div>
  );
}
