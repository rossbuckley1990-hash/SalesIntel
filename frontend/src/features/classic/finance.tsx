"use client";

import {
  type FinanceForecastSummary,
  type FinanceReviewItem,
  type FinanceWarning,
  type ForecastPoint,
  type MisiDashboardData,
  type OpenForecastItem,
  type Opportunity,
  type SecuredWorkItem,
} from "@/lib/api";
import {
  compactCurrency,
  currency,
  monthLabel,
  percentage,
  percentageValue,
  shortDate,
} from "@/lib/format";
import { CircleDollarSign } from "lucide-react";
import { PipelineChart } from "./charts";
import { confidenceTone } from "./evidence";
import { Tone, liveTenderStages } from "./shared";
import {
  EmptyState,
  MetricLine,
  MiniMetric,
  Panel,
  ProgressRow,
  RiskPill,
  StatusPill,
} from "./ui";

export function TenderIntelligenceView({
  opportunities,
}: {
  opportunities: Opportunity[];
}) {
  const tenders = opportunities
    .filter((opportunity) => liveTenderStages.has(opportunity.stage))
    .sort((first, second) =>
      (first.submission_deadline ?? "9999-12-31").localeCompare(
        second.submission_deadline ?? "9999-12-31",
      ),
    );

  return (
    <div className="grid gap-5">
      <Panel
        title="Tender Intelligence"
        action={
          <StatusPill tone="red" label={`${tenders.length} live tenders`} />
        }
      >
        {tenders.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px] border-collapse text-left">
              <thead>
                <tr className="border-b border-white/10 text-sm text-slate-400">
                  <th className="px-4 py-3 font-semibold">Tender</th>
                  <th className="px-4 py-3 font-semibold">Buyer</th>
                  <th className="px-4 py-3 font-semibold">Deadline</th>
                  <th className="px-4 py-3 font-semibold">Stage</th>
                  <th className="px-4 py-3 font-semibold">Owner</th>
                  <th className="px-4 py-3 font-semibold">Risk</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/10">
                {tenders.map((tender) => (
                  <tr
                    key={tender.id}
                    className="align-top hover:bg-white/[0.03]"
                  >
                    <td className="px-4 py-4 text-sm font-semibold text-white">
                      {tender.name}
                    </td>
                    <td className="px-4 py-4 text-sm text-slate-300">
                      {tender.buyer_name}
                    </td>
                    <td className="px-4 py-4 text-sm font-semibold text-red-200">
                      {shortDate(tender.submission_deadline)}
                    </td>
                    <td className="px-4 py-4 text-sm text-slate-300">
                      {tender.stage}
                    </td>
                    <td className="px-4 py-4 text-sm text-slate-300">
                      {tender.owner}
                    </td>
                    <td className="px-4 py-4">
                      <RiskPill
                        risk={
                          tender.calculated_risk_rating || tender.risk_rating
                        }
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            title="No live tenders"
            message="No opportunities are currently in PQQ, ITT, pricing, review or negotiation stages."
          />
        )}
      </Panel>
    </div>
  );
}

export function PipelineForecastView({ data }: { data: MisiDashboardData }) {
  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_400px]">
      <Panel
        title="Pipeline Forecast"
        action={<StatusPill tone="cyan" label="Dashboard API" />}
      >
        <PipelineChart
          revenue={data.dashboard.monthly_revenue_forecast}
          margin={data.dashboard.monthly_margin_forecast}
          tall
        />
      </Panel>
      <FinanceForecastPanel financeSummary={data.financeSummary} compact />
    </div>
  );
}

export function FinanceView({
  financeSummary,
}: {
  financeSummary: FinanceForecastSummary;
}) {
  return (
    <div className="grid gap-5">
      <FinanceForecastPanel financeSummary={financeSummary} />
      <FinanceControlStrip financeSummary={financeSummary} />

      <div className="grid gap-5 xl:grid-cols-2">
        <Panel
          title="April-to-March Revenue Forecast"
          action={
            <StatusPill
              tone="cyan"
              label={`FY ${financeSummary.financial_year}`}
            />
          }
        >
          <FinanceSingleSeriesChart
            label="Monthly revenue"
            points={financeSummary.monthly_revenue}
            tone="revenue"
            tall
          />
        </Panel>
        <Panel
          title="April-to-March Margin Forecast"
          action={
            <StatusPill
              tone="green"
              label={compactCurrency(
                financeSummary.forecast_margin_to_financial_year_end,
              )}
            />
          }
        >
          <FinanceSingleSeriesChart
            label="Monthly gross margin"
            points={financeSummary.monthly_margin}
            tone="margin"
            tall
          />
        </Panel>
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
        <SecuredWorkTable items={financeSummary.secured_work} />
        <FinanceWarningsPanel
          reviewItems={financeSummary.finance_review_items}
          warnings={financeSummary.margin_warnings}
        />
      </div>

      <OpenOpportunityForecastTable items={financeSummary.open_opportunities} />
    </div>
  );
}

export function FinanceControlStrip({
  financeSummary,
}: {
  financeSummary: FinanceForecastSummary;
}) {
  const openDownside =
    financeSummary.open_weighted_revenue - financeSummary.risk_adjusted_revenue;
  const reviewCount =
    financeSummary.margin_warnings.length +
    financeSummary.finance_review_items.length;
  const securedMix =
    financeSummary.forecast_to_financial_year_end > 0
      ? financeSummary.secured_revenue /
        financeSummary.forecast_to_financial_year_end
      : 0;

  return (
    <Panel
      title="FD Forecast Control"
      action={
        <StatusPill
          tone={reviewCount > 0 ? "amber" : "green"}
          label={`${reviewCount} review item${reviewCount === 1 ? "" : "s"}`}
        />
      }
    >
      <div className="grid gap-4 lg:grid-cols-[repeat(4,minmax(0,1fr))]">
        <MiniMetric
          label="Secured mix"
          value={percentage(securedMix)}
          danger={securedMix < 0.2}
        />
        <MiniMetric
          label="Open weighted revenue"
          value={compactCurrency(financeSummary.open_weighted_revenue)}
        />
        <MiniMetric
          label="Risk adjustment impact"
          value={compactCurrency(Math.max(openDownside, 0))}
          danger={openDownside > 0}
        />
        <MiniMetric
          label="Forecast GM to FY end"
          value={compactCurrency(
            financeSummary.forecast_margin_to_financial_year_end,
          )}
          danger={financeSummary.margin_warnings.length > 0}
        />
      </div>
      <div className="mt-5 rounded-md border border-amber-300/20 bg-amber-400/10 p-4">
        <p className="text-sm font-semibold text-amber-100">
          Finance decision required
        </p>
        <p className="mt-2 text-sm leading-6 text-amber-100/80">
          Validate margin warnings, probability weighting and risk adjustments
          before this forecast is used as an LE1 commitment. WON work remains
          separated from open opportunities.
        </p>
      </div>
    </Panel>
  );
}

export function FinanceForecastPanel({
  financeSummary,
  compact = false,
}: {
  financeSummary: FinanceForecastSummary;
  compact?: boolean;
}) {
  const headlineMetrics = compact
    ? [
        {
          label: "Secured revenue",
          value: compactCurrency(financeSummary.secured_revenue),
          danger: false,
        },
        {
          label: "Open weighted",
          value: compactCurrency(financeSummary.open_weighted_revenue),
          danger: false,
        },
        {
          label: "Risk-adjusted forecast",
          value: compactCurrency(financeSummary.risk_adjusted_revenue),
          danger: financeSummary.margin_warnings.length > 0,
        },
      ]
    : [
        {
          label: "WON revenue",
          value: compactCurrency(financeSummary.secured_revenue),
          danger: false,
        },
        {
          label: "WON gross margin",
          value: compactCurrency(financeSummary.secured_gross_margin),
          danger: false,
        },
        {
          label: "WON margin %",
          value: percentageValue(financeSummary.secured_margin_percentage),
          danger: financeSummary.secured_margin_percentage < 25,
        },
        {
          label: "Open weighted revenue",
          value: compactCurrency(financeSummary.open_weighted_revenue),
          danger: false,
        },
        {
          label: "Risk-adjusted forecast",
          value: compactCurrency(financeSummary.risk_adjusted_revenue),
          danger: financeSummary.margin_warnings.length > 0,
        },
        {
          label: "Forecast to FY end",
          value: compactCurrency(financeSummary.forecast_to_financial_year_end),
          danger: false,
        },
      ];

  return (
    <Panel
      title="LE1 Finance Forecast"
      action={
        <StatusPill
          tone="green"
          label={`April to March FY ${financeSummary.financial_year}`}
        />
      }
    >
      <div
        className={`grid gap-4 ${compact ? "md:grid-cols-3" : "md:grid-cols-3 2xl:grid-cols-6"}`}
      >
        {headlineMetrics.map((metric) => (
          <MiniMetric
            key={metric.label}
            danger={metric.danger}
            label={metric.label}
            value={metric.value}
          />
        ))}
      </div>

      {compact ? (
        <div className="mt-6">
          <PipelineChart
            revenue={financeSummary.monthly_revenue}
            margin={financeSummary.monthly_margin}
          />
        </div>
      ) : (
        <>
          <FinancialYearMonthStrip
            months={financeSummary.financial_year_months}
          />

          <div className="mt-6 grid gap-5 xl:grid-cols-[minmax(0,1fr)_390px]">
            <FinanceRevenueMix financeSummary={financeSummary} />
            <div className="grid content-start gap-3">
              <MetricLine
                label="Secured vs weighted open revenue"
                value={`${compactCurrency(financeSummary.secured_revenue)} / ${compactCurrency(financeSummary.open_weighted_revenue)}`}
                detail="WON work is held separately from probability-weighted open opportunities."
              />
              <MetricLine
                label="Risk-adjusted forecast"
                value={compactCurrency(financeSummary.risk_adjusted_revenue)}
                detail={`${compactCurrency(financeSummary.risk_adjusted_margin)} risk-adjusted gross margin`}
              />
              <MetricLine
                label="Finance review warnings"
                value={String(
                  financeSummary.finance_review_items.length +
                    financeSummary.margin_warnings.length,
                )}
                detail="Margin, risk and category checks requiring FD or bid governance attention."
              />
            </div>
          </div>
        </>
      )}

      <div className="mt-6 grid gap-3">
        <MetricLine
          label="Forecast to year end"
          value={compactCurrency(financeSummary.forecast_to_financial_year_end)}
          detail={`${compactCurrency(financeSummary.forecast_margin_to_financial_year_end)} forecast gross margin`}
        />
        <MetricLine
          label="Secured margin"
          value={percentageValue(financeSummary.secured_margin_percentage)}
          detail={`${financeSummary.secured_work.length} WON work items separated from open opportunities`}
        />
        <MetricLine
          label="Margin warnings"
          value={String(financeSummary.margin_warnings.length)}
          detail="Items below finance review margin threshold"
        />
      </div>
    </Panel>
  );
}

export function FinancialYearMonthStrip({ months }: { months: string[] }) {
  if (months.length === 0) {
    return null;
  }

  return (
    <div className="mt-5 rounded-md border border-cyan-300/20 bg-cyan-300/10 p-4">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm font-semibold text-cyan-100">
            April-to-March financial year
          </p>
          <p className="mt-1 text-sm leading-5 text-cyan-100/75">
            Forecast window runs {monthYearLabel(months[0])} to{" "}
            {monthYearLabel(months[months.length - 1])}.
          </p>
        </div>
        <p className="text-xs font-semibold uppercase text-cyan-100/60">
          {months.length} periods
        </p>
      </div>
      <div className="mt-4 grid grid-cols-6 gap-2 md:grid-cols-12">
        {months.map((month) => (
          <span
            key={month}
            className="rounded-sm border border-white/10 bg-[#0d151a] px-2 py-2 text-center text-xs font-semibold text-slate-300"
          >
            {monthLabel(month)}
          </span>
        ))}
      </div>
    </div>
  );
}

export function FinanceRevenueMix({
  financeSummary,
}: {
  financeSummary: FinanceForecastSummary;
}) {
  const maxValue = Math.max(
    financeSummary.secured_revenue,
    financeSummary.open_weighted_revenue,
    financeSummary.risk_adjusted_revenue,
    1,
  );

  return (
    <div className="rounded-md border border-white/10 bg-[#111a20] p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-white">
            Secured vs weighted open revenue
          </p>
          <p className="mt-1 text-sm leading-5 text-slate-500">
            LE1 separates committed WON work from open probability-weighted
            upside.
          </p>
        </div>
        <CircleDollarSign
          aria-hidden="true"
          className="h-5 w-5 shrink-0 text-mitie-lime"
        />
      </div>
      <div className="mt-5 grid gap-4">
        <ProgressRow
          label="Secured WON revenue"
          value={compactCurrency(financeSummary.secured_revenue)}
          width={(financeSummary.secured_revenue / maxValue) * 100}
        />
        <ProgressRow
          label="Weighted open revenue"
          value={compactCurrency(financeSummary.open_weighted_revenue)}
          width={(financeSummary.open_weighted_revenue / maxValue) * 100}
        />
        <ProgressRow
          label="Risk-adjusted open revenue"
          value={compactCurrency(financeSummary.risk_adjusted_revenue)}
          width={(financeSummary.risk_adjusted_revenue / maxValue) * 100}
        />
      </div>
    </div>
  );
}

export function FinanceSingleSeriesChart({
  label,
  points,
  tall = false,
  tone,
}: {
  label: string;
  points: ForecastPoint[];
  tall?: boolean;
  tone: "revenue" | "margin";
}) {
  const maxValue = Math.max(...points.map((point) => point.value), 1);
  const barClass =
    tone === "revenue"
      ? "bg-cyan-300/80 shadow-[0_0_18px_rgba(103,232,249,0.12)]"
      : "bg-mitie-lime/85 shadow-[0_0_18px_rgba(186,255,41,0.12)]";
  const total = points.reduce((sum, point) => sum + point.value, 0);

  if (points.length === 0) {
    return (
      <EmptyState
        title={`No ${label.toLowerCase()} data`}
        message="The backend returned no monthly finance forecast points."
      />
    );
  }

  return (
    <div>
      <div className="mb-4 flex items-end justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-white">{label}</p>
          <p className="mt-1 text-sm text-slate-500">
            April to March, sourced from /api/finance-forecast/summary.
          </p>
        </div>
        <p className="text-sm font-black text-white">
          {compactCurrency(total)}
        </p>
      </div>
      <div className="overflow-x-auto">
        <div
          className={`flex min-w-[560px] items-end gap-2 ${tall ? "h-80" : "h-60"} pb-1`}
        >
          {points.map((point) => {
            const height = (point.value / maxValue) * 100;

            return (
              <div
                key={point.month}
                className="flex h-full min-w-9 flex-1 flex-col justify-end gap-2"
              >
                <div
                  aria-label={`${monthLabel(point.month)} ${label}: ${currency(point.value)}`}
                  className={`w-full rounded-t-sm ${barClass}`}
                  style={{ height: `${height}%` }}
                  title={`${monthYearLabel(point.month)} ${label.toLowerCase()} ${currency(point.value)}`}
                />
                <div className="text-center text-xs font-semibold text-slate-500">
                  {monthLabel(point.month)}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export function SecuredWorkTable({ items }: { items: SecuredWorkItem[] }) {
  const sortedItems = [...items].sort((first, second) =>
    first.delivery_start_month.localeCompare(second.delivery_start_month),
  );

  return (
    <Panel
      title="WON Work"
      action={<StatusPill tone="green" label={`${items.length} secured`} />}
    >
      {sortedItems.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[920px] border-collapse text-left">
            <thead>
              <tr className="border-b border-white/10 text-sm text-slate-400">
                <th className="px-4 py-3 font-semibold">WON work</th>
                <th className="px-4 py-3 font-semibold">Client</th>
                <th className="px-4 py-3 font-semibold">WON revenue</th>
                <th className="px-4 py-3 font-semibold">WON gross margin</th>
                <th className="px-4 py-3 font-semibold">Margin %</th>
                <th className="px-4 py-3 font-semibold">
                  Delivery start month
                </th>
                <th className="px-4 py-3 font-semibold">Discipline</th>
                <th className="px-4 py-3 font-semibold">Confidence</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/10">
              {sortedItems.map((item) => (
                <tr
                  key={item.opportunity_id}
                  className="align-top hover:bg-white/[0.03]"
                >
                  <td className="px-4 py-4 text-sm font-semibold text-white">
                    {item.opportunity_name}
                  </td>
                  <td className="px-4 py-4 text-sm text-slate-300">
                    {item.client}
                  </td>
                  <td className="px-4 py-4 text-sm font-semibold text-white">
                    {currency(item.won_revenue)}
                  </td>
                  <td className="px-4 py-4 text-sm text-slate-300">
                    {currency(item.won_gross_margin)}
                  </td>
                  <td className="px-4 py-4 text-sm text-slate-300">
                    {percentageValue(item.margin_percentage)}
                  </td>
                  <td className="px-4 py-4 text-sm text-slate-300">
                    {monthYearLabel(item.delivery_start_month)}
                  </td>
                  <td className="px-4 py-4 text-sm text-slate-300">
                    {item.discipline ?? "Discipline TBC"}
                  </td>
                  <td className="px-4 py-4">
                    <StatusPill
                      tone={confidenceTone(item.confidence)}
                      label={percentage(item.confidence)}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState
          title="No WON work"
          message="No confirmed secured revenue is loaded for this financial year. Once WON work is imported, MiSi will separate committed revenue from open weighted forecast."
        />
      )}
    </Panel>
  );
}

export function OpenOpportunityForecastTable({
  items,
}: {
  items: OpenForecastItem[];
}) {
  const sortedItems = [...items].sort((first, second) => {
    const startOrder = first.forecast_start_month.localeCompare(
      second.forecast_start_month,
    );
    return startOrder === 0
      ? second.risk_adjusted_revenue - first.risk_adjusted_revenue
      : startOrder;
  });

  return (
    <Panel
      title="Open Opportunities"
      action={
        <StatusPill tone="cyan" label={`${items.length} forecast items`} />
      }
    >
      {sortedItems.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1180px] border-collapse text-left">
            <thead>
              <tr className="border-b border-white/10 text-sm text-slate-400">
                <th className="px-4 py-3 font-semibold">Opportunity</th>
                <th className="px-4 py-3 font-semibold">Client</th>
                <th className="px-4 py-3 font-semibold">
                  Forecast start month
                </th>
                <th className="px-4 py-3 font-semibold">Revenue to FY end</th>
                <th className="px-4 py-3 font-semibold">Estimated margin</th>
                <th className="px-4 py-3 font-semibold">Margin %</th>
                <th className="px-4 py-3 font-semibold">
                  Probability weighting
                </th>
                <th className="px-4 py-3 font-semibold">Risk adjustment</th>
                <th className="px-4 py-3 font-semibold">
                  Risk-adjusted revenue
                </th>
                <th className="px-4 py-3 font-semibold">Forecast category</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/10">
              {sortedItems.map((item) => (
                <tr
                  key={item.opportunity_id}
                  className="align-top hover:bg-white/[0.03]"
                >
                  <td className="px-4 py-4 text-sm font-semibold text-white">
                    {item.opportunity_name}
                  </td>
                  <td className="px-4 py-4 text-sm text-slate-300">
                    {item.client}
                  </td>
                  <td className="px-4 py-4 text-sm text-slate-300">
                    {monthYearLabel(item.forecast_start_month)}
                  </td>
                  <td className="px-4 py-4 text-sm font-semibold text-white">
                    {currency(item.revenue_to_financial_year_end)}
                  </td>
                  <td className="px-4 py-4 text-sm text-slate-300">
                    {currency(item.estimated_margin)}
                  </td>
                  <td className="px-4 py-4 text-sm text-slate-300">
                    {percentageValue(item.margin_percentage)}
                  </td>
                  <td className="px-4 py-4 text-sm text-slate-300">
                    {percentage(item.probability_weighting)}
                  </td>
                  <td className="px-4 py-4 text-sm text-slate-300">
                    {percentage(item.risk_adjustment)}
                  </td>
                  <td className="px-4 py-4 text-sm font-semibold text-mitie-lime">
                    {currency(item.risk_adjusted_revenue)}
                  </td>
                  <td className="px-4 py-4">
                    <StatusPill
                      tone={forecastCategoryTone(item.forecast_category)}
                      label={item.forecast_category}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState
          title="No open opportunity forecast"
          message="MiSi needs researched or uploaded opportunities before it can build weighted revenue, margin and risk-adjusted LE1 forecast lines."
        />
      )}
    </Panel>
  );
}

export function FinanceWarningsPanel({
  reviewItems,
  warnings,
}: {
  reviewItems: FinanceReviewItem[];
  warnings: FinanceWarning[];
}) {
  const warningCount = warnings.length + reviewItems.length;

  return (
    <Panel
      title="Finance Review Warnings"
      action={
        warningCount > 0 ? (
          <StatusPill tone="red" label={`${warningCount} warnings`} />
        ) : (
          <StatusPill tone="green" label="Clear" />
        )
      }
    >
      {warningCount > 0 ? (
        <div className="grid gap-4">
          {warnings.length > 0 ? (
            <div>
              <p className="text-sm font-semibold text-red-100">
                Margin threshold warnings
              </p>
              <div className="mt-3 grid gap-3">
                {warnings.map((warning) => (
                  <article
                    key={`warning-${warning.opportunity_id}`}
                    className="rounded-md border border-red-300/20 bg-red-500/10 p-4"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-white">
                          {warning.opportunity_name}
                        </p>
                        <p className="mt-1 text-xs text-red-100/70">
                          {warning.client}
                        </p>
                      </div>
                      <StatusPill
                        tone="red"
                        label={percentageValue(warning.margin_percentage)}
                      />
                    </div>
                    <p className="mt-3 text-sm leading-6 text-red-100/80">
                      {warning.reason}
                    </p>
                    <p className="mt-3 text-xs font-semibold uppercase text-red-100/60">
                      Threshold {percentageValue(warning.threshold_percentage)}
                    </p>
                  </article>
                ))}
              </div>
            </div>
          ) : null}

          {reviewItems.length > 0 ? (
            <div>
              <p className="text-sm font-semibold text-amber-100">
                FD / bid governance items
              </p>
              <div className="mt-3 grid gap-3">
                {reviewItems.map((item) => (
                  <article
                    key={`review-${item.opportunity_id}-${item.category}`}
                    className="rounded-md border border-white/10 bg-[#111a20] p-4"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-white">
                          {item.opportunity_name}
                        </p>
                        <p className="mt-1 text-xs text-slate-500">
                          {item.client}
                        </p>
                      </div>
                      <StatusPill
                        tone={priorityTone(item.priority)}
                        label={item.priority}
                      />
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-300">
                      {item.reason}
                    </p>
                    <p className="mt-3 text-sm font-semibold text-mitie-lime">
                      {item.recommended_action}
                    </p>
                  </article>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      ) : (
        <EmptyState
          title="No finance review warnings"
          message="No finance review items are currently flagged. MiSi will surface margin protection, risk adjustment and forecast confidence issues as opportunities are researched."
        />
      )}
    </Panel>
  );
}

export function forecastCategoryTone(category: string): Tone {
  const normalisedCategory = category.toLowerCase();

  if (
    normalisedCategory.includes("committed") ||
    normalisedCategory.includes("likely")
  ) {
    return "green";
  }

  if (normalisedCategory.includes("best")) {
    return "cyan";
  }

  if (
    normalisedCategory.includes("at risk") ||
    normalisedCategory.includes("excluded")
  ) {
    return "red";
  }

  return "amber";
}

export function priorityTone(priority: string): Tone {
  const normalisedPriority = priority.toLowerCase();

  if (
    normalisedPriority.includes("high") ||
    normalisedPriority.includes("urgent")
  ) {
    return "red";
  }

  if (normalisedPriority.includes("medium")) {
    return "amber";
  }

  return "cyan";
}

export function relationshipTone(relationship: string): Tone {
  const value = relationship.toLowerCase();
  if (value.includes("warm") || value.includes("strong")) {
    return "green";
  }
  if (value.includes("competitive") || value.includes("cold")) {
    return "red";
  }
  if (value.includes("developing") || value.includes("unknown")) {
    return "amber";
  }
  return "cyan";
}

export function threatTone(threat: string): Tone {
  const value = threat.toLowerCase();
  if (value.includes("high")) {
    return "red";
  }
  if (value.includes("medium")) {
    return "amber";
  }
  if (value.includes("low")) {
    return "green";
  }
  return "cyan";
}

export function monthYearLabel(value: string | null): string {
  if (!value) {
    return "Not set";
  }

  const [year, month] = value.split("-");
  const yearNumber = Number(year);
  const monthNumber = Number(month);

  if (
    !Number.isInteger(yearNumber) ||
    !Number.isInteger(monthNumber) ||
    monthNumber < 1 ||
    monthNumber > 12
  ) {
    return value;
  }

  const date = new Date(yearNumber, monthNumber - 1, 1);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-GB", {
    month: "short",
    year: "numeric",
  }).format(date);
}
