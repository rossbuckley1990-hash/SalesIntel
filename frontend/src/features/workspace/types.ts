import type {
  BuyerProfile,
  CompetitorProfile,
  ExecutiveAction as LegacyExecutiveAction,
  FieldIntelligence,
  FinanceForecastSummary,
  Opportunity,
  OpportunityEnrichment,
} from "@/lib/api";

export type ExecutiveAction = LegacyExecutiveAction & {
  depends_on: number[];
  blocked_by: number[];
  completion_evidence: string;
};

export type View =
  | "today"
  | "field"
  | "discover"
  | "radar"
  | "opportunities"
  | "pursuits"
  | "accounts"
  | "selfDelivery"
  | "finance"
  | "actions"
  | "assets"
  | "imports"
  | "outcomes";
export type Financials = {
  estimated_annual_revenue: number | null;
  estimated_total_contract_value: number | null;
  estimated_gross_margin: number | null;
  margin_percentage: number | null;
  probability: number | null;
  weighted_contract_value: number | null;
};
export type Qualification = {
  score: number;
  criteria: { label: string; passed: boolean; basis: string }[];
  risks: string[];
  gaps: string[];
  recommendation: string;
  method: string;
};
export type LivingOpportunity = Opportunity & {
  financials: Financials;
  evidence_count: number;
  unknown_count: number;
  qualification: Qualification;
};
export type Evidence = FieldIntelligence & {
  stale: boolean;
  review: { disposition: string; reviewer: string; note: string } | null;
};
export type Decision = {
  id: number;
  choice: string;
  rationale: string;
  reviewer: string;
  created_at: string;
};
export type Outcome = {
  id: number;
  opportunity_id: number;
  action_id: number | null;
  decision_id: number | null;
  stage: string;
  expected_impact: string | null;
  actual_value: string | null;
  owner: string;
  due_date: string | null;
  confidence: string;
  assumptions: string;
  completion_evidence: string;
  verified_by: string;
};
export type Requirement = {
  id: number;
  requirement: string;
  source_reference: string;
  compliance: string;
  evidence: string;
  owner: string;
};
export type Detail = {
  opportunity: Opportunity;
  financials: Financials;
  evidence: Evidence[];
  qualification: Qualification;
  enrichment: OpportunityEnrichment | null;
  buyer: BuyerProfile | null;
  actions: ExecutiveAction[];
  decisions: Decision[];
  requirements: Requirement[];
  scenarios: Scenario[];
  outcome: Outcome | null;
};
export type ScenarioInputs = {
  annual_revenue: string;
  baseline_share: string;
  proposed_share: string;
  inhouse_cost_ratio: string;
  subcontract_cost_ratio: string;
  probability: string;
  bid_cost: string;
  mobilisation_cost: string;
  payment_delay_days: number;
  start_month: string;
  financial_year_start: number;
  assumption_note: string;
  source_references: string[];
};
export type ScenarioCase = {
  annual_revenue: string;
  inhouse_cost: string;
  subcontract_cost: string;
  gross_margin: string;
  gross_margin_ratio: string;
  expected_contribution: string;
  working_capital_proxy: string;
  mobilisation_cost: string;
  bid_cost: string;
};
export type ScenarioResult = {
  model_version: string;
  baseline: ScenarioCase;
  proposed: ScenarioCase;
  delta_gross_margin: string;
  delta_expected_contribution: string;
  financial_year_revenue: string;
  monthly: { month: string; revenue: string; gross_margin: string }[];
  sensitivity: {
    inhouse_cost_ratio: string;
    gross_margin: string;
    expected_contribution: string;
  }[];
  warnings: string[];
  formula: string;
};
export type Scenario = {
  id: number;
  opportunity_id: number;
  name: string;
  owner: string;
  assumptions: ScenarioInputs;
  result: ScenarioResult;
  created_at: string;
};
export type AssetKind =
  | "dossier"
  | "bid_decision"
  | "pursuit_plan"
  | "battlecard"
  | "self_delivery"
  | "forecast"
  | "leadership"
  | "tender";
export type Asset = {
  id: number;
  opportunity_id: number | null;
  kind: AssetKind;
  title: string;
  version: number;
  review_status: string;
  reviewer: string;
  created_at: string;
  content?: {
    sections: {
      title: string;
      paragraphs: string[];
      columns: string[];
      rows: string[][];
    }[];
    sources: {
      reference: string;
      title: string;
      timestamp: string;
      type: string;
    }[];
    notes: string;
    scenario: Scenario | null;
  };
};
export type Movement = {
  opportunity_id: number;
  name: string;
  field: string;
  before: string | number | null;
  after: string | number | null;
};
export type Snapshot = {
  id: number;
  label: string;
  reviewer: string;
  captured_at: string;
  payload?: {
    opportunities: LivingOpportunity[];
    finance: FinanceForecastSummary;
  };
};
export type Workspace = {
  mode: string;
  as_of: string;
  notice: string;
  opportunities: LivingOpportunity[];
  actions: ExecutiveAction[];
  assets: Asset[];
  outcomes: Outcome[];
  buyers: BuyerProfile[];
  competitors: CompetitorProfile[];
  finance: FinanceForecastSummary;
  pulse: Record<
    | "estimated_total_contract_value"
    | "weighted_contract_value"
    | "estimated_gross_margin",
    { value: number; unknown: number }
  >;
  changes: {
    previous: Snapshot | null;
    current: Snapshot | null;
    changes: Movement[];
    forecast_movement: number | null;
    message: string;
  };
  last_event: { id: number; action: string } | null;
  connector_status: string;
};
export type Navigate = (view: View, opportunityId?: number) => void;
export type Notice = (message: string, error?: boolean) => void;
export type SharedProps = {
  data: Workspace;
  navigate: Navigate;
  inspect: (id: number) => void;
  refresh: () => Promise<void>;
  notify: Notice;
  selectedId: number | null;
  selectOpportunity: (id: number | null) => void;
};
