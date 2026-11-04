"use client";

import { useEffect, useState } from "react";
import { ArrowRight, Check } from "lucide-react";
import { getApiBaseUrl } from "@/lib/api";
import { dateLabel, safeSource } from "./api";
import "./today-porcelain.css";
import type { Navigate } from "./types";

type ResearchAction = { id: number; lead_id: number; organisation: string; headline: string; text: string; status: "open" | "completed" | "deferred"; due_date: string | null };
type ResearchLead = { id: number; organisation: string; headline: string; location: string; created_at: string; observations?: { id: string; source_url: string; source_title: string; fact: string; published_date?: string | null }[]; opportunity: { thesis: string; verification_action: string; contact_role?: string; supporting_observation_ids?: string[] } };

/** A compact briefing based on saved work, never a prediction of buying intent. */
export function DailyResearchBrief({ navigate }: { navigate: Navigate }) {
  const [actions, setActions] = useState<ResearchAction[]>([]);
  const [actionTotal, setActionTotal] = useState(0);
  const [leads, setLeads] = useState<ResearchLead[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionError, setActionError] = useState("");
  const [leadError, setLeadError] = useState("");
  const [saving, setSaving] = useState<number | null>(null);
  const [showAll, setShowAll] = useState(false);

  useEffect(() => {
    let active = true;
    async function read<T>(path: string): Promise<T> {
      const response = await fetch(`${getApiBaseUrl()}${path}`, { cache: "no-store" });
      if (!response.ok) throw new Error("Unavailable");
      return response.json();
    }
    void Promise.allSettled([
      read<{ items: ResearchAction[]; total: number }>("/api/research-dossiers/actions?status=open&limit=100"),
      read<{ items: ResearchLead[] }>("/api/research-dossiers/leads?status=new&limit=3"),
    ]).then(([followups, recent]) => {
      if (!active) return;
      if (followups.status === "fulfilled") { setActions(followups.value.items || []); setActionTotal(followups.value.total || 0); }
      else setActionError("Follow-ups are unavailable. Open research to try again.");
      if (recent.status === "fulfilled") setLeads(recent.value.items || []);
      else setLeadError("Recent research is unavailable. Open research to try again.");
      setLoading(false);
    });
    return () => { active = false; };
  }, []);

  async function complete(id: number) {
    setSaving(id); setActionError("");
    try {
      const response = await fetch(`${getApiBaseUrl()}/api/research-dossiers/actions/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status: "completed" }) });
      if (!response.ok) throw new Error("Unavailable");
      setActions((items) => items.filter((item) => item.id !== id));
      setActionTotal((total) => Math.max(0, total - 1));
    } catch { setActionError("Could not complete the follow-up. Try again."); }
    finally { setSaving(null); }
  }
  function openLead(id: number) {
    sessionStorage.setItem("misi-open-lead", String(id));
    navigate("discover");
  }
  const ordered = [...actions].sort((a, b) => (a.due_date || "9999").localeCompare(b.due_date || "9999") || a.id - b.id);
  const visible = showAll ? ordered : ordered.slice(0, 3);

  const featured = leads[0];
  const evidence = featured?.observations?.filter((item) => featured.opportunity.supporting_observation_ids?.includes(item.id)) || [];
  return <section aria-label="Research briefing" className="p-brief">
    <div className="p-section-head"><div><p className="p-overline">RESEARCH / 01</p><h2>Intelligence to review</h2><p>Recently saved research, not a ranking of opportunity value.</p></div><button className="p-link" onClick={() => navigate("discover")}>All research <ArrowRight size={15} /></button></div>
    {loading ? <div className="p-loading" role="status"><span className="p-loading-line" />Preparing your research briefing…</div> : <>
      {leadError && <p className="p-alert" role="alert">{leadError}</p>}
      {featured ? <div className="p-spotlight" aria-label="Recently saved leads">
        <article className="p-spotlight-story">
          <div className="p-spotlight-meta"><span>RECENT RESEARCH</span><span>{featured.created_at ? `SAVED ${dateLabel(featured.created_at).toUpperCase()}` : "DATE NOT PROVIDED"}</span></div>
          <p className="p-spotlight-customer">{featured.organisation}{featured.location ? ` · ${featured.location}` : ""}</p>
          <h3>{featured.headline}</h3>
          <p className="p-story-label">WHAT THIS COULD MEAN</p>
          <p className="p-story-summary">{featured.opportunity.thesis || "The commercial relevance still needs to be established."}</p>
          <div className="p-spotlight-foot"><span className="p-status"><span /> Hypothesis to verify</span><span>{evidence.length ? `${evidence.length} linked ${evidence.length === 1 ? "observation" : "observations"}` : "Evidence to review"}</span><span>Current timing to confirm</span></div>
        </article>
        <aside className="p-spotlight-action">
          <p className="p-overline">THE NEXT MOVE</p>
          <h3>Start with what matters.</h3>
          <p className="p-action-copy">{featured.opportunity.verification_action || "Review the evidence and confirm current arrangements."}</p>
          <div className="p-action-context"><span>WHO TO APPROACH</span><p>{featured.opportunity.contact_role || "Role to be identified"}</p><small>Confirm the person and role before engagement.</small></div>
          <button className="p-primary" onClick={() => openLead(featured.id)}>Open intelligence brief <ArrowRight size={16} /></button>
        </aside>
      </div> : !leadError && <div className="p-empty-brief"><p className="p-overline">YOUR RESEARCH</p><h3>Your next insight starts with a question.</h3><p>No new leads are waiting. Explore a commercial question to begin.</p><button className="p-primary" onClick={() => navigate("discover")}>Explore opportunities <ArrowRight size={16} /></button></div>}
      {featured && <details className="p-evidence"><summary><span>See the evidence behind this idea</span><span>{evidence.length ? `${evidence.length} linked` : "Open brief"} <ArrowRight size={15} /></span></summary><div className="p-evidence-body">{evidence.length ? evidence.slice(0,3).map(item => { const url = safeSource(item.source_url); return <div key={item.id}><p>{item.fact}</p><small>{item.source_title || "Public source"} · {item.published_date || "Date not provided"} · Verify source and relevance</small>{url && <a href={url} target="_blank" rel="noreferrer">Read source <ArrowRight size={13} /></a>}</div>; }) : <p>Open the intelligence brief to inspect its supporting sources.</p>}<p className="p-evidence-note">Source observations are research leads and have not been independently verified. They do not establish buying intent.</p></div></details>}
      {actionError && <p className="p-alert" role="alert">{actionError}</p>}
      {visible.length > 0 && <section className="p-followups" aria-label="Research follow-ups"><div className="p-section-head"><div><p className="p-overline">YOUR WORK / 02</p><h3>Your next moves</h3><p>Ordered by the due dates you set; undated actions follow.</p></div><span>{actionTotal} open</span></div><div className="p-followup-list">{visible.map(item => <article key={item.id}><div><p className="p-row-meta">{item.organisation} · {item.due_date ? `Due ${dateLabel(item.due_date)}` : "No due date"}</p><h4>{item.text}</h4><p>{item.headline}</p></div><div className="p-row-actions"><button className="p-link" onClick={() => openLead(item.lead_id)}>Review lead</button><button className="p-link" disabled={saving !== null} onClick={() => void complete(item.id)}><Check size={14} /> {saving === item.id ? "Saving…" : "Mark done"}</button></div></article>)}</div>{ordered.length > 3 && <button className="p-link p-show-more" onClick={() => setShowAll(!showAll)}>{showAll ? "Show fewer" : `Show ${ordered.length} loaded follow-ups`}</button>}{showAll && actionTotal > ordered.length && <p className="p-list-note">Showing the first {ordered.length} of {actionTotal} open follow-ups.</p>}</section>}
      {leads.length > 1 && <section className="p-stream" aria-label="Opportunities worth reviewing"><div className="p-section-head"><div><p className="p-overline">YOUR PIPELINE OF IDEAS / {visible.length ? "03" : "02"}</p><h3>More to explore</h3><p>Recent hypotheses. Verify the evidence and timing before engagement.</p></div><button className="p-link" onClick={() => navigate("discover")}>View all <ArrowRight size={15} /></button></div><div className="p-stream-list">{leads.slice(1).map(lead => <button key={lead.id} onClick={() => openLead(lead.id)}><span className="p-monogram" aria-hidden="true">{(lead.organisation || "?").trim().charAt(0).toUpperCase()}</span><span className="p-stream-content"><span className="p-row-meta">{lead.organisation}{lead.location ? ` · ${lead.location}` : ""}</span><strong>{lead.headline}</strong><small>Next: {lead.opportunity.verification_action || "Review the evidence."}</small></span><span className="p-stream-aside">{lead.created_at ? `Saved ${dateLabel(lead.created_at)}` : "Date not provided"}<ArrowRight size={16} /></span></button>)}</div></section>}
    </>}
  </section>;
}
