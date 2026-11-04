"use client";

import {
  convertMarketSignal,
  researchOpportunity,
  runInternetResearch,
  type InternetIntelligenceRequest,
  type InternetIntelligenceType,
  type MarketSignal,
  type Opportunity,
} from "@/lib/api";
import { compactCurrency, percentage, shortDate } from "@/lib/format";
import {
  AlertTriangle,
  ChevronRight,
  Compass,
  Globe2,
  Loader2,
  Radar,
  ShieldAlert,
} from "lucide-react";
import { useState } from "react";
import {
  getInternetResearchErrorMessage,
  getMarketSignalConversionErrorMessage,
  getOpportunityResearchErrorMessage,
  internetTypeLabel,
} from "./errors";
import {
  confidenceTone,
  fitToneForSignal,
  researchFieldToView,
} from "./evidence";
import { BriefingLane } from "./executive";
import { EarlyOpportunitiesPanel } from "./early-opportunities";
import { SkeletonLine } from "./research";
import {
  InternetResearchState,
  MarketSignalConversionState,
  OpportunityResearchState,
  internetIntelligenceTypes,
} from "./shared";
import {
  ConfidenceOrbit,
  DetailField,
  EmptyState,
  IntelligenceMetric,
  Panel,
  SourceRow,
  StatusPill,
} from "./ui";

export function MarketRadarView({
  marketSignals,
  onDataChanged,
  onSelectOpportunity,
}: {
  marketSignals: MarketSignal[];
  onDataChanged: () => void;
  onSelectOpportunity: (opportunity: Opportunity) => void;
}) {
  const [researchType, setResearchType] =
    useState<InternetIntelligenceType>("market_radar");
  const [query, setQuery] = useState(
    "UK fire and security tender opportunities, competitor movement and buyer compliance signals",
  );
  const [researchState, setResearchState] = useState<InternetResearchState>({
    status: "idle",
  });
  const [opportunityResearchState, setOpportunityResearchState] =
    useState<OpportunityResearchState>({
      status: "idle",
    });
  const [conversionStates, setConversionStates] = useState<
    Record<number, MarketSignalConversionState>
  >({});
  const [opportunityResearchQuery, setOpportunityResearchQuery] = useState(
    "University of Leeds fire and security tender",
  );
  const isResearchLoading = researchState.status === "loading";
  const isOpportunityResearchLoading =
    opportunityResearchState.status === "loading";

  async function handleRunResearch() {
    const trimmedQuery = query.trim();
    if (trimmedQuery.length < 8 || isResearchLoading) {
      return;
    }

    setResearchState({ status: "loading" });
    const request: InternetIntelligenceRequest = {
      intelligence_type: researchType,
      query: trimmedQuery,
    };

    try {
      const result = await runInternetResearch(request);
      setResearchState({ status: "success", result });
    } catch (error: unknown) {
      setResearchState({
        status: "error",
        message: getInternetResearchErrorMessage(error),
      });
    }
  }

  async function handleResearchOpportunity() {
    const trimmedQuery = opportunityResearchQuery.trim();
    if (trimmedQuery.length < 4 || isOpportunityResearchLoading) {
      return;
    }

    setOpportunityResearchState({ status: "loading" });

    try {
      const result = await researchOpportunity({
        query: trimmedQuery,
        create_opportunity: true,
      });
      setOpportunityResearchState({ status: "success", result });
      onDataChanged();
    } catch (error: unknown) {
      setOpportunityResearchState({
        status: "error",
        message: getOpportunityResearchErrorMessage(error),
      });
    }
  }

  async function handleConvertSignal(signal: MarketSignal) {
    const currentState = conversionStates[signal.id];
    if (currentState?.status === "loading") {
      return;
    }

    setConversionStates((current) => ({
      ...current,
      [signal.id]: { status: "loading" },
    }));

    try {
      const result = await convertMarketSignal(signal.id);
      setConversionStates((current) => ({
        ...current,
        [signal.id]: { status: "success", result },
      }));
      onDataChanged();
    } catch (error: unknown) {
      setConversionStates((current) => ({
        ...current,
        [signal.id]: {
          status: "error",
          message: getMarketSignalConversionErrorMessage(error),
        },
      }));
    }
  }

  return (
    <div className="grid gap-5">
      <EarlyOpportunitiesPanel />
      <Panel
        title="AI Opportunity Builder"
        action={<StatusPill tone="green" label="Standing-start research" />}
      >
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
          <div className="grid gap-3">
            <label className="grid gap-1.5">
              <span className="text-xs font-semibold text-slate-500">
                Start with a rough phrase
              </span>
              <input
                value={opportunityResearchQuery}
                onChange={(event) =>
                  setOpportunityResearchQuery(event.target.value)
                }
                className="h-11 rounded-md border border-white/10 bg-[#111a20] px-3 text-sm text-white placeholder:text-slate-500"
                placeholder="Example: West Yorkshire Police estate maintenance"
              />
            </label>
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={handleResearchOpportunity}
                disabled={
                  opportunityResearchQuery.trim().length < 4 ||
                  isOpportunityResearchLoading
                }
                data-testid="research-opportunity-button"
                className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-mitie-lime/30 bg-mitie-lime px-3 py-2 text-sm font-bold text-[#07100b] transition hover:bg-[#d8ff62] disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/10 disabled:text-slate-400"
              >
                {isOpportunityResearchLoading ? (
                  <Loader2
                    aria-hidden="true"
                    className="h-4 w-4 animate-spin"
                  />
                ) : (
                  <Radar aria-hidden="true" className="h-4 w-4" />
                )}
                {isOpportunityResearchLoading
                  ? "Building Intelligence Pack"
                  : "Research And Create Opportunity"}
              </button>
              <StatusPill
                tone="cyan"
                label="Creates labelled field intelligence"
              />
            </div>
          </div>
          <div className="rounded-md border border-white/10 bg-[#111a20] p-4">
            <p className="text-sm font-semibold text-white">
              What MiSi will do
            </p>
            <p className="mt-2 text-sm leading-6 text-slate-400">
              Research public sources, infer missing context, estimate
              commercial values with rationale, mark unknowns with next steps,
              then refresh the dashboard.
            </p>
          </div>
        </div>
        <OpportunityResearchResultPanel state={opportunityResearchState} />
      </Panel>

      <Panel
        title="Internet Intelligence Scan"
        action={<StatusPill tone="cyan" label="OpenAI web search" />}
      >
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_300px]">
          <div className="grid gap-3">
            <label className="grid gap-1.5">
              <span className="text-xs font-semibold text-slate-500">
                Research brief
              </span>
              <textarea
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                rows={4}
                className="min-h-28 rounded-md border border-white/10 bg-[#111a20] px-3 py-3 text-sm leading-6 text-white placeholder:text-slate-500"
                placeholder="Example: UK fire alarm framework opportunities in local authority estates, incumbent competitors and buyer compliance drivers"
              />
            </label>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
              <label className="grid flex-1 gap-1.5">
                <span className="text-xs font-semibold text-slate-500">
                  Intelligence lane
                </span>
                <select
                  value={researchType}
                  onChange={(event) =>
                    setResearchType(
                      event.target.value as InternetIntelligenceType,
                    )
                  }
                  className="h-10 rounded-md border border-white/10 bg-[#111a20] px-3 text-sm font-semibold text-white"
                >
                  {internetIntelligenceTypes.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                onClick={handleRunResearch}
                disabled={query.trim().length < 8 || isResearchLoading}
                className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-mitie-lime/30 bg-mitie-lime px-3 py-2 text-sm font-bold text-[#07100b] transition hover:bg-[#d8ff62] disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/10 disabled:text-slate-400"
              >
                {isResearchLoading ? (
                  <Loader2
                    aria-hidden="true"
                    className="h-4 w-4 animate-spin"
                  />
                ) : (
                  <Globe2 aria-hidden="true" className="h-4 w-4" />
                )}
                {isResearchLoading ? "Scanning The Web" : "Run Internet Scan"}
              </button>
            </div>
          </div>
          <div className="rounded-md border border-white/10 bg-[#111a20] p-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-white">
              <ShieldAlert
                aria-hidden="true"
                className="h-4 w-4 text-amber-200"
              />
              Research boundary
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-400">
              MiSi uses backend-only OpenAI web search for public internet
              research. It does not scrape private systems, bypass site terms or
              expose API keys to the browser.
            </p>
          </div>
        </div>
        <InternetResearchResultPanel state={researchState} />
      </Panel>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
        <Panel
          title="Market Radar"
          action={
            <StatusPill tone="cyan" label={`${marketSignals.length} signals`} />
          }
        >
          {marketSignals.length > 0 ? (
            <div className="grid gap-4 xl:grid-cols-2 2xl:grid-cols-3">
              {marketSignals.map((signal) => (
                <MarketSignalCard
                  key={signal.id}
                  signal={signal}
                  conversionState={
                    conversionStates[signal.id] ?? { status: "idle" }
                  }
                  onConvert={() => handleConvertSignal(signal)}
                  onOpenOpportunity={(opportunity) =>
                    onSelectOpportunity(opportunity)
                  }
                />
              ))}
            </div>
          ) : (
            <EmptyState
              title="Awaiting source-attributed signals"
              message="MiSi has not researched this market area yet. Start with a buyer, sector or tender phrase and MiSi will build source-attributed signals with fit, disciplines, rationale and next action."
            />
          )}
        </Panel>
        <Panel
          title="Source Coverage"
          action={
            <Compass aria-hidden="true" className="h-5 w-5 text-mitie-lime" />
          }
        >
          <div className="grid gap-4">
            <SourceRow
              label="Find a Tender"
              value="Connector framework only until a live approved feed is wired"
              tone="amber"
            />
            <SourceRow
              label="Contracts Finder"
              value="Connector framework only until a live approved feed is wired"
              tone="amber"
            />
            <SourceRow
              label="Manual upload"
              value="Use source-attributed internal tracker data"
              tone="cyan"
            />
            <SourceRow
              label="Buyer watchlist"
              value="No aggressive scraping"
              tone="amber"
            />
          </div>
        </Panel>
      </div>
    </div>
  );
}

export function InternetResearchResultPanel({
  state,
}: {
  state: InternetResearchState;
}) {
  if (state.status === "idle") {
    return (
      <div className="mt-4 rounded-md border border-cyan-300/20 bg-cyan-400/10 p-4">
        <p className="text-sm font-semibold text-cyan-100">
          Search public internet intelligence
        </p>
        <p className="mt-2 text-sm leading-6 text-cyan-100/75">
          Use this to research public tender signals, buyer priorities,
          competitor movements, self-delivery opportunities and market context.
          Results are source-attributed research for review, not imported
          pipeline truth.
        </p>
      </div>
    );
  }

  if (state.status === "loading") {
    return (
      <div className="mt-4 rounded-md border border-cyan-300/20 bg-cyan-400/10 p-4">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-3 text-sm font-semibold text-cyan-100">
              <Loader2 aria-hidden="true" className="h-5 w-5 animate-spin" />
              Searching public internet sources...
            </div>
            <p className="mt-2 text-sm leading-6 text-cyan-100/75">
              MiSi is gathering source-attributed findings, checking evidence
              strength and translating them into commercial next actions.
            </p>
          </div>
          <ConfidenceOrbit score={0.54} label="Live" />
        </div>
        <div className="mt-4 grid gap-2">
          <SkeletonLine className="h-3 w-full rounded-full" />
          <SkeletonLine className="h-3 w-5/6 rounded-full" />
          <SkeletonLine className="h-3 w-2/3 rounded-full" />
        </div>
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div
        className="mt-4 rounded-md border border-amber-300/20 bg-amber-400/10 p-4"
        role="alert"
      >
        <div className="flex gap-3">
          <AlertTriangle
            aria-hidden="true"
            className="mt-0.5 h-5 w-5 shrink-0 text-amber-200"
          />
          <div>
            <p className="text-sm font-semibold text-amber-100">
              Internet intelligence scan was not completed
            </p>
            <p className="mt-2 text-sm leading-6 text-amber-100/80">
              {state.message}
            </p>
          </div>
        </div>
      </div>
    );
  }

  const result = state.result;

  return (
    <div className="mt-4 grid gap-4">
      <section className="rounded-md border border-white/10 bg-[#111a20] p-4">
        <div className="flex flex-wrap items-center gap-2">
          <StatusPill
            tone="green"
            label={internetTypeLabel(result.intelligence_type)}
          />
          <StatusPill
            tone="cyan"
            label={`${result.findings.length} findings`}
          />
          <StatusPill
            tone="amber"
            label={`${result.source_urls.length} sources`}
          />
        </div>
        <h3 className="mt-4 text-xl font-semibold leading-8 text-white">
          {result.headline}
        </h3>
        <p className="mt-3 text-sm leading-6 text-slate-300">
          {result.summary}
        </p>
      </section>

      {result.findings.length > 0 ? (
        <div className="grid gap-4 xl:grid-cols-2">
          {result.findings.map((finding) => (
            <article
              key={`${finding.title}-${finding.recommended_action}`}
              className="rounded-md border border-white/10 bg-[#111a20] p-4"
            >
              <div className="flex items-start justify-between gap-3">
                <h4 className="text-sm font-semibold leading-6 text-white">
                  {finding.title}
                </h4>
                <StatusPill
                  tone={confidenceTone(finding.confidence_score)}
                  label={percentage(finding.confidence_score)}
                />
              </div>
              <p className="mt-3 text-sm leading-6 text-slate-300">
                {finding.finding}
              </p>
              <p className="mt-3 text-sm leading-6 text-cyan-100">
                {finding.so_what}
              </p>
              <p className="mt-3 border-t border-white/10 pt-3 text-sm font-semibold leading-6 text-mitie-lime">
                {finding.recommended_action}
              </p>
              {finding.source_urls.length > 0 ? (
                <div className="mt-3 grid gap-1">
                  {finding.source_urls.slice(0, 3).map((url) => (
                    <a
                      key={url}
                      href={url}
                      target="_blank"
                      rel="noreferrer"
                      className="truncate text-xs font-semibold text-cyan-200 hover:text-white"
                    >
                      {url}
                    </a>
                  ))}
                </div>
              ) : null}
            </article>
          ))}
        </div>
      ) : (
        <EmptyState
          title="No strong public findings yet"
          message="MiSi did not find enough source-backed evidence for a useful finding. Try a more specific buyer, sector, region, discipline or tender phrase so weak signals can be labelled rather than hidden."
        />
      )}

      <div className="grid gap-4 xl:grid-cols-3">
        <BriefingLane
          title="Risk Warnings"
          tone="red"
          items={result.risk_warnings}
        />
        <BriefingLane
          title="Next Best Actions"
          tone="green"
          items={result.next_best_actions}
        />
        <BriefingLane
          title="Limitations"
          tone="amber"
          items={result.limitations}
        />
      </div>
    </div>
  );
}

export function OpportunityResearchResultPanel({
  state,
}: {
  state: OpportunityResearchState;
}) {
  if (state.status === "idle") {
    return (
      <div className="mt-4 rounded-md border border-emerald-300/20 bg-emerald-400/10 p-4">
        <p className="text-sm font-semibold text-emerald-100">
          AI-first opportunity creation
        </p>
        <p className="mt-2 text-sm leading-6 text-emerald-100/75">
          Start from an imperfect phrase. MiSi will research, infer, estimate,
          mark unknowns and create a reviewed commercial record with evidence.
        </p>
      </div>
    );
  }

  if (state.status === "loading") {
    return (
      <div className="mt-4 rounded-md border border-cyan-300/20 bg-cyan-400/10 p-4">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-3 text-sm font-semibold text-cyan-100">
              <Loader2 aria-hidden="true" className="h-5 w-5 animate-spin" />
              Researching and enriching opportunity...
            </div>
            <p className="mt-2 text-sm leading-6 text-cyan-100/75">
              MiSi is searching public sources, creating field-level confidence
              labels and preparing a dashboard-ready record.
            </p>
          </div>
          <ConfidenceOrbit score={0.68} label="AI" />
        </div>
        <div className="mt-4 grid gap-2">
          <SkeletonLine className="h-3 w-full rounded-full" />
          <SkeletonLine className="h-3 w-4/5 rounded-full" />
          <SkeletonLine className="h-3 w-3/5 rounded-full" />
        </div>
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div
        className="mt-4 rounded-md border border-amber-300/20 bg-amber-400/10 p-4"
        role="alert"
      >
        <div className="flex gap-3">
          <AlertTriangle
            aria-hidden="true"
            className="mt-0.5 h-5 w-5 shrink-0 text-amber-200"
          />
          <div>
            <p className="text-sm font-semibold text-amber-100">
              Opportunity research was not completed
            </p>
            <p className="mt-2 text-sm leading-6 text-amber-100/80">
              {state.message}
            </p>
          </div>
        </div>
      </div>
    );
  }

  const result = state.result;
  const fields = result.draft_field_intelligence.map(researchFieldToView);
  const unknownCount = fields.filter(
    (field) => field.valueType === "unknown",
  ).length;

  return (
    <div className="mt-4 grid gap-4">
      <section className="rounded-md border border-white/10 bg-[#111a20] p-4">
        <div className="flex flex-wrap items-center gap-2">
          <StatusPill
            tone="green"
            label={
              result.created_opportunity
                ? "Opportunity created"
                : "Preview only"
            }
          />
          <StatusPill
            tone={confidenceTone(result.overall_confidence)}
            label={`${percentage(result.overall_confidence)} confidence`}
          />
          <StatusPill
            tone={unknownCount > 0 ? "amber" : "green"}
            label={`${unknownCount} unknowns`}
          />
        </div>
        <h3 className="mt-4 text-xl font-semibold leading-8 text-white">
          {result.draft_opportunity.name || "AI researched opportunity"}
        </h3>
        <p className="mt-3 text-sm leading-6 text-slate-300">
          {result.draft_enrichment.opportunity_summary}
        </p>
        <p className="mt-3 text-sm font-semibold leading-6 text-mitie-lime">
          {result.draft_enrichment.executive_recommendation}
        </p>
      </section>

      <div className="grid gap-3 lg:grid-cols-3">
        {fields.slice(0, 6).map((field) => (
          <IntelligenceMetric
            key={field.fieldName}
            field={field}
            fallbackLabel={field.label}
          />
        ))}
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <BriefingLane
          title="Recommended Next Steps"
          tone="green"
          items={result.draft_enrichment.recommended_next_steps}
        />
        <section className="rounded-md border border-white/10 bg-[#111a20] p-4">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold text-white">
              Evidence Sources
            </h3>
            <StatusPill
              tone="cyan"
              label={`${result.sources.length} sources`}
            />
          </div>
          {result.sources.length > 0 ? (
            <div className="mt-3 grid gap-2">
              {result.sources.slice(0, 5).map((source) => (
                <a
                  key={source.url}
                  href={source.url}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-md border border-white/10 bg-[#0d151a] p-3 text-xs leading-5 text-slate-300 transition hover:bg-white/[0.04]"
                >
                  <span className="block font-semibold text-cyan-100">
                    {source.title}
                  </span>
                  <span className="mt-1 block text-slate-500">
                    {source.source_type} · {source.relevance}
                  </span>
                </a>
              ))}
            </div>
          ) : (
            <p className="mt-3 text-sm leading-6 text-slate-500">
              No source URLs were returned. Treat the pack as unverified until
              evidence is attached.
            </p>
          )}
        </section>
      </div>
    </div>
  );
}

export function MarketSignalCard({
  signal,
  conversionState,
  onConvert,
  onOpenOpportunity,
}: {
  signal: MarketSignal;
  conversionState: MarketSignalConversionState;
  onConvert: () => void;
  onOpenOpportunity: (opportunity: Opportunity) => void;
}) {
  const isConverting = conversionState.status === "loading";
  const fitTone = fitToneForSignal(signal.likely_mitie_fit);
  const disciplines =
    signal.potential_disciplines.length > 0
      ? signal.potential_disciplines
      : ["Discipline unknown - confirm source scope"];
  const sourceLabel =
    signal.source_attribution ||
    signal.source_type ||
    "Source attribution required";

  return (
    <article className="rounded-md border border-white/10 bg-[#111a20] p-4 shadow-[0_18px_50px_rgba(0,0,0,0.2)]">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-white">
            {signal.buyer_name}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {signal.sector} · {signal.region}
          </p>
        </div>
        <StatusPill
          tone={confidenceTone(signal.confidence_score)}
          label={`${Math.round(signal.confidence_score * 100)}% confidence`}
        />
      </div>

      <h3 className="mt-4 text-base font-semibold leading-6 text-slate-100">
        {signal.title}
      </h3>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <DetailField label="Source" value={sourceLabel} />
        <DetailField
          label="Expected tender"
          value={
            signal.expected_tender_date
              ? shortDate(signal.expected_tender_date)
              : "Unknown - monitor source"
          }
        />
        <DetailField
          label="Estimated value"
          value={
            signal.estimated_value == null
              ? "Unknown - value not evidenced"
              : compactCurrency(signal.estimated_value)
          }
        />
        <DetailField
          label="Likely Mitie fit"
          value={signal.likely_mitie_fit || "Unknown - needs qualification"}
        />
      </div>

      <div className="mt-4 rounded-md border border-cyan-300/20 bg-cyan-400/10 p-3">
        <div className="flex flex-wrap items-center gap-2">
          <StatusPill
            tone={fitTone}
            label={`${signal.likely_mitie_fit || "Unknown"} fit`}
          />
          <StatusPill
            tone="cyan"
            label={`${disciplines.length} discipline${disciplines.length === 1 ? "" : "s"}`}
          />
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {disciplines.map((discipline) => (
            <span
              key={discipline}
              className="rounded-md border border-white/10 bg-white/[0.04] px-2.5 py-1 text-xs font-semibold text-slate-300"
            >
              {discipline}
            </span>
          ))}
        </div>
        <p className="mt-3 text-xs font-black uppercase text-cyan-100/70">
          AI rationale
        </p>
        <p className="mt-3 text-sm leading-6 text-cyan-100/80">
          {signal.ai_rationale ||
            "MiSi has not yet attached rationale. Convert this signal to create field-level intelligence and an opportunity pack."}
        </p>
      </div>

      <div className="mt-4 rounded-md border border-white/10 bg-[#0d151a] p-3">
        <p className="text-xs font-black uppercase text-slate-500">
          Suggested action
        </p>
        <p className="mt-2 text-sm font-semibold leading-6 text-white">
          {signal.suggested_action || "Review source and qualify relevance."}
        </p>
      </div>

      {signal.source_url ? (
        <a
          href={signal.source_url}
          target="_blank"
          rel="noreferrer"
          className="mt-3 block truncate text-xs font-semibold text-cyan-200 hover:text-white"
        >
          {signal.source_url}
        </a>
      ) : (
        <p className="mt-3 text-xs leading-5 text-slate-500">
          Unknown source URL - attach source evidence before bid governance.
        </p>
      )}

      <div className="mt-4 border-t border-white/10 pt-4">
        <button
          type="button"
          onClick={onConvert}
          disabled={isConverting}
          data-testid={`convert-market-signal-${signal.id}`}
          className="inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-md border border-mitie-lime/30 bg-mitie-lime px-3 py-2 text-sm font-black text-[#07100b] transition hover:bg-[#d8ff62] disabled:cursor-wait disabled:border-white/10 disabled:bg-white/10 disabled:text-slate-400"
        >
          {isConverting ? (
            <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
          ) : (
            <ChevronRight aria-hidden="true" className="h-4 w-4" />
          )}
          {isConverting ? "Converting Signal" : "Convert to Opportunity"}
        </button>

        {conversionState.status === "error" ? (
          <div
            className="mt-3 rounded-md border border-amber-300/20 bg-amber-400/10 p-3"
            role="alert"
          >
            <p className="text-sm font-semibold text-amber-100">
              Signal was not converted
            </p>
            <p className="mt-2 text-sm leading-6 text-amber-100/80">
              {conversionState.message}
            </p>
          </div>
        ) : null}

        {conversionState.status === "success" ? (
          <div className="mt-3 rounded-md border border-emerald-300/20 bg-emerald-400/10 p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-semibold text-emerald-100">
                Opportunity created
              </p>
              <StatusPill
                tone="green"
                label={`${conversionState.result.fields_filled} fields labelled`}
              />
            </div>
            <p className="mt-2 text-sm leading-6 text-emerald-100/80">
              {conversionState.result.conversion_summary}
            </p>
            <button
              type="button"
              onClick={() =>
                onOpenOpportunity(conversionState.result.opportunity)
              }
              className="mt-3 inline-flex min-h-9 items-center justify-center gap-2 rounded-md border border-emerald-200/30 bg-[#0b2f24] px-3 py-2 text-sm font-bold text-emerald-50 transition hover:bg-[#134734]"
            >
              Open intelligence pack
              <ChevronRight aria-hidden="true" className="h-4 w-4" />
            </button>
          </div>
        ) : null}
      </div>
    </article>
  );
}
