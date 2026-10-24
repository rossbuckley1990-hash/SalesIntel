import type { Opportunity } from "./api";

export const selfDeliveryDisciplines = [
  "Fire Alarms",
  "Emergency Lighting",
  "Extinguishers",
  "Intruder Alarms",
  "CCTV",
  "Access Control",
  "PAVA",
  "Disabled Refuge",
  "Fire Doors",
  "Dry Risers",
  "Sprinklers",
  "Fire Dampers",
  "Smoke Control",
  "Gas Suppression",
  "Fire Risk Assessments",
  "Passive Fire",
] as const;

export type SelfDeliveryDiscipline = (typeof selfDeliveryDisciplines)[number];

export type SelfDeliveryOpportunityInsight = {
  opportunityId: number;
  name: string;
  buyerName: string;
  sector: string;
  stage: string;
  owner: string;
  discipline: SelfDeliveryDiscipline;
  displacedSupplier: string;
  estimatedValue: number;
  weightedValue: number;
  riskRating: string;
  recommendedAction: string;
  reason: string;
};

export type SelfDeliveryAggregate = {
  label: string;
  value: number;
  count: number;
};

export type SelfDeliverySummary = {
  opportunityValue: number;
  valueCaptured: number;
  valueAtRisk: number;
  acceptedCount: number;
  declinedCount: number;
  conversionRate: number;
  routeOpportunities: SelfDeliveryOpportunityInsight[];
  leakageOpportunities: SelfDeliveryOpportunityInsight[];
  acceptedOpportunities: SelfDeliveryOpportunityInsight[];
  declinedOpportunities: SelfDeliveryOpportunityInsight[];
  topDisplacedSuppliers: SelfDeliveryAggregate[];
  disciplineOpportunity: SelfDeliveryAggregate[];
};

const supplierByDiscipline: Record<SelfDeliveryDiscipline, string> = {
  "Fire Alarms": "Incumbent Fire Alarm Specialist",
  "Emergency Lighting": "Regional Electrical Compliance Partner",
  Extinguishers: "National Extinguisher Service",
  "Intruder Alarms": "Security Systems Subcontractor",
  CCTV: "CCTV Integration Partner",
  "Access Control": "Access Control Integrator",
  PAVA: "Voice Alarm Specialist",
  "Disabled Refuge": "Life Safety Communications Partner",
  "Fire Doors": "Passive Fire Door Contractor",
  "Dry Risers": "Dry Riser Testing Contractor",
  Sprinklers: "Sprinkler Inspection Partner",
  "Fire Dampers": "Airside Fire Damper Contractor",
  "Smoke Control": "Smoke Control Specialist",
  "Gas Suppression": "Specialist Suppression Partner",
  "Fire Risk Assessments": "Independent FRA Bureau",
  "Passive Fire": "Passive Fire Remedials Contractor",
};

const disciplinePatterns: Array<{
  discipline: SelfDeliveryDiscipline;
  patterns: string[];
}> = [
  { discipline: "Gas Suppression", patterns: ["gas suppression", "suppression", "vesda"] },
  { discipline: "Fire Risk Assessments", patterns: ["fire risk assessment", "fra "] },
  { discipline: "Emergency Lighting", patterns: ["emergency lighting"] },
  { discipline: "Disabled Refuge", patterns: ["disabled refuge", "refuge"] },
  { discipline: "Access Control", patterns: ["access control"] },
  { discipline: "Intruder Alarms", patterns: ["intruder alarm"] },
  { discipline: "Fire Dampers", patterns: ["fire damper", "dampers"] },
  { discipline: "Smoke Control", patterns: ["smoke control"] },
  { discipline: "Extinguishers", patterns: ["extinguishers", "extinguisher"] },
  { discipline: "Dry Risers", patterns: ["dry riser"] },
  { discipline: "Sprinklers", patterns: ["sprinkler"] },
  { discipline: "Fire Doors", patterns: ["fire door"] },
  { discipline: "Passive Fire", patterns: ["passive fire", "remediation", "remedials"] },
  { discipline: "PAVA", patterns: ["pava"] },
  { discipline: "CCTV", patterns: ["cctv"] },
  { discipline: "Fire Alarms", patterns: ["fire alarm", "fire detection", "alarm"] },
];

const declinedStages = new Set(["lost", "qualified out"]);
const wonStages = new Set(["won"]);

export function buildSelfDeliverySummary(
  opportunities: Opportunity[],
): SelfDeliverySummary {
  const enriched = opportunities.map(toSelfDeliveryInsight);

  const declinedOpportunities = enriched.filter((item) =>
    isDeclinedSelfDelivery(item, opportunities),
  );
  const acceptedOpportunities = enriched.filter((item) =>
    isAcceptedSelfDelivery(item, opportunities),
  );
  const leakageOpportunities = enriched
    .filter((item) => isLeakageRisk(item, opportunities))
    .sort(compareInsights);
  const routeOpportunities = enriched
    .filter((item) => isRouteCandidate(item, opportunities))
    .sort(compareInsights);

  const opportunityValue = sumBy(enriched, (item) => item.estimatedValue);
  const valueCaptured = sumBy(acceptedOpportunities, (item) =>
    wonStages.has(item.stage.toLowerCase()) ? item.estimatedValue : item.weightedValue,
  );
  const valueAtRisk = sumBy(leakageOpportunities, (item) => item.estimatedValue);
  const decisionCount = acceptedOpportunities.length + declinedOpportunities.length;

  return {
    opportunityValue,
    valueCaptured,
    valueAtRisk,
    acceptedCount: acceptedOpportunities.length,
    declinedCount: declinedOpportunities.length,
    conversionRate: decisionCount === 0 ? 0 : acceptedOpportunities.length / decisionCount,
    routeOpportunities: routeOpportunities.slice(0, 8),
    leakageOpportunities: leakageOpportunities.slice(0, 8),
    acceptedOpportunities,
    declinedOpportunities,
    topDisplacedSuppliers: aggregateBy(enriched, (item) => item.displacedSupplier).slice(0, 5),
    disciplineOpportunity: aggregateBy(enriched, (item) => item.discipline).slice(0, 8),
  };
}

function toSelfDeliveryInsight(opportunity: Opportunity): SelfDeliveryOpportunityInsight {
  const discipline = inferDiscipline(opportunity);
  const riskRating = opportunity.calculated_risk_rating || opportunity.risk_rating || "Unknown";

  return {
    opportunityId: opportunity.id,
    name: opportunity.name,
    buyerName: opportunity.buyer_name,
    sector: opportunity.sector,
    stage: opportunity.stage,
    owner: opportunity.owner,
    discipline,
    displacedSupplier: supplierByDiscipline[discipline],
    estimatedValue: opportunity.estimated_total_contract_value,
    weightedValue: opportunity.weighted_pipeline_value,
    riskRating,
    recommendedAction:
      opportunity.calculated_recommended_action ||
      opportunity.recommended_action ||
      "Confirm whether the scope should be routed through Mitie Fire & Security.",
    reason: getRouteReason(opportunity, discipline, riskRating),
  };
}

function inferDiscipline(opportunity: Opportunity): SelfDeliveryDiscipline {
  const haystack = `${opportunity.name} ${opportunity.recommended_action}`.toLowerCase();
  const match = disciplinePatterns.find(({ patterns }) =>
    patterns.some((pattern) => haystack.includes(pattern)),
  );

  if (match) {
    return match.discipline;
  }

  if (opportunity.sector === "Facilities Management") {
    return "Passive Fire";
  }

  return "Fire Alarms";
}

function isAcceptedSelfDelivery(
  insight: SelfDeliveryOpportunityInsight,
  opportunities: Opportunity[],
): boolean {
  const opportunity = findOpportunity(insight, opportunities);
  if (!opportunity || isDeclinedSelfDelivery(insight, opportunities)) {
    return false;
  }

  return (
    opportunity.self_delivery_capture ||
    opportunity.self_delivery_fit.toLowerCase() === "strong" ||
    wonStages.has(opportunity.stage.toLowerCase())
  );
}

function isDeclinedSelfDelivery(
  insight: SelfDeliveryOpportunityInsight,
  opportunities: Opportunity[],
): boolean {
  const opportunity = findOpportunity(insight, opportunities);
  if (!opportunity) {
    return false;
  }

  const recommendation = opportunity.calculated_bid_no_bid_recommendation.toLowerCase();
  return (
    declinedStages.has(opportunity.stage.toLowerCase()) ||
    recommendation === "no bid" ||
    recommendation === "qualify out" ||
    opportunity.self_delivery_fit.toLowerCase() === "weak"
  );
}

function isRouteCandidate(
  insight: SelfDeliveryOpportunityInsight,
  opportunities: Opportunity[],
): boolean {
  const opportunity = findOpportunity(insight, opportunities);
  if (!opportunity || isDeclinedSelfDelivery(insight, opportunities)) {
    return false;
  }

  return opportunity.self_delivery_capture || opportunity.self_delivery_fit.toLowerCase() === "strong";
}

function isLeakageRisk(
  insight: SelfDeliveryOpportunityInsight,
  opportunities: Opportunity[],
): boolean {
  const opportunity = findOpportunity(insight, opportunities);
  if (!opportunity || isDeclinedSelfDelivery(insight, opportunities)) {
    return false;
  }

  const fit = opportunity.self_delivery_fit.toLowerCase();
  const risk = insight.riskRating.toLowerCase();
  const requiresReview = opportunity.calculated_bid_no_bid_recommendation === "Watch";

  return (
    !opportunity.self_delivery_capture ||
    fit === "moderate" ||
    risk === "red" ||
    opportunity.sector === "Facilities Management" ||
    requiresReview
  );
}

function getRouteReason(
  opportunity: Opportunity,
  discipline: SelfDeliveryDiscipline,
  riskRating: string,
): string {
  if (opportunity.stage === "Won") {
    return "Won work should stay under MFS mobilisation governance to protect delivery and margin.";
  }

  if (riskRating === "Red") {
    return `${discipline} scope needs sponsor control before any third-party route is agreed.`;
  }

  if (opportunity.self_delivery_capture) {
    return `${discipline} scope is a strong MFS fit and should be captured before commercial close.`;
  }

  return `${discipline} scope has leakage risk and should be qualified with the bid owner.`;
}

function aggregateBy(
  insights: SelfDeliveryOpportunityInsight[],
  getLabel: (insight: SelfDeliveryOpportunityInsight) => string,
): SelfDeliveryAggregate[] {
  const aggregate = new Map<string, SelfDeliveryAggregate>();

  for (const insight of insights) {
    const label = getLabel(insight);
    const current = aggregate.get(label) ?? { label, value: 0, count: 0 };
    current.value += insight.estimatedValue;
    current.count += 1;
    aggregate.set(label, current);
  }

  return [...aggregate.values()].sort((first, second) => {
    const valueDelta = second.value - first.value;
    return valueDelta === 0 ? first.label.localeCompare(second.label) : valueDelta;
  });
}

function compareInsights(
  first: SelfDeliveryOpportunityInsight,
  second: SelfDeliveryOpportunityInsight,
) {
  const riskDelta = riskPriority(second.riskRating) - riskPriority(first.riskRating);
  if (riskDelta !== 0) {
    return riskDelta;
  }

  return second.estimatedValue - first.estimatedValue;
}

function riskPriority(risk: string): number {
  const normalised = risk.toLowerCase();
  if (normalised === "red") {
    return 3;
  }
  if (normalised === "amber") {
    return 2;
  }
  if (normalised === "green") {
    return 1;
  }
  return 0;
}

function findOpportunity(
  insight: SelfDeliveryOpportunityInsight,
  opportunities: Opportunity[],
): Opportunity | undefined {
  return opportunities.find((opportunity) => opportunity.id === insight.opportunityId);
}

function sumBy<T>(items: T[], getValue: (item: T) => number): number {
  return items.reduce((total, item) => total + getValue(item), 0);
}
