"use client";

import {
  analyseOpportunity,
  fetchOpportunityEnrichments,
  fetchOpportunityFieldIntelligence,
  type BuyerProfile,
  type CompetitorProfile,
  type ExecutiveAction,
  type FieldIntelligence,
  type MarketSignal,
  type MisiDashboardData,
  type OpenForecastItem,
  type Opportunity,
  type OpportunityAIAnalysis,
  type OpportunityEnrichment,
} from "@/lib/api";
import { compactCurrency, percentage, shortDate } from "@/lib/format";
import {
  AlertTriangle,
  CheckCircle2,
  Loader2,
  RefreshCw,
  X,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { getOpportunityAnalysisErrorMessage } from "./errors";
import {
  buildOpportunityFieldViews,
  confidenceTone,
  displayOpportunityValue,
  fieldByName,
  summariseFieldConfidence,
} from "./evidence";
import { uniqueSorted } from "./filters";
import { monthYearLabel, threatTone } from "./finance";
import { NextActionCallout, SkeletonLine } from "./research";
import {
  FieldIntelligenceState,
  IntelligenceFieldView,
  OpportunityAnalysisState,
  OpportunityEnrichmentState,
  Tone,
  researchFilterOptions,
  toneClasses,
} from "./shared";
import {
  ConfidenceFieldCard,
  ConfidenceFieldCompact,
  DetailField,
  DetailList,
  EmptyState,
  IntelligenceMetric,
  MetricLine,
  MiniMetric,
  RiskPill,
  StatusPill,
} from "./ui";

export function OpportunityTable({
  opportunities,
  onSelectOpportunity,
}: {
  opportunities: Opportunity[];
  onSelectOpportunity: (opportunity: Opportunity) => void;
}) {
  if (opportunities.length === 0) {
    return (
      <EmptyState
        title="MiSi has not researched matching opportunities yet"
        message="Start with a buyer, sector or tender phrase in the AI Research Workspace. MiSi will build the opportunity record, label weak fields and show the next best action."
      />
    );
  }

  return (
    <>
      <div className="grid gap-3 md:hidden">
        {opportunities.map((item) => (
          <button
            key={item.id}
            type="button"
            data-testid={`opportunity-card-${item.id}`}
            onClick={() => onSelectOpportunity(item)}
            className="rounded-md border border-white/10 bg-[#111a20] p-4 text-left outline-none transition hover:border-mitie-lime/30 hover:bg-white/[0.06] focus-visible:border-mitie-lime/60"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm font-semibold text-mitie-lime">
                  {displayOpportunityValue("buyer_name", item.buyer_name)}
                </p>
                <p className="mt-1 text-sm font-semibold leading-6 text-white">
                  {displayOpportunityValue("name", item.name)}
                </p>
                <p className="mt-1 text-xs font-semibold text-slate-500">
                  {displayOpportunityValue("stage", item.stage)}
                </p>
              </div>
              <RiskPill
                risk={item.calculated_risk_rating || item.risk_rating}
              />
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {item.strategic_must_win ? (
                <StatusPill tone="green" label="Strategic must-win" />
              ) : null}
              {item.self_delivery_capture ? (
                <StatusPill tone="cyan" label="Self-delivery capture" />
              ) : null}
              {item.deadline_warning ? (
                <StatusPill tone="red" label="Deadline warning" />
              ) : null}
            </div>
            <div className="mt-4 grid grid-cols-3 gap-3 text-sm">
              <div>
                <p className="text-xs font-semibold text-slate-500">Value</p>
                <p className="mt-1 font-semibold text-white">
                  {displayOpportunityValue(
                    "estimated_total_contract_value",
                    item.estimated_total_contract_value,
                  )}
                </p>
              </div>
              <div>
                <p className="text-xs font-semibold text-slate-500">Prob.</p>
                <p className="mt-1 font-semibold text-slate-200">
                  {displayOpportunityValue("probability", item.probability)}
                </p>
              </div>
              <div>
                <p className="text-xs font-semibold text-slate-500">Margin</p>
                <p className="mt-1 font-semibold text-slate-200">
                  {displayOpportunityValue(
                    "margin_percentage",
                    item.margin_percentage,
                  )}
                </p>
              </div>
            </div>
            <NextActionCallout
              action={displayOpportunityValue(
                "recommended_action",
                item.calculated_recommended_action || item.recommended_action,
              )}
              tone={item.executive_escalation ? "amber" : "green"}
            />
          </button>
        ))}
      </div>

      <div className="hidden overflow-x-auto md:block">
        <table className="w-full min-w-[860px] border-collapse text-left">
          <thead>
            <tr className="border-b border-white/10 text-sm text-slate-400">
              <th className="px-3 py-3 font-semibold">Buyer</th>
              <th className="px-3 py-3 font-semibold">Opportunity</th>
              <th className="px-3 py-3 font-semibold">Stage</th>
              <th className="px-3 py-3 font-semibold">Value</th>
              <th className="px-3 py-3 font-semibold">Prob.</th>
              <th className="px-3 py-3 font-semibold">Margin</th>
              <th className="px-3 py-3 font-semibold">Risk</th>
              <th className="px-3 py-3 font-semibold">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/10">
            {opportunities.map((item) => (
              <tr
                key={item.id}
                tabIndex={0}
                role="button"
                data-testid={`opportunity-row-${item.id}`}
                onClick={() => onSelectOpportunity(item)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onSelectOpportunity(item);
                  }
                }}
                className="cursor-pointer align-top outline-none transition hover:bg-white/[0.03] focus-visible:bg-white/[0.06]"
              >
                <td className="px-3 py-4 text-sm font-semibold text-white">
                  {displayOpportunityValue("buyer_name", item.buyer_name)}
                </td>
                <td className="px-3 py-4 text-sm text-slate-300">
                  <div className="font-semibold text-white">
                    {displayOpportunityValue("name", item.name)}
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {item.strategic_must_win ? (
                      <StatusPill tone="green" label="Strategic" />
                    ) : null}
                    {item.self_delivery_capture ? (
                      <StatusPill tone="cyan" label="Self-delivery" />
                    ) : null}
                    {item.margin_warning ? (
                      <StatusPill tone="amber" label="Margin" />
                    ) : null}
                  </div>
                </td>
                <td className="px-3 py-4 text-sm text-slate-300">
                  {displayOpportunityValue("stage", item.stage)}
                </td>
                <td className="px-3 py-4 text-sm font-semibold text-white">
                  {displayOpportunityValue(
                    "estimated_total_contract_value",
                    item.estimated_total_contract_value,
                  )}
                </td>
                <td className="px-3 py-4 text-sm text-slate-300">
                  {displayOpportunityValue("probability", item.probability)}
                </td>
                <td className="px-3 py-4 text-sm text-slate-300">
                  {displayOpportunityValue(
                    "margin_percentage",
                    item.margin_percentage,
                  )}
                </td>
                <td className="px-3 py-4">
                  <RiskPill
                    risk={item.calculated_risk_rating || item.risk_rating}
                  />
                </td>
                <td className="max-w-[230px] px-3 py-4 text-sm leading-6 text-slate-300">
                  {displayOpportunityValue(
                    "recommended_action",
                    item.calculated_recommended_action ||
                      item.recommended_action,
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

export function OpportunityDetailDrawer({
  contextData,
  opportunity,
  onAnalysisComplete,
  onClose,
}: {
  contextData: MisiDashboardData;
  opportunity: Opportunity;
  onAnalysisComplete: (
    opportunityId: number,
    analysis: OpportunityAIAnalysis,
  ) => void;
  onClose: () => void;
}) {
  const analysis = opportunity.latest_ai_analysis;
  const [analysisState, setAnalysisState] = useState<OpportunityAnalysisState>({
    status: "idle",
  });
  const [fieldState, setFieldState] = useState<FieldIntelligenceState>({
    status: "loading",
  });
  const [enrichmentState, setEnrichmentState] =
    useState<OpportunityEnrichmentState>({
      status: "loading",
    });
  const [acceptedFieldNames, setAcceptedFieldNames] = useState<Set<string>>(
    () => new Set(),
  );
  const [editingFieldName, setEditingFieldName] = useState<string | null>(null);
  const [fieldOverrides, setFieldOverrides] = useState<Record<string, string>>(
    {},
  );

  useEffect(() => {
    setAnalysisState({ status: "idle" });
    setAcceptedFieldNames(new Set());
    setEditingFieldName(null);
    setFieldOverrides({});
  }, [opportunity.id]);

  useEffect(() => {
    const controller = new AbortController();
    setFieldState({ status: "loading" });
    setEnrichmentState({ status: "loading" });

    fetchOpportunityFieldIntelligence(opportunity.id, controller.signal)
      .then((fields) => {
        setFieldState({ status: "success", fields });
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }

        setFieldState({
          status: "error",
          message:
            error instanceof Error
              ? error.message
              : "Could not load field-level confidence metadata.",
        });
      });

    fetchOpportunityEnrichments(opportunity.id, controller.signal)
      .then((enrichments) => {
        setEnrichmentState({ status: "success", enrichments });
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }

        setEnrichmentState({
          status: "error",
          message:
            error instanceof Error
              ? error.message
              : "Could not load opportunity enrichment pack.",
        });
      });

    return () => {
      controller.abort();
    };
  }, [opportunity.id]);

  async function handleRunAnalysis() {
    setAnalysisState({ status: "loading" });

    try {
      const result = await analyseOpportunity(opportunity.id);
      onAnalysisComplete(opportunity.id, {
        ...result,
        created_at: new Date().toISOString(),
      });
      setAnalysisState({ status: "idle" });
    } catch (error: unknown) {
      setAnalysisState({
        status: "error",
        message: getOpportunityAnalysisErrorMessage(error),
      });
    }
  }

  const intelligenceFields = buildOpportunityFieldViews(
    opportunity,
    fieldState.status === "success" ? fieldState.fields : [],
    fieldOverrides,
  );
  const confidenceSummary = summariseFieldConfidence(intelligenceFields);
  const latestEnrichment =
    enrichmentState.status === "success"
      ? (enrichmentState.enrichments[0] ?? null)
      : null;

  return (
    <div
      className="fixed inset-0 z-40 flex justify-end bg-black/65 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label="Opportunity intelligence pack"
    >
      <button
        type="button"
        className="absolute inset-0 cursor-default"
        onClick={onClose}
        aria-label="Close opportunity intelligence pack"
      />
      <aside className="relative z-10 flex h-full w-full max-w-[1240px] flex-col overflow-y-auto border-l border-white/10 bg-[#080d10] shadow-[0_30px_90px_rgba(0,0,0,0.5)]">
        <div className="sticky top-0 z-20 border-b border-white/10 bg-[#080d10]/95 p-5 backdrop-blur">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-sm font-semibold text-mitie-lime">
                Opportunity Intelligence Pack
              </p>
              <h2 className="mt-2 text-2xl font-semibold leading-8 text-white">
                {displayOpportunityValue("name", opportunity.name)}
              </h2>
              <p className="mt-2 text-sm text-slate-500">
                {displayOpportunityValue("buyer_name", opportunity.buyer_name)}{" "}
                | {displayOpportunityValue("sector", opportunity.sector)} |{" "}
                {displayOpportunityValue("region", opportunity.region)} |{" "}
                {displayOpportunityValue("stage", opportunity.stage)}
              </p>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <StatusPill
                  tone={confidenceTone(confidenceSummary.score)}
                  label={`${percentage(confidenceSummary.score)} record confidence`}
                />
                <StatusPill
                  tone="cyan"
                  label={`${confidenceSummary.aiFieldCount} AI-labelled fields`}
                />
                <StatusPill
                  tone={latestEnrichment ? "green" : "amber"}
                  label={latestEnrichment ? "Enriched pack" : "Fallback pack"}
                />
                {confidenceSummary.unknownCount > 0 ? (
                  <StatusPill
                    tone="amber"
                    label={`${confidenceSummary.unknownCount} unknowns to confirm`}
                  />
                ) : null}
              </div>
              <div className="mt-3 max-w-4xl rounded-md border border-mitie-lime/20 bg-mitie-lime/10 px-3 py-2">
                <p className="text-xs font-black uppercase text-mitie-lime">
                  Next best action
                </p>
                <p className="mt-1 text-sm font-semibold leading-6 text-white">
                  {displayOpportunityValue(
                    "recommended_action",
                    opportunity.calculated_recommended_action ||
                      opportunity.recommended_action,
                  )}
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-md border border-white/10 bg-white/[0.04] text-slate-300 transition hover:bg-white/[0.08] hover:text-white"
              aria-label="Close opportunity intelligence pack"
            >
              <X aria-hidden="true" className="h-5 w-5" />
            </button>
          </div>
        </div>

        <div className="grid gap-5 p-5">
          <OpportunityIntelligencePack
            acceptedFieldNames={acceptedFieldNames}
            analysis={analysis}
            contextData={contextData}
            editingFieldName={editingFieldName}
            enrichment={latestEnrichment}
            enrichmentState={enrichmentState}
            fieldState={fieldState}
            fields={intelligenceFields}
            onAcceptField={(fieldName) => {
              setAcceptedFieldNames((current) => {
                const next = new Set(current);
                next.add(fieldName);
                return next;
              });
            }}
            onCancelEdit={() => setEditingFieldName(null)}
            onEditField={setEditingFieldName}
            onSaveFieldEdit={(fieldName, value) => {
              setFieldOverrides((current) => ({
                ...current,
                [fieldName]: value,
              }));
              setEditingFieldName(null);
            }}
            opportunity={opportunity}
          />

          <section className="rounded-lg border border-white/10 bg-[#0d151a] p-4 shadow-[0_20px_70px_rgba(0,0,0,0.24)]">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h3 className="text-base font-semibold text-white">
                  Refresh AI Analysis
                </h3>
                <p className="mt-1 text-sm leading-5 text-slate-500">
                  Run this when the opportunity record changes or when
                  leadership wants a fresh structured bid/no-bid view.
                </p>
              </div>
              <div className="flex shrink-0 flex-wrap items-center gap-2">
                {analysis ? (
                  <StatusPill tone="green" label="Stored" />
                ) : (
                  <StatusPill tone="amber" label="Not run" />
                )}
                <button
                  type="button"
                  onClick={handleRunAnalysis}
                  disabled={analysisState.status === "loading"}
                  data-testid="run-ai-analysis-button"
                  className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-mitie-lime/30 bg-mitie-lime px-3 py-2 text-sm font-bold text-[#07100b] transition hover:bg-[#d8ff62] disabled:cursor-wait disabled:border-white/10 disabled:bg-white/10 disabled:text-slate-400"
                >
                  {analysisState.status === "loading" ? (
                    <Loader2
                      aria-hidden="true"
                      className="h-4 w-4 animate-spin"
                    />
                  ) : (
                    <RefreshCw aria-hidden="true" className="h-4 w-4" />
                  )}
                  {analysisState.status === "loading"
                    ? "Running AI Analysis"
                    : "Run AI Analysis"}
                </button>
              </div>
            </div>

            {analysisState.status === "error" ? (
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
                      AI analysis was not completed
                    </p>
                    <p className="mt-2 text-sm leading-6 text-amber-100/80">
                      {analysisState.message}
                    </p>
                  </div>
                </div>
              </div>
            ) : null}

            {analysisState.status === "loading" ? (
              <div className="mt-4 rounded-md border border-cyan-300/20 bg-cyan-400/10 p-4">
                <div className="flex items-center gap-3 text-sm font-semibold text-cyan-100">
                  <Loader2
                    aria-hidden="true"
                    className="h-5 w-5 animate-spin"
                  />
                  Building structured commercial analysis...
                </div>
                <p className="mt-2 text-sm leading-6 text-cyan-100/75">
                  MiSi is asking the backend to assess fit, risk, buyer drivers,
                  margin and the next leadership action.
                </p>
              </div>
            ) : null}

            {analysis ? <OpportunityAnalysisPanel analysis={analysis} /> : null}

            {!analysis && analysisState.status !== "loading" ? (
              <EmptyState
                title="No separate AI analysis yet"
                message="The intelligence pack above still uses field evidence, enrichment records and rule-based fallbacks. Run AI Analysis to attach an additional structured OpenAI assessment."
              />
            ) : null}
          </section>
        </div>
      </aside>
    </div>
  );
}

export function OpportunityIntelligencePack({
  acceptedFieldNames,
  analysis,
  contextData,
  editingFieldName,
  enrichment,
  enrichmentState,
  fieldState,
  fields,
  onAcceptField,
  onCancelEdit,
  onEditField,
  onSaveFieldEdit,
  opportunity,
}: {
  acceptedFieldNames: Set<string>;
  analysis: OpportunityAIAnalysis | null;
  contextData: MisiDashboardData;
  editingFieldName: string | null;
  enrichment: OpportunityEnrichment | null;
  enrichmentState: OpportunityEnrichmentState;
  fieldState: FieldIntelligenceState;
  fields: IntelligenceFieldView[];
  onAcceptField: (fieldName: string) => void;
  onCancelEdit: () => void;
  onEditField: (fieldName: string) => void;
  onSaveFieldEdit: (fieldName: string, value: string) => void;
  opportunity: Opportunity;
}) {
  const confidenceSummary = summariseFieldConfidence(fields);
  const buyerProfile = findBuyerProfileForOpportunity(
    contextData.buyerProfiles,
    opportunity,
  );
  const openForecast = contextData.financeSummary.open_opportunities.find(
    (item) => item.opportunity_id === opportunity.id,
  );
  const securedWork = contextData.financeSummary.secured_work.find(
    (item) => item.opportunity_id === opportunity.id,
  );
  const relatedActions = contextData.executiveActions.filter(
    (action) => action.related_opportunity_id === opportunity.id,
  );
  const matchingCompetitors = findCompetitorsForOpportunity(
    contextData.competitorProfiles,
    opportunity,
  );
  const matchingSignals = findMarketSignalsForOpportunity(
    contextData.marketSignals,
    opportunity,
  );
  const sourceLinks = collectEvidenceLinks(fields);
  const likelyScope = listOrFallback(
    splitLikelyScope(enrichment?.likely_scope),
    [
      "Likely scope unknown. Confirm asset schedule, disciplines and procurement documents.",
    ],
  );
  const buyerDrivers = listOrFallback(
    enrichment?.likely_buyer_drivers,
    buyerProfile?.procurement_drivers,
    analysis?.likely_buyer_drivers,
    [
      "Buyer priorities unknown. Confirm compliance, cost, resilience and estate drivers with the buyer.",
    ],
  );
  const complianceDrivers = listOrFallback(enrichment?.compliance_drivers, [
    "Fire safety compliance, life-safety assurance and statutory inspection evidence should be validated.",
  ]);
  const recommendedSteps = listOrFallback(
    enrichment?.recommended_next_steps,
    relatedActions.map((action) => action.recommended_action),
    [
      "Confirm buyer owner, tender route, scope, incumbent, asset schedule and commercial gate before committing bid resources.",
    ],
  );
  const unknowns = listOrFallback(
    enrichment?.unknowns,
    fields
      .filter((field) => field.valueType === "unknown")
      .map((field) => `${field.label}: ${field.recommendedNextStep}`),
    [
      "No critical unknowns are recorded, but validate source evidence before bid governance.",
    ],
  );
  const commercialRisks = listOrFallback(
    analysis?.commercial_risks,
    enrichment?.commercial_assessment ? [enrichment.commercial_assessment] : [],
    opportunity.margin_warning
      ? [
          "Margin is below target. Finance should challenge cost build, self-delivery assumptions and risk allowance.",
        ]
      : [],
    [
      "Commercial risks not fully evidenced. Confirm value, margin, inflation, term and risk transfer.",
    ],
  );
  const mobilisationRisks = listOrFallback(
    analysis?.mobilisation_risks,
    enrichment?.mobilisation_assessment
      ? [enrichment.mobilisation_assessment]
      : [],
    [
      "Mobilisation risk unknown. Confirm asset count, geography, TUPE exposure, incumbent handover and engineer capacity.",
    ],
  );
  const competitorNames = listOrFallback(
    matchingCompetitors.map((competitor) => competitor.name),
    [
      "Likely competitors unknown. Check award history, buyer portal and incumbent contract notices.",
    ],
  );
  const highestThreat =
    analysis?.competitor_threat ||
    matchingCompetitors[0]?.threat_level ||
    "Unknown";
  const forecastCategory =
    openForecast?.forecast_category ||
    (securedWork
      ? "Committed"
      : "Unknown - finance forecast category not linked yet");
  const financialYearImpact = openForecast
    ? `${compactCurrency(openForecast.risk_adjusted_revenue)} risk-adjusted revenue to FY end`
    : securedWork
      ? `${compactCurrency(securedWork.won_revenue)} secured revenue from ${monthYearLabel(securedWork.delivery_start_month)}`
      : "Unknown - create or review LE1 forecast line";
  const sourceStatus =
    sourceLinks.length > 0
      ? `${sourceLinks.length} source link${sourceLinks.length === 1 ? "" : "s"} attached`
      : "No source URLs attached - validate against approved sources";

  return (
    <div className="grid gap-5">
      <section className="overflow-hidden rounded-lg border border-mitie-lime/20 bg-[#0d151a] shadow-[0_26px_90px_rgba(0,0,0,0.36)]">
        <div className="grid gap-0 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="p-5 sm:p-6">
            <div className="flex flex-wrap items-center gap-2">
              <RiskPill
                risk={
                  opportunity.calculated_risk_rating || opportunity.risk_rating
                }
              />
              <StatusPill
                tone={confidenceTone(
                  enrichment?.overall_confidence ?? confidenceSummary.score,
                )}
                label={`${percentage(enrichment?.overall_confidence ?? confidenceSummary.score)} confidence`}
              />
              <StatusPill
                tone={sourceLinks.length > 0 ? "green" : "amber"}
                label={sourceStatus}
              />
              {opportunity.strategic_must_win ? (
                <StatusPill tone="green" label="Strategic must-win" />
              ) : null}
            </div>
            <h3 className="mt-5 text-2xl font-semibold leading-9 text-white">
              Executive Summary
            </h3>
            <div className="mt-5 grid gap-4 lg:grid-cols-3">
              <PackNarrativeCard
                label="What this opportunity is"
                text={firstUsefulText(
                  enrichment?.opportunity_summary,
                  analysis?.executive_summary,
                  `${displayOpportunityValue("name", opportunity.name)} for ${displayOpportunityValue("buyer_name", opportunity.buyer_name)}. Confirm scope and tender route before treating this as committed pipeline.`,
                )}
              />
              <PackNarrativeCard
                label="Why it matters"
                text={firstUsefulText(
                  enrichment?.commercial_assessment,
                  fieldByName(fields, "estimated_total_contract_value")
                    ?.rationale,
                  `${displayOpportunityValue("estimated_total_contract_value", opportunity.estimated_total_contract_value)} potential contract value with ${displayOpportunityValue("self_delivery_fit", opportunity.self_delivery_fit)} self-delivery fit.`,
                )}
              />
              <PackNarrativeCard
                label="What MiSi recommends"
                text={firstUsefulText(
                  enrichment?.executive_recommendation,
                  opportunity.calculated_recommended_action,
                  opportunity.recommended_action,
                  "Confirm buyer owner, source evidence, scope and bid governance route this week.",
                )}
                accent
              />
            </div>
          </div>
          <div className="border-t border-white/10 bg-[#111a20] p-5 xl:border-l xl:border-t-0">
            <p className="text-xs font-black uppercase text-slate-500">
              Leadership readout
            </p>
            <div className="mt-4 grid gap-3">
              <MetricLine
                label="Bid recommendation"
                value={displayOpportunityValue(
                  "bid_no_bid_recommendation",
                  opportunity.calculated_bid_no_bid_recommendation ||
                    opportunity.bid_no_bid_recommendation,
                )}
                detail="Review against fit, risk, margin and source confidence"
              />
              <MetricLine
                label="Strategic fit"
                value={displayOpportunityValue(
                  "strategic_fit_score",
                  opportunity.strategic_fit_score,
                )}
                detail={
                  fieldByName(fields, "strategic_fit_score")?.rationale ??
                  "Confirm fit against Mitie sector and self-delivery priorities."
                }
              />
              <MetricLine
                label="Priority score"
                value={`${Math.round(opportunity.priority_score)}/100`}
                detail="Rule-based pursuit priority"
              />
            </div>
          </div>
        </div>
      </section>

      <OpportunityPackSection
        title="Commercial Snapshot"
        subtitle="Finance-quality view of value, margin, weighting and current forecast status."
        action={
          <StatusPill
            tone={openForecast || securedWork ? "green" : "amber"}
            label={forecastCategory}
          />
        }
      >
        <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-4">
          <IntelligenceMetric
            field={fieldByName(fields, "estimated_annual_revenue")}
            fallbackLabel="Annual revenue"
          />
          <IntelligenceMetric
            field={fieldByName(fields, "estimated_total_contract_value")}
            fallbackLabel="Total contract value"
          />
          <IntelligenceMetric
            field={fieldByName(fields, "estimated_gross_margin")}
            fallbackLabel="Estimated margin"
            danger={opportunity.margin_warning}
          />
          <IntelligenceMetric
            field={fieldByName(fields, "margin_percentage")}
            fallbackLabel="Margin percentage"
            danger={opportunity.margin_warning}
          />
          <IntelligenceMetric
            field={fieldByName(fields, "weighted_value")}
            fallbackLabel="Weighted value"
          />
          <PackMetricCard
            label="Forecast category"
            value={forecastCategory}
            detail="LE1 forecast status for this opportunity"
            tone={openForecast || securedWork ? "green" : "amber"}
          />
          <PackMetricCard
            label="Financial year impact"
            value={financialYearImpact}
            detail={
              enrichment?.finance_assessment ||
              "Finance impact needs review before forecast commitment."
            }
            tone={openForecast || securedWork ? "cyan" : "amber"}
          />
          <PackMetricCard
            label="Forecast start"
            value={displayOpportunityValue(
              "forecast_start_month",
              opportunity.forecast_start_month,
            )}
            detail={
              fieldByName(fields, "forecast_start_month")?.rationale ??
              "Confirm expected start month from procurement timetable."
            }
            tone="cyan"
          />
        </div>
      </OpportunityPackSection>

      <div className="grid gap-5 xl:grid-cols-2">
        <OpportunityPackSection
          title="Buyer Intelligence"
          subtitle="Buyer drivers, relationship context and decision criteria."
        >
          <PackNarrativeCard
            label="Buyer profile"
            text={firstUsefulText(
              enrichment?.buyer_summary,
              buyerProfile
                ? `${buyerProfile.buyer_name} is a ${buyerProfile.sector} buyer in ${buyerProfile.region}. ${buyerProfile.estate_size || "Estate size is not confirmed."}`
                : "Buyer profile unknown. Create or enrich the buyer record before relying on relationship assumptions.",
            )}
          />
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <PackList title="Likely priorities" items={buyerDrivers} />
            <PackList title="Compliance drivers" items={complianceDrivers} />
            <PackList
              title="Procurement drivers"
              items={listOrFallback(buyerProfile?.procurement_drivers, [
                "Procurement drivers unknown. Confirm route, evaluation weighting and incumbent position.",
              ])}
            />
            <PackList
              title="Decision criteria"
              items={listOrFallback(buyerProfile?.decision_criteria, [
                "Decision criteria unknown. Confirm price, quality, compliance, social value and mobilisation weighting.",
              ])}
            />
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <DetailField
              label="Relationship status"
              value={
                buyerProfile?.relationship_status ||
                "Unknown - confirm CRM relationship owner"
              }
            />
            <DetailField
              label="Next best action"
              value={
                buyerProfile?.next_best_action ||
                "Identify buyer contact, procurement owner and estates sponsor."
              }
            />
          </div>
        </OpportunityPackSection>

        <OpportunityPackSection
          title="Tender Intelligence"
          subtitle="Tender status, likely scope, source signals and missing bid information."
        >
          <div className="grid gap-4 md:grid-cols-2">
            <ConfidenceFieldCompact
              field={fieldByName(fields, "stage")}
              label="Likely stage"
            />
            <DetailField
              label="Deadline"
              value={
                opportunity.submission_deadline
                  ? shortDate(opportunity.submission_deadline)
                  : "Unknown - no deadline found in current sources"
              }
            />
            <ConfidenceFieldCompact
              field={fieldByName(fields, "forecast_start_month")}
              label="Expected start date"
            />
            <DetailField
              label="Source signals"
              value={
                matchingSignals.length > 0
                  ? `${matchingSignals.length} related market signal${matchingSignals.length === 1 ? "" : "s"}`
                  : sourceStatus
              }
            />
          </div>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <PackList title="Likely scope" items={likelyScope} />
            <PackList
              title="Missing documents"
              items={deriveMissingDocuments(unknowns)}
            />
            <PackList
              title="Clarification questions needed"
              items={deriveClarificationQuestions(opportunity, unknowns)}
            />
            <PackList
              title="Source signals"
              items={listOrFallback(
                matchingSignals.map(
                  (signal) => `${signal.buyer_name}: ${signal.title}`,
                ),
                [
                  "No related market signals loaded. Attach source notice, portal result or approved research evidence.",
                ],
              )}
            />
          </div>
        </OpportunityPackSection>

        <OpportunityPackSection
          title="Competitor Intelligence"
          subtitle="Incumbent clues, likely posture and counter-strategy."
        >
          <div className="grid gap-4 md:grid-cols-2">
            <PackList title="Likely competitors" items={competitorNames} />
            <PackList
              title="Incumbent clues"
              items={listOrFallback(
                [
                  fieldByName(fields, "incumbent_supplier")?.displayValue,
                ].filter(Boolean) as string[],
                [
                  "Incumbent unknown. Check award notices, buyer portal, CRM notes and prior framework data.",
                ],
              )}
            />
            <PackList
              title="Likely competitor posture"
              items={listOrFallback(
                matchingCompetitors.map(
                  (competitor) =>
                    `${competitor.name}: ${competitor.pricing_behaviour || "Pricing posture unknown"}`,
                ),
                [
                  enrichment?.competitor_assessment ||
                    "Competitor posture unknown. Confirm incumbent, regional specialists and national FM bidders.",
                ],
              )}
            />
            <PackList
              title="Counter-strategy"
              items={listOrFallback(
                matchingCompetitors
                  .map((competitor) => competitor.counter_strategy)
                  .filter(Boolean),
                [
                  "Lead with compliance assurance, self-delivery control, mobilisation confidence and whole-estate evidence.",
                ],
              )}
            />
          </div>
          <div className="mt-4 rounded-md border border-white/10 bg-[#111a20] p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-semibold text-white">Threat level</p>
              <StatusPill
                tone={threatTone(highestThreat)}
                label={highestThreat}
              />
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-400">
              {firstUsefulText(
                enrichment?.competitor_assessment,
                "Threat level is inferred from current competitor records and should be validated before bid strategy is locked.",
              )}
            </p>
          </div>
        </OpportunityPackSection>

        <OpportunityPackSection
          title="Self-Delivery Intelligence"
          subtitle="Fit for Mitie Fire & Security delivery and leakage prevention."
        >
          <div className="grid gap-4 md:grid-cols-2">
            <ConfidenceFieldCompact
              field={fieldByName(fields, "self_delivery_fit")}
              label="Internal capability fit"
            />
            <PackMetricCard
              label="Leakage risk"
              value={
                opportunity.self_delivery_capture
                  ? "High capture opportunity"
                  : "Needs review"
              }
              detail={
                opportunity.self_delivery_capture
                  ? "Strong fit and value should be routed internally."
                  : "Confirm whether scope can be self-delivered before third-party route is assumed."
              }
              tone={opportunity.self_delivery_capture ? "green" : "amber"}
            />
            <PackList
              title="Relevant disciplines"
              items={deriveDisciplines(likelyScope)}
            />
            <PackList
              title="Operations input required"
              items={deriveOperationsInputs(opportunity, unknowns)}
            />
          </div>
          <PackNarrativeCard
            label="Recommended Mitie delivery route"
            text={firstUsefulText(
              enrichment?.self_delivery_assessment,
              "Route Fire & Security disciplines to Mitie delivery leads, validate regional engineering coverage and challenge any third-party leakage before pricing.",
            )}
          />
        </OpportunityPackSection>

        <OpportunityPackSection
          title="Risk And Controls"
          subtitle="Commercial, mobilisation, compliance and margin risks with mitigation actions."
        >
          <div className="grid gap-4 md:grid-cols-2">
            <PackList title="Commercial risks" items={commercialRisks} />
            <PackList title="Mobilisation risks" items={mobilisationRisks} />
            <PackList
              title="Asset data risks"
              items={[
                "Asset count, condition, age, cause-and-effect data and service history must be confirmed before final pricing.",
              ]}
            />
            <PackList
              title="Compliance risks"
              items={listOrFallback(enrichment?.compliance_drivers, [
                "Confirm statutory inspection history, remedial backlog and critical life-safety obligations.",
              ])}
            />
            <PackList
              title="Margin risks"
              items={
                opportunity.margin_warning
                  ? [
                      "Margin warning active. Recheck labour assumptions, specialist subcontract exposure and risk allowance.",
                    ]
                  : [
                      "No margin warning active, but validate cost build and self-delivery assumptions.",
                    ]
              }
            />
            <PackList title="Mitigation actions" items={recommendedSteps} />
          </div>
        </OpportunityPackSection>

        <OpportunityPackSection
          title="Executive Actions"
          subtitle="Clear leadership and functional actions for the next control point."
        >
          <div className="grid gap-3">
            <ExecutivePackAction
              role="MD attention required"
              action={deriveRoleAction(
                "MD",
                relatedActions,
                opportunity,
                recommendedSteps,
              )}
              tone={opportunity.strategic_must_win ? "green" : "cyan"}
            />
            <ExecutivePackAction
              role="Finance attention required"
              action={deriveRoleAction(
                "Finance",
                relatedActions,
                opportunity,
                recommendedSteps,
                openForecast,
              )}
              tone={opportunity.margin_warning ? "amber" : "green"}
            />
            <ExecutivePackAction
              role="Sales Director action"
              action={deriveRoleAction(
                "Sales",
                relatedActions,
                opportunity,
                recommendedSteps,
              )}
              tone="cyan"
            />
            <ExecutivePackAction
              role="Bid team action"
              action={deriveRoleAction(
                "Bid",
                relatedActions,
                opportunity,
                recommendedSteps,
              )}
              tone={opportunity.deadline_warning ? "red" : "amber"}
            />
            <ExecutivePackAction
              role="Commercial review"
              action={deriveRoleAction(
                "Commercial",
                relatedActions,
                opportunity,
                recommendedSteps,
              )}
              tone="amber"
            />
            <ExecutivePackAction
              role="Operations input"
              action={deriveRoleAction(
                "Operations",
                relatedActions,
                opportunity,
                recommendedSteps,
              )}
              tone="green"
            />
          </div>
        </OpportunityPackSection>
      </div>

      <OpportunityPackSection
        title="Evidence And Confidence"
        subtitle="Every important field is labelled as actual, inferred, estimated, unknown or needs confirmation."
        action={
          <StatusPill
            tone={confidenceTone(confidenceSummary.score)}
            label={`${percentage(confidenceSummary.score)} average confidence`}
          />
        }
      >
        {enrichmentState.status === "loading" ? (
          <div className="mb-4 rounded-md border border-cyan-300/20 bg-cyan-400/10 p-4">
            <div className="flex items-center gap-3 text-sm font-semibold text-cyan-100">
              <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
              Loading stored enrichment pack...
            </div>
            <div className="mt-4 grid gap-2">
              <SkeletonLine className="h-3 w-full rounded-full" />
              <SkeletonLine className="h-3 w-4/5 rounded-full" />
            </div>
          </div>
        ) : null}
        {enrichmentState.status === "error" ? (
          <div className="mb-4 rounded-md border border-amber-300/20 bg-amber-400/10 p-4 text-sm leading-6 text-amber-100">
            Enrichment record could not be loaded. MiSi is showing field
            evidence and fallback analysis. {enrichmentState.message}
          </div>
        ) : null}
        {fieldState.status === "loading" ? (
          <div className="mb-4 rounded-md border border-cyan-300/20 bg-cyan-400/10 p-4">
            <div className="flex items-center gap-3 text-sm font-semibold text-cyan-100">
              <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
              Loading field evidence...
            </div>
            <div className="mt-4 grid gap-2">
              <SkeletonLine className="h-3 w-11/12 rounded-full" />
              <SkeletonLine className="h-3 w-2/3 rounded-full" />
            </div>
          </div>
        ) : null}
        {fieldState.status === "error" ? (
          <div className="mb-4 rounded-md border border-amber-300/20 bg-amber-400/10 p-4 text-sm leading-6 text-amber-100">
            Field evidence could not be loaded. MiSi is showing inferred local
            explanations instead. {fieldState.message}
          </div>
        ) : null}

        <div className="grid gap-5 xl:grid-cols-[360px_minmax(0,1fr)]">
          <div className="grid content-start gap-4">
            <PackList
              title="Source links"
              items={
                sourceLinks.length > 0
                  ? sourceLinks.map((source) => source.title || source.url)
                  : [
                      "No source URLs attached. Add approved evidence before bid governance.",
                    ]
              }
            />
            <PackList
              title="Known fields"
              items={fieldNamesByType(fields, [
                "known",
                "user_provided",
                "system_calculated",
              ])}
            />
            <PackList
              title="Inferred fields"
              items={fieldNamesByType(fields, ["inferred"])}
            />
            <PackList
              title="Estimated fields"
              items={fieldNamesByType(fields, ["estimated"])}
            />
            <PackList title="Unknowns" items={unknowns} />
            <PackList
              title="Recommended next research steps"
              items={recommendedSteps}
            />
          </div>
          <div className="grid gap-3">
            {fields.map((field) => (
              <ConfidenceFieldCard
                key={field.fieldName}
                field={field}
                accepted={acceptedFieldNames.has(field.fieldName)}
                editing={editingFieldName === field.fieldName}
                onAccept={() => onAcceptField(field.fieldName)}
                onEdit={() => onEditField(field.fieldName)}
                onCancelEdit={onCancelEdit}
                onSaveEdit={(value) => onSaveFieldEdit(field.fieldName, value)}
              />
            ))}
          </div>
        </div>
      </OpportunityPackSection>
    </div>
  );
}

export function PackNarrativeCard({
  label,
  text,
  accent = false,
}: {
  label: string;
  text: string;
  accent?: boolean;
}) {
  return (
    <article
      className={`rounded-md border p-4 ${accent ? "border-mitie-lime/25 bg-mitie-lime/10" : "border-white/10 bg-[#111a20]"}`}
    >
      <p className="text-xs font-black uppercase text-slate-500">{label}</p>
      <p
        className={`mt-3 text-sm font-semibold leading-6 ${accent ? "text-mitie-lime" : "text-slate-200"}`}
      >
        {text}
      </p>
    </article>
  );
}

export function OpportunityPackSection({
  title,
  subtitle,
  action,
  children,
}: {
  title: string;
  subtitle: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="rounded-lg border border-white/10 bg-[#0d151a] shadow-[0_20px_70px_rgba(0,0,0,0.24)]">
      <div className="flex min-h-16 flex-col gap-3 border-b border-white/10 px-4 py-4 sm:flex-row sm:items-start sm:justify-between sm:px-5">
        <div>
          <h3 className="text-base font-semibold text-white sm:text-lg">
            {title}
          </h3>
          <p className="mt-1 text-sm leading-5 text-slate-500">{subtitle}</p>
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
      <div className="p-4 sm:p-5">{children}</div>
    </section>
  );
}

export function PackMetricCard({
  label,
  value,
  detail,
  tone,
}: {
  label: string;
  value: string;
  detail: string;
  tone: Tone;
}) {
  return (
    <article className={`rounded-md border p-4 ${toneClasses[tone]}`}>
      <p className="text-sm font-semibold text-slate-300">{label}</p>
      <p className="mt-2 text-xl font-semibold leading-7 text-white">{value}</p>
      <p className="mt-2 text-xs leading-5 text-slate-300">{detail}</p>
    </article>
  );
}

export function PackList({ title, items }: { title: string; items: string[] }) {
  const visibleItems =
    items.length > 0
      ? items
      : ["Unknown - confirm with approved source evidence."];
  return (
    <div className="rounded-md border border-white/10 bg-[#111a20] p-4">
      <p className="text-xs font-black uppercase text-slate-500">{title}</p>
      <ul className="mt-3 grid gap-2">
        {visibleItems.map((item) => (
          <li
            key={item}
            className="flex gap-2 text-sm leading-6 text-slate-300"
          >
            <CheckCircle2
              aria-hidden="true"
              className="mt-1 h-4 w-4 shrink-0 text-mitie-lime"
            />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ExecutivePackAction({
  role,
  action,
  tone,
}: {
  role: string;
  action: string;
  tone: Tone;
}) {
  return (
    <article className="rounded-md border border-white/10 bg-[#111a20] p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm font-semibold text-white">{role}</p>
        <StatusPill tone={tone} label="Action" />
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-300">{action}</p>
    </article>
  );
}

export function firstUsefulText(...values: Array<string | null | undefined>) {
  return (
    values
      .find((value) => typeof value === "string" && value.trim().length > 0)
      ?.trim() ??
    "Unknown - MiSi needs more source evidence before this can be treated as confirmed."
  );
}

export function listOrFallback(...lists: Array<string[] | null | undefined>) {
  for (const list of lists) {
    const cleaned = uniqueSorted(
      (list ?? [])
        .map((item) => (typeof item === "string" ? item.trim() : ""))
        .filter(Boolean),
    );
    if (cleaned.length > 0) {
      return cleaned;
    }
  }

  return ["Unknown - confirm with approved source evidence."];
}

export function splitLikelyScope(value: string | null | undefined) {
  if (!value?.trim()) {
    return [];
  }

  return value
    .split(/[;\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function findBuyerProfileForOpportunity(
  buyers: BuyerProfile[],
  opportunity: Opportunity,
) {
  const buyerName = opportunity.buyer_name.toLowerCase();
  return (
    buyers.find((buyer) => buyer.buyer_name.toLowerCase() === buyerName) ??
    buyers.find(
      (buyer) =>
        buyer.sector === opportunity.sector &&
        (!opportunity.region || buyer.region === opportunity.region),
    ) ??
    null
  );
}

export function findCompetitorsForOpportunity(
  competitors: CompetitorProfile[],
  opportunity: Opportunity,
) {
  const sector = opportunity.sector.toLowerCase();
  return competitors
    .filter((competitor) =>
      competitor.sectors.some((item) => item.toLowerCase() === sector),
    )
    .slice(0, 4);
}

export function findMarketSignalsForOpportunity(
  marketSignals: MarketSignal[],
  opportunity: Opportunity,
) {
  const buyerName = opportunity.buyer_name.toLowerCase();
  return marketSignals
    .filter((signal) => {
      const signalBuyer = signal.buyer_name.toLowerCase();
      return (
        signalBuyer === buyerName ||
        signalBuyer.includes(buyerName) ||
        buyerName.includes(signalBuyer) ||
        (signal.sector === opportunity.sector &&
          signal.region === opportunity.region)
      );
    })
    .slice(0, 4);
}

export function collectEvidenceLinks(fields: IntelligenceFieldView[]) {
  const links = new Map<string, { url: string; title: string }>();
  fields.forEach((field) => {
    field.sourceUrls.forEach((url, index) => {
      if (!url.trim() || links.has(url)) {
        return;
      }
      links.set(url, {
        url,
        title: field.sourceTitles[index] || `${field.label} source`,
      });
    });
  });
  return Array.from(links.values());
}

export function deriveMissingDocuments(unknowns: string[]) {
  const combined = unknowns.join(" ").toLowerCase();
  const documents = [
    combined.includes("deadline") || combined.includes("timetable")
      ? "Tender timetable and submission deadline"
      : "",
    combined.includes("asset") || combined.includes("scope")
      ? "Asset register, scope schedule and service specification"
      : "",
    combined.includes("incumbent")
      ? "Incumbent supplier evidence and current contract expiry"
      : "",
    combined.includes("margin") || combined.includes("value")
      ? "Commercial model, pricing assumptions and value evidence"
      : "",
  ].filter(Boolean);

  return listOrFallback(documents, [
    "Tender notice, specification, asset schedule, pricing schedule, mobilisation requirements and evaluation criteria.",
  ]);
}

export function deriveClarificationQuestions(
  opportunity: Opportunity,
  unknowns: string[],
) {
  const questions = [
    "What exact fire and security disciplines are in scope, and what asset volumes apply?",
    "Is there a confirmed procurement route, framework or direct tender timetable?",
    "Who is the incumbent supplier and what is the current service performance position?",
    opportunity.margin_warning
      ? "Which cost assumptions must be challenged to restore target margin?"
      : "What commercial risks should be priced before final review?",
    unknowns.length > 0
      ? `Which unknowns can the buyer or source documents resolve first: ${unknowns.slice(0, 2).join("; ")}?`
      : "",
  ].filter(Boolean);

  return listOrFallback(questions);
}

export function deriveDisciplines(likelyScope: string[]) {
  const scopeText = likelyScope.join(" ").toLowerCase();
  const matchedDisciplines = researchFilterOptions.disciplines.filter(
    (discipline) => scopeText.includes(discipline.toLowerCase()),
  );

  return listOrFallback(matchedDisciplines, likelyScope, [
    "Fire Alarms, Emergency Lighting, Extinguishers, CCTV, Access Control and Fire Risk Assessments should be confirmed against the scope.",
  ]);
}

export function deriveOperationsInputs(
  opportunity: Opportunity,
  unknowns: string[],
) {
  return listOrFallback([
    "Confirm regional engineering capacity, call-out model and mobilisation lead.",
    "Validate specialist subcontract exposure, access constraints and critical asset coverage.",
    opportunity.self_delivery_capture
      ? "Confirm self-delivery route before third-party leakage is priced into the bid."
      : "Assess whether scope can be routed to Mitie Fire & Security before bid/no-bid.",
    unknowns.some((item) => item.toLowerCase().includes("asset"))
      ? "Resolve asset register gaps before final pricing."
      : "",
  ]);
}

export function deriveRoleAction(
  role: string,
  relatedActions: ExecutiveAction[],
  opportunity: Opportunity,
  recommendedSteps: string[],
  openForecast?: OpenForecastItem,
) {
  const roleMatch = relatedActions.find((action) =>
    [action.owner, action.category, action.reason, action.recommended_action]
      .join(" ")
      .toLowerCase()
      .includes(role.toLowerCase()),
  );
  if (roleMatch?.recommended_action) {
    return roleMatch.recommended_action;
  }

  const firstStep =
    recommendedSteps[0] || "Confirm source evidence and next commercial gate.";
  const roleKey = role.toLowerCase();
  if (roleKey.includes("md")) {
    return opportunity.strategic_must_win
      ? "Assign executive sponsor and confirm must-win governance before bid resources are committed."
      : firstStep;
  }
  if (roleKey.includes("finance")) {
    return openForecast
      ? `Review ${compactCurrency(openForecast.risk_adjusted_revenue)} risk-adjusted forecast, margin and probability weighting.`
      : "Create or validate LE1 forecast line, probability weighting, risk adjustment and margin assumptions.";
  }
  if (roleKey.includes("sales")) {
    return "Confirm buyer access, relationship owner, decision criteria and close plan.";
  }
  if (roleKey.includes("bid")) {
    return opportunity.deadline_warning
      ? "Escalate timetable, clarification ownership and final review readiness today."
      : "Confirm bid/no-bid evidence, clarifications and governance dates.";
  }
  if (roleKey.includes("commercial")) {
    return "Validate value, margin, risk transfer, scope exclusions and self-delivery assumptions.";
  }
  if (roleKey.includes("operations")) {
    return "Confirm mobilisation plan, engineering capacity, asset data quality and delivery route.";
  }

  return firstStep;
}

export function fieldNamesByType(
  fields: IntelligenceFieldView[],
  valueTypes: FieldIntelligence["value_type"][],
) {
  const names = fields
    .filter((field) => valueTypes.includes(field.valueType))
    .map((field) => `${field.label} (${percentage(field.confidenceScore)})`);
  return listOrFallback(names, ["No fields in this category yet."]);
}

export function OpportunityAnalysisPanel({
  analysis,
}: {
  analysis: OpportunityAIAnalysis;
}) {
  return (
    <div className="mt-4 grid gap-4">
      <div className="rounded-md border border-white/10 bg-[#111a20] p-4">
        <div className="flex flex-wrap items-center gap-2">
          <RiskPill risk={analysis.risk_rating} />
          <StatusPill
            tone={
              analysis.competitor_threat === "High"
                ? "red"
                : analysis.competitor_threat === "Medium"
                  ? "amber"
                  : "green"
            }
            label={`${analysis.competitor_threat} competitor threat`}
          />
          <StatusPill tone="cyan" label={analysis.bid_no_bid_recommendation} />
        </div>
        <h4 className="mt-4 text-sm font-semibold text-white">
          Executive Summary
        </h4>
        <p className="mt-2 text-sm leading-6 text-slate-300">
          {analysis.executive_summary}
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <MiniMetric
          label="Strategic fit score"
          value={`${Math.round(analysis.strategic_fit_score)}/100`}
        />
        <MiniMetric
          label="Win probability"
          value={percentage(analysis.win_probability)}
        />
        <MiniMetric
          label="Risk rating"
          value={analysis.risk_rating}
          danger={analysis.risk_rating === "Red"}
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <DetailField
          label="Bid / no-bid recommendation"
          value={analysis.bid_no_bid_recommendation}
        />
        <DetailField
          label="Competitor threat"
          value={analysis.competitor_threat}
        />
      </div>

      <DetailField
        label="Margin commentary"
        value={analysis.margin_commentary}
      />
      <DetailList title="Buyer drivers" items={analysis.likely_buyer_drivers} />
      <DetailList
        title="Mobilisation risks"
        items={analysis.mobilisation_risks}
      />
      <DetailList title="Commercial risks" items={analysis.commercial_risks} />
      <DetailField
        label="Self-delivery assessment"
        value={analysis.self_delivery_assessment}
      />
      <DetailField
        label="Recommended action"
        value={analysis.recommended_action}
      />
    </div>
  );
}
