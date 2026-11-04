"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { ArrowRight, Compass, Globe2, Loader2, Sparkles } from "lucide-react";
import { getApiBaseUrl } from "@/lib/api";
import { safeSource } from "./api";
import { Badge, Button, Empty, SectionHeading } from "./ui";
import { ResearchLibrary } from "./research-library";
import { ImportedObservationDetails, type ObservationOrigin } from "./observation-origin";
import { SourceDiscoverySummary, type SourceDiscovery } from "./source-discovery-summary";
import { publicResearchExport, publicSourceLabel } from "./public-source-labels";
import { EstateLookupSummary, type EstateLookup } from "./estate-lookup-summary";

type ResearchObservation = ObservationOrigin & {
  id: string;
  source_url: string;
  source_title: string;
  published_date: string | null;
  fact: string;
};
type ResearchOpportunity = {
  organisation: string;
  location: string;
  headline: string;
  thesis: string;
  potential_solution?: string;
  supporting_observation_ids: string[];
  counter_observation_ids: string[];
  unknowns: string[];
  contact_name: string;
  contact_role: string;
  contact_observation_ids: string[];
  engagement: string;
  verification_action: string;
};
type PublicResearchResult = {
  brief: string;
  model: string;
  searches: { query: string; status: "completed" | "failed"; detail: string; web_queries?: string[]; web_sources?: string[]; stage?: "initial" | "follow_up" | "planned_fallback" }[];
  observations: ResearchObservation[];
  opportunities: ResearchOpportunity[];
  limitations: string[];
  source_discovery?: SourceDiscovery | null;
  estate_lookup?: EstateLookup | null;
};
type State =
  | { status: "idle" | "loading" }
  | { status: "error"; message: string }
  | { status: "success"; result: PublicResearchResult };
type ResearchJob = {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  progress: { phase: string; planned: number; completed: number; failed: number; active_queries: string[] };
  result: PublicResearchResult | null;
  error: string | null;
  saved_run_id?: number | null;
  save_error?: string | null;
};
const JOB_KEY = "misi-public-research-job";
const starterBriefs = [
  {
    label: "Estate change",
    detail: "New sites, refurbishments and changes in systems",
    brief: "Find UK organisations where public estate changes, refurbishments, acquisitions or changes to fire and security systems could create a future need for maintenance. Connect independent observations, check existing arrangements and contrary evidence, suggest a relevant service to explore, and identify who to approach and what to ask. Do not assume a buying need.",
  },
  {
    label: "Service friction",
    detail: "Repeated disruption, complaints or service pressure",
    brief: "Find UK organisations with public observations that could indicate disruption or pressure around fire and security systems, such as repeated attendances, reported faults or relevant complaints. Look for independent context and counter-evidence; do not attribute fault to a supplier or assert poor maintenance. Suggest a helpful service conversation and who could own it.",
  },
  {
    label: "Complex estates",
    detail: "Multiple sites, systems and maintenance coordination",
    brief: "Investigate UK organisations with complex multi-site estates where public evidence suggests a possible need to coordinate fire and security maintenance, inspections or system support. Look for observable effects and alternative explanations, not just tenders. Suggest a practical solution to test, the likely service owner and a useful first question.",
  },
  {
    label: "Choose your market",
    detail: "A flexible starting point for any sector or service",
    brief: "Find organisations in the UK with public signals that could suggest an unadvertised opportunity for [service] in [sector or location]. Connect observable signals to a cautious hypothesis, seek alternative explanations and evidence against it, and suggest a relevant solution, contact role and first question. Separate unknowns from facts.",
  },
];
function searchStageLabel(stage: PublicResearchResult["searches"][number]["stage"]): string {
  if (stage === "follow_up") return "Follow-up pass";
  if (stage === "planned_fallback") return "Planned fallback pass";
  return "Initial pass";
}
function downloadResearch(result: PublicResearchResult) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(publicResearchExport(result), null, 2)], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = "misi-public-research.json";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function Evidence({
  label,
  ids,
  observations,
}: {
  label: string;
  ids: string[];
  observations: ResearchObservation[];
}) {
  if (!ids.length) return null;
  const byId = new Map(observations.map((item) => [item.id, item]));
  return (
    <div className="mt-4">
      <h4 className="text-xs font-bold uppercase tracking-wide text-[var(--misi-muted)]">{label}</h4>
      <ul className="mt-2 grid gap-2">
        {ids.map((id) => {
          const observation = byId.get(id);
          if (!observation) return <li key={id} className="text-sm text-[#825929]">Source {id} unavailable; verify before using.</li>;
          const url = safeSource(observation.source_url);
          return (
            <li key={id} className="rounded-lg border border-[var(--misi-border)] bg-[var(--misi-surface-secondary)] p-3">
              <p className="text-sm leading-6 text-[var(--misi-ink)]">{observation.fact}</p>
              <p className="mt-1 text-xs text-[var(--misi-muted)]">{observation.source_title || "Source"} · {observation.published_date || "Date not provided"}</p>
              <ImportedObservationDetails observation={observation} />
              {url ? <a className="mt-1 inline-block break-all text-xs font-semibold text-[var(--misi-accent)] underline decoration-[var(--misi-border)] hover:text-[var(--misi-ink)]" href={url} target="_blank" rel="noreferrer">View source <span className="sr-only">{observation.source_title}</span></a> : <p className="text-xs text-[#825929]">Source link unavailable</p>}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function PublicResearch() {
  const [brief, setBrief] = useState("Find UK organisations with public signals that their fire and security maintenance arrangements may need review. Connect independent evidence and suggest who to approach and how.");
  const [maxSearches, setMaxSearches] = useState(6);
  const [includeInbox, setIncludeInbox] = useState(false);
  const [includeEstateLookup, setIncludeEstateLookup] = useState(false);
  const [estatePostcode, setEstatePostcode] = useState("");
  const [includeRightClick, setIncludeRightClick] = useState(false);
  const [rightclickIdentifier, setRightclickIdentifier] = useState("");
  const [rightclickDataset, setRightclickDataset] = useState("planning-application");
  const [state, setState] = useState<State>({ status: "idle" });
  const [jobId, setJobId] = useState<string | null>(null);
  const [progress, setProgress] = useState<ResearchJob["progress"] | null>(null);
  const [trackingWarning, setTrackingWarning] = useState("");
  const [libraryRevision, setLibraryRevision] = useState(0);
  const [saveMessage, setSaveMessage] = useState("");
  const [unsavedJobId, setUnsavedJobId] = useState<string | null>(null);
  const refreshSavedResearch = useCallback(() => setLibraryRevision((value) => value + 1), []);

  async function saveResearch(id: string) {
    try {
      const response = await fetch(`${getApiBaseUrl()}/api/research-dossiers/from-job/${encodeURIComponent(id)}`, { method: "POST" });
      if (!response.ok) throw new Error(`Save failed (${response.status})`);
      setUnsavedJobId(null);
      sessionStorage.removeItem(JOB_KEY);
      setSaveMessage("Research saved to your workspace.");
      setLibraryRevision((value) => value + 1);
    } catch {
      setUnsavedJobId(id);
      setSaveMessage("Research could not be saved yet. Retry while this job is available, or download a copy.");
    }
  }

  useEffect(() => {
    function prepare(event: Event) {
      const detail = (event as CustomEvent<{ brief?: unknown }>).detail;
      if (typeof detail?.brief === "string" && detail.brief.length <= 1200) setBrief(detail.brief);
    }
    window.addEventListener("misi:research-brief", prepare);
    return () => window.removeEventListener("misi:research-brief", prepare);
  }, []);

  useEffect(() => {
    const saved = sessionStorage.getItem(JOB_KEY);
    if (saved) {
      setJobId(saved);
      setState({ status: "loading" });
    }
  }, []);

  useEffect(() => {
    if (!jobId) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const controller = new AbortController();
    async function poll() {
      try {
        const response = await fetch(`${getApiBaseUrl()}/api/intelligence/universal-research-jobs/${encodeURIComponent(jobId!)}`, { cache: "no-store", signal: controller.signal });
        if (response.status === 404) {
          sessionStorage.removeItem(JOB_KEY);
          if (!stopped) { setJobId(null); setState({ status: "error", message: "The research job expired or the server restarted. Start a new search." }); }
          return;
        }
        if (!response.ok) throw new Error(`Status check failed (${response.status}).`);
        const job: ResearchJob = await response.json();
        if (stopped) return;
        setProgress(job.progress);
        setTrackingWarning("");
        if (job.status === "completed") {
          setJobId(null);
          setState(job.result ? { status: "success", result: job.result } : { status: "error", message: "The job finished without a result." });
          if (job.result) {
            if (job.saved_run_id) {
              sessionStorage.removeItem(JOB_KEY);
              setSaveMessage("Research saved to your workspace.");
              setLibraryRevision((value) => value + 1);
            } else void saveResearch(job.job_id);
          }
          return;
        }
        if (job.status === "failed") {
          sessionStorage.removeItem(JOB_KEY);
          setJobId(null);
          setState({ status: "error", message: job.error || "The research job failed." });
          return;
        }
        timer = setTimeout(poll, 2000);
      } catch (error) {
        if (stopped) return;
        setTrackingWarning("Status temporarily unavailable; retrying. The job may still be running.");
        timer = setTimeout(poll, 5000);
      }
    }
    void poll();
    return () => { stopped = true; controller.abort(); if (timer) clearTimeout(timer); };
  }, [jobId]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const requestBrief = brief.trim();
    if (requestBrief.length < 8 || state.status === "loading") return;
    setState({ status: "loading" });
    setProgress(null);
    setTrackingWarning("");
    setSaveMessage("");
    setUnsavedJobId(null);
    try {
      const response = await fetch(`${getApiBaseUrl()}/api/intelligence/universal-research-jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ brief: requestBrief, max_searches: maxSearches, ...(includeInbox ? { include_inbox: true } : {}), ...(includeEstateLookup ? { include_estate_lookup: true, estate_postcode: estatePostcode.trim() } : {}), ...(includeRightClick ? { include_rightclick: true, ...(rightclickIdentifier.trim() ? { rightclick_identifier: rightclickIdentifier.trim(), rightclick_dataset: rightclickDataset } : {}) } : {}) }),
        cache: "no-store",
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(typeof payload?.detail === "string" ? payload.detail : `Research failed (${response.status}).`);
      }
      const job: ResearchJob = await response.json();
      sessionStorage.setItem(JOB_KEY, job.job_id);
      setProgress(job.progress);
      setJobId(job.job_id);
    } catch (error) {
      setState({ status: "error", message: error instanceof Error ? error.message : "The research could not be completed." });
    }
  }
  return (
    <>
    <section className="m-results mt-5" aria-label="Public opportunity research">
      <div className="overflow-hidden rounded-xl border border-[var(--misi-border)] bg-[var(--misi-surface)] text-[var(--misi-ink)]">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--misi-border)] px-5 py-4 sm:px-6">
          <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[.16em] text-[var(--misi-muted)]"><Compass size={14} aria-hidden="true" /> Public opportunity research</p>
          <span className="text-[11px] font-medium tracking-wide text-[var(--misi-muted)]">AI research · Public sources</span>
        </div>
        <div className="px-5 pb-6 pt-5 sm:px-6">
          <div className="max-w-3xl"><h2 className="max-w-2xl text-[18px] font-semibold leading-[1.35] tracking-[-.015em] text-[var(--misi-ink)]">Investigate a market</h2><p className="mt-1 max-w-2xl text-sm leading-6 text-[var(--misi-muted)]">Start with a question. MiSi investigates public signals and surfaces evidence to review.</p></div>
          <form onSubmit={submit} className="mt-5">
            <div className="grid gap-5">
              <div>
                <div className="flex flex-wrap items-baseline justify-between gap-2"><label htmlFor="public-research-brief" className="text-sm font-semibold text-[var(--misi-ink)]">Research brief</label><span className="text-xs text-[var(--misi-muted)]">Your question, in your words</span></div>
                <textarea id="public-research-brief" style={{ background: "var(--misi-surface-secondary)", color: "var(--misi-ink)", borderColor: "var(--misi-border)", fontSize: "14px", lineHeight: "1.6", padding: "12px" }} value={brief} onChange={(event) => setBrief(event.target.value)} minLength={8} maxLength={1200} rows={3} required disabled={state.status === "loading"} placeholder="For example: Find signals of fire and security maintenance pressure in UK logistics and retail estates." className="mt-3 block min-h-[108px] w-full resize-y rounded-md border border-[var(--misi-border)] bg-[var(--misi-surface-secondary)] px-4 py-4 text-[15px] leading-7 text-[var(--misi-ink)] outline-none transition focus:border-[var(--misi-accent)] focus:ring-2 focus:ring-[var(--misi-accent)]/30 disabled:opacity-60" />
                <details className="mt-4 border-b border-[var(--misi-border)] pb-4">
                  <summary className="cursor-pointer text-sm font-semibold text-[var(--misi-accent)] underline decoration-[var(--misi-border)] underline-offset-4 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--misi-accent)]">Need a starting point? Choose a research angle</summary>
                  <p className="mt-3 text-xs leading-5 text-[var(--misi-muted)]">Selecting an example replaces the brief below. Edit the sector, location and service before you run it.</p>
                  <div className="mt-3 grid gap-x-5 sm:grid-cols-2">
                    {starterBriefs.map((item) => <button key={item.label} type="button" disabled={state.status === "loading"} onClick={() => setBrief(item.brief)} className="border-t border-[var(--misi-border)] py-3 text-left transition hover:text-[var(--misi-accent)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--misi-accent)] disabled:opacity-50"><span className="block text-sm font-semibold">{item.label}</span><span className="mt-1 block text-xs leading-5 text-[var(--misi-muted)]">{item.detail}</span></button>)}
                  </div>
                </details>
                <div className="mt-5 flex flex-wrap items-end justify-between gap-4">
                  <div><label className="block text-xs font-semibold text-[var(--misi-muted)]" htmlFor="public-research-breadth">Research breadth</label><select id="public-research-breadth" style={{ background: "var(--misi-surface-secondary)", color: "var(--misi-ink)", borderColor: "var(--misi-border)", fontSize: "14px", padding: "10px 28px 10px 12px" }} className="mt-2 min-w-[220px] rounded-md border border-[var(--misi-border)] bg-[var(--misi-surface-secondary)] px-3 py-2.5 text-sm text-[var(--misi-ink)] outline-none focus:border-[var(--misi-accent)]" value={maxSearches} onChange={(event) => setMaxSearches(Number(event.target.value))} disabled={state.status === "loading"}>
                    <option value={3}>Quick · up to 3 research passes</option><option value={6}>Broader · up to 6 research passes</option><option value={12}>Deep · up to 12 research passes</option>
                  </select></div>
                  <button type="submit" disabled={state.status === "loading" || brief.trim().length < 8} className="inline-flex min-h-[40px] items-center justify-center gap-3 rounded-lg bg-[var(--misi-accent)] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[var(--misi-accent-hover)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--misi-accent)] disabled:cursor-not-allowed disabled:opacity-50">
                    {state.status === "loading" ? <Loader2 className="animate-spin" size={16} aria-hidden="true" /> : <Globe2 size={16} aria-hidden="true" />}{state.status === "loading" ? "Researching public sources" : "Research opportunities"} <ArrowRight size={16} aria-hidden="true" />
                  </button>
                </div>
                <p className="mt-4 max-w-2xl text-xs leading-5 text-[var(--misi-muted)]">Your brief is sent to the configured model for public web research. Each pass may run multiple web queries. Model and search use incur API costs; more passes can take longer. Findings require review.</p>
              </div>
              <div className="grid gap-x-6 border-t border-[var(--misi-border)] pt-4 md:grid-cols-3">
                <div className="flex items-baseline justify-between gap-2 md:col-span-3"><p className="text-sm font-semibold text-[var(--misi-ink)]">Add context</p><span className="text-[11px] uppercase tracking-[.13em] text-[var(--misi-muted)]">Optional</span></div>
                <p className="mt-1 text-xs leading-5 text-[var(--misi-muted)] md:col-span-3">Choose the sources you would like to include.</p>
                <div className="mt-4 border-t border-[var(--misi-border)] py-4">
                  <label className="flex items-start gap-3 text-sm font-medium text-[var(--misi-ink)]" htmlFor="public-research-include-inbox"><input id="public-research-include-inbox" type="checkbox" checked={includeInbox} onChange={(event) => setIncludeInbox(event.target.checked)} disabled={state.status === "loading"} aria-describedby="public-research-inbox-note" className="mt-1 h-4 w-4 shrink-0 accent-[var(--misi-accent)]" /><span>Include matching evidence from your inbox</span></label>
                  <p id="public-research-inbox-note" className="mt-2 pl-7 text-xs leading-5 text-[var(--misi-muted)]">Matching inbox statements will be sent to the configured AI provider. Check they contain only public information before including them. Organisation-name matches and source claims remain unverified.</p>
                </div>
                <div className="mt-4 border-t border-[var(--misi-border)] py-4">
                  <label className="flex items-start gap-3 text-sm font-medium text-[var(--misi-ink)]" htmlFor="public-research-include-rightclick"><input id="public-research-include-rightclick" type="checkbox" checked={includeRightClick} onChange={(event) => setIncludeRightClick(event.target.checked)} disabled={state.status === "loading"} aria-describedby="public-research-rightclick-note" className="mt-1 h-4 w-4 shrink-0 accent-[var(--misi-accent)]" /><span>Include England planning context</span></label>
                  <p id="public-research-rightclick-note" className="mt-2 pl-7 text-xs leading-5 text-[var(--misi-muted)]">Include the reviewed Planning Data England capability alongside this brief. Its description and any returned records will be sent to the configured AI provider. Available sources and execution status will be shown; discovery does not grant broad access.</p>
                  {includeRightClick && <div className="mt-3 grid gap-3 pl-7">
                    <label htmlFor="rightclick-research-identifier" className="text-xs text-[var(--misi-muted)]">UPRN or postcode, optional<input id="rightclick-research-identifier" style={{ background: "var(--misi-surface-secondary)", color: "var(--misi-ink)", borderColor: "var(--misi-border)", fontSize: "14px" }} value={rightclickIdentifier} onChange={(event) => setRightclickIdentifier(event.target.value)} disabled={state.status === "loading"} maxLength={20} placeholder="For example 10008315764" className="mt-1 block w-full rounded-md border border-[var(--misi-border)] bg-[var(--misi-surface-secondary)] px-3 py-2 text-sm text-[var(--misi-ink)]" /></label>
                    <label htmlFor="rightclick-research-dataset" className="text-xs text-[var(--misi-muted)]">England planning context<select id="rightclick-research-dataset" style={{ background: "var(--misi-surface-secondary)", color: "var(--misi-ink)", borderColor: "var(--misi-border)", fontSize: "14px" }} aria-label="Planning dataset in England" value={rightclickDataset} onChange={(event) => setRightclickDataset(event.target.value)} disabled={state.status === "loading"} className="mt-1 block w-full rounded-md border border-[var(--misi-border)] bg-[var(--misi-surface-secondary)] px-3 py-2 text-sm text-[var(--misi-ink)]"><option value="planning-application">Planning applications</option><option value="brownfield-land">Brownfield land</option><option value="conservation-area">Conservation areas</option></select></label>
                    <p className="text-xs leading-5 text-[var(--misi-muted)]">Providing an identifier queries the selected approved source. Coverage varies; an empty result does not mean no activity, and a record is not evidence of demand.</p>
                  </div>}
                </div>
                <div className="mt-4 border-t border-[var(--misi-border)] py-4"><label className="flex items-start gap-3 text-sm font-medium text-[var(--misi-ink)]" htmlFor="public-research-include-estate"><input id="public-research-include-estate" type="checkbox" checked={includeEstateLookup} onChange={(event) => setIncludeEstateLookup(event.target.checked)} disabled={state.status === "loading"} aria-describedby="public-research-estate-note" className="mt-1 h-4 w-4 shrink-0 accent-[var(--misi-accent)]" /><span>Check the UK food establishments register</span></label><p id="public-research-estate-note" className="mt-2 pl-7 text-xs leading-5 text-[var(--misi-muted)]">With your permission, the postcode is sent to the public food regulator and up to five returned records are sent to your AI provider. These are site context, not evidence of maintenance needs or a match to a customer. An empty result does not establish absence.</p>{includeEstateLookup && <label htmlFor="public-research-estate-postcode" className="mt-3 block pl-7 text-xs text-[var(--misi-muted)]">Full UK postcode<input id="public-research-estate-postcode" style={{ background: "var(--misi-surface-secondary)", color: "var(--misi-ink)", borderColor: "var(--misi-border)", fontSize: "14px" }} value={estatePostcode} onChange={(event) => setEstatePostcode(event.target.value)} required maxLength={8} disabled={state.status === "loading"} placeholder="For example SW1A 1AA" className="mt-1 block w-full max-w-xs rounded-md border border-[var(--misi-border)] bg-[var(--misi-surface-secondary)] px-3 py-2 text-sm text-[var(--misi-ink)]" /></label>}</div>
              </div>
            </div>
          </form>
        </div>
      </div>
      {state.status === "loading" && <div className="m-notice mt-3" role="status">
        <p>{progress?.phase ? `Research stage: ${progress.phase}.` : "Starting research."} {progress?.planned ? `${progress.completed} completed, ${progress.failed} failed of ${progress.planned} planned research passes.` : "Planning research passes and reviewing sources."} Where useful, follow-up passes investigate what the first pass found. This may take a few minutes.</p>
        {!!progress?.active_queries.length && <ul className="mt-2 list-disc pl-5 text-sm">{progress.active_queries.map((query, i) => <li key={`${query}-${i}`}>{query}</li>)}</ul>}
        {trackingWarning && <p className="mt-2">{trackingWarning}</p>}
        <p className="m-small mt-2">You can return to this view in this tab. Jobs do not survive a server restart.</p>
      </div>}
      {state.status === "error" && <p className="m-error mt-3" role="alert">Research could not be completed: {publicSourceLabel(state.message)}</p>}
      {state.status === "success" && <div className="mt-5 grid gap-4" aria-live="polite">
        <div className="m-between flex-wrap gap-2">
          <SectionHeading title={`${state.result.opportunities.length} ${state.result.opportunities.length === 1 ? "lead" : "leads"} to investigate`} detail="These are hypotheses supported by the sources shown, not confirmed demand or procurement." />
          <div className="flex flex-wrap items-center gap-2"><Badge tone="neutral">{state.result.model}</Badge><Button onClick={() => downloadResearch(state.result)}>Download research JSON</Button></div>
        </div>
        <p className="m-small m-muted">Research brief: {state.result.brief}</p>
        {saveMessage && <div className="flex flex-wrap items-center gap-3 text-sm text-[var(--misi-accent)]" role="status"><Sparkles size={15} aria-hidden="true" /> {saveMessage} {unsavedJobId && <Button onClick={() => void saveResearch(unsavedJobId)}>Retry saving</Button>}</div>}
        {state.result.source_discovery && <SourceDiscoverySummary discovery={state.result.source_discovery} />}
        {state.result.estate_lookup && <EstateLookupSummary lookup={state.result.estate_lookup} />}
        {state.result.searches.some((search) => search.status === "failed") && <p className="m-error" role="status">{state.result.searches.filter((search) => search.status === "failed").length} planned research {state.result.searches.filter((search) => search.status === "failed").length === 1 ? "pass failed" : "passes failed"}. Results are partial; see Research passes and coverage for details.</p>}
        {state.result.opportunities.length === 0 ? <Empty title="No sufficiently supported opportunities found">Try a more specific sector, geography, organisation or maintenance issue. The search may not cover every source.</Empty> : state.result.opportunities.map((opportunity, index) => (
          <article className="m-surface rounded-xl border border-[var(--misi-border)] p-5" key={`${opportunity.organisation}-${index}`}>
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div><p className="m-eyebrow">{opportunity.organisation}{opportunity.location ? ` · ${opportunity.location}` : ""}</p><h3 className="mt-1 text-lg font-semibold text-[var(--misi-ink)]">{opportunity.headline}</h3></div>
              <Badge tone="amber">Hypothesis</Badge>
            </div>
            <p className="mt-3 text-sm leading-6 text-[var(--misi-ink)]">{opportunity.thesis}</p>
            {opportunity.potential_solution && <div className="mt-4 rounded-lg border border-[var(--misi-border)] bg-[var(--misi-surface-secondary)] p-3"><h4 className="text-xs font-bold uppercase tracking-wide text-[var(--misi-accent)]">Potential solution to explore</h4><p className="mt-2 text-sm leading-6 text-[var(--misi-ink)]">{opportunity.potential_solution}</p><p className="mt-2 text-xs leading-5 text-[var(--misi-muted)]">A suggestion to test with the customer, not a confirmed requirement or delivery capability.</p></div>}
            <Evidence label="Evidence" ids={opportunity.supporting_observation_ids} observations={state.result.observations} />
            <Evidence label="Counter-evidence or alternative context" ids={opportunity.counter_observation_ids} observations={state.result.observations} />
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <div><h4 className="text-xs font-bold uppercase tracking-wide text-[var(--misi-muted)]">Who to approach</h4><p className="mt-1 text-sm leading-6 text-[var(--misi-ink)]">{[opportunity.contact_name, opportunity.contact_role].filter(Boolean).join(" · ") || "Contact not established"}</p><Evidence label="Contact evidence" ids={opportunity.contact_observation_ids} observations={state.result.observations} /></div>
              <div><h4 className="text-xs font-bold uppercase tracking-wide text-[var(--misi-muted)]">How to engage</h4><p className="mt-1 text-sm leading-6 text-[var(--misi-ink)]">{opportunity.engagement}</p><p className="mt-2 text-sm font-semibold text-[var(--misi-accent)]">{opportunity.verification_action}</p></div>
            </div>
            {opportunity.unknowns.length > 0 && <div className="mt-4 border-t border-[var(--misi-border)] pt-3"><h4 className="text-xs font-bold uppercase tracking-wide text-[#825929]">What remains unknown</h4><ul className="mt-2 list-disc pl-5 text-sm leading-6 text-[#825929]">{opportunity.unknowns.map((item, i) => <li key={`${item}-${i}`}>{item}</li>)}</ul></div>}
          </article>
        ))}
        <details className="m-surface rounded-xl border border-[var(--misi-border)] p-4">
          <summary className="cursor-pointer font-semibold text-[var(--misi-ink)]">Research passes and coverage <span className="m-small m-muted">· {state.result.searches.length} passes</span></summary>
          <p className="m-small m-muted mt-2">Each pass can run multiple web queries. Reported queries and returned URLs reflect this run; they do not establish complete coverage of the UK or of the web.</p>
          <ul className="mt-3 grid gap-2">{state.result.searches.map((search, i) => <li key={`${search.query}-${i}`} className="text-sm text-[var(--misi-ink)]">
            <strong>{searchStageLabel(search.stage)} · {search.status === "completed" ? "Completed" : "Failed"}:</strong> {search.query}{search.detail ? ` — ${search.detail}` : ""}
            {!!search.web_queries?.length && <><p className="mt-1 text-xs text-[var(--misi-muted)]">Web queries reported by the search tool:</p><ul className="mt-1 list-disc pl-5 text-xs text-[var(--misi-muted)]">{search.web_queries.map((query, j) => <li key={`${query}-${j}`}>{query}</li>)}</ul></>}
            {!!search.web_sources?.length && <details className="mt-2 rounded border border-[var(--misi-border)] px-3 py-2">
              <summary className="cursor-pointer text-xs text-[var(--misi-accent)]">URLs returned by search · {search.web_sources.length}</summary>
              <p className="mt-2 text-xs text-[var(--misi-muted)]">These URLs were returned by the search tool. Their contents and any claims have not been independently verified.</p>
              <ul className="mt-2 grid gap-1">{search.web_sources.map((source, j) => {
                const url = safeSource(source);
                return <li key={`${source}-${j}`} className="break-all text-xs">{url ? <a href={url} target="_blank" rel="noreferrer" className="text-[var(--misi-accent)] underline decoration-[var(--misi-border)] hover:text-[var(--misi-ink)]">{url}</a> : <span className="text-[#825929]">Invalid source URL: {source}</span>}</li>;
              })}</ul>
            </details>}
          </li>)}</ul>
          {state.result.limitations.length > 0 && <><h4 className="mt-4 font-semibold text-[#825929]">Limitations</h4><ul className="mt-2 list-disc pl-5 text-sm leading-6 text-[#825929]">{state.result.limitations.map((item, i) => <li key={`${item}-${i}`}>{publicSourceLabel(item)}</li>)}</ul></>}
        </details>
        {state.result.observations.length > 0 && <details className="m-surface rounded-xl border border-[var(--misi-border)] p-4">
          <summary className="cursor-pointer font-semibold text-[var(--misi-ink)]">All gathered observations <span className="m-small m-muted">· {state.result.observations.length} source observations</span></summary>
          <p className="m-small m-muted mt-2">These were gathered during this search. Source links and the accuracy, date and relevance of each claim still need review.</p>
          <Evidence label="Observations" ids={state.result.observations.map((item) => item.id)} observations={state.result.observations} />
        </details>}
        <p className="m-small m-muted">Research has not been saved to the pipeline or sent to any contact. Verify sources, identities and service requirements before engagement.</p>
      </div>}
    </section>
    <ResearchLibrary revision={libraryRevision} onResearchSaved={refreshSavedResearch} />
    </>
  );
}
