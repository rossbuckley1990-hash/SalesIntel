"use client";

import {
  type FieldIntelligence,
  type ForecastPoint,
  type Opportunity,
} from "@/lib/api";
import { currency, percentageValue } from "@/lib/format";
import { monthYearLabel } from "./finance";
import { IntelligenceFieldView, Tone } from "./shared";

export function mergeForecastSeries(
  revenue: ForecastPoint[],
  margin: ForecastPoint[],
) {
  const valuesByMonth = new Map<
    string,
    { month: string; revenue: number; margin: number }
  >();

  revenue.forEach((point) => {
    valuesByMonth.set(point.month, {
      month: point.month,
      revenue: point.value,
      margin: valuesByMonth.get(point.month)?.margin ?? 0,
    });
  });

  margin.forEach((point) => {
    const existing = valuesByMonth.get(point.month);
    valuesByMonth.set(point.month, {
      month: point.month,
      revenue: existing?.revenue ?? 0,
      margin: point.value,
    });
  });

  return Array.from(valuesByMonth.values()).sort((first, second) =>
    first.month.localeCompare(second.month),
  );
}

export const opportunityFieldConfigs: Array<{
  fieldName: string;
  label: string;
  getValue: (opportunity: Opportunity) => unknown;
  format: (value: unknown) => string;
  unknownReason: string;
  nextStep: string;
}> = [
  {
    fieldName: "name",
    label: "Opportunity name",
    getValue: (opportunity) => opportunity.name,
    format: textDisplay,
    unknownReason: "Opportunity name is not confirmed from the source signal.",
    nextStep:
      "Confirm the tender title, buyer project name or internal opportunity name.",
  },
  {
    fieldName: "buyer_name",
    label: "Buyer",
    getValue: (opportunity) => opportunity.buyer_name,
    format: textDisplay,
    unknownReason: "Buyer is not confirmed from the source data.",
    nextStep:
      "Confirm the contracting authority or client from an approved source.",
  },
  {
    fieldName: "sector",
    label: "Sector",
    getValue: (opportunity) => opportunity.sector,
    format: textDisplay,
    unknownReason: "Sector is not confirmed from the source data.",
    nextStep:
      "Confirm the buyer sector from CRM, tender notice or buyer profile.",
  },
  {
    fieldName: "region",
    label: "Region",
    getValue: (opportunity) => opportunity.region,
    format: textDisplay,
    unknownReason: "Region is not confirmed from the source data.",
    nextStep: "Confirm the delivery region and local branch coverage.",
  },
  {
    fieldName: "stage",
    label: "Tender stage",
    getValue: (opportunity) => opportunity.stage,
    format: textDisplay,
    unknownReason: "Tender stage is not yet evidenced.",
    nextStep: "Check the tender portal, CRM stage or opportunity owner update.",
  },
  {
    fieldName: "estimated_annual_revenue",
    label: "Annual revenue",
    getValue: (opportunity) => opportunity.estimated_annual_revenue,
    format: currencyDisplay,
    unknownReason:
      "Annual revenue is not supported by a contract value, term or asset schedule.",
    nextStep: "Confirm contract term, asset count and annual service run-rate.",
  },
  {
    fieldName: "estimated_total_contract_value",
    label: "Contract value",
    getValue: (opportunity) => opportunity.estimated_total_contract_value,
    format: currencyDisplay,
    unknownReason:
      "Total contract value is not evidenced by public sources or internal tracker data.",
    nextStep:
      "Validate value against tender notice, spend history or buyer budget.",
  },
  {
    fieldName: "estimated_gross_margin",
    label: "Gross margin",
    getValue: (opportunity) => opportunity.estimated_gross_margin,
    format: currencyDisplay,
    unknownReason:
      "Gross margin cannot be supported without service mix and delivery assumptions.",
    nextStep:
      "Model labour mix, subcontract exposure, remedials and SLA assumptions.",
  },
  {
    fieldName: "margin_percentage",
    label: "Margin %",
    getValue: (opportunity) => opportunity.margin_percentage,
    format: percentageDisplay,
    unknownReason:
      "Margin percentage is not yet supported by pricing or cost assumptions.",
    nextStep:
      "Confirm pricing model, self-delivery content and commercial walkaway point.",
  },
  {
    fieldName: "probability",
    label: "Win probability",
    getValue: (opportunity) => opportunity.probability,
    format: probabilityDisplay,
    unknownReason:
      "Probability is not evidenced by stage, buyer access or incumbent position.",
    nextStep:
      "Confirm procurement stage, relationship strength and competitor threat.",
  },
  {
    fieldName: "weighted_value",
    label: "Weighted value",
    getValue: (opportunity) =>
      opportunity.weighted_pipeline_value || opportunity.weighted_value,
    format: currencyDisplay,
    unknownReason:
      "Weighted value cannot be calculated until contract value and probability are credible.",
    nextStep:
      "Validate estimated value and probability, then let SalesIntel recalculate weighted pipeline.",
  },
  {
    fieldName: "forecast_start_month",
    label: "Forecast start month",
    getValue: (opportunity) => opportunity.forecast_start_month,
    format: monthDisplay,
    unknownReason:
      "Forecast start month is not known from the current evidence.",
    nextStep:
      "Confirm expected award date, mobilisation window and LE1 treatment.",
  },
  {
    fieldName: "self_delivery_fit",
    label: "Self-delivery fit",
    getValue: (opportunity) => opportunity.self_delivery_fit,
    format: textDisplay,
    unknownReason:
      "Self-delivery fit has not been assessed against Mitie Fire & Security capability.",
    nextStep:
      "Check discipline mix, regional coverage, accreditations and subcontract exposure.",
  },
  {
    fieldName: "risk_rating",
    label: "Risk rating",
    getValue: (opportunity) =>
      opportunity.calculated_risk_rating || opportunity.risk_rating,
    format: riskDisplay,
    unknownReason:
      "Risk rating is not supported by enough commercial evidence.",
    nextStep:
      "Review value, margin, deadline, mobilisation and competitor risk.",
  },
  {
    fieldName: "strategic_fit_score",
    label: "Strategic fit",
    getValue: (opportunity) => opportunity.strategic_fit_score,
    format: scoreDisplay,
    unknownReason:
      "Strategic fit has not been scored against Mitie priorities.",
    nextStep:
      "Confirm sector priority, buyer relationship, self-delivery capture and margin quality.",
  },
  {
    fieldName: "bid_no_bid_recommendation",
    label: "Bid / no-bid",
    getValue: (opportunity) =>
      opportunity.calculated_bid_no_bid_recommendation ||
      opportunity.bid_no_bid_recommendation,
    format: textDisplay,
    unknownReason: "Bid/no-bid position has not been qualified.",
    nextStep:
      "Run bid/no-bid review with value, fit, risk, margin and deadline evidence.",
  },
  {
    fieldName: "recommended_action",
    label: "Recommended action",
    getValue: (opportunity) =>
      opportunity.calculated_recommended_action ||
      opportunity.recommended_action,
    format: textDisplay,
    unknownReason: "Next action is not yet defined.",
    nextStep:
      "Confirm contract scope, asset schedule, buyer contact and next governance gate.",
  },
  {
    fieldName: "incumbent_supplier",
    label: "Incumbent supplier",
    getValue: () => null,
    format: textDisplay,
    unknownReason: "Incumbent supplier was not found in available SalesIntel data.",
    nextStep:
      "Check tender award history, buyer website, CRM notes or approved market sources.",
  },
];

export function buildOpportunityFieldViews(
  opportunity: Opportunity,
  fieldIntelligence: FieldIntelligence[],
  overrides: Record<string, string>,
): IntelligenceFieldView[] {
  const fieldsByName = new Map(
    fieldIntelligence.map((field) => [field.field_name, field]),
  );

  return opportunityFieldConfigs.map((config) => {
    const sourceField = fieldsByName.get(config.fieldName);
    const rawValue =
      overrides[config.fieldName] ??
      sourceField?.field_value ??
      config.getValue(opportunity);
    const valueMissing = isMissingCommercialValue(config.fieldName, rawValue);
    const valueType =
      sourceField?.value_type ?? (valueMissing ? "unknown" : "known");
    const confidenceScore =
      sourceField?.confidence_score ?? (valueMissing ? 0 : 1);
    const displayValue = valueMissing ? "Unknown" : config.format(rawValue);

    return {
      fieldName: config.fieldName,
      label: config.label,
      displayValue,
      rawValue,
      valueType,
      confidenceScore,
      rationale:
        sourceField?.rationale ||
        (valueMissing
          ? config.unknownReason
          : "Actual value currently held in the SalesIntel opportunity record."),
      sourceUrls: sourceField?.source_urls ?? [],
      sourceTitles: sourceField?.source_titles ?? [],
      recommendedNextStep:
        sourceField?.recommended_next_step ||
        (valueMissing
          ? config.nextStep
          : "Keep this value under review as source evidence changes."),
      needsUserConfirmation:
        sourceField?.needs_user_confirmation ??
        (valueMissing || valueType !== "known"),
    };
  });
}

export function researchFieldToView(field: {
  field_name: string;
  field_value: unknown;
  value_type: FieldIntelligence["value_type"];
  confidence_score: number;
  rationale: string;
  source_urls: string[];
  source_titles: string[];
  recommended_next_step: string;
  needs_user_confirmation: boolean;
}): IntelligenceFieldView {
  const config = opportunityFieldConfigs.find(
    (item) => item.fieldName === field.field_name,
  );
  const valueMissing = isMissingCommercialValue(
    field.field_name,
    field.field_value,
  );

  return {
    fieldName: field.field_name,
    label: config?.label ?? field.field_name.replaceAll("_", " "),
    displayValue: valueMissing
      ? "Unknown"
      : (config?.format(field.field_value) ?? textDisplay(field.field_value)),
    rawValue: field.field_value,
    valueType: field.value_type,
    confidenceScore: field.confidence_score,
    rationale: field.rationale,
    sourceUrls: field.source_urls,
    sourceTitles: field.source_titles,
    recommendedNextStep: field.recommended_next_step,
    needsUserConfirmation: field.needs_user_confirmation,
  };
}

export function fieldByName(
  fields: IntelligenceFieldView[],
  fieldName: string,
) {
  return fields.find((field) => field.fieldName === fieldName);
}

export function displayOpportunityValue(fieldName: string, value: unknown) {
  const config = opportunityFieldConfigs.find(
    (item) => item.fieldName === fieldName,
  );
  if (!config) {
    return isMissingCommercialValue(fieldName, value)
      ? "Unknown"
      : textDisplay(value);
  }

  return isMissingCommercialValue(fieldName, value)
    ? "Unknown"
    : config.format(value);
}

export function summariseFieldConfidence(fields: IntelligenceFieldView[]) {
  const aiFields = fields.filter(
    (field) => field.sourceUrls.length > 0 || field.valueType !== "known",
  );
  const average =
    fields.length > 0
      ? fields.reduce((total, field) => total + field.confidenceScore, 0) /
        fields.length
      : 0;

  return {
    score: average,
    aiFieldCount: aiFields.length,
    unknownCount: fields.filter((field) => field.valueType === "unknown")
      .length,
  };
}

export function isMissingCommercialValue(fieldName: string, value: unknown) {
  if (value == null) {
    return true;
  }
  if (typeof value === "string") {
    const trimmed = value.trim();
    return (
      trimmed.length === 0 ||
      ["unknown", "not set", "tbc", "n/a", "null"].includes(
        trimmed.toLowerCase(),
      )
    );
  }
  if (typeof value === "number") {
    return value === 0 && commercialZeroMeansUnknownFields.has(fieldName);
  }
  return false;
}

export const commercialZeroMeansUnknownFields = new Set([
  "estimated_annual_revenue",
  "estimated_total_contract_value",
  "estimated_gross_margin",
  "margin_percentage",
  "probability",
  "weighted_value",
  "strategic_fit_score",
]);

export function textDisplay(value: unknown) {
  return typeof value === "string" ? value : String(value ?? "Unknown");
}

export function currencyDisplay(value: unknown) {
  return typeof value === "number" ? currency(value) : textDisplay(value);
}

export function percentageDisplay(value: unknown) {
  return typeof value === "number"
    ? percentageValue(value)
    : textDisplay(value);
}

export function probabilityDisplay(value: unknown) {
  return typeof value === "number"
    ? percentageValue(value)
    : textDisplay(value);
}

export function monthDisplay(value: unknown) {
  return typeof value === "string" ? monthYearLabel(value) : textDisplay(value);
}

export function riskDisplay(value: unknown) {
  return typeof value === "string"
    ? normaliseRiskLabel(value)
    : textDisplay(value);
}

export function scoreDisplay(value: unknown) {
  return typeof value === "number"
    ? `${Math.round(value)}/100`
    : textDisplay(value);
}

export function valueTypeLabel(valueType: FieldIntelligence["value_type"]) {
  if (valueType === "known" || valueType === "user_provided") {
    return "Actual";
  }
  if (valueType === "system_calculated") {
    return "Calculated";
  }
  return valueType.charAt(0).toUpperCase() + valueType.slice(1);
}

export function valueTypeDescription(field: IntelligenceFieldView) {
  if (field.valueType === "unknown") {
    return `${field.label} is unknown because SalesIntel does not have enough evidence yet. ${field.recommendedNextStep}`;
  }
  if (field.valueType === "estimated") {
    return `${field.label} is an estimate. Treat it as useful for direction, not as confirmed commercial truth.`;
  }
  if (field.valueType === "inferred") {
    return `${field.label} is inferred from available evidence and should be confirmed before bid or forecast commitment.`;
  }
  if (field.valueType === "system_calculated") {
    return `${field.label} is calculated by SalesIntel from other commercial fields.`;
  }
  return `${field.label} is held as an actual value in SalesIntel.`;
}

export function fieldConfidenceClass(
  valueType: FieldIntelligence["value_type"],
) {
  if (valueType === "unknown") {
    return "border-slate-400/25 bg-slate-400/10 text-slate-200";
  }
  if (valueType === "estimated") {
    return "border-amber-300/25 bg-amber-400/10 text-amber-100";
  }
  if (valueType === "inferred") {
    return "border-cyan-300/25 bg-cyan-400/10 text-cyan-100";
  }
  return "border-emerald-300/25 bg-emerald-400/10 text-emerald-100";
}

export function fieldConfidenceBorder(
  valueType: FieldIntelligence["value_type"],
) {
  if (valueType === "unknown") {
    return "border-slate-400/20 bg-slate-400/5";
  }
  if (valueType === "estimated") {
    return "border-amber-300/20 bg-amber-400/5";
  }
  if (valueType === "inferred") {
    return "border-cyan-300/20 bg-cyan-400/5";
  }
  return "border-emerald-300/20 bg-emerald-400/5";
}

export function valueTypeDotClass(valueType: FieldIntelligence["value_type"]) {
  if (valueType === "unknown") {
    return "bg-slate-400";
  }
  if (valueType === "estimated") {
    return "bg-amber-300";
  }
  if (valueType === "inferred") {
    return "bg-cyan-300";
  }
  return "bg-emerald-300";
}

export function riskTone(risk: string): Tone {
  const value = risk.toLowerCase();

  if (value.includes("red") || value.includes("high")) {
    return "red";
  }

  if (value.includes("amber") || value.includes("medium")) {
    return "amber";
  }

  if (value.includes("green") || value.includes("low")) {
    return "green";
  }

  return "cyan";
}

export function fitToneForSignal(fit: string): Tone {
  const value = fit.toLowerCase();
  if (value.includes("high")) {
    return "green";
  }
  if (value.includes("medium")) {
    return "cyan";
  }
  if (value.includes("low")) {
    return "amber";
  }
  return "amber";
}

export function autofillResultTone(
  status: "enriched" | "skipped" | "failed",
): Tone {
  if (status === "enriched") {
    return "green";
  }
  if (status === "failed") {
    return "red";
  }
  return "cyan";
}

export function normaliseRiskLabel(risk: string): string {
  const value = risk.toLowerCase();

  if (value.includes("red") || value.includes("high")) {
    return "Red";
  }

  if (value.includes("amber") || value.includes("medium")) {
    return "Amber";
  }

  if (value.includes("green") || value.includes("low")) {
    return "Green";
  }

  return risk || "Review";
}

export function confidenceTone(confidence: number): Tone {
  if (confidence >= 0.75) {
    return "green";
  }

  if (confidence >= 0.45) {
    return "amber";
  }

  return "red";
}
