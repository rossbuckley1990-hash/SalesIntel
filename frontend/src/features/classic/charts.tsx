"use client";

import {
  type DashboardSummary,
  type ExecutiveAction,
  type FinanceForecastSummary,
  type ForecastPoint,
  type MarketSignal,
} from "@/lib/api";
import {
  compactCurrency,
  currency,
  monthLabel,
  percentageValue,
  shortDate,
} from "@/lib/format";
import { useMemo } from "react";
import {
  confidenceTone,
  fitToneForSignal,
  mergeForecastSeries,
} from "./evidence";
import { EmptyState, Panel, ProgressRow, StatusPill } from "./ui";

export function PipelineChart({
  revenue,
  margin,
  tall = false,
}: {
  revenue: ForecastPoint[];
  margin: ForecastPoint[];
  tall?: boolean;
}) {
  const monthRows = useMemo(
    () => mergeForecastSeries(revenue, margin),
    [revenue, margin],
  );
  const maxValue = Math.max(...monthRows.map((item) => item.revenue), 1);

  if (monthRows.length === 0) {
    return (
      <EmptyState
        title="No forecast curve yet"
        message="MiSi has not built an April-to-March forecast for this view. Research or upload opportunities and MiSi will estimate weighted revenue, margin and forecast confidence."
      />
    );
  }

  return (
    <div className="overflow-x-auto">
      <div
        className={`flex min-w-[520px] items-end gap-2 ${tall ? "h-96" : "h-64"} pb-1`}
      >
        {monthRows.map((item) => {
          const revenueHeight = (item.revenue / maxValue) * 100;
          const marginHeight = (item.margin / maxValue) * 100;

          return (
            <div
              key={item.month}
              className="flex h-full min-w-9 flex-1 flex-col justify-end gap-2"
            >
              <div className="flex flex-1 items-end gap-1">
                <div
                  className="w-full rounded-t-sm bg-cyan-300/70"
                  style={{ height: `${revenueHeight}%` }}
                  title={`${item.month} revenue ${currency(item.revenue)}`}
                />
                <div
                  className="w-full rounded-t-sm bg-mitie-lime/80"
                  style={{ height: `${marginHeight}%` }}
                  title={`${item.month} margin ${currency(item.margin)}`}
                />
              </div>
              <div className="text-center text-xs font-semibold text-slate-500">
                {monthLabel(item.month)}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function MarginChart({
  dashboard,
  financeSummary,
}: {
  dashboard: DashboardSummary;
  financeSummary: FinanceForecastSummary;
}) {
  return (
    <Panel
      title="Margin Position"
      action={
        <StatusPill
          tone={dashboard.average_margin_percentage < 25 ? "red" : "green"}
          label={percentageValue(dashboard.average_margin_percentage)}
        />
      }
    >
      <div className="grid gap-4">
        <ProgressRow
          label="Blended pipeline margin"
          value={percentageValue(dashboard.average_margin_percentage)}
          width={Math.min(dashboard.average_margin_percentage, 100)}
        />
        <ProgressRow
          label="Secured margin"
          value={percentageValue(financeSummary.secured_margin_percentage)}
          width={Math.min(financeSummary.secured_margin_percentage, 100)}
        />
        <ProgressRow
          label="Open weighted margin"
          value={
            financeSummary.open_weighted_revenue > 0
              ? percentageValue(
                  financeSummary.open_weighted_margin /
                    financeSummary.open_weighted_revenue,
                )
              : "0%"
          }
          width={
            financeSummary.open_weighted_revenue > 0
              ? Math.min(
                  (financeSummary.open_weighted_margin /
                    financeSummary.open_weighted_revenue) *
                    100,
                  100,
                )
              : 0
          }
        />
      </div>
      <div className="mt-5 rounded-md border border-amber-300/20 bg-amber-400/10 p-4">
        <p className="text-sm font-semibold text-amber-100">
          {financeSummary.margin_warnings.length} margin warning
          {financeSummary.margin_warnings.length === 1 ? "" : "s"}
        </p>
        <p className="mt-2 text-sm leading-5 text-amber-100/75">
          Review opportunities below threshold before final pricing or
          submission.
        </p>
      </div>
    </Panel>
  );
}

export function MarketSignalsPanel({
  marketSignals,
  compact = false,
}: {
  marketSignals: MarketSignal[];
  compact?: boolean;
}) {
  return (
    <Panel
      title="Market Signals"
      action={
        <StatusPill tone="cyan" label={`${marketSignals.length} shown`} />
      }
    >
      {marketSignals.length > 0 ? (
        <div className="divide-y divide-white/10">
          {marketSignals.map((signal) => (
            <article key={signal.id} className="py-4 first:pt-0 last:pb-0">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-white">
                    {signal.buyer_name}
                  </p>
                  <p className="mt-1 text-sm text-slate-500">{signal.sector}</p>
                </div>
                <StatusPill
                  tone={confidenceTone(signal.confidence_score)}
                  label={`${Math.round(signal.confidence_score * 100)}%`}
                />
              </div>
              <p className="mt-3 text-sm leading-6 text-slate-300">
                {signal.title}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <StatusPill
                  tone={fitToneForSignal(signal.likely_mitie_fit)}
                  label={`${signal.likely_mitie_fit || "Unknown"} fit`}
                />
                <StatusPill
                  tone="cyan"
                  label={
                    signal.estimated_value == null
                      ? "Value unknown"
                      : compactCurrency(signal.estimated_value)
                  }
                />
              </div>
              {!compact ? (
                <>
                  <p className="mt-2 text-sm leading-6 text-slate-500">
                    {signal.suggested_action}
                  </p>
                  <p className="mt-2 text-xs leading-5 text-slate-500">
                    {signal.ai_rationale ||
                      "Rationale not yet attached; convert or refresh the signal to create a fuller pack."}
                  </p>
                </>
              ) : null}
            </article>
          ))}
        </div>
      ) : (
        <EmptyState
          title="Awaiting source-attributed signals"
          message="MiSi has not researched this market area yet. Start with a buyer, sector or tender phrase and MiSi will build source-attributed signals with fit, disciplines, rationale and next action."
        />
      )}
    </Panel>
  );
}

export function ExecutiveActionsList({
  actions,
  title,
  expanded = false,
}: {
  actions: ExecutiveAction[];
  title: string;
  expanded?: boolean;
}) {
  return (
    <Panel
      title={title}
      action={<StatusPill tone="red" label={`${actions.length} actions`} />}
    >
      {actions.length > 0 ? (
        <div className="grid gap-3">
          {actions.map((item) => (
            <div
              key={item.id}
              className={`grid gap-3 rounded-md border border-white/10 bg-[#111a20] p-4 ${
                expanded
                  ? "md:grid-cols-[80px_130px_minmax(0,1fr)_150px_120px]"
                  : ""
              }`}
            >
              <div className="text-sm font-black text-red-200">
                {item.priority.toUpperCase()}
              </div>
              <div className="text-sm font-semibold text-slate-300">
                {item.category}
              </div>
              <div>
                <p className="text-sm font-semibold text-white">
                  {item.recommended_action}
                </p>
                <p className="mt-1 text-sm text-slate-500">{item.reason}</p>
              </div>
              {expanded ? (
                <div className="text-sm text-slate-300">
                  Due {shortDate(item.due_date)}
                </div>
              ) : null}
              {expanded ? (
                <div className="text-sm font-semibold text-white">
                  {item.commercial_value == null
                    ? "Value TBC"
                    : currency(item.commercial_value)}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      ) : (
        <EmptyState
          title="No executive actions yet"
          message="MiSi will create leadership actions when an opportunity has material value, risk, deadline pressure or self-delivery capture potential."
        />
      )}
    </Panel>
  );
}
