"use client";

import {
  autofillOpportunities,
  fetchExecutiveReport,
  generateExecutiveSummary,
  type DashboardSummary,
  type ExecutiveLeadershipBriefing,
  type MisiDashboardData,
  type Opportunity,
} from "@/lib/api";
import { compactCurrency, percentageValue, shortDate } from "@/lib/format";
import {
  createExecutiveReportExportUrls,
  revokeExecutiveReportExportUrls,
} from "@/lib/report-export";
import {
  buildSelfDeliverySummary,
  type SelfDeliverySummary,
} from "@/lib/self-delivery";
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  Loader2,
  Printer,
  RefreshCw,
  TrendingUp,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  ExecutiveActionsList,
  MarginChart,
  MarketSignalsPanel,
  PipelineChart,
} from "./charts";
import {
  getAutofillErrorMessage,
  getExecutiveBriefingErrorMessage,
  getReportExportErrorMessage,
} from "./errors";
import { autofillResultTone } from "./evidence";
import { splitSummary } from "./filters";
import { OpportunityTable } from "./opportunity";
import {
  AutofillState,
  LeadershipBriefingState,
  ReportExportState,
  Tone,
} from "./shared";
import {
  AutofillSummaryMetric,
  KpiTile,
  MetricLine,
  Panel,
  StatusPill,
} from "./ui";

export function ExecutiveCommandView({
  data,
  onDataChanged,
  onSelectOpportunity,
}: {
  data: MisiDashboardData;
  onDataChanged: () => void;
  onSelectOpportunity: (opportunity: Opportunity) => void;
}) {
  const [briefingState, setBriefingState] = useState<LeadershipBriefingState>({
    status: "idle",
  });
  const [reportExportState, setReportExportState] = useState<ReportExportState>(
    {
      status: "idle",
    },
  );
  const selfDeliverySummary = useMemo(
    () => buildSelfDeliverySummary(data.opportunities),
    [data.opportunities],
  );

  useEffect(() => {
    return () => {
      if (reportExportState.status === "success") {
        revokeExecutiveReportExportUrls(reportExportState.urls);
      }
    };
  }, [reportExportState]);

  async function handleGenerateBriefing() {
    setBriefingState({ status: "loading" });

    try {
      const briefing = await generateExecutiveSummary();
      setBriefingState({ status: "success", briefing });
    } catch (error: unknown) {
      setBriefingState({
        status: "error",
        message: getExecutiveBriefingErrorMessage(error),
      });
    }
  }

  async function handleExportReport() {
    setReportExportState((current) => {
      if (current.status === "success") {
        revokeExecutiveReportExportUrls(current.urls);
      }

      return { status: "loading" };
    });

    try {
      const report = await fetchExecutiveReport();
      const urls = createExecutiveReportExportUrls(report);
      setReportExportState({ status: "success", report, urls });
    } catch (error: unknown) {
      setReportExportState({
        status: "error",
        message: getReportExportErrorMessage(error),
      });
    }
  }

  return (
    <div className="grid gap-5">
      <KpiCards dashboard={data.dashboard} />
      <LeadershipControlPanel
        data={data}
        selfDeliverySummary={selfDeliverySummary}
      />
      <AutofillMissingIntelligencePanel onDataChanged={onDataChanged} />

      <div className="grid gap-5 2xl:grid-cols-[minmax(0,1fr)_420px]">
        <div className="grid min-w-0 gap-5">
          <ExecutiveSummaryPanel dashboard={data.dashboard} />
          <ExecutiveReportExportPanel
            state={reportExportState}
            onExport={handleExportReport}
          />
          <LeadershipBriefingPanel
            state={briefingState}
            onGenerate={handleGenerateBriefing}
          />

          <Panel
            title="Priority Opportunity Control"
            action={
              <StatusPill
                tone="amber"
                label={`${data.opportunities.length} visible`}
              />
            }
          >
            <OpportunityTable
              opportunities={data.opportunities}
              onSelectOpportunity={onSelectOpportunity}
            />
          </Panel>
        </div>

        <div className="grid content-start gap-5">
          <Panel
            title="Pipeline and Margin Shape"
            action={
              <TrendingUp
                aria-hidden="true"
                className="h-5 w-5 text-cyan-200"
              />
            }
          >
            <PipelineChart
              revenue={data.dashboard.monthly_revenue_forecast}
              margin={data.dashboard.monthly_margin_forecast}
            />
          </Panel>
          <MarginChart
            dashboard={data.dashboard}
            financeSummary={data.financeSummary}
          />
          <MarketSignalsPanel
            marketSignals={data.marketSignals.slice(0, 3)}
            compact
          />
          <ExecutiveActionsList
            actions={data.dashboard.top_executive_actions}
            title="Leadership Actions"
          />
        </div>
      </div>
    </div>
  );
}

export function KpiCards({ dashboard }: { dashboard: DashboardSummary }) {
  const cards = [
    {
      label: "Total live pipeline",
      display: compactCurrency(dashboard.total_pipeline_value),
      detail: `${dashboard.live_opportunity_count} live opportunities`,
      tone: "green" as Tone,
    },
    {
      label: "Weighted live pipeline",
      display: compactCurrency(dashboard.weighted_pipeline_value),
      detail: `${dashboard.strategic_must_win_count} strategic must-wins`,
      tone: "cyan" as Tone,
    },
    {
      label: "Gross margin value",
      display: compactCurrency(dashboard.estimated_gross_margin),
      detail: `${percentageValue(dashboard.average_margin_percentage)} blended margin`,
      tone: "amber" as Tone,
    },
    {
      label: "Leadership risk queue",
      display: String(dashboard.high_risk_count),
      detail: `${dashboard.urgent_deadline_count} urgent deadlines`,
      tone: "red" as Tone,
    },
  ];

  return (
    <section
      className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-4"
      aria-label="Executive KPIs"
    >
      {cards.map((metric) => (
        <KpiTile key={metric.label} {...metric} />
      ))}
    </section>
  );
}

export function LeadershipControlPanel({
  data,
  selfDeliverySummary,
}: {
  data: MisiDashboardData;
  selfDeliverySummary: SelfDeliverySummary;
}) {
  const topOpportunity =
    data.dashboard.top_opportunities[0] ?? data.opportunities[0] ?? null;
  const nextAction =
    data.dashboard.top_executive_actions[0]?.recommended_action;
  const financeReviewCount =
    data.financeSummary.margin_warnings.length +
    data.financeSummary.finance_review_items.length;
  const openToRiskDelta =
    data.financeSummary.open_weighted_revenue -
    data.financeSummary.risk_adjusted_revenue;
  const roleActions = [
    {
      role: "MD",
      headline:
        data.dashboard.strategic_must_win_count > 0
          ? `${data.dashboard.strategic_must_win_count} must-win sponsor decision${data.dashboard.strategic_must_win_count === 1 ? "" : "s"}`
          : data.dashboard.live_opportunity_count > 0
            ? "No must-win sponsor gaps"
            : "Awaiting researched pursuits",
      metric: topOpportunity
        ? compactCurrency(topOpportunity.weighted_pipeline_value)
        : "Research needed",
      action:
        nextAction ??
        (data.dashboard.live_opportunity_count > 0
          ? "Hold the weekly MD / FD / GSD control point on priority pursuits."
          : "Use AI Opportunity Builder or upload approved source data to create the first intelligence pack."),
      tone: data.dashboard.strategic_must_win_count > 0 ? "green" : "cyan",
    },
    {
      role: "FD",
      headline:
        financeReviewCount > 0
          ? `${financeReviewCount} LE1 review item${financeReviewCount === 1 ? "" : "s"}`
          : "LE1 controls clear",
      metric: compactCurrency(data.financeSummary.risk_adjusted_revenue),
      action:
        openToRiskDelta > 0
          ? `Challenge ${compactCurrency(openToRiskDelta)} removed by risk adjustment before forecast lock.`
          : "Confirm secured and open forecast assumptions remain supportable.",
      tone: financeReviewCount > 0 ? "amber" : "green",
    },
    {
      role: "GSD",
      headline: `${data.dashboard.live_opportunity_count} live pursuits to convert`,
      metric: compactCurrency(data.dashboard.weighted_pipeline_value),
      action:
        topOpportunity?.calculated_recommended_action ??
        "Confirm buyer access and close plans for the highest weighted pursuits.",
      tone: data.dashboard.high_risk_count > 0 ? "amber" : "green",
    },
    {
      role: "Bid",
      headline: `${data.dashboard.live_tender_count} live tender${data.dashboard.live_tender_count === 1 ? "" : "s"}`,
      metric: `${data.dashboard.urgent_deadline_count} urgent`,
      action:
        data.dashboard.urgent_deadline_count > 0
          ? "Escalate deadline ownership and unresolved clarifications today."
          : "Keep pricing, clarification and final review gates visible to leadership.",
      tone: data.dashboard.urgent_deadline_count > 0 ? "red" : "cyan",
    },
    {
      role: "Commercial",
      headline: `${selfDeliverySummary.routeOpportunities.length} self-delivery routes`,
      metric: compactCurrency(selfDeliverySummary.valueAtRisk),
      action:
        selfDeliverySummary.valueAtRisk > 0
          ? "Route strong-fit fire and security scope before third-party leakage is priced in."
          : "Maintain capture discipline on routed fire and security scope.",
      tone: selfDeliverySummary.valueAtRisk > 0 ? "red" : "green",
    },
  ] satisfies Array<{
    role: string;
    headline: string;
    metric: string;
    action: string;
    tone: Tone;
  }>;

  return (
    <Panel
      title="Leadership Control This Week"
      action={<StatusPill tone="green" label="Role-led actions" />}
    >
      <div className="grid gap-3 lg:grid-cols-5">
        {roleActions.map((item) => (
          <article
            key={item.role}
            className="rounded-md border border-white/10 bg-[#111a20] p-4"
          >
            <div className="flex items-center justify-between gap-3">
              <p className="text-xs font-black uppercase text-slate-500">
                {item.role}
              </p>
              <StatusPill tone={item.tone} label={item.metric} />
            </div>
            <h3 className="mt-4 text-sm font-semibold leading-6 text-white">
              {item.headline}
            </h3>
            <p className="mt-3 text-sm leading-6 text-slate-400">
              {item.action}
            </p>
          </article>
        ))}
      </div>
    </Panel>
  );
}

export function AutofillMissingIntelligencePanel({
  onDataChanged,
}: {
  onDataChanged: () => void;
}) {
  const [state, setState] = useState<AutofillState>({ status: "idle" });
  const [limit, setLimit] = useState(10);
  const isLoading = state.status === "loading";

  async function handleAutofill() {
    setState({ status: "loading" });

    try {
      const result = await autofillOpportunities({
        only_incomplete: true,
        limit,
      });
      setState({ status: "success", result });
    } catch (error: unknown) {
      setState({
        status: "error",
        message: getAutofillErrorMessage(error),
      });
    }
  }

  const result = state.status === "success" ? state.result : null;
  const warningCount = result?.confidence_warnings.length ?? 0;

  return (
    <Panel
      title="AI Autofill Control"
      action={
        <button
          type="button"
          onClick={handleAutofill}
          disabled={isLoading}
          data-testid="autofill-missing-intelligence-button"
          className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-mitie-lime/30 bg-mitie-lime px-3 py-2 text-sm font-bold text-[#07100b] transition hover:bg-[#d8ff62] disabled:cursor-wait disabled:border-white/10 disabled:bg-white/10 disabled:text-slate-400"
        >
          {isLoading ? (
            <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw aria-hidden="true" className="h-4 w-4" />
          )}
          {isLoading
            ? "Autofilling Intelligence"
            : "Autofill missing intelligence"}
        </button>
      }
    >
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="rounded-md border border-cyan-300/20 bg-cyan-400/10 p-4">
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill tone="cyan" label="AI-first records" />
            <StatusPill tone="green" label="User values protected" />
            <StatusPill tone="amber" label="Confidence labelled" />
          </div>
          <h3 className="mt-4 text-lg font-semibold leading-7 text-white">
            Fill weak records without pretending the data is perfect.
          </h3>
          <p className="mt-2 text-sm leading-6 text-cyan-100/75">
            MiSi scans incomplete opportunities, researches available public
            evidence, fills missing commercial fields, and stores field-level
            rationale. Existing non-empty values are preserved unless a future
            run explicitly allows overwrite.
          </p>
        </div>

        <div className="grid content-start gap-3">
          <label className="grid gap-1.5">
            <span className="text-xs font-semibold text-slate-500">
              Batch limit
            </span>
            <input
              value={limit}
              onChange={(event) => {
                const nextValue = Number(event.target.value);
                setLimit(
                  Number.isFinite(nextValue)
                    ? Math.max(1, Math.min(nextValue, 50))
                    : 10,
                );
              }}
              min={1}
              max={50}
              type="number"
              className="h-10 rounded-md border border-white/10 bg-[#111a20] px-3 text-sm font-semibold text-white"
            />
          </label>
          <MetricLine
            label="Mode"
            value="Incomplete only"
            detail="Blank, zero, unknown or review-required fields are targeted first"
          />
        </div>
      </div>

      {state.status === "loading" ? (
        <div className="mt-4 rounded-md border border-mitie-lime/20 bg-mitie-lime/10 p-4">
          <div className="flex items-center gap-3 text-sm font-semibold text-mitie-lime">
            <Loader2 aria-hidden="true" className="h-5 w-5 animate-spin" />
            Researching and labelling missing intelligence...
          </div>
          <p className="mt-2 text-sm leading-6 text-mitie-lime/80">
            MiSi is enriching records one by one. A failed record will be
            reported in the batch summary without stopping the rest of the run.
          </p>
        </div>
      ) : null}

      {state.status === "error" ? (
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
                Autofill was not completed
              </p>
              <p className="mt-2 text-sm leading-6 text-amber-100/80">
                {state.message}
              </p>
            </div>
          </div>
        </div>
      ) : null}

      {result ? (
        <div className="mt-4 grid gap-4">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <AutofillSummaryMetric
              label="Records scanned"
              value={String(result.records_scanned)}
              detail={`${result.records_skipped} already complete or protected`}
            />
            <AutofillSummaryMetric
              label="Records enriched"
              value={String(result.records_enriched)}
              detail={`${result.records_failed} failed without stopping batch`}
            />
            <AutofillSummaryMetric
              label="Fields filled"
              value={String(result.fields_filled)}
              detail="Known, inferred, estimated or calculated"
            />
            <AutofillSummaryMetric
              label="Still unknown"
              value={String(result.fields_still_unknown)}
              detail="Now labelled with next checks"
            />
            <AutofillSummaryMetric
              label="Warnings"
              value={String(warningCount)}
              detail="Confidence or confirmation items"
            />
          </div>

          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
            <div className="rounded-md border border-white/10 bg-[#111a20] p-4">
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-sm font-semibold text-white">
                  Batch outcome
                </h3>
                <StatusPill
                  tone={result.records_failed > 0 ? "amber" : "green"}
                  label={
                    result.records_failed > 0 ? "Partial success" : "Completed"
                  }
                />
              </div>
              <div className="mt-4 grid gap-3">
                {result.results.length > 0 ? (
                  result.results.slice(0, 5).map((item) => (
                    <div
                      key={`${item.opportunity_id}-${item.enrichment_run_id ?? item.status}`}
                      className="rounded-md border border-white/10 bg-[#0d151a] p-3"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-sm font-semibold text-white">
                          {item.opportunity_name}
                        </p>
                        <StatusPill
                          tone={autofillResultTone(item.status)}
                          label={item.status}
                        />
                      </div>
                      <p className="mt-2 text-xs leading-5 text-slate-400">
                        {item.fields_filled} filled · {item.fields_preserved}{" "}
                        protected · {item.fields_still_unknown} still unknown
                      </p>
                      {item.error_message ? (
                        <p className="mt-2 text-xs leading-5 text-amber-100/80">
                          {item.error_message}
                        </p>
                      ) : null}
                    </div>
                  ))
                ) : (
                  <p className="text-sm leading-6 text-slate-400">
                    No incomplete opportunities were selected for enrichment.
                    New research records will appear here after a batch run.
                  </p>
                )}
              </div>
            </div>

            <div className="grid content-start gap-3">
              <div className="rounded-md border border-amber-300/20 bg-amber-400/10 p-4">
                <p className="text-sm font-semibold text-amber-100">
                  Confidence warnings
                </p>
                <div className="mt-3 grid gap-2">
                  {result.confidence_warnings.length > 0 ? (
                    result.confidence_warnings.slice(0, 4).map((warning) => (
                      <p
                        key={warning}
                        className="text-sm leading-6 text-amber-100/80"
                      >
                        {warning}
                      </p>
                    ))
                  ) : (
                    <p className="text-sm leading-6 text-amber-100/80">
                      No low-confidence field fills were reported. Continue to
                      validate estimates before bid or forecast commitment.
                    </p>
                  )}
                </div>
              </div>
              <button
                type="button"
                onClick={onDataChanged}
                className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-white/10 bg-white/[0.04] px-3 py-2 text-sm font-bold text-slate-200 transition hover:bg-white/[0.08]"
              >
                <RefreshCw aria-hidden="true" className="h-4 w-4" />
                Refresh dashboard data
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </Panel>
  );
}

export function ExecutiveSummaryPanel({
  dashboard,
}: {
  dashboard: DashboardSummary;
}) {
  const summaryParts = splitSummary(dashboard.executive_summary_text);
  const moduleHealth = [
    {
      label: "Open opportunities",
      value: String(dashboard.live_opportunity_count),
      detail: "Live commercial pursuits in the API dataset",
    },
    {
      label: "Market signals",
      value: String(dashboard.market_signal_count),
      detail: "Public tender and watchlist indicators",
    },
    {
      label: "Strategic must-wins",
      value: String(dashboard.strategic_must_win_count),
      detail: "High-value pursuits above sponsor threshold",
    },
    {
      label: "Live tenders",
      value: String(dashboard.live_tender_count),
      detail: "PQQ, ITT, pricing, review or negotiation stages",
    },
  ];

  return (
    <Panel
      title="Executive Command Summary"
      action={<StatusPill tone="green" label="Live API" />}
    >
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_260px]">
        <div>
          <h2 className="text-xl font-semibold leading-8 text-white">
            {summaryParts[0]}
          </h2>
          <div className="mt-5 grid gap-3">
            {summaryParts.slice(1).map((point) => (
              <div
                key={point}
                className="flex gap-3 text-sm leading-6 text-slate-300"
              >
                <CheckCircle2
                  aria-hidden="true"
                  className="mt-1 h-4 w-4 shrink-0 text-mitie-lime"
                />
                <p>{point}</p>
              </div>
            ))}
          </div>
        </div>
        <div className="grid content-start gap-3">
          {moduleHealth.map((item) => (
            <MetricLine key={item.label} {...item} />
          ))}
        </div>
      </div>
    </Panel>
  );
}

export function ExecutiveReportExportPanel({
  state,
  onExport,
}: {
  state: ReportExportState;
  onExport: () => void;
}) {
  const isLoading = state.status === "loading";

  return (
    <Panel
      title="Executive Report Export"
      action={
        <button
          type="button"
          onClick={onExport}
          disabled={isLoading}
          data-testid="export-executive-report-button"
          className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-white/10 bg-white px-3 py-2 text-sm font-bold text-[#10171b] transition hover:bg-slate-200 disabled:cursor-wait disabled:border-white/10 disabled:bg-white/10 disabled:text-slate-400"
        >
          {isLoading ? (
            <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
          ) : (
            <Download aria-hidden="true" className="h-4 w-4" />
          )}
          {isLoading ? "Exporting Report" : "Export Executive Report"}
        </button>
      }
    >
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
        <div className="rounded-md border border-white/10 bg-[#111a20] p-4">
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill tone="green" label="MD / FD / GSD" />
            <StatusPill tone="cyan" label="Report-ready JSON" />
            <StatusPill tone="amber" label="Printable HTML" />
          </div>
          <h3 className="mt-4 text-lg font-semibold leading-7 text-white">
            Board pack snapshot for commercial review
          </h3>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            Pulls live dashboard KPIs, leadership summary, top opportunities,
            LE1 finance, self-delivery, executive actions, risks and
            recommendations from the backend report endpoint.
          </p>
        </div>

        <div className="grid content-start gap-3">
          <MetricLine
            label="Report source"
            value="/api/reports/executive-summary"
            detail="Backend generated; no OpenAI key is exposed to the browser"
          />
          {state.status === "success" ? (
            <MetricLine
              label="Last export"
              value={shortDate(state.report.reporting_date)}
              detail={
                state.urls
                  ? "JSON download and printable report view are ready"
                  : "Report generated; export links are unavailable in this browser"
              }
            />
          ) : (
            <MetricLine
              label="Export format"
              value="JSON + HTML"
              detail="MVP report output for review and browser printing"
            />
          )}
        </div>
      </div>

      {state.status === "error" ? (
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
                Executive report was not exported
              </p>
              <p className="mt-2 text-sm leading-6 text-amber-100/80">
                {state.message}
              </p>
            </div>
          </div>
        </div>
      ) : null}

      {state.status === "success" ? (
        <div className="mt-4 rounded-md border border-emerald-300/20 bg-emerald-400/10 p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-semibold text-emerald-100">
                Executive report exported
              </p>
              <p className="mt-2 text-sm leading-6 text-emerald-100/80">
                {state.report.report_name} is ready for MD, FD and Group Sales
                Director review.
              </p>
            </div>
            {state.urls ? (
              <div className="flex flex-wrap items-center gap-2">
                <a
                  href={state.urls.jsonUrl}
                  download={state.urls.filename}
                  className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-emerald-200/30 bg-emerald-100 px-3 py-2 text-sm font-bold text-[#0b2f24] transition hover:bg-white"
                >
                  <Download aria-hidden="true" className="h-4 w-4" />
                  Download JSON
                </a>
                <a
                  href={state.urls.htmlUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-emerald-200/30 bg-[#0b2f24] px-3 py-2 text-sm font-bold text-emerald-50 transition hover:bg-[#134734]"
                >
                  <Printer aria-hidden="true" className="h-4 w-4" />
                  Open Printable Report
                </a>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
    </Panel>
  );
}

export function LeadershipBriefingPanel({
  state,
  onGenerate,
}: {
  state: LeadershipBriefingState;
  onGenerate: () => void;
}) {
  const isLoading = state.status === "loading";

  return (
    <Panel
      title="Leadership Briefing"
      action={
        <button
          type="button"
          onClick={onGenerate}
          disabled={isLoading}
          data-testid="generate-leadership-briefing-button"
          className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-mitie-lime/30 bg-mitie-lime px-3 py-2 text-sm font-bold text-[#07100b] transition hover:bg-[#d8ff62] disabled:cursor-wait disabled:border-white/10 disabled:bg-white/10 disabled:text-slate-400"
        >
          {isLoading ? (
            <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw aria-hidden="true" className="h-4 w-4" />
          )}
          {isLoading ? "Generating Briefing" : "Generate Leadership Briefing"}
        </button>
      }
    >
      <div className="grid gap-4">
        {state.status === "idle" ? (
          <div className="rounded-md border border-cyan-300/20 bg-cyan-400/10 p-4">
            <p className="text-sm font-semibold text-cyan-100">
              Board-ready AI briefing
            </p>
            <p className="mt-2 text-sm leading-6 text-cyan-100/75">
              Generate a concise leadership view of pipeline position, weighted
              value, margin, urgent deadlines, must-wins, red risks, finance
              attention and this week&apos;s actions.
            </p>
          </div>
        ) : null}

        {state.status === "loading" ? (
          <div className="rounded-md border border-cyan-300/20 bg-cyan-400/10 p-4">
            <div className="flex items-center gap-3 text-sm font-semibold text-cyan-100">
              <Loader2 aria-hidden="true" className="h-5 w-5 animate-spin" />
              Building leadership briefing...
            </div>
            <p className="mt-2 text-sm leading-6 text-cyan-100/75">
              MiSi is asking the backend to convert the live dashboard into MD,
              FD, Sales and Bid Team action lanes.
            </p>
          </div>
        ) : null}

        {state.status === "error" ? (
          <div
            className="rounded-md border border-amber-300/20 bg-amber-400/10 p-4"
            role="alert"
          >
            <div className="flex gap-3">
              <AlertTriangle
                aria-hidden="true"
                className="mt-0.5 h-5 w-5 shrink-0 text-amber-200"
              />
              <div>
                <p className="text-sm font-semibold text-amber-100">
                  Leadership briefing was not generated
                </p>
                <p className="mt-2 text-sm leading-6 text-amber-100/80">
                  {state.message}
                </p>
              </div>
            </div>
          </div>
        ) : null}

        {state.status === "success" ? (
          <LeadershipBriefingResult briefing={state.briefing} />
        ) : null}
      </div>
    </Panel>
  );
}

export function LeadershipBriefingResult({
  briefing,
}: {
  briefing: ExecutiveLeadershipBriefing;
}) {
  return (
    <div className="grid gap-4">
      <section className="rounded-md border border-white/10 bg-[#111a20] p-4">
        <div className="flex flex-wrap items-center gap-2">
          <StatusPill tone="green" label="Board-ready" />
          <StatusPill tone="cyan" label="Backend generated" />
        </div>
        <h3 className="mt-4 text-xl font-semibold leading-8 text-white">
          {briefing.headline}
        </h3>
        <p className="mt-3 text-sm leading-6 text-slate-300">
          {briefing.summary}
        </p>
      </section>

      <div className="grid gap-4 xl:grid-cols-2">
        <BriefingLane
          title="MD Attention"
          tone="green"
          items={briefing.md_attention}
        />
        <BriefingLane
          title="Finance Attention"
          tone="amber"
          items={briefing.finance_attention}
        />
        <BriefingLane
          title="Sales Attention"
          tone="cyan"
          items={briefing.sales_attention}
        />
        <BriefingLane
          title="Bid Team Attention"
          tone="cyan"
          items={briefing.bid_team_attention}
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
        <BriefingLane
          title="Risk Warnings"
          tone="red"
          items={briefing.risk_warnings}
        />
        <BriefingLane
          title="Next Best Actions"
          tone="green"
          items={briefing.next_best_actions}
        />
      </div>
    </div>
  );
}

export function BriefingLane({
  title,
  tone,
  items,
}: {
  title: string;
  tone: Tone;
  items: string[];
}) {
  const Icon = tone === "red" ? AlertTriangle : CheckCircle2;

  return (
    <section className="rounded-md border border-white/10 bg-[#111a20] p-4">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-white">{title}</h3>
        <StatusPill
          tone={tone}
          label={`${items.length} item${items.length === 1 ? "" : "s"}`}
        />
      </div>
      {items.length > 0 ? (
        <ul className="mt-3 grid gap-2">
          {items.map((item) => (
            <li
              key={item}
              className="flex gap-2 text-sm leading-6 text-slate-300"
            >
              <Icon
                aria-hidden="true"
                className={`mt-1 h-4 w-4 shrink-0 ${tone === "red" ? "text-red-200" : "text-mitie-lime"}`}
              />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-sm leading-6 text-slate-500">
          No immediate attention items returned.
        </p>
      )}
    </section>
  );
}
