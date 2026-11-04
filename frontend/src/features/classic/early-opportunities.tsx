"use client";

import { useState, type FormEvent } from "react";
import { Globe2, Loader2 } from "lucide-react";
import { researchEarlyOpportunities, type EarlyOpportunityResult } from "@/lib/api";
import { getInternetResearchErrorMessage } from "./errors";
import { EmptyState, Panel, StatusPill } from "./ui";

type State =
  | { status: "idle" | "loading" }
  | { status: "error"; message: string }
  | { status: "success"; result: EarlyOpportunityResult };

function SourceLink({ url, label }: { url: string; label: string }) {
  let safeUrl: string | null = null;
  try {
    const parsed = new URL(url);
    if (parsed.protocol === "https:" || parsed.protocol === "http:") safeUrl = parsed.href;
  } catch {
    // A missing or malformed source remains visible as a gap.
  }
  return safeUrl ? (
    <a href={safeUrl} target="_blank" rel="noreferrer" className="break-all text-xs font-semibold text-cyan-200 hover:text-white">
      {label}: {safeUrl}
    </a>
  ) : <span className="text-xs text-amber-200">{label}: not available</span>;
}

export function EarlyOpportunitiesPanel({ showDemoNote = false }: { showDemoNote?: boolean }) {
  const [query, setQuery] = useState("Find UK organisations with existing estates and public signals of a potential need for ongoing fire and security maintenance, inspections or service renewal. Identify who owns maintenance and how to engage.");
  const [state, setState] = useState<State>({ status: "idle" });
  async function submit(event: FormEvent) {
    event.preventDefault();
    const brief = query.trim();
    if (brief.length < 8 || state.status === "loading") return;
    setState({ status: "loading" });
    try {
      setState({ status: "success", result: await researchEarlyOpportunities(brief) });
    } catch (error) {
      setState({ status: "error", message: getInternetResearchErrorMessage(error) });
    }
  }
  return (
    <Panel title="Early Opportunity Research" action={<StatusPill tone="cyan" label="Public business signals" />}>
      <p className="text-sm leading-6 text-slate-300">Look for public signals of ongoing fire and security maintenance needs across existing estates, including inspections, compliance, service renewal or supplier changes. Explore who may own the service and how to begin a useful conversation. A signal alone does not confirm a requirement or upcoming renewal.</p>
      {showDemoNote && <p className="mt-2 text-sm leading-6 text-amber-100">This separate search sends your brief to the external model and searches the public web. It requires a backend API key; the synthetic Living demo deliberately disables that key. Use the configured backend to run live research.</p>}
      <form onSubmit={submit} className="mt-4 grid gap-3">
        <label className="grid gap-1.5">
          <span className="text-xs font-semibold text-slate-500">Maintenance research brief: sector, region or organisation</span>
          <textarea value={query} onChange={(event) => setQuery(event.target.value)} minLength={8} maxLength={600} required rows={3} className="min-h-24 rounded-md border border-white/10 bg-[#111a20] px-3 py-3 text-sm leading-6 text-white placeholder:text-slate-500" />
        </label>
        <div>
          <button type="submit" disabled={query.trim().length < 8 || state.status === "loading"} className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-mitie-lime/30 bg-mitie-lime px-3 py-2 text-sm font-bold text-[#07100b] transition hover:bg-[#d8ff62] disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/10 disabled:text-slate-400">
            {state.status === "loading" ? <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" /> : <Globe2 aria-hidden="true" className="h-4 w-4" />}
            {state.status === "loading" ? "Researching signals" : "Find early opportunities"}
          </button>
        </div>
      </form>
      {state.status === "loading" && <p className="mt-4 text-sm text-cyan-100" role="status">Searching public sources and preparing engagement ideas…</p>}
      {state.status === "error" && <p className="mt-4 rounded-md border border-amber-300/20 bg-amber-400/10 p-4 text-sm text-amber-100" role="alert">{state.message}</p>}
      {state.status === "success" && (
        <div className="mt-4 grid gap-4">
          <p className="text-sm leading-6 text-slate-300">{state.result.summary}</p>
          {state.result.findings.length === 0 ? <EmptyState title="No sufficiently evidenced signals found" message="Try another sector, location or organisation. No opportunity has been created." /> : state.result.findings.map((finding, index) => (
            <article key={`${finding.organisation}-${index}`} className="rounded-md border border-white/10 bg-[#111a20] p-4">
              <h3 className="text-lg font-semibold text-white">{finding.organisation}</h3>
              <div className="mt-3 grid gap-4 md:grid-cols-2">
                <div><h4 className="text-xs font-black uppercase text-slate-500">Observed signal{finding.signal_date ? ` · ${finding.signal_date}` : " · date unknown"}</h4><p className="mt-1 text-sm leading-6 text-slate-300">{finding.signal}</p><SourceLink url={finding.signal_source_url} label="Signal source" /></div>
                <div><h4 className="text-xs font-black uppercase text-slate-500">Possible need · inferred</h4><p className="mt-1 text-sm leading-6 text-slate-300">{finding.inferred_need}</p><p className="mt-2 text-sm leading-6 text-slate-300">{finding.fit_and_timing}</p></div>
                <div><h4 className="text-xs font-black uppercase text-slate-500">Who to approach</h4><p className="mt-1 text-sm leading-6 text-slate-300">{finding.contact_name ? `${finding.contact_name} · ` : "Named contact unknown · "}{finding.contact_role}</p><SourceLink url={finding.contact_source_url} label="Contact source" /></div>
                <div><h4 className="text-xs font-black uppercase text-slate-500">How to engage</h4><p className="mt-1 text-sm leading-6 text-slate-300">{finding.engagement_opener}</p><p className="mt-2 text-sm leading-6 text-cyan-100">{finding.discovery_question}</p><p className="mt-2 text-sm font-semibold leading-6 text-mitie-lime">{finding.next_action}</p></div>
              </div>
              <p className="mt-4 border-t border-white/10 pt-3 text-sm leading-6 text-amber-100"><strong>To verify:</strong> {finding.uncertainties}</p>
            </article>
          ))}
          {state.result.limitations.length > 0 && <div className="rounded-md border border-amber-300/20 bg-amber-400/10 p-4"><h3 className="text-sm font-semibold text-amber-100">Research limitations</h3><ul className="mt-2 list-disc pl-5 text-sm leading-6 text-amber-100/80">{state.result.limitations.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul></div>}
          <p className="text-xs text-slate-500">Results are for review and have not been added to the pipeline. Verify sources and contacts before engagement.</p>
        </div>
      )}
    </Panel>
  );
}
