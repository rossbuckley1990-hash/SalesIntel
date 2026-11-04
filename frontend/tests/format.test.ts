import { afterEach, describe, expect, it, vi } from "vitest";

import {
  analyseOpportunity,
  autofillOpportunities,
  convertMarketSignal,
  fetchExecutiveReport,
  fetchOpportunityEnrichments,
  fetchOpportunityFieldIntelligence,
  generateExecutiveSummary,
  getApiBaseUrl,
  researchEarlyOpportunities,
  researchOpportunity,
  runInternetResearch,
  type ExecutiveReport,
  type Opportunity,
} from "../src/lib/api";
import {
  compactCurrency,
  currency,
  monthLabel,
  percentage,
  percentageValue,
  shortDate,
} from "../src/lib/format";
import {
  buildExecutiveReportFilename,
  buildExecutiveReportHtml,
} from "../src/lib/report-export";
import { buildSelfDeliverySummary } from "../src/lib/self-delivery";

describe("format helpers", () => {
  it("formats sterling currency without decimal places", () => {
    expect(currency(420000)).toBe("£420,000");
  });

  it("formats percentages without decimal places", () => {
    expect(percentage(0.62)).toBe("62%");
  });

  it("formats compact executive currency values", () => {
    expect(compactCurrency(4_380_000)).toBe("£4.4m");
    expect(compactCurrency(890_000)).toBe("£890k");
  });

  it("normalises backend percentage values", () => {
    expect(percentageValue(28.4)).toBe("28%");
    expect(percentageValue(0.62)).toBe("62%");
  });

  it("formats backend date and month labels", () => {
    expect(shortDate("2026-07-08")).toBe("08 Jul");
    expect(shortDate(null)).toBe("Not set");
    expect(monthLabel("2026-04")).toBe("Apr");
  });
});

describe("api configuration", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("defaults to the local backend URL", () => {
    const previousValue = process.env.NEXT_PUBLIC_API_BASE_URL;
    delete process.env.NEXT_PUBLIC_API_BASE_URL;

    expect(getApiBaseUrl()).toBe("http://localhost:8000");

    if (previousValue === undefined) {
      delete process.env.NEXT_PUBLIC_API_BASE_URL;
    } else {
      process.env.NEXT_PUBLIC_API_BASE_URL = previousValue;
    }
  });

  it("posts opportunity analysis requests through the backend", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          strategic_fit_score: 84,
          win_probability: 0.67,
          risk_rating: "Amber",
          bid_no_bid_recommendation: "Pursue",
          likely_buyer_drivers: ["Compliance assurance"],
          competitor_threat: "Medium",
          margin_commentary: "Margin is acceptable but needs final protection.",
          mobilisation_risks: ["Access windows are not confirmed."],
          commercial_risks: ["Incumbent may respond aggressively."],
          self_delivery_assessment: "Good fit for Mitie Fire & Security delivery.",
          recommended_action: "Proceed with sponsor review.",
          executive_summary: "Pursue with clear margin guardrails.",
        }),
        {
          headers: { "Content-Type": "application/json" },
          status: 200,
        },
      ),
    );
    globalThis.fetch = fetchMock;

    const result = await analyseOpportunity(42);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/intelligence/analyse-opportunity/42",
      expect.objectContaining({ method: "POST" }),
    );
    expect(result.bid_no_bid_recommendation).toBe("Pursue");
    expect(result.likely_buyer_drivers).toContain("Compliance assurance");
  });

  it("posts leadership briefing requests through the backend", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          headline: "Protect margin and sponsor priority submissions this week.",
          summary: "Pipeline is strong but leadership attention should stay on risk, margin and conversion.",
          md_attention: ["Sponsor two strategic must-wins before final review."],
          finance_attention: ["Review low-margin pricing before submission."],
          sales_attention: ["Confirm buyer contact plans for top pursuits."],
          bid_team_attention: ["Close red-risk clarification logs."],
          risk_warnings: ["One deadline is inside the escalation window."],
          next_best_actions: ["Hold a 30-minute MD/FD/GSD checkpoint."],
        }),
        {
          headers: { "Content-Type": "application/json" },
          status: 200,
        },
      ),
    );
    globalThis.fetch = fetchMock;

    const result = await generateExecutiveSummary();

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/intelligence/generate-executive-summary",
      expect.objectContaining({ method: "POST" }),
    );
    expect(result.headline).toContain("Protect margin");
    expect(result.md_attention).toContain("Sponsor two strategic must-wins before final review.");
  });

  it("requests early opportunity research without creating a pipeline record", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({
      query: "UK university estate expansion",
      summary: "Review the sources.",
      findings: [],
      limitations: ["Buying intent is unconfirmed."],
    }), { headers: { "Content-Type": "application/json" }, status: 200 }));
    globalThis.fetch = fetchMock;

    const result = await researchEarlyOpportunities("UK university estate expansion");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/intelligence/early-opportunities",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ query: "UK university estate expansion" }) }),
    );
    expect(result.findings).toEqual([]);
    expect(result.limitations).toContain("Buying intent is unconfirmed.");
  });

  it("posts internet research requests through the backend", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          intelligence_type: "market_radar",
          query: "UK fire and security public sector tender signals",
          headline: "Public sector compliance signals are active.",
          summary: "Public sources suggest continued life-safety demand.",
          findings: [
            {
              title: "Framework signal",
              finding: "A public source references compliance-led estates activity.",
              so_what: "MiSi should qualify whether this maps to Fire & Security scope.",
              recommended_action: "Create a source-backed target account review.",
              confidence_score: 0.7,
              source_urls: ["https://example.invalid/source"],
            },
          ],
          source_urls: ["https://example.invalid/source"],
          risk_warnings: ["Source coverage is incomplete."],
          next_best_actions: ["Validate against approved account data."],
          limitations: ["Mocked frontend test response."],
        }),
        {
          headers: { "Content-Type": "application/json" },
          status: 200,
        },
      ),
    );
    globalThis.fetch = fetchMock;

    const result = await runInternetResearch({
      intelligence_type: "market_radar",
      query: "UK fire and security public sector tender signals",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/intelligence/internet-research",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          intelligence_type: "market_radar",
          query: "UK fire and security public sector tender signals",
        }),
      }),
    );
    expect(result.findings[0]?.recommended_action).toContain("target account");
  });

  it("fetches field-level opportunity intelligence from the backend", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify([
          {
            id: 1,
            entity_type: "opportunity",
            entity_id: 42,
            field_name: "sector",
            field_value: "Healthcare",
            value_type: "inferred",
            confidence_score: 0.72,
            rationale: "Inferred from buyer profile.",
            source_urls: ["https://example.invalid/source"],
            source_titles: ["Source"],
            recommended_next_step: "Confirm with CRM.",
            needs_user_confirmation: true,
            created_at: "2026-07-01T10:00:00",
            updated_at: "2026-07-01T10:00:00",
          },
        ]),
        {
          headers: { "Content-Type": "application/json" },
          status: 200,
        },
      ),
    );
    globalThis.fetch = fetchMock;

    const result = await fetchOpportunityFieldIntelligence(42);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/enrichment/field-intelligence?entity_type=opportunity&entity_id=42",
      expect.objectContaining({ cache: "no-store" }),
    );
    expect(result[0]?.value_type).toBe("inferred");
  });

  it("fetches stored opportunity enrichment packs from the backend", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify([
          {
            id: 3,
            opportunity_id: 42,
            enrichment_run_id: 7,
            buyer_summary: "Large healthcare estate buyer.",
            opportunity_summary: "Fire maintenance renewal signal.",
            likely_scope: "Fire Alarms; Emergency Lighting",
            estimated_contract_value_rationale: "Comparable estate maintenance value.",
            likely_buyer_drivers: ["Compliance"],
            compliance_drivers: ["Life safety"],
            competitor_assessment: "Incumbent unknown.",
            commercial_assessment: "Qualify before bid commitment.",
            mobilisation_assessment: "Asset data required.",
            self_delivery_assessment: "Strong potential fit.",
            finance_assessment: "Likely only until source value confirmed.",
            executive_recommendation: "Validate route and scope.",
            unknowns: ["Incumbent supplier"],
            recommended_next_steps: ["Confirm procurement route"],
            overall_confidence: 0.68,
            created_at: "2026-07-01T10:00:00",
          },
        ]),
        {
          headers: { "Content-Type": "application/json" },
          status: 200,
        },
      ),
    );
    globalThis.fetch = fetchMock;

    const result = await fetchOpportunityEnrichments(42);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/enrichment/opportunities/42",
      expect.objectContaining({ cache: "no-store" }),
    );
    expect(result[0]?.overall_confidence).toBe(0.68);
  });

  it("posts standing-start opportunity research through the backend", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          created_opportunity: true,
          opportunity: null,
          draft_opportunity: {
            name: "NHS fire alarm maintenance opportunity",
            buyer_name: "NHS Trust",
            sector: "Healthcare",
            region: "North West",
            source_type: "Public web research",
            stage: "Market signal",
            estimated_annual_revenue: 250000,
            estimated_total_contract_value: 1000000,
            estimated_gross_margin: 280000,
            margin_percentage: 28,
            probability: 0.35,
            weighted_value: 350000,
            submission_deadline: null,
            forecast_start_month: null,
            self_delivery_fit: "High",
            risk_rating: "Amber",
            strategic_fit_score: 76,
            bid_no_bid_recommendation: "Watch",
            recommended_action: "Confirm procurement route.",
            finance_forecast_category: "Stretch",
            executive_action: "Assign BD owner.",
          },
          field_intelligence: [],
          draft_field_intelligence: [
            {
              field_name: "sector",
              field_value: "Healthcare",
              value_type: "inferred",
              confidence_score: 0.72,
              rationale: "Inferred from buyer type.",
              source_urls: [],
              source_titles: [],
              recommended_next_step: "Confirm buyer profile.",
              needs_user_confirmation: true,
            },
          ],
          draft_enrichment: {
            buyer_summary: "Healthcare buyer.",
            opportunity_summary: "Potential compliance opportunity.",
            likely_scope: ["Fire alarms"],
            estimated_contract_value_rationale: "Estimated from comparable estates.",
            likely_buyer_drivers: ["Compliance"],
            compliance_drivers: ["Life safety"],
            competitor_threat: "Unknown",
            competitor_assessment: "Incumbent unknown.",
            commercial_assessment: "Qualify before bid.",
            mobilisation_assessment: "Scope unknown.",
            self_delivery_assessment: "Potentially strong.",
            finance_assessment: "Stretch only.",
            executive_recommendation: "Watch and validate.",
            unknowns: ["Incumbent"],
            recommended_next_steps: ["Confirm route"],
            overall_confidence: 0.62,
          },
          sources: [],
          overall_confidence: 0.62,
        }),
        {
          headers: { "Content-Type": "application/json" },
          status: 200,
        },
      ),
    );
    globalThis.fetch = fetchMock;

    const result = await researchOpportunity({
      query: "UK NHS fire alarm maintenance opportunities",
      sector_hint: "Healthcare",
      region_hint: "North West",
      buyer_hint: "NHS / healthcare",
      create_opportunity: true,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/intelligence/research-opportunity",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          query: "UK NHS fire alarm maintenance opportunities",
          sector_hint: "Healthcare",
          region_hint: "North West",
          buyer_hint: "NHS / healthcare",
          create_opportunity: true,
        }),
      }),
    );
    expect(result.draft_field_intelligence[0]?.value_type).toBe("inferred");
  });

  it("posts bulk opportunity autofill requests through the backend", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          records_scanned: 3,
          records_enriched: 2,
          records_skipped: 4,
          records_failed: 1,
          fields_filled: 12,
          fields_still_unknown: 5,
          confidence_warnings: [
            "One margin estimate was filled at 51% confidence; confirm before governance.",
          ],
          results: [
            {
              opportunity_id: 42,
              opportunity_name: "NHS fire maintenance signal",
              status: "enriched",
              enrichment_run_id: 9,
              fields_filled: 6,
              fields_preserved: 8,
              fields_still_unknown: 2,
              confidence_warnings: [],
              error_message: null,
            },
          ],
        }),
        {
          headers: { "Content-Type": "application/json" },
          status: 200,
        },
      ),
    );
    globalThis.fetch = fetchMock;

    const result = await autofillOpportunities({
      only_incomplete: true,
      limit: 10,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/intelligence/autofill-opportunities",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          only_incomplete: true,
          limit: 10,
        }),
      }),
    );
    expect(result.records_enriched).toBe(2);
    expect(result.fields_filled).toBe(12);
  });

  it("posts market signal conversion requests through the backend", async () => {
    const marketSignal = {
      id: 7,
      title: "Warehouse sprinkler inspection framework",
      buyer_name: "Atlas Distribution Parks",
      sector: "Logistics",
      region: "Yorkshire",
      estimated_value: 1200000,
      expected_tender_date: "2026-07-15",
      source_type: "synthetic_market_signal",
      source_url: "https://example.invalid/market-signals/7",
      source_attribution: "Controlled market signal.",
      confidence_score: 0.72,
      suggested_action: "Build operating model for high-bay access.",
      likely_mitie_fit: "High",
      potential_disciplines: ["Sprinklers"],
      ai_rationale: "Maps to sprinkler inspection and Mitie self-delivery fit.",
      created_at: "2026-07-01T10:00:00",
    };
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          market_signal: marketSignal,
          opportunity: opportunityFixture({
            id: 101,
            name: marketSignal.title,
            buyer_name: marketSignal.buyer_name,
          }),
          enrichment_run: {
            id: 12,
            run_type: "market_signal_conversion",
            status: "completed",
            user_query: marketSignal.title,
            opportunity_id: 101,
            started_at: "2026-07-01T10:00:00",
            finished_at: "2026-07-01T10:00:01",
            model_used: "rule-based-market-signal-enrichment",
            search_performed: false,
            sources_checked: [],
            records_created: 21,
            records_updated: 0,
            error_message: null,
          },
          field_intelligence: [],
          opportunity_enrichment: {
            id: 5,
            opportunity_id: 101,
            enrichment_run_id: 12,
            buyer_summary: "Logistics buyer.",
            opportunity_summary: "Source-backed market signal.",
            likely_scope: "Sprinklers",
            estimated_contract_value_rationale: "Signal value.",
            likely_buyer_drivers: ["Operational continuity"],
            compliance_drivers: ["Fire safety compliance"],
            competitor_assessment: "Incumbent unknown.",
            commercial_assessment: "Worth qualifying.",
            mobilisation_assessment: "Access plan needed.",
            self_delivery_assessment: "Strong fit.",
            finance_assessment: "Best case only.",
            executive_recommendation: "Qualify route.",
            unknowns: ["Incumbent"],
            recommended_next_steps: ["Confirm buyer route"],
            overall_confidence: 0.72,
            created_at: "2026-07-01T10:00:00",
          },
          executive_action: null,
          finance_forecast: null,
          created_opportunity: true,
          fields_filled: 18,
          fields_still_unknown: 1,
          conversion_summary: "Converted market signal into opportunity.",
        }),
        {
          headers: { "Content-Type": "application/json" },
          status: 200,
        },
      ),
    );
    globalThis.fetch = fetchMock;

    const result = await convertMarketSignal(7);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/market-signals/7/convert",
      expect.objectContaining({ method: "POST" }),
    );
    expect(result.opportunity.name).toBe("Warehouse sprinkler inspection framework");
    expect(result.market_signal.likely_mitie_fit).toBe("High");
  });

  it("fetches the executive report from the backend reports endpoint", async () => {
    const report = executiveReportFixture();
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify(report), {
        headers: { "Content-Type": "application/json" },
        status: 200,
      }),
    );
    globalThis.fetch = fetchMock;

    const result = await fetchExecutiveReport();

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/reports/executive-summary",
      expect.objectContaining({ cache: "no-store" }),
    );
    expect(result.report_name).toBe("MiSi Executive Summary");
    expect(result.risks_and_recommendations[0]?.category).toBe("Pipeline risk");
  });

  it("surfaces safe backend detail for missing OpenAI configuration", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          detail: "OpenAI analysis is not configured. Configure the backend environment.",
        }),
        {
          headers: { "Content-Type": "application/json" },
          status: 503,
        },
      ),
    );
    globalThis.fetch = fetchMock;

    await expect(analyseOpportunity(42)).rejects.toThrow(
      "OpenAI analysis is not configured",
    );
  });
});

describe("executive report export", () => {
  it("builds a stable report filename from the reporting date", () => {
    expect(buildExecutiveReportFilename(executiveReportFixture())).toBe(
      "misi-executive-report-2026-06-29.json",
    );
  });

  it("builds escaped printable HTML for report data", () => {
    const report = executiveReportFixture();
    report.top_opportunities[0].buyer_name = "Buyer <Confidential>";

    const html = buildExecutiveReportHtml(report);

    expect(html).toContain("MiSi Executive Summary");
    expect(html).toContain("Buyer &lt;Confidential&gt;");
    expect(html).not.toContain("Buyer <Confidential>");
    expect(html).toContain("LE1 Finance Forecast");
    expect(html).toContain("Risks And Recommendations");
  });
});

describe("self-delivery intelligence", () => {
  it("derives capture KPIs, disciplines and leakage risks from backend opportunities", () => {
    const opportunities = [
      opportunityFixture({
        id: 1,
        name: "Retail estate fire alarm maintenance",
        buyer_name: "Northshire Retail Group",
        self_delivery_fit: "strong",
        self_delivery_capture: true,
        estimated_total_contract_value: 1_000_000,
        weighted_pipeline_value: 700_000,
        calculated_risk_rating: "Amber",
      }),
      opportunityFixture({
        id: 2,
        name: "Housing fire door remedials",
        buyer_name: "Harbour Homes Partnership",
        self_delivery_fit: "moderate",
        self_delivery_capture: false,
        estimated_total_contract_value: 800_000,
        weighted_pipeline_value: 320_000,
        calculated_bid_no_bid_recommendation: "Watch",
      }),
      opportunityFixture({
        id: 3,
        name: "Commercial tower smoke control maintenance",
        buyer_name: "Crownwell Property Management",
        stage: "Qualified out",
        self_delivery_fit: "weak",
        calculated_bid_no_bid_recommendation: "No bid",
        estimated_total_contract_value: 400_000,
        weighted_pipeline_value: 0,
      }),
      opportunityFixture({
        id: 4,
        name: "Local authority extinguishers call-off",
        buyer_name: "Dales County Council",
        stage: "Won",
        self_delivery_fit: "strong",
        self_delivery_capture: true,
        estimated_total_contract_value: 250_000,
        weighted_pipeline_value: 250_000,
      }),
    ];

    const summary = buildSelfDeliverySummary(opportunities);

    expect(summary.opportunityValue).toBe(2_450_000);
    expect(summary.valueCaptured).toBe(950_000);
    expect(summary.acceptedCount).toBe(2);
    expect(summary.declinedCount).toBe(1);
    expect(summary.conversionRate).toBeCloseTo(2 / 3);
    expect(summary.routeOpportunities.map((item) => item.opportunityId)).toContain(1);
    expect(summary.leakageOpportunities.map((item) => item.opportunityId)).toContain(2);
    expect(summary.disciplineOpportunity.map((item) => item.label)).toContain("Fire Alarms");
    expect(summary.topDisplacedSuppliers[0]?.label).toBe("Incumbent Fire Alarm Specialist");
  });
});

function opportunityFixture(overrides: Partial<Opportunity>): Opportunity {
  return {
    id: 100,
    name: "Fire alarm maintenance",
    buyer_name: "Example Buyer",
    sector: "Retail",
    region: "UK-wide",
    source_type: "pipeline_upload",
    stage: "Negotiation",
    owner: "Commercial Manager",
    estimated_annual_revenue: 100_000,
    estimated_total_contract_value: 500_000,
    estimated_gross_margin: 125_000,
    margin_percentage: 25,
    probability: 0.5,
    weighted_value: 250_000,
    submission_deadline: null,
    forecast_start_month: null,
    self_delivery_fit: "strong",
    risk_rating: "medium",
    strategic_fit_score: 70,
    bid_no_bid_recommendation: "bid",
    recommended_action: "Route to Mitie Fire & Security.",
    created_at: "2026-06-30T00:00:00",
    updated_at: "2026-06-30T00:00:00",
    weighted_pipeline_value: 250_000,
    strategic_must_win: false,
    calculated_risk_rating: "Amber",
    margin_warning: false,
    deadline_warning: false,
    self_delivery_capture: true,
    executive_escalation: false,
    calculated_bid_no_bid_recommendation: "Pursue",
    priority_score: 50,
    calculated_recommended_action: "Route to Mitie Fire & Security.",
    latest_ai_analysis: null,
    ...overrides,
  };
}

function executiveReportFixture(): ExecutiveReport {
  const opportunity = opportunityFixture({
    id: 1,
    name: "Strategic fire alarm renewal",
    buyer_name: "Dales County Council",
    weighted_pipeline_value: 900_000,
  });

  return {
    report_name: "MiSi Executive Summary",
    generated_at: "2026-06-29T09:00:00Z",
    reporting_date: "2026-06-29",
    audience: ["Managing Director", "Finance Director", "Group Sales Director"],
    data_note: "MVP report generated from current MiSi local data.",
    dashboard_kpis: {
      total_pipeline_value: 2_000_000,
      weighted_pipeline_value: 1_200_000,
      estimated_gross_margin: 420_000,
      average_margin_percentage: 21,
      live_opportunity_count: 3,
      strategic_must_win_count: 1,
      live_tender_count: 2,
      market_signal_count: 4,
      high_risk_count: 1,
      urgent_deadline_count: 1,
      executive_summary_text: "Pipeline position. Recommended next action: sponsor review.",
      monthly_revenue_forecast: [{ month: "2026-04", value: 100_000 }],
      monthly_margin_forecast: [{ month: "2026-04", value: 25_000 }],
      top_opportunities: [opportunity],
      top_executive_actions: [
        {
          id: 1,
          priority: "high",
          category: "Sponsor review",
          owner: "MD",
          due_date: "2026-07-01",
          related_opportunity_id: 1,
          commercial_value: 900_000,
          reason: "Strategic must-win needs sponsor attention.",
          recommended_action: "Assign sponsor this week.",
          status: "open",
        },
      ],
    },
    leadership_summary: {
      headline: "Protect priority pipeline this week.",
      summary: "Weighted pipeline and margin need leadership attention.",
      md_attention: ["Sponsor strategic must-wins."],
      finance_attention: ["Review margin warnings."],
      sales_attention: ["Confirm buyer plan."],
      bid_team_attention: ["Close bid actions."],
      risk_warnings: ["One red risk requires sponsor control."],
      next_best_actions: ["Hold MD/FD/GSD checkpoint."],
    },
    top_opportunities: [opportunity],
    finance_forecast: {
      financial_year: "2026/27",
      financial_year_start: 2026,
      financial_year_end: 2027,
      financial_year_months: ["2026-04", "2026-05"],
      monthly_revenue: [{ month: "2026-04", value: 100_000 }],
      monthly_margin: [{ month: "2026-04", value: 25_000 }],
      secured_revenue: 180_000,
      secured_gross_margin: 45_000,
      secured_margin_percentage: 25,
      open_weighted_revenue: 1_000_000,
      open_weighted_margin: 250_000,
      risk_adjusted_revenue: 850_000,
      risk_adjusted_margin: 210_000,
      forecast_to_financial_year_end: 1_030_000,
      forecast_margin_to_financial_year_end: 255_000,
      secured_work: [
        {
          opportunity_id: 1,
          opportunity_name: "Won FRA call-off",
          client: "Dales County Council",
          won_revenue: 180_000,
          won_gross_margin: 45_000,
          margin_percentage: 25,
          delivery_start_month: "2026-04",
          business_unit: null,
          discipline: "Fire Risk Assessments",
          confidence: 1,
        },
      ],
      open_opportunities: [
        {
          opportunity_id: 1,
          opportunity_name: "Strategic fire alarm renewal",
          client: "Dales County Council",
          forecast_start_month: "2026-04",
          revenue_to_financial_year_end: 1_000_000,
          estimated_margin: 250_000,
          margin_percentage: 25,
          probability_weighting: 0.7,
          risk_adjustment: 0.1,
          forecast_category: "Likely",
          weighted_revenue: 700_000,
          weighted_margin: 175_000,
          risk_adjusted_revenue: 630_000,
          risk_adjusted_margin: 157_500,
        },
      ],
      margin_warnings: [],
      finance_review_items: [],
    },
    self_delivery_summary: {
      opportunity_value: 2_000_000,
      value_captured: 900_000,
      value_at_risk: 500_000,
      accepted_count: 2,
      declined_count: 1,
      conversion_rate: 0.67,
      top_displaced_suppliers: [
        { label: "Incumbent Fire Alarm Specialist", value: 1_000_000, count: 1 },
      ],
      disciplines_with_highest_opportunity: [
        { label: "Fire Alarms", value: 1_000_000, count: 1 },
      ],
      route_opportunities: [
        {
          opportunity_id: 1,
          name: "Strategic fire alarm renewal",
          buyer_name: "Dales County Council",
          discipline: "Fire Alarms",
          estimated_value: 1_000_000,
          weighted_value: 700_000,
          risk_rating: "Amber",
          recommended_action: "Route to Mitie Fire & Security.",
        },
      ],
      leakage_risks: [],
    },
    executive_actions: [
      {
        id: 1,
        priority: "high",
        category: "Sponsor review",
        owner: "MD",
        due_date: "2026-07-01",
        related_opportunity_id: 1,
        commercial_value: 900_000,
        reason: "Strategic must-win needs sponsor attention.",
        recommended_action: "Assign sponsor this week.",
        status: "open",
      },
    ],
    risks_and_recommendations: [
      {
        priority: "high",
        category: "Pipeline risk",
        summary: "One red-risk pursuit requires leadership control.",
        commercial_value: 1_200_000,
        owner: "Group Sales Director",
        recommended_action: "Confirm executive sponsor.",
      },
    ],
  };
}
