"use client";
/** Find the right people: roles that matter, named people where sources support them, and legitimate business routes. */
import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowUpRight, Ban, CircleHelp, Loader2, MailPlus, Phone, Search, ShieldCheck, Square, Users } from "lucide-react";
import { Pill } from "./ds";
import { goto, si } from "./si-api";

export type JobT = { id: number; kind: string; status: "queued" | "running" | "succeeded" | "partial" | "failed" | "cancelled"; stage: string; attempts: number;
  estimated_cents: number; actual_cents: number; usage: { web_searches?: number; simulated?: boolean; provider?: string }; error: string; finished_at: string | null;
  result: { message?: string; checked?: number; accepted?: number; rejected?: { kind: string; value: string; source: string; reason: string }[]; prospect_ids?: number[]; note?: string } };
type Route = { contact_id: number; name: string | null; label: string; verification_method: string; status: string; basis: string; role: string; role_category: string; route_kind: string; route_label: string; email: string | null; phone: string | null;
  url: string | null; quality: string; quality_label: string; source_url: string | null; source_quote: string | null; source_date: string | null; flags: string[];
  use_restriction: string; why: string[] };
type People = { roles: { key: string; label: string; why: string; basis: string }[]; routes: Route[]; job: JobT | null; partial_message: string };

export const ACTIVE = ["queued", "running"];
export const newKey = () => (typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `k-${Date.now()}-${Math.random().toString(36).slice(2)}`);
const QUALITY_TONE: Record<string, "green" | "blue" | "amber" | "neutral"> = { public_source: "green", provider_verified: "blue", unverified: "amber", role_only: "neutral" };

/** Poll a durable job until it ends. It keeps working across refreshes and restarts; this only watches it. */
export function useJob(initial: JobT | null, onDone: () => void) {
  const [job, setJob] = useState<JobT | null>(initial);
  useEffect(() => setJob(initial), [initial]);
  useEffect(() => {
    if (!job || !ACTIVE.includes(job.status)) return;
    const t = setInterval(async () => {
      try {
        const next = await si<JobT>(`/research-jobs/${job.id}`);
        setJob(next);
        if (!ACTIVE.includes(next.status)) { clearInterval(t); onDone(); }
      } catch { clearInterval(t); }
    }, 1500);
    return () => clearInterval(t);
  }, [job, onDone]);
  return [job, setJob] as const;
}

export function JobStatus({ job, onCancel }: { job: JobT; onCancel?: () => void }) {
  const active = ACTIVE.includes(job.status);
  const cost = job.actual_cents ? `$${(job.actual_cents / 100).toFixed(2)}${job.usage?.simulated ? " (simulated)" : ""}` : active ? `up to $${(job.estimated_cents / 100).toFixed(2)} reserved` : "no cost";
  return (
    <div role="status" className={`flex flex-wrap items-center justify-between gap-2 rounded-lg px-3 py-2 text-[13px] ${active ? "bg-ds-brand-soft text-ds-brand" : job.status === "failed" ? "bg-ds-red-soft text-ds-red" : "bg-ds-canvas text-ds-ink-2"}`}>
      <span className="flex items-center gap-2">{active && <Loader2 size={14} className="ds-spin" />}
        <span><strong className="font-semibold">{{ queued: "Waiting to start", running: job.stage || "Researching", succeeded: "Complete", partial: "Complete, with gaps", failed: "Did not complete", cancelled: "Cancelled" }[job.status]}</strong>
          {job.attempts > 1 && active && " · resumed after an interruption"} · {cost}</span></span>
      {active && onCancel && <button className="ds-btn ghost sm" onClick={onCancel}><Square size={13} /> Stop</button>}
    </div>
  );
}

export function PeopleFinder({ accountId, notify, onChanged }: { accountId: number; notify: (m: string, e?: boolean) => void; onChanged: () => void }) {
  const [people, setPeople] = useState<People | null>(null);
  const key = useRef(newKey());
  const load = useCallback(async () => { try { setPeople(await si<People>(`/accounts/${accountId}/people`)); } catch (e) { notify((e as Error).message, true); } }, [accountId, notify]);
  const done = useCallback(() => { void load(); onChanged(); }, [load, onChanged]);
  const [job, setJob] = useJob(people?.job || null, done);
  useEffect(() => { void load(); }, [load]);

  async function find(refresh = false) {
    try {
      const started = await si<JobT & { reused: boolean }>(`/accounts/${accountId}/people-search`, { method: "POST", json: { refresh }, headers: { "Idempotency-Key": key.current } });
      key.current = newKey();
      setJob(started);
      if (started.reused && !ACTIVE.includes(started.status)) notify("Showing the research already saved for this account.");
    } catch (e) { notify((e as Error).message, true); }
  }
  async function cancel() { if (job) { try { setJob(await si<JobT>(`/research-jobs/${job.id}/cancel`, { method: "POST" })); } catch (e) { notify((e as Error).message, true); } } }
  async function confirm(r: Route) {
    try { await si(`/contacts/${r.contact_id}`, { method: "PATCH", json: { status: "verified" } }); notify("Marked verified by you."); done(); }
    catch (e) { notify((e as Error).message, true); }
  }
  async function optOut(r: Route) {
    try { await si(`/contacts/${r.contact_id}`, { method: "PATCH", json: { status: "do_not_contact" } }); notify("Marked do not contact. Research will never offer this route again."); done(); }
    catch (e) { notify((e as Error).message, true); }
  }
  if (!people) return <section className="ds-card p-4" aria-label="Find the right people"><div className="ds-skeleton h-24 rounded-lg" /></section>;
  const active = job && ACTIVE.includes(job.status);
  const message = job && !active ? job.result?.message : "";
  return (
    <section className="ds-card p-4" aria-label="Find the right people">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-[15px] font-semibold text-ds-ink"><Users size={16} className="text-ds-brand" /> Find the right people</h2>
        {!active && <button className="ds-btn primary sm" onClick={() => void find(!!job)}><Search size={14} /> {job ? "Search again" : "Find the right people"}</button>}
      </div>
      <p className="mt-1 text-[13px] text-ds-ink-2">Roles that usually decide, then named people and business routes only where a source supports them. Nothing is guessed or sent.</p>
      <ul className="mt-3 flex flex-wrap gap-1.5" aria-label="Roles to reach">{people.roles.map((r) => <li key={r.key}><Pill title={`${r.why} ${r.basis}`}>{r.label}</Pill></li>)}</ul>
      {job && <div className="mt-3"><JobStatus job={job} onCancel={() => void cancel()} /></div>}
      {message && <p className={`mt-3 rounded-lg border px-3 py-2 text-[13px] ${job?.status === "succeeded" ? "border-ds-border bg-ds-canvas text-ds-ink" : "border-ds-amber-line bg-ds-amber-soft text-ds-amber"}`}>{message}</p>}
      {job?.result?.note && <p className="mt-2 text-[12px] text-ds-muted">{job.result.note}</p>}
      {!!people.routes.length && <ol className="mt-3 space-y-2" aria-label="Best contact routes">{people.routes.map((r, i) => (
        <li key={r.contact_id} className="rounded-lg border border-ds-border p-3">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="text-[14px] font-semibold text-ds-ink">{i === 0 && <span className="mr-1.5 rounded bg-ds-brand px-1.5 py-0.5 text-[11px] font-semibold text-white">Best</span>}{r.name || r.label || r.role || r.route_label}</p>
              <p className="text-[12px] text-ds-muted">{[r.name ? r.role : r.role !== r.route_label && r.role !== (r.label || "") ? r.role : "", r.route_label].filter(Boolean).join(" · ")}</p>
            </div>
            <span className="flex flex-wrap gap-1"><Pill tone={QUALITY_TONE[r.quality] || "neutral"}>{r.quality_label || (r.basis === "user_entered" ? "Entered by your team" : "Unverified")}</Pill>
              {r.status === "verified" && <Pill tone="green">Confirmed by you</Pill>}</span>
          </div>
          <p className="mt-1.5 text-[14px]">{r.email ? <a className="font-medium text-ds-brand hover:underline" href={`mailto:${r.email}`}>{r.email}</a>
            : r.phone ? <a className="inline-flex items-center gap-1 font-medium text-ds-brand hover:underline" href={`tel:${r.phone.replace(/\s/g, "")}`}><Phone size={13} />{r.phone}</a>
            : r.url ? <a className="inline-flex items-center gap-1 font-medium text-ds-brand hover:underline" href={r.url} target="_blank" rel="noreferrer">{r.route_kind === "procurement_notice" ? "Official notice" : "Enquiry form"} <ArrowUpRight size={13} /></a>
            : <span className="inline-flex items-center gap-1 text-ds-muted"><CircleHelp size={13} /> No direct route published</span>}</p>
          {r.source_quote && <blockquote className="mt-1.5 border-l-2 border-ds-border pl-2 text-[12px] italic text-ds-ink-2">“{r.source_quote}”</blockquote>}
          <p className="mt-1 flex flex-wrap items-center gap-x-2 text-[12px] text-ds-muted"><ShieldCheck size={12} />{[r.verification_method.split("; ")[0], ...r.why.slice(3)].filter(Boolean).join(" · ") || "Checked against its source"}
            {r.source_url && <a className="inline-flex items-center gap-0.5 font-medium text-ds-brand hover:underline" href={r.source_url} target="_blank" rel="noreferrer">Source{r.source_date ? `, ${r.source_date}` : ""} <ArrowUpRight size={11} /></a>}</p>
          {r.use_restriction && <p className="mt-1 text-[12px] text-ds-muted">{r.use_restriction}</p>}
          <div className="mt-2 flex flex-wrap gap-2">
            {(r.email || r.phone) && <button className="ds-btn sm" onClick={() => goto("engage", { account: accountId, contact: r.contact_id })}><MailPlus size={13} /> Prepare introduction</button>}
            {r.status !== "verified" && <button className="ds-btn ghost sm" onClick={() => void confirm(r)}><ShieldCheck size={13} /> Mark verified</button>}
            <button className="ds-btn ghost sm" onClick={() => void optOut(r)}><Ban size={13} /> Do not contact</button>
          </div>
        </li>))}</ol>}
      {!!job?.result?.rejected?.length && <details className="mt-3 text-[12px] text-ds-muted"><summary className="cursor-pointer font-semibold">{job.result.rejected.length} finding(s) rejected</summary>
        <ul className="mt-1 space-y-1">{job.result.rejected.map((x, i) => <li key={i}>{x.kind}: {x.reason}</li>)}</ul></details>}
    </section>
  );
}
