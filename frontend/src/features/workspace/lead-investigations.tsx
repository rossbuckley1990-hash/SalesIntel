"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { ArrowRight, Loader2 } from "lucide-react";
import { getApiBaseUrl } from "@/lib/api";
import { safeSource } from "./api";
import { Button } from "./ui";

type Progress = { phase?: string; planned?: number; completed?: number; failed?: number; active_queries?: string[] };
type Investigation = {
  id: number; lead_id: number; question: string; job_id: string; status: "queued" | "running" | "completed" | "failed" | "interrupted" | "completed_unsaved";
  saved_run_id: number | null; created_at: string; progress: Progress | null; error: string | null; save_error: string | null;
};
type ResultLead = { id: number; organisation: string; headline: string; location: string; opportunity: { thesis: string; verification_action: string } };
type Observation = { id: string; fact: string; source_title: string; source_url: string; published_date: string | null };
type SavedRun = { id: number; leads: ResultLead[]; result: { observations: Observation[]; limitations: string[]; searches: unknown[] } };
type TemporaryResult = { opportunities: { organisation: string; headline: string; thesis: string; verification_action: string; unknowns: string[] }[]; observations: Observation[]; limitations: string[] };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, { ...init, cache: "no-store" });
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new Error(typeof body?.detail === "string" ? body.detail : `Request failed (${response.status}).`);
  return body as T;
}

function InvestigationResult({ run, onOpenLead }: { run: SavedRun; onOpenLead: (leadId: number) => void }) {
  const observations = run.result?.observations || [];
  const leads = run.leads || [];
  return <div className="mt-4 border-l-2 border-[var(--misi-border)] pl-4">
    <p className="text-xs font-semibold uppercase tracking-wide text-[var(--misi-muted)]">Research findings</p>
    <p className="mt-1 text-xs leading-5 text-[var(--misi-muted)]">{leads.length} {leads.length === 1 ? "lead" : "leads"} · {observations.length} observations · {(run.result?.searches || []).length} passes. Review the original sources and confirm identity and current arrangements.</p>
    {leads.length ? <div className="mt-3 grid gap-3">{leads.map((lead) => <article key={lead.id} className="border-t border-[var(--misi-border)] pt-3"><p className="text-xs text-[var(--misi-muted)]">{lead.organisation}{lead.location ? ` · ${lead.location}` : ""}</p><h5 className="mt-1 text-sm font-semibold text-[var(--misi-ink)]">{lead.headline}</h5><p className="mt-1 text-sm leading-6 text-[var(--misi-ink)]">{lead.opportunity?.thesis}</p><p className="mt-1 text-xs leading-5 text-[var(--misi-muted)]">Next to verify: {lead.opportunity?.verification_action || "Review the available evidence."}</p><button type="button" onClick={() => onOpenLead(lead.id)} className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-[var(--misi-accent)] underline underline-offset-4">Open saved lead <ArrowRight size={13} aria-hidden="true" /></button></article>)}</div> : <p className="mt-3 text-sm leading-6 text-[var(--misi-ink)]">No sufficiently supported lead was found in this research. This does not mean an opportunity or source is absent.</p>}
    {observations.length > 0 && <details className="mt-3"><summary className="cursor-pointer text-xs font-semibold text-[var(--misi-ink)]">Inspect gathered observations · {observations.length}</summary><ul className="mt-2 divide-y divide-[var(--misi-border)]">{observations.map((item) => { const url = safeSource(item.source_url); return <li key={item.id} className="py-3"><p className="text-sm leading-6 text-[var(--misi-ink)]">{item.fact}</p><p className="mt-1 text-xs text-[var(--misi-muted)]">{item.source_title || "Source"} · {item.published_date || "Date not provided"}</p>{url && <a href={url} target="_blank" rel="noreferrer" className="mt-1 inline-block text-xs font-semibold text-[var(--misi-accent)] underline">Review source</a>}</li>; })}</ul></details>}
    {!!run.result?.limitations?.length && <details className="mt-3 text-xs leading-5 text-[var(--misi-muted)]"><summary className="cursor-pointer font-semibold text-[var(--misi-ink)]">Coverage and limitations</summary><ul className="mt-2 list-disc pl-5">{run.result.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul></details>}
  </div>;
}

/** Research turns are separate saved jobs, never a claim that MiSi verified the lead. */
export function LeadInvestigations({ leadId, organisation, onOpenLead, onResearchSaved }: { leadId: number; organisation: string; onOpenLead: (leadId: number) => void; onResearchSaved: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const [question, setQuestion] = useState("");
  const [breadth, setBreadth] = useState(6);
  const [items, setItems] = useState<Investigation[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [trackingWarning, setTrackingWarning] = useState("");
  const [resultError, setResultError] = useState("");
  const [run, setRun] = useState<SavedRun | null>(null);
  const [viewingId, setViewingId] = useState<number | null>(null);
  const [temporary, setTemporary] = useState<{ investigationId: number; result: TemporaryResult } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await request<{ items: Investigation[] }>(`/api/research-dossiers/leads/${leadId}/investigations`);
      setItems(data.items || []); setError(""); setLoaded(true);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not load follow-up research."); }
    finally { setLoading(false); }
  }, [leadId]);
  useEffect(() => { if (expanded && !loaded) void load(); }, [expanded, loaded, load]);

  // Poll the durable investigation record, so a tab reload can resume tracking.
  useEffect(() => {
    if (!expanded) return;
    const pending = items.filter((item) => item.status === "queued" || item.status === "running");
    if (!pending.length) return;
    const timer = setTimeout(() => {
      void Promise.allSettled(pending.map((item) => request<Investigation>(`/api/research-dossiers/investigations/${item.id}`))).then((results) => {
        const saved = results.some((result) => result.status === "fulfilled" && result.value.status === "completed" && !!result.value.saved_run_id);
        setTrackingWarning(results.some((result) => result.status === "rejected") ? "Status temporarily unavailable; retrying. Your follow-up may still be running." : "");
        setItems((current) => current.map((item) => {
          const index = pending.findIndex((entry) => entry.id === item.id);
          if (index < 0 || results[index].status !== "fulfilled") return item;
          const next = (results[index] as PromiseFulfilledResult<Investigation>).value;
          return next;
        }));
        if (saved) onResearchSaved();
      });
    }, 2500);
    return () => clearTimeout(timer);
  }, [expanded, items, onResearchSaved]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy || question.trim().length < 8) return;
    setBusy(true); setError("");
    try {
      const item = await request<Investigation>(`/api/research-dossiers/leads/${leadId}/investigations`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: question.trim(), max_searches: breadth }) });
      setItems((current) => [item, ...current.filter((existing) => existing.id !== item.id)]); setQuestion(""); setLoaded(true);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not start the follow-up."); }
    finally { setBusy(false); }
  }
  async function showRun(id: number) {
    setViewingId(id); setResultError("");
    try { setRun(await request<SavedRun>(`/api/research-dossiers/runs/${id}`)); }
    catch (reason) { setResultError(reason instanceof Error ? reason.message : "Could not load the saved research."); }
    finally { setViewingId(null); }
  }
  async function retrySave(item: Investigation) {
    setBusy(true); setError("");
    try {
      await request(`/api/research-dossiers/from-job/${encodeURIComponent(item.job_id)}`, { method: "POST" });
      const latest = await request<Investigation>(`/api/research-dossiers/investigations/${item.id}`);
      setItems((current) => current.map((entry) => entry.id === item.id ? latest : entry));
      onResearchSaved();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "The research could not be saved. The temporary result may have expired."); }
    finally { setBusy(false); }
  }
  async function showTemporary(item: Investigation) {
    setBusy(true); setResultError("");
    try {
      const job = await request<{ status: string; result: TemporaryResult | null }>(`/api/intelligence/universal-research-jobs/${encodeURIComponent(item.job_id)}`);
      if (job.status !== "completed" || !job.result) throw new Error("The temporary research result is no longer available.");
      setTemporary({ investigationId: item.id, result: job.result });
    } catch (reason) { setResultError(reason instanceof Error ? reason.message : "The temporary research result could not be loaded."); }
    finally { setBusy(false); }
  }
  const statusText: Record<Investigation["status"], string> = { queued: "Queued", running: "Researching", completed: "Saved", failed: "Research failed", interrupted: "Interrupted", completed_unsaved: "Completed but not saved" };
  return <details className="mt-5 border-t border-[var(--misi-border)] pt-5" onToggle={(event) => setExpanded(event.currentTarget.open)}>
    <summary className="cursor-pointer text-sm font-semibold text-[var(--misi-ink)]">Ask a follow-up about {organisation}</summary>
    <p className="mt-2 text-xs leading-5 text-[var(--misi-muted)]">Ask a new question about this lead. MiSi searches public sources again using the selected organisation, location, headline, prior hypothesis and verification step; up to one cited web observation from the lead and each of the last two saved follow-ups; and up to two earlier follow-up questions (80 characters each), all as unverified context. Imported observations and private notes are not included.</p>
    <p className="mt-2 text-xs leading-5 text-[var(--misi-muted)]">Each follow-up starts a new, bounded research run; findings depend on the selected breadth and available sources. The question and context are sent to your configured AI provider. Model and web research may incur costs. This does not contact the organisation.</p>
    <form onSubmit={(event) => void submit(event)} className="mt-4">
      <label htmlFor={`followup-question-${leadId}`} className="text-xs font-semibold text-[var(--misi-ink)]">Your follow-up question</label>
      <textarea id={`followup-question-${leadId}`} value={question} onChange={(event) => setQuestion(event.target.value)} required minLength={8} maxLength={600} rows={3} placeholder="What would you like MiSi to investigate next?" className="mt-2 block w-full rounded-md border border-[var(--misi-border)] bg-white p-3 text-sm text-[var(--misi-ink)]" />
      <div className="mt-3 flex flex-wrap items-end gap-3"><label htmlFor={`followup-depth-${leadId}`} className="text-xs text-[var(--misi-muted)]">Research breadth<select id={`followup-depth-${leadId}`} value={breadth} onChange={(event) => setBreadth(Number(event.target.value))} className="mt-1 block rounded-md border border-[var(--misi-border)] bg-white px-3 py-2 text-sm text-[var(--misi-ink)]"><option value={3}>Quick · up to 3 passes</option><option value={6}>Broader · up to 6 passes</option><option value={12}>Deep · up to 12 passes</option></select></label><Button type="submit" kind="primary" disabled={busy || !loaded || question.trim().length < 8}>{busy ? "Starting…" : "Research follow-up"}</Button></div>
    </form>
    {error && <div className="mt-3"><p className="text-xs leading-5 text-[#825929]" role="alert">{error}</p>{!loaded && <button type="button" className="mt-2 text-xs font-semibold text-[var(--misi-accent)] underline" onClick={() => void load()}>Retry loading research history</button>}</div>}
    {trackingWarning && <p className="mt-3 text-xs leading-5 text-[#825929]" role="status">{trackingWarning}</p>}
    {loading && <p className="mt-4 flex items-center gap-2 text-xs text-[var(--misi-muted)]" role="status"><Loader2 size={14} className="animate-spin motion-reduce:animate-none" /> Loading research history…</p>}
    {loaded && items.length > 0 && <div className="mt-5"><h4 className="text-xs font-semibold uppercase tracking-wide text-[var(--misi-muted)]">Follow-up research</h4><div className="mt-2 divide-y divide-[var(--misi-border)] border-y border-[var(--misi-border)]">{items.map((item) => <article key={item.id} className="py-4"><p className="text-sm font-semibold leading-6 text-[var(--misi-ink)]">{item.question}</p><p className="mt-1 text-xs text-[var(--misi-muted)]" role="status">{statusText[item.status]}{item.progress?.phase && (item.status === "running" || item.status === "queued") ? ` · ${item.progress.phase}` : ""}{item.progress?.planned ? ` · ${item.progress.completed || 0} completed, ${item.progress.failed || 0} failed of ${item.progress.planned} planned passes` : ""}</p>{item.error && <p className="mt-2 text-xs leading-5 text-[#825929]">{item.error}</p>}{item.status === "completed_unsaved" && <><p className="mt-2 text-xs leading-5 text-[#825929]">The result is temporary until saved and may expire if the server restarts.</p><div className="mt-2 flex flex-wrap gap-2"><Button disabled={busy} onClick={() => void retrySave(item)}>Retry saving</Button><Button disabled={busy} onClick={() => void showTemporary(item)}>View temporary result</Button></div></>}{temporary?.investigationId === item.id && item.status === "completed_unsaved" && <div className="mt-3 border-l-2 border-[var(--misi-border)] pl-4"><p className="text-xs font-semibold text-[#825929]">Temporary result · not saved</p>{temporary.result.opportunities.length ? temporary.result.opportunities.map((opportunity, index) => <div key={`${opportunity.organisation}-${index}`} className="mt-3"><p className="text-sm font-semibold text-[var(--misi-ink)]">{opportunity.organisation} · {opportunity.headline}</p><p className="mt-1 text-sm leading-6 text-[var(--misi-ink)]">{opportunity.thesis}</p><p className="mt-1 text-xs leading-5 text-[var(--misi-muted)]">Next to verify: {opportunity.verification_action}</p></div>) : <p className="mt-2 text-sm text-[var(--misi-muted)]">No sufficiently supported leads were found.</p>}<details className="mt-3"><summary className="cursor-pointer text-xs font-semibold text-[var(--misi-ink)]">Gathered observations · {temporary.result.observations.length}</summary><ul className="mt-2 divide-y divide-[var(--misi-border)]">{temporary.result.observations.map((observation) => { const url = safeSource(observation.source_url); return <li key={observation.id} className="py-2"><p className="text-sm leading-6 text-[var(--misi-ink)]">{observation.fact}</p><p className="mt-1 text-xs text-[var(--misi-muted)]">{observation.source_title || "Source"} · {observation.published_date || "Date not provided"}</p>{url && <a href={url} target="_blank" rel="noreferrer" className="mt-1 inline-block text-xs text-[var(--misi-accent)] underline">Review source</a>}</li>; })}</ul></details><p className="mt-2 text-xs text-[var(--misi-muted)]">Review the original sources and save the result before it expires.</p></div>}{item.saved_run_id && <Button className="mt-2" disabled={viewingId !== null} onClick={() => void showRun(item.saved_run_id!)}>{viewingId === item.saved_run_id ? "Loading findings…" : "View findings"}</Button>}{run?.id === item.saved_run_id && <InvestigationResult run={run} onOpenLead={onOpenLead} />}</article>)}</div></div>}
    {resultError && <p className="mt-3 text-xs text-[#825929]" role="alert">{resultError}</p>}
  </details>;
}
