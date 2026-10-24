import type {
  Detail,
  LivingOpportunity,
  ScenarioResult,
} from "../workspace/types";
import { money, fieldLabel } from "../workspace/api";

export type FieldNode = {
  id: string;
  kind: "opportunity" | "evidence" | "account" | "action" | "financial";
  title: string;
  subtitle: string;
  value: string;
  numericValue: number | null;
  risk: string;
  confidence: number | null;
  unknown: boolean;
  recordId: number;
  rationale: string;
};
export type FieldEdge = {
  source: string;
  target: string;
  relationship: string;
};
export type FieldGraph = {
  nodes: FieldNode[];
  edges: FieldEdge[];
  maxValue: number;
  metricLabel: string;
};
export type Metric =
  | "estimated_gross_margin"
  | "estimated_annual_revenue"
  | "weighted_contract_value";
export function boundedScale(value: number | null, maximum: number) {
  return value == null
    ? 1
    : 0.85 +
        0.6 *
          Math.sqrt(
            Math.max(0, Math.min(1, maximum > 0 ? value / maximum : 0)),
          );
}

export function commercialGraph(
  opportunities: LivingOpportunity[],
  detail: Detail | null,
  metric: Metric,
): FieldGraph {
  const maxValue = Math.max(
    1,
    ...opportunities.map((o) => o.financials[metric] ?? 0),
  );
  const items = detail
    ? opportunities.filter((o) => o.id === detail.opportunity.id)
    : opportunities;
  const nodes: FieldNode[] = items.map((o) => ({
    id: `opportunity:${o.id}`,
    kind: "opportunity",
    title: o.buyer_name,
    subtitle: o.stage,
    value: money(o.financials[metric]),
    numericValue: o.financials[metric],
    risk: o.risk_rating,
    confidence: null,
    unknown: o.financials[metric] == null,
    recordId: o.id,
    rationale: o.name,
  }));
  const edges: FieldEdge[] = [];
  if (detail) {
    const source = `opportunity:${detail.opportunity.id}`;
    if (detail.buyer) {
      nodes.push({
        id: `account:${detail.buyer.id}`,
        kind: "account",
        title: detail.buyer.buyer_name,
        subtitle: "BUYER PROFILE",
        value: detail.buyer.region,
        numericValue: null,
        risk: "",
        confidence: null,
        unknown: false,
        recordId: detail.buyer.id,
        rationale: detail.buyer.procurement_drivers.join("; "),
      });
      edges.push({
        source,
        target: `account:${detail.buyer.id}`,
        relationship: "Recorded buyer name matches account profile",
      });
    }
    detail.evidence.forEach((e) => {
      const id = `field:${e.id}`;
      const financial = [
        "estimated_annual_revenue",
        "estimated_total_contract_value",
        "estimated_gross_margin",
      ].includes(e.field_name);
      nodes.push({
        id,
        kind: "evidence",
        title: fieldLabel(e.field_name),
        subtitle: e.value_type.toUpperCase().replaceAll("_", " "),
        value:
          e.field_value == null
            ? "Evidence missing"
            : financial
              ? money(Number(e.field_value))
              : e.field_name === "probability"
                ? `${Number(e.field_value) * 100}%`
                : String(e.field_value),
        numericValue: null,
        risk: e.value_type === "unknown" ? "Amber" : "",
        confidence: e.confidence_score,
        unknown: e.value_type === "unknown",
        recordId: e.id,
        rationale: e.rationale,
      });
      edges.push({
        source,
        target: id,
        relationship: `Field belongs to opportunity ${detail.opportunity.id}`,
      });
    });
    detail.actions.forEach((a) => {
      const id = `action:${a.id}`;
      nodes.push({
        id,
        kind: "action",
        title: a.owner,
        subtitle: "NEXT ACTION",
        value: a.due_date || "No due date",
        numericValue: null,
        risk: a.status === "blocked" ? "Red" : "",
        confidence: null,
        unknown: false,
        recordId: a.id,
        rationale: a.recommended_action,
      });
      edges.push({
        source,
        target: id,
        relationship: "Recorded related_opportunity_id",
      });
    });
  }
  return { nodes, edges, maxValue, metricLabel: fieldLabel(metric) };
}

export function financialGraph(result: ScenarioResult): FieldGraph {
  const maxValue = Math.max(Number(result.proposed.annual_revenue), 1);
  const definitions = [
    ["inhouse_cost", "In-house cost", "Cyan"],
    ["subcontract_cost", "Subcontract cost", "Amber"],
    ["gross_margin", "Gross margin", "Green"],
  ] as const;
  return {
    maxValue,
    metricLabel: "Annual GBP · bounded square-root width",
    nodes: definitions.map(([key, label, risk], i) => ({
      id: `scenario:${key}`,
      kind: "financial",
      title: label,
      subtitle: "PROPOSED SCENARIO",
      value: money(result.proposed[key]),
      numericValue: Number(result.proposed[key]),
      risk,
      confidence: null,
      unknown: false,
      recordId: i,
      rationale: result.formula,
    })),
    edges: [],
  };
}
