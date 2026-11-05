export type ForecastPoint = {
  month: string;
  value: number;
};

export type Opportunity = {
  id: number;
  name: string;
  buyer_name: string;
  sector: string;
  region: string;
  source_type: string;
  stage: string;
  owner: string;
  estimated_annual_revenue: number;
  estimated_total_contract_value: number;
  estimated_gross_margin: number;
  margin_percentage: number;
  probability: number;
  weighted_value: number;
  submission_deadline: string | null;
  forecast_start_month: string | null;
  self_delivery_fit: string;
  risk_rating: string;
  strategic_fit_score: number;
  bid_no_bid_recommendation: string;
  recommended_action: string;
  created_at: string;
  updated_at: string;
  weighted_pipeline_value: number;
  strategic_must_win: boolean;
  calculated_risk_rating: string;
  margin_warning: boolean;
  deadline_warning: boolean;
  self_delivery_capture: boolean;
  executive_escalation: boolean;
  calculated_bid_no_bid_recommendation: string;
  priority_score: number;
  calculated_recommended_action: string;
  latest_ai_analysis: OpportunityAIAnalysis | null;
};

export type OpportunityAIAnalysis = {
  strategic_fit_score: number;
  win_probability: number;
  risk_rating: "Green" | "Amber" | "Red";
  bid_no_bid_recommendation: string;
  likely_buyer_drivers: string[];
  competitor_threat: "Low" | "Medium" | "High";
  margin_commentary: string;
  mobilisation_risks: string[];
  commercial_risks: string[];
  self_delivery_assessment: string;
  recommended_action: string;
  executive_summary: string;
  created_at?: string;
};

export type FieldValueType =
  | "known"
  | "inferred"
  | "estimated"
  | "unknown"
  | "user_provided"
  | "system_calculated";

export type FieldIntelligence = {
  id: number;
  entity_type: string;
  entity_id: number;
  field_name: string;
  field_value: unknown;
  value_type: FieldValueType;
  confidence_score: number;
  rationale: string;
  source_urls: string[];
  source_titles: string[];
  recommended_next_step: string;
  needs_user_confirmation: boolean;
  created_at: string;
  updated_at: string;
};

export type EnrichmentRun = {
  id: number;
  run_type: string;
  status: string;
  user_query: string;
  opportunity_id: number | null;
  started_at: string;
  finished_at: string | null;
  model_used: string;
  search_performed: boolean;
  sources_checked: unknown[];
  records_created: number;
  records_updated: number;
  error_message: string | null;
};

export type OpportunityEnrichment = {
  id: number;
  opportunity_id: number;
  enrichment_run_id: number;
  buyer_summary: string;
  opportunity_summary: string;
  likely_scope: string;
  estimated_contract_value_rationale: string;
  likely_buyer_drivers: string[];
  compliance_drivers: string[];
  competitor_assessment: string;
  commercial_assessment: string;
  mobilisation_assessment: string;
  self_delivery_assessment: string;
  finance_assessment: string;
  executive_recommendation: string;
  unknowns: string[];
  recommended_next_steps: string[];
  overall_confidence: number;
  created_at: string;
};

export type MarketSignal = {
  id: number;
  title: string;
  buyer_name: string;
  sector: string;
  region: string;
  estimated_value: number | null;
  expected_tender_date: string | null;
  source_type: string;
  source_url: string | null;
  source_attribution: string;
  confidence_score: number;
  suggested_action: string;
  likely_mitie_fit: string;
  potential_disciplines: string[];
  ai_rationale: string;
  created_at: string;
};

export type ExecutiveAction = {
  id: number;
  priority: string;
  category: string;
  owner: string;
  due_date: string | null;
  related_opportunity_id: number | null;
  commercial_value: number | null;
  reason: string;
  recommended_action: string;
  status: string;
};

export type BuyerProfile = {
  id: number;
  buyer_name: string;
  sector: string;
  region: string;
  estate_size: string | null;
  procurement_drivers: string[];
  pain_points: string[];
  decision_criteria: string[];
  relationship_status: string;
  next_best_action: string;
};

export type CompetitorProfile = {
  id: number;
  name: string;
  sectors: string[];
  strengths: string[];
  weaknesses: string[];
  pricing_behaviour: string;
  threat_level: string;
  counter_strategy: string;
};

export type DashboardSummary = {
  total_pipeline_value: number;
  weighted_pipeline_value: number;
  estimated_gross_margin: number;
  average_margin_percentage: number;
  live_opportunity_count: number;
  strategic_must_win_count: number;
  live_tender_count: number;
  market_signal_count: number;
  high_risk_count: number;
  urgent_deadline_count: number;
  executive_summary_text: string;
  monthly_revenue_forecast: ForecastPoint[];
  monthly_margin_forecast: ForecastPoint[];
  top_opportunities: Opportunity[];
  top_executive_actions: ExecutiveAction[];
};

export type ExecutiveLeadershipBriefing = {
  headline: string;
  summary: string;
  md_attention: string[];
  finance_attention: string[];
  sales_attention: string[];
  bid_team_attention: string[];
  risk_warnings: string[];
  next_best_actions: string[];
};

export type InternetIntelligenceType =
  | "market_radar"
  | "competitor_intelligence"
  | "buyer_intelligence"
  | "opportunity_intelligence"
  | "tender_intelligence"
  | "pipeline_forecast"
  | "self_delivery";

export type InternetIntelligenceRequest = {
  intelligence_type: InternetIntelligenceType;
  query: string;
  sector?: string;
  region?: string;
  buyer_name?: string;
  competitor_name?: string;
  opportunity_name?: string;
};

export type InternetIntelligenceFinding = {
  title: string;
  finding: string;
  so_what: string;
  recommended_action: string;
  confidence_score: number;
  source_urls: string[];
};

export type InternetIntelligenceResult = {
  intelligence_type: InternetIntelligenceType;
  query: string;
  headline: string;
  summary: string;
  findings: InternetIntelligenceFinding[];
  source_urls: string[];
  risk_warnings: string[];
  next_best_actions: string[];
  limitations: string[];
};

export type EarlyOpportunityFinding = {
  organisation: string;
  signal: string;
  signal_date: string;
  signal_source_url: string;
  inferred_need: string;
  fit_and_timing: string;
  uncertainties: string;
  contact_name: string;
  contact_role: string;
  contact_source_url: string;
  engagement_opener: string;
  discovery_question: string;
  next_action: string;
};

export type EarlyOpportunityResult = {
  query: string;
  summary: string;
  findings: EarlyOpportunityFinding[];
  limitations: string[];
};

export type ResearchOpportunityRequest = {
  query: string;
  sector_hint?: string;
  region_hint?: string;
  buyer_hint?: string;
  create_opportunity?: boolean;
};

export type ChatGPTAssistPromptResponse = {
  prompt: string;
  expected_output_schema: Record<string, unknown>;
  copy_steps: string[];
  safety_note: string;
};

export type ChatGPTAssistImportRequest = ResearchOpportunityRequest & {
  result_json: string;
};

export type ResearchOpportunitySource = {
  title: string;
  url: string;
  source_type: string;
  relevance: string;
};

export type ResearchOpportunityFieldIntelligence = {
  field_name: string;
  field_value: unknown;
  value_type: FieldValueType;
  confidence_score: number;
  rationale: string;
  source_urls: string[];
  source_titles: string[];
  recommended_next_step: string;
  needs_user_confirmation: boolean;
};

export type ResearchOpportunityDraft = {
  name: string | null;
  buyer_name: string | null;
  sector: string | null;
  region: string | null;
  source_type: string | null;
  stage: string | null;
  estimated_annual_revenue: number | null;
  estimated_total_contract_value: number | null;
  estimated_gross_margin: number | null;
  margin_percentage: number | null;
  probability: number | null;
  weighted_value: number | null;
  submission_deadline: string | null;
  forecast_start_month: string | null;
  self_delivery_fit: string | null;
  risk_rating: string | null;
  strategic_fit_score: number | null;
  bid_no_bid_recommendation: string | null;
  recommended_action: string | null;
  finance_forecast_category: string | null;
  executive_action: string | null;
};

export type ResearchOpportunityEnrichmentPack = {
  buyer_summary: string;
  opportunity_summary: string;
  likely_scope: string[];
  estimated_contract_value_rationale: string;
  likely_buyer_drivers: string[];
  compliance_drivers: string[];
  competitor_threat: string;
  competitor_assessment: string;
  commercial_assessment: string;
  mobilisation_assessment: string;
  self_delivery_assessment: string;
  finance_assessment: string;
  executive_recommendation: string;
  unknowns: string[];
  recommended_next_steps: string[];
  overall_confidence: number;
};

export type ResearchOpportunityResponse = {
  enrichment_run?: EnrichmentRun;
  created_opportunity: boolean;
  opportunity: Opportunity | null;
  draft_opportunity: ResearchOpportunityDraft;
  field_intelligence: FieldIntelligence[];
  draft_field_intelligence: ResearchOpportunityFieldIntelligence[];
  opportunity_enrichment?: OpportunityEnrichment | null;
  draft_enrichment: ResearchOpportunityEnrichmentPack;
  sources: ResearchOpportunitySource[];
  overall_confidence: number;
};

export type MarketSignalConversionResponse = {
  market_signal: MarketSignal;
  opportunity: Opportunity;
  enrichment_run: EnrichmentRun;
  field_intelligence: FieldIntelligence[];
  opportunity_enrichment: OpportunityEnrichment;
  executive_action: ExecutiveAction | null;
  finance_forecast: {
    id: number;
    opportunity_id: number;
    forecast_category: string;
    start_month: string;
    revenue_to_year_end: number;
    estimated_margin: number;
    margin_percentage: number;
    probability_weighting: number;
    risk_adjustment: number;
    notes: string;
  } | null;
  created_opportunity: boolean;
  fields_filled: number;
  fields_still_unknown: number;
  conversion_summary: string;
};

export type AutofillOpportunitiesRequest = {
  only_incomplete?: boolean;
  limit?: number;
  allow_overwrite?: boolean;
  overwrite_confidence_threshold?: number;
};

export type AutofillOpportunityResult = {
  opportunity_id: number;
  opportunity_name: string;
  status: "enriched" | "skipped" | "failed";
  enrichment_run_id: number | null;
  fields_filled: number;
  fields_preserved: number;
  fields_still_unknown: number;
  confidence_warnings: string[];
  error_message: string | null;
};

export type AutofillOpportunitiesResponse = {
  records_scanned: number;
  records_enriched: number;
  records_skipped: number;
  records_failed: number;
  fields_filled: number;
  fields_still_unknown: number;
  confidence_warnings: string[];
  results: AutofillOpportunityResult[];
};

export type SecuredWorkItem = {
  opportunity_id: number;
  opportunity_name: string;
  client: string;
  won_revenue: number;
  won_gross_margin: number;
  margin_percentage: number;
  delivery_start_month: string;
  business_unit: string | null;
  discipline: string | null;
  confidence: number;
};

export type OpenForecastItem = {
  opportunity_id: number;
  opportunity_name: string;
  client: string;
  forecast_start_month: string;
  revenue_to_financial_year_end: number;
  estimated_margin: number;
  margin_percentage: number;
  probability_weighting: number;
  risk_adjustment: number;
  forecast_category: string;
  weighted_revenue: number;
  weighted_margin: number;
  risk_adjusted_revenue: number;
  risk_adjusted_margin: number;
};

export type FinanceWarning = {
  opportunity_id: number;
  opportunity_name: string;
  client: string;
  margin_percentage: number;
  threshold_percentage: number;
  reason: string;
};

export type FinanceReviewItem = {
  opportunity_id: number;
  opportunity_name: string;
  client: string;
  priority: string;
  category: string;
  reason: string;
  recommended_action: string;
};

export type FinanceForecastSummary = {
  financial_year: string;
  financial_year_start: number;
  financial_year_end: number;
  financial_year_months: string[];
  monthly_revenue: ForecastPoint[];
  monthly_margin: ForecastPoint[];
  secured_revenue: number;
  secured_gross_margin: number;
  secured_margin_percentage: number;
  open_weighted_revenue: number;
  open_weighted_margin: number;
  risk_adjusted_revenue: number;
  risk_adjusted_margin: number;
  forecast_to_financial_year_end: number;
  forecast_margin_to_financial_year_end: number;
  secured_work: SecuredWorkItem[];
  open_opportunities: OpenForecastItem[];
  margin_warnings: FinanceWarning[];
  finance_review_items: FinanceReviewItem[];
};

export type ReportAggregate = {
  label: string;
  value: number;
  count: number;
};

export type SelfDeliveryReportOpportunity = {
  opportunity_id: number;
  name: string;
  buyer_name: string;
  discipline: string;
  estimated_value: number;
  weighted_value: number;
  risk_rating: string;
  recommended_action: string;
};

export type SelfDeliveryReportSummary = {
  opportunity_value: number;
  value_captured: number;
  value_at_risk: number;
  accepted_count: number;
  declined_count: number;
  conversion_rate: number;
  top_displaced_suppliers: ReportAggregate[];
  disciplines_with_highest_opportunity: ReportAggregate[];
  route_opportunities: SelfDeliveryReportOpportunity[];
  leakage_risks: SelfDeliveryReportOpportunity[];
};

export type ReportRiskRecommendation = {
  priority: string;
  category: string;
  summary: string;
  commercial_value: number | null;
  owner: string | null;
  recommended_action: string;
};

export type ExecutiveReport = {
  report_name: string;
  generated_at: string;
  reporting_date: string;
  audience: string[];
  data_note: string;
  dashboard_kpis: DashboardSummary;
  leadership_summary: ExecutiveLeadershipBriefing;
  top_opportunities: Opportunity[];
  finance_forecast: FinanceForecastSummary;
  self_delivery_summary: SelfDeliveryReportSummary;
  executive_actions: ExecutiveAction[];
  risks_and_recommendations: ReportRiskRecommendation[];
};

export type MisiDashboardData = {
  dashboard: DashboardSummary;
  opportunities: Opportunity[];
  marketSignals: MarketSignal[];
  executiveActions: ExecutiveAction[];
  financeSummary: FinanceForecastSummary;
  buyerProfiles: BuyerProfile[];
  competitorProfiles: CompetitorProfile[];
};

export function getApiBaseUrl(): string {
  return (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(
    /\/$/,
    "",
  );
}

export async function fetchMisiDashboardData(
  signal?: AbortSignal,
): Promise<MisiDashboardData> {
  const [
    dashboard,
    opportunities,
    marketSignals,
    executiveActions,
    financeSummary,
    buyerProfiles,
    competitorProfiles,
  ] = await Promise.all([
    fetchJson<DashboardSummary>("/api/dashboard", signal),
    fetchJson<Opportunity[]>("/api/opportunities", signal),
    fetchJson<MarketSignal[]>("/api/market-signals", signal),
    fetchJson<ExecutiveAction[]>("/api/executive-actions", signal),
    fetchJson<FinanceForecastSummary>("/api/finance-forecast/summary", signal),
    fetchJson<BuyerProfile[]>("/api/buyers", signal),
    fetchJson<CompetitorProfile[]>("/api/competitors", signal),
  ]);

  return {
    dashboard,
    opportunities,
    marketSignals,
    executiveActions,
    financeSummary,
    buyerProfiles,
    competitorProfiles,
  };
}

export async function analyseOpportunity(
  opportunityId: number,
  signal?: AbortSignal,
): Promise<OpportunityAIAnalysis> {
  return postJson<OpportunityAIAnalysis>(
    `/api/intelligence/analyse-opportunity/${opportunityId}`,
    signal,
  );
}

export async function generateExecutiveSummary(
  signal?: AbortSignal,
): Promise<ExecutiveLeadershipBriefing> {
  return postJson<ExecutiveLeadershipBriefing>(
    "/api/intelligence/generate-executive-summary",
    signal,
  );
}

export async function runInternetResearch(
  request: InternetIntelligenceRequest,
  signal?: AbortSignal,
): Promise<InternetIntelligenceResult> {
  return postJson<InternetIntelligenceResult>(
    "/api/intelligence/internet-research",
    signal,
    request,
  );
}

export async function researchEarlyOpportunities(
  query: string,
  signal?: AbortSignal,
): Promise<EarlyOpportunityResult> {
  return postJson<EarlyOpportunityResult>(
    "/api/intelligence/early-opportunities",
    signal,
    { query },
  );
}

export async function researchOpportunity(
  request: ResearchOpportunityRequest,
  signal?: AbortSignal,
): Promise<ResearchOpportunityResponse> {
  return postJson<ResearchOpportunityResponse>(
    "/api/intelligence/research-opportunity",
    signal,
    request,
  );
}

export async function generateChatGPTAssistPrompt(
  request: ResearchOpportunityRequest,
  signal?: AbortSignal,
): Promise<ChatGPTAssistPromptResponse> {
  return postJson<ChatGPTAssistPromptResponse>(
    "/api/intelligence/chatgpt-assist/prompt",
    signal,
    request,
  );
}

export async function importChatGPTAssistResult(
  request: ChatGPTAssistImportRequest,
  signal?: AbortSignal,
): Promise<ResearchOpportunityResponse> {
  return postJson<ResearchOpportunityResponse>(
    "/api/intelligence/chatgpt-assist/import",
    signal,
    request,
  );
}

export async function convertMarketSignal(
  signalId: number,
  signal?: AbortSignal,
): Promise<MarketSignalConversionResponse> {
  return postJson<MarketSignalConversionResponse>(
    `/api/market-signals/${signalId}/convert`,
    signal,
  );
}

export async function autofillOpportunities(
  request: AutofillOpportunitiesRequest = {
    only_incomplete: true,
    limit: 10,
  },
  signal?: AbortSignal,
): Promise<AutofillOpportunitiesResponse> {
  return postJson<AutofillOpportunitiesResponse>(
    "/api/intelligence/autofill-opportunities",
    signal,
    request,
  );
}

export async function fetchOpportunityFieldIntelligence(
  opportunityId: number,
  signal?: AbortSignal,
): Promise<FieldIntelligence[]> {
  const params = new URLSearchParams({
    entity_type: "opportunity",
    entity_id: String(opportunityId),
  });
  return fetchJson<FieldIntelligence[]>(
    `/api/enrichment/field-intelligence?${params.toString()}`,
    signal,
  );
}

export async function fetchOpportunityEnrichments(
  opportunityId: number,
  signal?: AbortSignal,
): Promise<OpportunityEnrichment[]> {
  return fetchJson<OpportunityEnrichment[]>(
    `/api/enrichment/opportunities/${opportunityId}`,
    signal,
  );
}

export async function fetchExecutiveReport(
  signal?: AbortSignal,
): Promise<ExecutiveReport> {
  return fetchJson<ExecutiveReport>("/api/reports/executive-summary", signal);
}

async function fetchJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    cache: "no-store",
    signal,
  });

  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, path));
  }

  return response.json() as Promise<T>;
}

async function postJson<T>(
  path: string,
  signal?: AbortSignal,
  body?: unknown,
): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    cache: "no-store",
    method: "POST",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });

  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, path));
  }

  return response.json() as Promise<T>;
}

async function getApiErrorMessage(response: Response, path: string): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: unknown; message?: unknown };
    if (typeof payload.detail === "string" && payload.detail.trim()) {
      return payload.detail;
    }
    if (typeof payload.message === "string" && payload.message.trim()) {
      return payload.message;
    }
  } catch {
    // Fall through to a safe generic message.
  }

  return `${path} returned ${response.status}`;
}
