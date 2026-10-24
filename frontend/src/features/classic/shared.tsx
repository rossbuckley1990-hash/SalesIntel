"use client";

import {
  type AutofillOpportunitiesResponse,
  type ChatGPTAssistPromptResponse,
  type ExecutiveLeadershipBriefing,
  type ExecutiveReport,
  type FieldIntelligence,
  type InternetIntelligenceResult,
  type InternetIntelligenceType,
  type MarketSignalConversionResponse,
  type MisiDashboardData,
  type OpportunityEnrichment,
  type ResearchOpportunityResponse,
} from "@/lib/api";
import { type ExecutiveReportExportUrls } from "@/lib/report-export";
import type { LucideIcon } from "lucide-react";
import {
  Building2,
  CircleDollarSign,
  ClipboardList,
  Cog,
  FileText,
  Gauge,
  LineChart,
  Radar,
  Search,
  ShieldCheck,
  Users,
} from "lucide-react";

export type NavigationItem = {
  id: ViewId;
  label: string;
  icon: LucideIcon;
};

export type ViewId =
  | "research"
  | "executive"
  | "market"
  | "tenders"
  | "pipeline"
  | "finance"
  | "selfDelivery"
  | "buyers"
  | "competitors"
  | "actions"
  | "settings";

export type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; data: MisiDashboardData };

export type OpportunityAnalysisState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string };

export type LeadershipBriefingState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; briefing: ExecutiveLeadershipBriefing };

export type ReportExportState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | {
      status: "success";
      report: ExecutiveReport;
      urls: ExecutiveReportExportUrls | null;
    };

export type InternetResearchState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; result: InternetIntelligenceResult };

export type OpportunityResearchState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; result: ResearchOpportunityResponse };

export type MarketSignalConversionState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; result: MarketSignalConversionResponse };

export type AutofillState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; result: AutofillOpportunitiesResponse };

export type FieldIntelligenceState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; fields: FieldIntelligence[] };

export type OpportunityEnrichmentState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; enrichments: OpportunityEnrichment[] };

export type ResearchWorkspaceFilters = {
  sector: string;
  region: string;
  discipline: string;
  buyerType: string;
  minimumValue: string;
};

export type ResearchWorkspaceRequest = {
  query: string;
  filters: ResearchWorkspaceFilters;
};

export type ResearchWorkspaceState =
  | { status: "idle" }
  | { status: "loading"; stepIndex: number }
  | { status: "error"; message: string }
  | {
      status: "preview";
      request: ResearchWorkspaceRequest;
      result: ResearchOpportunityResponse;
    }
  | {
      status: "saving";
      request: ResearchWorkspaceRequest;
      result: ResearchOpportunityResponse;
      stepIndex: number;
    }
  | {
      status: "saved";
      request: ResearchWorkspaceRequest;
      result: ResearchOpportunityResponse;
    };

export type ChatGPTAssistState =
  | { status: "idle" }
  | { status: "prompting" }
  | {
      status: "ready";
      request: ResearchWorkspaceRequest;
      promptResponse: ChatGPTAssistPromptResponse;
      pastedJson: string;
      copyStatus: "idle" | "copied" | "failed";
    }
  | {
      status: "importing";
      request: ResearchWorkspaceRequest;
      promptResponse: ChatGPTAssistPromptResponse;
      pastedJson: string;
    }
  | { status: "error"; message: string };

export type Tone = "green" | "cyan" | "amber" | "red";

export type DashboardFilters = {
  sector: string;
  region: string;
  stage: string;
  riskRating: string;
  owner: string;
  search: string;
};

export type FilterOptions = {
  sectors: string[];
  regions: string[];
  stages: string[];
  riskRatings: string[];
  owners: string[];
};

export const emptyFilters: DashboardFilters = {
  sector: "",
  region: "",
  stage: "",
  riskRating: "",
  owner: "",
  search: "",
};

export const navigation: NavigationItem[] = [
  { id: "research", label: "AI Research Workspace", icon: Search },
  { id: "executive", label: "Executive Command", icon: Gauge },
  { id: "market", label: "Market Radar", icon: Radar },
  { id: "tenders", label: "Tender Intelligence", icon: FileText },
  { id: "pipeline", label: "Pipeline Forecast", icon: LineChart },
  { id: "finance", label: "LE1 Finance", icon: CircleDollarSign },
  { id: "selfDelivery", label: "Self-Delivery", icon: ShieldCheck },
  { id: "buyers", label: "Buyers", icon: Building2 },
  { id: "competitors", label: "Competitors", icon: Users },
  { id: "actions", label: "Executive Actions", icon: ClipboardList },
  { id: "settings", label: "Settings", icon: Cog },
];

export const moduleDescriptions: Record<ViewId, string> = {
  research:
    "Start with a rough phrase and let MiSi research, infer, estimate and build a commercial intelligence pack.",
  executive:
    "Where is the opportunity, what is it worth, what is the risk, and what action is needed this week.",
  market:
    "Public tender signals, watchlist movement and early buyer intent with source attribution.",
  tenders:
    "Live bid workload, deadlines, ownership and escalation points before submission.",
  pipeline:
    "Weighted commercial value, probability, margin and forecast shape by month.",
  finance:
    "LE1 view of secured work, open weighted revenue, risk adjustment and FD review items.",
  selfDelivery:
    "Capture fire and security scope in-house before third-party leakage becomes embedded.",
  buyers:
    "Buyer drivers, pain points, decision criteria and the next relationship action.",
  competitors:
    "Competitor threat, pricing behaviour and counter-strategy by sector.",
  actions: "Named leadership actions with owner, due date, value and reason.",
  settings:
    "Local demo configuration, backend boundary and prototype controls.",
};

export const liveTenderStages = new Set([
  "PQQ",
  "ITT live",
  "Clarification",
  "Pricing",
  "Final review",
  "Submitted",
  "Presentation",
  "Negotiation",
]);

export const internetIntelligenceTypes: Array<{
  value: InternetIntelligenceType;
  label: string;
}> = [
  { value: "market_radar", label: "Market Radar" },
  { value: "tender_intelligence", label: "Tender Intelligence" },
  { value: "competitor_intelligence", label: "Competitor Intelligence" },
  { value: "buyer_intelligence", label: "Buyer Intelligence" },
  { value: "opportunity_intelligence", label: "Opportunity Intelligence" },
  { value: "pipeline_forecast", label: "Pipeline Forecast" },
  { value: "self_delivery", label: "Self-Delivery" },
];

export const researchExamples = [
  "Find UK healthcare fire maintenance opportunities",
  "Research West Yorkshire Police fire and security estate",
  "Search local authority fire door inspection frameworks",
  "Identify retail fire alarm maintenance contracts due for renewal",
  "Analyse NHS fire compliance tender opportunities",
];

export const researchProgressSteps = [
  "Searching public sources",
  "Extracting tender signals",
  "Building buyer profile",
  "Estimating contract value",
  "Assessing self-delivery fit",
  "Scoring bid/no-bid",
  "Creating executive actions",
  "Updating MiSi dashboard",
];

export const researchProgressDetails = [
  "Checking public evidence and source attribution before any claim is treated as known.",
  "Separating tender signal, buyer intent and weak evidence so the record does not overclaim.",
  "Building the buyer view: drivers, compliance pressure, estate assumptions and unknowns.",
  "Creating directional value, margin and forecast assumptions with confidence labels.",
  "Assessing which Fire & Security disciplines should stay inside Mitie delivery.",
  "Combining commercial value, fit, risk, evidence strength and mobilisation pressure.",
  "Turning the insight into named leadership, sales, finance and bid-team actions.",
  "Preparing the pipeline, forecast and intelligence pack for review.",
];

export const researchFilterOptions = {
  sectors: [
    "Healthcare",
    "Education",
    "Police",
    "Local Authority",
    "Retail",
    "Housing",
    "Transport",
    "Utilities",
    "Commercial Property",
  ],
  regions: [
    "National",
    "London",
    "North West",
    "Yorkshire and the Humber",
    "West Midlands",
    "South East",
    "Scotland",
    "Wales",
  ],
  disciplines: [
    "Fire Alarms",
    "Emergency Lighting",
    "Extinguishers",
    "CCTV",
    "Access Control",
    "Fire Doors",
    "Fire Risk Assessments",
    "Passive Fire",
  ],
  buyerTypes: [
    "Public sector",
    "NHS / healthcare",
    "Blue light",
    "Higher education",
    "Local authority",
    "Retail estate",
    "Housing provider",
    "Private FM client",
  ],
};

export const emptyResearchFilters: ResearchWorkspaceFilters = {
  sector: "",
  region: "",
  discipline: "",
  buyerType: "",
  minimumValue: "",
};

export const toneClasses: Record<Tone, string> = {
  green: "border-emerald-300/25 bg-emerald-400/10 text-emerald-200",
  cyan: "border-cyan-300/25 bg-cyan-400/10 text-cyan-200",
  amber: "border-amber-300/25 bg-amber-400/10 text-amber-200",
  red: "border-red-300/25 bg-red-400/10 text-red-200",
};

export type IntelligenceFieldView = {
  fieldName: string;
  label: string;
  displayValue: string;
  rawValue: unknown;
  valueType: FieldIntelligence["value_type"];
  confidenceScore: number;
  rationale: string;
  sourceUrls: string[];
  sourceTitles: string[];
  recommendedNextStep: string;
  needsUserConfirmation: boolean;
};
