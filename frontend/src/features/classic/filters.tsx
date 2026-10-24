"use client";

import {
  type DashboardSummary,
  type ExecutiveAction,
  type MarketSignal,
  type MisiDashboardData,
  type Opportunity,
} from "@/lib/api";
import { compactCurrency } from "@/lib/format";
import { normaliseRiskLabel } from "./evidence";
import { DashboardFilters, FilterOptions, liveTenderStages } from "./shared";

export function buildFilteredDashboardData(
  data: MisiDashboardData,
  filters: DashboardFilters,
): MisiDashboardData {
  const opportunities = data.opportunities
    .filter((opportunity) => opportunityMatchesFilters(opportunity, filters))
    .slice()
    .sort((first, second) => {
      const priorityDelta = second.priority_score - first.priority_score;
      if (priorityDelta !== 0) {
        return priorityDelta;
      }
      return second.weighted_pipeline_value - first.weighted_pipeline_value;
    });
  const visibleOpportunityIds = new Set(
    opportunities.map((opportunity) => opportunity.id),
  );
  const marketSignals = data.marketSignals.filter((signal) =>
    marketSignalMatchesFilters(signal, filters),
  );
  const executiveActions = data.executiveActions
    .filter((action) =>
      executiveActionMatchesFilters(action, filters, visibleOpportunityIds),
    )
    .slice()
    .sort(compareExecutiveActions);
  const dashboard = buildFilteredDashboardSummary(
    data.dashboard,
    opportunities,
    marketSignals,
    executiveActions,
    filters,
  );

  return {
    ...data,
    dashboard,
    opportunities,
    marketSignals,
    executiveActions,
  };
}

export function buildFilteredDashboardSummary(
  originalDashboard: DashboardSummary,
  opportunities: Opportunity[],
  marketSignals: MarketSignal[],
  executiveActions: ExecutiveAction[],
  filters: DashboardFilters,
): DashboardSummary {
  const liveOpportunities = opportunities.filter(
    (opportunity) =>
      !["Won", "Lost", "Qualified out"].includes(opportunity.stage),
  );
  const totalPipelineValue = sumBy(
    liveOpportunities,
    (opportunity) => opportunity.estimated_total_contract_value,
  );
  const weightedPipelineValue = sumBy(
    liveOpportunities,
    (opportunity) => opportunity.weighted_pipeline_value,
  );
  const estimatedGrossMargin = sumBy(
    liveOpportunities,
    (opportunity) => opportunity.estimated_gross_margin,
  );
  const averageMarginPercentage = totalPipelineValue
    ? (estimatedGrossMargin / totalPipelineValue) * 100
    : 0;
  const highRiskCount = liveOpportunities.filter(
    (opportunity) =>
      normaliseRiskLabel(
        opportunity.calculated_risk_rating || opportunity.risk_rating,
      ) === "Red",
  ).length;
  const urgentDeadlineCount = liveOpportunities.filter(
    (opportunity) => opportunity.deadline_warning,
  ).length;
  const strategicMustWinCount = liveOpportunities.filter(
    (opportunity) => opportunity.strategic_must_win,
  ).length;
  const liveTenderCount = liveOpportunities.filter((opportunity) =>
    liveTenderStages.has(opportunity.stage),
  ).length;

  return {
    ...originalDashboard,
    total_pipeline_value: totalPipelineValue,
    weighted_pipeline_value: weightedPipelineValue,
    estimated_gross_margin: estimatedGrossMargin,
    average_margin_percentage: averageMarginPercentage,
    live_opportunity_count: liveOpportunities.length,
    strategic_must_win_count: strategicMustWinCount,
    live_tender_count: liveTenderCount,
    market_signal_count: marketSignals.length,
    high_risk_count: highRiskCount,
    urgent_deadline_count: urgentDeadlineCount,
    executive_summary_text: buildFilteredExecutiveSummaryText({
      filters,
      weightedPipelineValue,
      liveOpportunityCount: liveOpportunities.length,
      highRiskCount,
      urgentDeadlineCount,
      topAction: executiveActions[0],
    }),
    top_opportunities: opportunities.slice(0, 5),
    top_executive_actions: executiveActions.slice(0, 5),
  };
}

export function buildFilteredExecutiveSummaryText({
  filters,
  weightedPipelineValue,
  liveOpportunityCount,
  highRiskCount,
  urgentDeadlineCount,
  topAction,
}: {
  filters: DashboardFilters;
  weightedPipelineValue: number;
  liveOpportunityCount: number;
  highRiskCount: number;
  urgentDeadlineCount: number;
  topAction?: ExecutiveAction;
}) {
  if (liveOpportunityCount === 0) {
    const hasActiveFilters = Object.values(filters).some(Boolean);
    return hasActiveFilters
      ? "No live opportunities match the selected filters. Reset filters or broaden the search to restore the executive view."
      : "No researched opportunity records yet. Use AI Opportunity Builder to turn a rough buyer, tender or sector phrase into a labelled commercial intelligence pack.";
  }

  const scope = activeFilterSummary(filters);
  const action = topAction?.recommended_action
    ? topAction.recommended_action
    : "Review the highest weighted opportunities and confirm next actions.";

  return `${scope} MiSi is tracking ${compactCurrency(weightedPipelineValue)} weighted pipeline across ${liveOpportunityCount} live opportunities, with ${highRiskCount} Red-risk pursuits and ${urgentDeadlineCount} deadline warnings. Recommended next action: ${action}`;
}

export function buildFilterOptions(
  opportunities: Opportunity[],
): FilterOptions {
  return {
    sectors: uniqueSorted(
      opportunities.map((opportunity) => opportunity.sector),
    ),
    regions: uniqueSorted(
      opportunities.map((opportunity) => opportunity.region),
    ),
    stages: uniqueSorted(opportunities.map((opportunity) => opportunity.stage)),
    riskRatings: uniqueSorted(
      opportunities.map((opportunity) =>
        normaliseRiskLabel(
          opportunity.calculated_risk_rating || opportunity.risk_rating,
        ),
      ),
    ),
    owners: uniqueSorted(opportunities.map((opportunity) => opportunity.owner)),
  };
}

export function opportunityMatchesFilters(
  opportunity: Opportunity,
  filters: DashboardFilters,
): boolean {
  if (filters.sector && opportunity.sector !== filters.sector) {
    return false;
  }
  if (filters.region && opportunity.region !== filters.region) {
    return false;
  }
  if (filters.stage && opportunity.stage !== filters.stage) {
    return false;
  }
  if (
    filters.riskRating &&
    normaliseRiskLabel(
      opportunity.calculated_risk_rating || opportunity.risk_rating,
    ) !== filters.riskRating
  ) {
    return false;
  }
  if (filters.owner && opportunity.owner !== filters.owner) {
    return false;
  }

  return textMatches(
    [
      opportunity.name,
      opportunity.buyer_name,
      opportunity.sector,
      opportunity.region,
      opportunity.stage,
      opportunity.owner,
      opportunity.calculated_recommended_action,
      opportunity.recommended_action,
    ],
    filters.search,
  );
}

export function marketSignalMatchesFilters(
  signal: MarketSignal,
  filters: DashboardFilters,
): boolean {
  if (filters.sector && signal.sector !== filters.sector) {
    return false;
  }
  if (filters.region && signal.region !== filters.region) {
    return false;
  }

  return textMatches(
    [
      signal.title,
      signal.buyer_name,
      signal.sector,
      signal.region,
      signal.source_type,
      signal.source_attribution,
      signal.suggested_action,
    ],
    filters.search,
  );
}

export function executiveActionMatchesFilters(
  action: ExecutiveAction,
  filters: DashboardFilters,
  visibleOpportunityIds: Set<number>,
): boolean {
  const opportunityScoped =
    filters.sector ||
    filters.region ||
    filters.stage ||
    filters.riskRating ||
    filters.owner;
  if (opportunityScoped && action.related_opportunity_id !== null) {
    if (!visibleOpportunityIds.has(action.related_opportunity_id)) {
      return false;
    }
  } else if (filters.owner && action.owner !== filters.owner) {
    return false;
  }

  return textMatches(
    [
      action.priority,
      action.category,
      action.owner,
      action.reason,
      action.recommended_action,
      action.status,
    ],
    filters.search,
  );
}

export function compareExecutiveActions(
  first: ExecutiveAction,
  second: ExecutiveAction,
) {
  const priorityDelta =
    priorityRank(first.priority) - priorityRank(second.priority);
  if (priorityDelta !== 0) {
    return priorityDelta;
  }

  return (first.due_date ?? "9999-12-31").localeCompare(
    second.due_date ?? "9999-12-31",
  );
}

export function priorityRank(priority: string) {
  const value = priority.toLowerCase();
  if (value === "high" || value === "p1") {
    return 0;
  }
  if (value === "medium" || value === "p2") {
    return 1;
  }
  if (value === "low" || value === "p3") {
    return 2;
  }
  return 9;
}

export function sumBy<T>(items: T[], getValue: (item: T) => number) {
  return items.reduce((total, item) => total + getValue(item), 0);
}

export function textMatches(values: string[], search: string) {
  const query = search.trim().toLowerCase();
  if (!query) {
    return true;
  }

  return values.some((value) => value.toLowerCase().includes(query));
}

export function uniqueSorted(values: string[]) {
  return Array.from(new Set(values.filter(Boolean))).sort((first, second) =>
    first.localeCompare(second),
  );
}

export function activeFilterSummary(filters: DashboardFilters) {
  const labels = [
    filters.sector,
    filters.region,
    filters.stage,
    filters.riskRating,
    filters.owner,
    filters.search ? `"${filters.search}"` : "",
  ].filter(Boolean);

  return labels.length > 0
    ? `Filtered view (${labels.join(", ")}).`
    : "Full view.";
}

export function splitSummary(summary: string): string[] {
  const parts = summary
    .split(". ")
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => (part.endsWith(".") ? part : `${part}.`));

  return parts.length > 0
    ? parts
    : ["No executive summary was returned by the backend."];
}
