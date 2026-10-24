"use client";

import { useDeferredValue, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Bell,
  Building2,
  CheckCircle2,
  ChevronRight,
  CircleDollarSign,
  ClipboardList,
  Cog,
  Compass,
  Download,
  FileText,
  Gauge,
  Globe2,
  Landmark,
  LineChart,
  Loader2,
  LockKeyhole,
  Map as MapIcon,
  Printer,
  Radar,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  SlidersHorizontal,
  Target,
  TrendingUp,
  Users,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { HealthIndicator } from "@/components/health-indicator";
import {
  analyseOpportunity,
  autofillOpportunities,
  convertMarketSignal,
  fetchExecutiveReport,
  fetchOpportunityEnrichments,
  fetchOpportunityFieldIntelligence,
  fetchMisiDashboardData,
  generateChatGPTAssistPrompt,
  generateExecutiveSummary,
  getApiBaseUrl,
  importChatGPTAssistResult,
  researchOpportunity,
  runInternetResearch,
  type ChatGPTAssistPromptResponse,
  type DashboardSummary,
  type AutofillOpportunitiesResponse,
  type BuyerProfile,
  type CompetitorProfile,
  type ExecutiveAction,
  type ExecutiveLeadershipBriefing,
  type ExecutiveReport,
  type FieldIntelligence,
  type FinanceForecastSummary,
  type FinanceReviewItem,
  type FinanceWarning,
  type ForecastPoint,
  type InternetIntelligenceRequest,
  type InternetIntelligenceResult,
  type InternetIntelligenceType,
  type MarketSignal,
  type MarketSignalConversionResponse,
  type MisiDashboardData,
  type OpenForecastItem,
  type Opportunity,
  type OpportunityAIAnalysis,
  type OpportunityEnrichment,
  type ResearchOpportunityRequest,
  type ResearchOpportunityResponse,
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
import {
  createExecutiveReportExportUrls,
  revokeExecutiveReportExportUrls,
  type ExecutiveReportExportUrls,
} from "@/lib/report-export";
import {
  buildSelfDeliverySummary,
  type SelfDeliveryAggregate,
  type SelfDeliveryOpportunityInsight,
  type SelfDeliverySummary,
} from "@/lib/self-delivery";

type NavigationItem = {
  id: ViewId;
  label: string;
  icon: LucideIcon;
};

type ViewId =
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

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; data: MisiDashboardData };

type OpportunityAnalysisState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string };

type LeadershipBriefingState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; briefing: ExecutiveLeadershipBriefing };

type ReportExportState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; report: ExecutiveReport; urls: ExecutiveReportExportUrls | null };

type InternetResearchState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; result: InternetIntelligenceResult };

type OpportunityResearchState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; result: ResearchOpportunityResponse };

type MarketSignalConversionState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; result: MarketSignalConversionResponse };

type AutofillState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; result: AutofillOpportunitiesResponse };

type FieldIntelligenceState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; fields: FieldIntelligence[] };

type OpportunityEnrichmentState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; enrichments: OpportunityEnrichment[] };

type ResearchWorkspaceFilters = {
  sector: string;
  region: string;
  discipline: string;
  buyerType: string;
  minimumValue: string;
};

type ResearchWorkspaceRequest = {
  query: string;
  filters: ResearchWorkspaceFilters;
};

type ResearchWorkspaceState =
  | { status: "idle" }
  | { status: "loading"; stepIndex: number }
  | { status: "error"; message: string }
  | { status: "preview"; request: ResearchWorkspaceRequest; result: ResearchOpportunityResponse }
  | { status: "saving"; request: ResearchWorkspaceRequest; result: ResearchOpportunityResponse; stepIndex: number }
  | { status: "saved"; request: ResearchWorkspaceRequest; result: ResearchOpportunityResponse };

type ChatGPTAssistState =
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

type Tone = "green" | "cyan" | "amber" | "red";

type DashboardFilters = {
  sector: string;
  region: string;
  stage: string;
  riskRating: string;
  owner: string;
  search: string;
};

type FilterOptions = {
  sectors: string[];
  regions: string[];
  stages: string[];
  riskRatings: string[];
  owners: string[];
};

const emptyFilters: DashboardFilters = {
  sector: "",
  region: "",
  stage: "",
  riskRating: "",
  owner: "",
  search: "",
};

const navigation: NavigationItem[] = [
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

const moduleDescriptions: Record<ViewId, string> = {
  research: "Start with a rough phrase and let MiSi research, infer, estimate and build a commercial intelligence pack.",
  executive: "Where is the opportunity, what is it worth, what is the risk, and what action is needed this week.",
  market: "Public tender signals, watchlist movement and early buyer intent with source attribution.",
  tenders: "Live bid workload, deadlines, ownership and escalation points before submission.",
  pipeline: "Weighted commercial value, probability, margin and forecast shape by month.",
  finance: "LE1 view of secured work, open weighted revenue, risk adjustment and FD review items.",
  selfDelivery: "Capture fire and security scope in-house before third-party leakage becomes embedded.",
  buyers: "Buyer drivers, pain points, decision criteria and the next relationship action.",
  competitors: "Competitor threat, pricing behaviour and counter-strategy by sector.",
  actions: "Named leadership actions with owner, due date, value and reason.",
  settings: "Local demo configuration, backend boundary and prototype controls.",
};

const liveTenderStages = new Set([
  "PQQ",
  "ITT live",
  "Clarification",
  "Pricing",
  "Final review",
  "Submitted",
  "Presentation",
  "Negotiation",
]);

const internetIntelligenceTypes: Array<{
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

const researchExamples = [
  "Find UK healthcare fire maintenance opportunities",
  "Research West Yorkshire Police fire and security estate",
  "Search local authority fire door inspection frameworks",
  "Identify retail fire alarm maintenance contracts due for renewal",
  "Analyse NHS fire compliance tender opportunities",
];

const researchProgressSteps = [
  "Searching public sources",
  "Extracting tender signals",
  "Building buyer profile",
  "Estimating contract value",
  "Assessing self-delivery fit",
  "Scoring bid/no-bid",
  "Creating executive actions",
  "Updating MiSi dashboard",
];

const researchProgressDetails = [
  "Checking public evidence and source attribution before any claim is treated as known.",
  "Separating tender signal, buyer intent and weak evidence so the record does not overclaim.",
  "Building the buyer view: drivers, compliance pressure, estate assumptions and unknowns.",
  "Creating directional value, margin and forecast assumptions with confidence labels.",
  "Assessing which Fire & Security disciplines should stay inside Mitie delivery.",
  "Combining commercial value, fit, risk, evidence strength and mobilisation pressure.",
  "Turning the insight into named leadership, sales, finance and bid-team actions.",
  "Preparing the pipeline, forecast and intelligence pack for review.",
];

const researchFilterOptions = {
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

const emptyResearchFilters: ResearchWorkspaceFilters = {
  sector: "",
  region: "",
  discipline: "",
  buyerType: "",
  minimumValue: "",
};

const toneClasses: Record<Tone, string> = {
  green: "border-emerald-300/25 bg-emerald-400/10 text-emerald-200",
  cyan: "border-cyan-300/25 bg-cyan-400/10 text-cyan-200",
  amber: "border-amber-300/25 bg-amber-400/10 text-amber-200",
  red: "border-red-300/25 bg-red-400/10 text-red-200",
};

export function DashboardShell() {
  const [activeView, setActiveView] = useState<ViewId>("research");
  const [filters, setFilters] = useState<DashboardFilters>(emptyFilters);
  const [selectedOpportunity, setSelectedOpportunity] = useState<Opportunity | null>(null);
  const { state, reload, updateOpportunityAnalysis } = useMisiData();
  const activeModule = navigation.find((item) => item.id === activeView) ?? navigation[0];
  const deferredFilters = useDeferredValue(filters);
  const filteredData = useMemo(
    () => (state.status === "success" ? buildFilteredDashboardData(state.data, deferredFilters) : null),
    [state, deferredFilters],
  );
  const filterOptions = useMemo(
    () => (state.status === "success" ? buildFilterOptions(state.data.opportunities) : null),
    [state],
  );
  const hasActiveFilters = Object.values(filters).some(Boolean);

  function updateFilter<Key extends keyof DashboardFilters>(
    key: Key,
    value: DashboardFilters[Key],
  ) {
    setFilters((current) => ({
      ...current,
      [key]: value,
    }));
  }

  function resetFilters() {
    setFilters(emptyFilters);
  }

  function handleOpportunityAnalysisComplete(
    opportunityId: number,
    analysis: OpportunityAIAnalysis,
  ) {
    updateOpportunityAnalysis(opportunityId, analysis);
    setSelectedOpportunity((current) =>
      current?.id === opportunityId ? { ...current, latest_ai_analysis: analysis } : current,
    );
  }

  return (
    <main className="min-h-screen bg-[#080d10] bg-[linear-gradient(180deg,#080d10_0%,#0b1317_42%,#080d10_100%)] text-slate-100">
      <div className="grid min-h-screen grid-cols-1 xl:grid-cols-[280px_minmax(0,1fr)]">
        <Sidebar activeView={activeView} onSelect={setActiveView} />

        <section className="min-w-0">
          <Header
            activeModule={activeModule}
            search={filters.search}
            onSearchChange={(value) => updateFilter("search", value)}
          />

          <div className="mx-auto grid w-full max-w-[1600px] gap-5 px-4 py-5 sm:px-5 lg:px-7">
            <MobileModuleTabs activeView={activeView} onSelect={setActiveView} />
            {filterOptions && activeView !== "research" ? (
              <DashboardFilterBar
                filters={filters}
                filterOptions={filterOptions}
                hasActiveFilters={hasActiveFilters}
                onFilterChange={updateFilter}
                onReset={resetFilters}
              />
            ) : null}
            {state.status === "loading" ? <DashboardLoading /> : null}
            {state.status === "error" ? (
              <DashboardError message={state.message} onRetry={reload} />
            ) : null}
            {filteredData ? (
              <>
                {renderView(activeView, filteredData, setSelectedOpportunity, reload)}
                {selectedOpportunity ? (
                  <OpportunityDetailDrawer
                    contextData={filteredData}
                    opportunity={selectedOpportunity}
                    onAnalysisComplete={handleOpportunityAnalysisComplete}
                    onClose={() => setSelectedOpportunity(null)}
                  />
                ) : null}
              </>
            ) : null}
          </div>
        </section>
      </div>
    </main>
  );
}

function useMisiData() {
  const [refreshKey, setRefreshKey] = useState(0);
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    setState((current) =>
      current.status === "success" ? current : { status: "loading" },
    );

    fetchMisiDashboardData(controller.signal)
      .then((data) => {
        setState({ status: "success", data });
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }

        const message =
          error instanceof Error
            ? error.message
            : "Unable to connect to the MiSi backend.";
        setState({ status: "error", message });
      });

    return () => {
      controller.abort();
    };
  }, [refreshKey]);

  return {
    state,
    reload: () => setRefreshKey((current) => current + 1),
    updateOpportunityAnalysis: (
      opportunityId: number,
      analysis: OpportunityAIAnalysis,
    ) => {
      setState((current) => {
        if (current.status !== "success") {
          return current;
        }

        const updateOpportunity = (opportunity: Opportunity): Opportunity =>
          opportunity.id === opportunityId
            ? { ...opportunity, latest_ai_analysis: analysis }
            : opportunity;

        return {
          status: "success",
          data: {
            ...current.data,
            opportunities: current.data.opportunities.map(updateOpportunity),
            dashboard: {
              ...current.data.dashboard,
              top_opportunities: current.data.dashboard.top_opportunities.map(updateOpportunity),
            },
          },
        };
      });
    },
  };
}

function Sidebar({
  activeView,
  onSelect,
}: {
  activeView: ViewId;
  onSelect: (view: ViewId) => void;
}) {
  return (
    <aside className="hidden border-r border-white/10 bg-[#0b1115] xl:block">
      <div className="flex h-full min-h-screen flex-col">
        <div className="border-b border-white/10 px-6 py-6">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-md bg-mitie-green text-lg font-black text-white">
              M
            </div>
            <div>
              <div className="text-xl font-semibold text-white">MiSi</div>
              <div className="mt-1 text-sm text-slate-400">Mitie Sales Intelligence</div>
            </div>
          </div>
        </div>

        <nav className="grid gap-1 px-3 py-4" aria-label="Primary modules">
          {navigation.map((item) => {
            const Icon = item.icon;
            const active = item.id === activeView;

            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onSelect(item.id)}
                aria-current={active ? "page" : undefined}
                className={`flex h-11 items-center justify-between rounded-md px-3 text-left text-sm font-semibold transition ${
                  active
                    ? "bg-white text-[#10171b] shadow-[0_10px_28px_rgba(0,0,0,0.22)]"
                    : "text-slate-300 hover:bg-white/[0.06] hover:text-white"
                }`}
              >
                <span className="flex min-w-0 items-center gap-3">
                  <Icon aria-hidden="true" className="h-4 w-4 shrink-0" />
                  <span className="truncate">{item.label}</span>
                </span>
                {active ? <ChevronRight aria-hidden="true" className="h-4 w-4 shrink-0" /> : null}
              </button>
            );
          })}
        </nav>

        <div className="mt-auto border-t border-white/10 p-4">
          <div className="rounded-lg border border-emerald-300/20 bg-emerald-400/10 p-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-emerald-100">
              <LockKeyhole aria-hidden="true" className="h-4 w-4" />
              Backend boundary
            </div>
            <p className="mt-2 text-sm leading-5 text-slate-300">
              Dashboard data is read from the MiSi API. OpenAI credentials stay on the backend.
            </p>
          </div>
        </div>
      </div>
    </aside>
  );
}

function Header({
  activeModule,
  search,
  onSearchChange,
}: {
  activeModule: NavigationItem;
  search: string;
  onSearchChange: (value: string) => void;
}) {
  const Icon = activeModule.icon;

  return (
    <header className="sticky top-0 z-20 border-b border-white/10 bg-[#080d10]/94 px-4 py-4 backdrop-blur sm:px-5 lg:px-7">
      <div className="mx-auto flex max-w-[1600px] flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-3 text-sm font-semibold text-mitie-lime">
            <Icon aria-hidden="true" className="h-4 w-4" />
            <span>{activeModule.label}</span>
          </div>
          <h1 className="mt-2 text-2xl font-semibold text-white sm:text-3xl">
            MiSi — Mitie Sales Intelligence
          </h1>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-400">
            {moduleDescriptions[activeModule.id]}
          </p>
        </div>

        <div className="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-center">
          <label className="relative block min-w-0 sm:w-80">
            <Search
              aria-hidden="true"
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500"
            />
            <span className="sr-only">Search buyers, tenders and opportunities</span>
            <input
              value={search}
              onChange={(event) => onSearchChange(event.target.value)}
              className="h-10 w-full rounded-md border border-white/10 bg-white/[0.04] pl-9 pr-3 text-sm text-white placeholder:text-slate-500"
              placeholder="Search buyers, tenders, opportunities"
            />
          </label>
          <HealthIndicator />
        </div>
      </div>
    </header>
  );
}

function DashboardFilterBar({
  filters,
  filterOptions,
  hasActiveFilters,
  onFilterChange,
  onReset,
}: {
  filters: DashboardFilters;
  filterOptions: FilterOptions;
  hasActiveFilters: boolean;
  onFilterChange: <Key extends keyof DashboardFilters>(
    key: Key,
    value: DashboardFilters[Key],
  ) => void;
  onReset: () => void;
}) {
  return (
    <section className="rounded-lg border border-white/10 bg-[#0d151a] p-4 shadow-[0_20px_70px_rgba(0,0,0,0.22)]" aria-label="Dashboard filters">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-sm font-semibold text-white">
            <SlidersHorizontal aria-hidden="true" className="h-4 w-4 text-mitie-lime" />
            Dashboard filters
          </div>
          <p className="mt-1 text-sm leading-5 text-slate-500">
            Refine the command view without another backend request.
          </p>
        </div>

        <div className="grid min-w-0 flex-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-[repeat(5,minmax(0,1fr))_auto]">
          <FilterSelect
            label="Sector"
            value={filters.sector}
            options={filterOptions.sectors}
            onChange={(value) => onFilterChange("sector", value)}
          />
          <FilterSelect
            label="Region"
            value={filters.region}
            options={filterOptions.regions}
            onChange={(value) => onFilterChange("region", value)}
          />
          <FilterSelect
            label="Stage"
            value={filters.stage}
            options={filterOptions.stages}
            onChange={(value) => onFilterChange("stage", value)}
          />
          <FilterSelect
            label="Risk rating"
            value={filters.riskRating}
            options={filterOptions.riskRatings}
            onChange={(value) => onFilterChange("riskRating", value)}
          />
          <FilterSelect
            label="Owner"
            value={filters.owner}
            options={filterOptions.owners}
            onChange={(value) => onFilterChange("owner", value)}
          />
          <button
            type="button"
            onClick={onReset}
            disabled={!hasActiveFilters}
            className="inline-flex h-10 items-center justify-center gap-2 self-end rounded-md border border-white/10 bg-white px-3 text-sm font-semibold text-[#10171b] transition hover:bg-slate-200 disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/[0.04] disabled:text-slate-500"
          >
            <RefreshCw aria-hidden="true" className="h-4 w-4" />
            Reset
          </button>
        </div>
      </div>
    </section>
  );
}

function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="grid gap-1.5">
      <span className="text-xs font-semibold text-slate-500">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-10 rounded-md border border-white/10 bg-[#111a20] px-3 text-sm font-semibold text-white"
      >
        <option value="">All {label.toLowerCase()}</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function MobileModuleTabs({
  activeView,
  onSelect,
}: {
  activeView: ViewId;
  onSelect: (view: ViewId) => void;
}) {
  return (
    <div className="overflow-x-auto xl:hidden">
      <div className="flex min-w-max gap-2">
        {navigation.map((item) => {
          const active = item.id === activeView;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onSelect(item.id)}
              className={`h-10 rounded-md border px-3 text-sm font-semibold transition ${
                active
                  ? "border-white bg-white text-[#10171b]"
                  : "border-white/10 bg-white/[0.04] text-slate-300 hover:bg-white/[0.08]"
              }`}
            >
              {item.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function renderView(
  activeView: ViewId,
  data: MisiDashboardData,
  onSelectOpportunity: (opportunity: Opportunity) => void,
  onDataChanged: () => void,
) {
  switch (activeView) {
    case "research":
      return (
        <AIResearchWorkspaceView
          onDataChanged={onDataChanged}
          onSelectOpportunity={onSelectOpportunity}
        />
      );
    case "executive":
      return (
        <ExecutiveCommandView
          data={data}
          onDataChanged={onDataChanged}
          onSelectOpportunity={onSelectOpportunity}
        />
      );
    case "market":
      return (
        <MarketRadarView
          marketSignals={data.marketSignals}
          onDataChanged={onDataChanged}
          onSelectOpportunity={onSelectOpportunity}
        />
      );
    case "tenders":
      return <TenderIntelligenceView opportunities={data.opportunities} />;
    case "pipeline":
      return <PipelineForecastView data={data} />;
    case "finance":
      return <FinanceView financeSummary={data.financeSummary} />;
    case "selfDelivery":
      return <SelfDeliveryView opportunities={data.opportunities} />;
    case "buyers":
      return <BuyersView buyers={data.buyerProfiles} />;
    case "competitors":
      return <CompetitorsView competitors={data.competitorProfiles} />;
    case "actions":
      return <ExecutiveActionsView actions={data.executiveActions} />;
    case "settings":
      return <SettingsView />;
    default:
      return (
        <ExecutiveCommandView
          data={data}
          onDataChanged={onDataChanged}
          onSelectOpportunity={onSelectOpportunity}
        />
      );
  }
}

function AIResearchWorkspaceView({
  onDataChanged,
  onSelectOpportunity,
}: {
  onDataChanged: () => void;
  onSelectOpportunity: (opportunity: Opportunity) => void;
}) {
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState<ResearchWorkspaceFilters>(emptyResearchFilters);
  const [workspaceState, setWorkspaceState] = useState<ResearchWorkspaceState>({
    status: "idle",
  });
  const [chatgptAssistState, setChatgptAssistState] = useState<ChatGPTAssistState>({
    status: "idle",
  });
  const trimmedQuery = query.trim();
  const canResearch = trimmedQuery.length >= 6 && workspaceState.status !== "loading" && workspaceState.status !== "saving";
  const canUseChatGPTAssist =
    trimmedQuery.length >= 6 &&
    chatgptAssistState.status !== "prompting" &&
    chatgptAssistState.status !== "importing";

  function updateResearchFilter<Key extends keyof ResearchWorkspaceFilters>(
    key: Key,
    value: ResearchWorkspaceFilters[Key],
  ) {
    setFilters((current) => ({
      ...current,
      [key]: value,
    }));
  }

  async function handleResearch() {
    if (!canResearch) {
      return;
    }

    const request: ResearchWorkspaceRequest = {
      query: trimmedQuery,
      filters,
    };
    setWorkspaceState({ status: "loading", stepIndex: 0 });

    const progressTimer = window.setInterval(() => {
      setWorkspaceState((current) =>
        current.status === "loading"
          ? {
              ...current,
              stepIndex: Math.min(current.stepIndex + 1, researchProgressSteps.length - 2),
            }
          : current,
      );
    }, 900);

    try {
      const result = await researchOpportunity(buildResearchPayload(request, false));
      window.clearInterval(progressTimer);
      setWorkspaceState({ status: "preview", request, result });
    } catch (error: unknown) {
      window.clearInterval(progressTimer);
      setWorkspaceState({
        status: "error",
        message: getOpportunityResearchErrorMessage(error),
      });
    }
  }

  async function handleSaveToPipeline(
    request: ResearchWorkspaceRequest,
    currentResult: ResearchOpportunityResponse,
  ) {
    setWorkspaceState({
      status: "saving",
      request,
      result: currentResult,
      stepIndex: 5,
    });

    const progressTimer = window.setInterval(() => {
      setWorkspaceState((current) =>
        current.status === "saving"
          ? {
              ...current,
              stepIndex: Math.min(current.stepIndex + 1, researchProgressSteps.length - 1),
            }
          : current,
      );
    }, 800);

    try {
      const savedResult = await researchOpportunity(buildResearchPayload(request, true));
      window.clearInterval(progressTimer);
      setWorkspaceState({ status: "saved", request, result: savedResult });
      onDataChanged();
    } catch (error: unknown) {
      window.clearInterval(progressTimer);
      setWorkspaceState({
        status: "error",
        message: getOpportunityResearchErrorMessage(error),
      });
    }
  }

  async function handleGenerateChatGPTAssistPrompt() {
    if (!canUseChatGPTAssist) {
      return;
    }

    const request: ResearchWorkspaceRequest = {
      query: trimmedQuery,
      filters,
    };
    setChatgptAssistState({ status: "prompting" });

    try {
      const promptResponse = await generateChatGPTAssistPrompt(
        buildResearchPayload(request, true),
      );
      setChatgptAssistState({
        status: "ready",
        request,
        promptResponse,
        pastedJson: "",
        copyStatus: "idle",
      });
    } catch (error: unknown) {
      setChatgptAssistState({
        status: "error",
        message: getChatGPTAssistErrorMessage(error),
      });
    }
  }

  async function handleCopyChatGPTPrompt() {
    if (chatgptAssistState.status !== "ready") {
      return;
    }

    try {
      await navigator.clipboard.writeText(chatgptAssistState.promptResponse.prompt);
      setChatgptAssistState({
        ...chatgptAssistState,
        copyStatus: "copied",
      });
    } catch {
      setChatgptAssistState({
        ...chatgptAssistState,
        copyStatus: "failed",
      });
    }
  }

  function handleChatGPTJsonChange(value: string) {
    if (chatgptAssistState.status !== "ready") {
      return;
    }
    setChatgptAssistState({
      ...chatgptAssistState,
      pastedJson: value,
    });
  }

  async function handleImportChatGPTAssistResult() {
    if (
      chatgptAssistState.status !== "ready" ||
      chatgptAssistState.pastedJson.trim().length < 2
    ) {
      return;
    }

    const { request, promptResponse, pastedJson } = chatgptAssistState;
    setChatgptAssistState({
      status: "importing",
      request,
      promptResponse,
      pastedJson,
    });

    try {
      const result = await importChatGPTAssistResult({
        ...buildResearchPayload(request, true),
        result_json: pastedJson,
      });
      setWorkspaceState({ status: "saved", request, result });
      setChatgptAssistState({ status: "idle" });
      onDataChanged();
    } catch (error: unknown) {
      setChatgptAssistState({
        status: "error",
        message: getChatGPTAssistErrorMessage(error),
      });
    }
  }

  const result =
    workspaceState.status === "preview" ||
    workspaceState.status === "saving" ||
    workspaceState.status === "saved"
      ? workspaceState.result
      : null;
  const resultRequest =
    workspaceState.status === "preview" ||
    workspaceState.status === "saving" ||
    workspaceState.status === "saved"
      ? workspaceState.request
      : null;

  return (
    <div className="grid gap-5">
      <section className="overflow-hidden rounded-lg border border-mitie-lime/20 bg-[#0d151a] shadow-[0_28px_110px_rgba(0,0,0,0.42)]">
        <div className="grid gap-0 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="p-5 sm:p-6 lg:p-7">
            <div className="flex flex-wrap items-center gap-2">
              <StatusPill tone="green" label="AI-first workspace" />
              <StatusPill tone="cyan" label="Public-source research" />
              <StatusPill tone="amber" label="Confidence labelled" />
            </div>
            <h2 className="mt-5 max-w-4xl text-2xl font-semibold leading-9 text-white sm:text-3xl">
              Start with a rough phrase. MiSi builds the evidence-backed commercial readout.
            </h2>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
              Known facts, inferred context, estimated value and unresolved unknowns stay visibly separate so leadership can act without pretending the data is perfect.
            </p>

            <div className="mt-6 grid gap-3">
              <label className="grid gap-2">
                <span className="text-xs font-semibold uppercase text-slate-500">
                  Ask MiSi
                </span>
                <textarea
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  rows={4}
                  data-testid="ai-research-query"
                  className="min-h-36 rounded-lg border border-mitie-lime/25 bg-[#080d10] px-4 py-4 text-lg font-semibold leading-8 text-white outline-none ring-0 placeholder:text-slate-500 transition focus:border-mitie-lime/70 focus:shadow-[0_0_0_4px_rgba(124,179,66,0.12)]"
                  placeholder="Ask MiSi to research a buyer, tender, market, sector or opportunity..."
                />
              </label>

              <div className="flex flex-wrap gap-2" aria-label="Example research prompts">
                {researchExamples.map((example) => (
                  <button
                    key={example}
                    type="button"
                    onClick={() => setQuery(example)}
                    className="rounded-md border border-white/10 bg-white/[0.04] px-3 py-2 text-left text-xs font-semibold leading-5 text-slate-300 transition hover:border-mitie-lime/40 hover:bg-mitie-lime/10 hover:text-white"
                  >
                    {example}
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-5 grid gap-3 lg:grid-cols-5">
              <WorkspaceFilterSelect
                label="Sector"
                value={filters.sector}
                options={researchFilterOptions.sectors}
                onChange={(value) => updateResearchFilter("sector", value)}
              />
              <WorkspaceFilterSelect
                label="Region"
                value={filters.region}
                options={researchFilterOptions.regions}
                onChange={(value) => updateResearchFilter("region", value)}
              />
              <WorkspaceFilterSelect
                label="Discipline"
                value={filters.discipline}
                options={researchFilterOptions.disciplines}
                onChange={(value) => updateResearchFilter("discipline", value)}
              />
              <WorkspaceFilterSelect
                label="Buyer type"
                value={filters.buyerType}
                options={researchFilterOptions.buyerTypes}
                onChange={(value) => updateResearchFilter("buyerType", value)}
              />
              <label className="grid gap-1.5">
                <span className="text-xs font-semibold text-slate-500">Minimum value</span>
                <input
                  value={filters.minimumValue}
                  onChange={(event) => updateResearchFilter("minimumValue", event.target.value)}
                  inputMode="numeric"
                  className="h-10 rounded-md border border-white/10 bg-[#111a20] px-3 text-sm font-semibold text-white placeholder:text-slate-500"
                  placeholder="e.g. 500000"
                />
              </label>
            </div>

            <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-center">
              <button
                type="button"
                onClick={handleResearch}
                disabled={!canResearch}
                data-testid="ai-research-submit"
                className="inline-flex min-h-12 items-center justify-center gap-2 rounded-md border border-mitie-lime/30 bg-mitie-lime px-4 py-3 text-sm font-black text-[#07100b] shadow-[0_14px_40px_rgba(124,179,66,0.18)] transition hover:bg-[#d8ff62] disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/10 disabled:text-slate-400 disabled:shadow-none"
              >
                {workspaceState.status === "loading" ? (
                  <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                ) : (
                  <Search aria-hidden="true" className="h-4 w-4" />
                )}
                {workspaceState.status === "loading" ? "Researching with MiSi" : "Research with MiSi"}
              </button>
              <button
                type="button"
                onClick={handleGenerateChatGPTAssistPrompt}
                disabled={!canUseChatGPTAssist}
                data-testid="chatgpt-assist-prompt-button"
                className="inline-flex min-h-12 items-center justify-center gap-2 rounded-md border border-cyan-300/30 bg-cyan-400/10 px-4 py-3 text-sm font-black text-cyan-100 transition hover:border-cyan-200/60 hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/5 disabled:text-slate-500"
              >
                {chatgptAssistState.status === "prompting" ? (
                  <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                ) : (
                  <ClipboardList aria-hidden="true" className="h-4 w-4" />
                )}
                {chatgptAssistState.status === "prompting"
                  ? "Preparing ChatGPT Prompt"
                  : "Use ChatGPT Plus Assist"}
              </button>
              <p className="text-sm leading-6 text-slate-500">
                API path uses backend OpenAI. Assist path uses your manual ChatGPT Plus session and pasted JSON.
              </p>
            </div>
          </div>

          <aside className="border-t border-white/10 bg-[#111a20] p-5 xl:border-l xl:border-t-0">
            <div className="rounded-md border border-mitie-lime/20 bg-mitie-lime/10 p-4">
              <p className="text-xs font-black uppercase text-mitie-lime">30-second leadership read</p>
              <p className="mt-2 text-sm font-semibold leading-6 text-white">
                What is it, why does it matter, what is it worth, what is the risk, and what should Mitie do next?
              </p>
            </div>
            <h3 className="mt-5 text-sm font-semibold text-white">What MiSi creates</h3>
            <div className="mt-4 grid gap-3">
              <SourceRow label="Opportunity record" value="Commercial values, stage, risk and next action" tone="green" />
              <SourceRow label="Field evidence" value="Known, inferred, estimated and unknown labels" tone="cyan" />
              <SourceRow label="Executive action" value="Owner, priority, value and reason" tone="amber" />
              <SourceRow label="Dashboard update" value="Saved records feed the MiSi command centre" tone="green" />
            </div>
          </aside>
        </div>
      </section>

      {workspaceState.status === "loading" || workspaceState.status === "saving" ? (
        <ResearchProgressPanel
          stepIndex={workspaceState.stepIndex}
          saving={workspaceState.status === "saving"}
        />
      ) : null}

      {chatgptAssistState.status !== "idle" ? (
        <ChatGPTAssistPanel
          state={chatgptAssistState}
          onCopyPrompt={handleCopyChatGPTPrompt}
          onJsonChange={handleChatGPTJsonChange}
          onImport={handleImportChatGPTAssistResult}
          onDismiss={() => setChatgptAssistState({ status: "idle" })}
        />
      ) : null}

      {workspaceState.status === "error" ? (
        <Panel title="Research Needs Attention" action={<StatusPill tone="amber" label="Not completed" />}>
          <div className="flex gap-3 rounded-md border border-amber-300/20 bg-amber-400/10 p-4">
            <AlertTriangle aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0 text-amber-200" />
            <div>
              <p className="text-sm font-semibold text-amber-100">MiSi could not complete this research run.</p>
              <p className="mt-2 text-sm leading-6 text-amber-100/80">{workspaceState.message}</p>
              <p className="mt-2 text-sm leading-6 text-amber-100/70">
                Check the backend OpenAI configuration, then retry with a specific buyer, sector, region or discipline.
              </p>
            </div>
          </div>
        </Panel>
      ) : null}

      {result && resultRequest ? (
        <ResearchWorkspaceResult
          state={workspaceState.status}
          request={resultRequest}
          result={result}
          onSave={() => handleSaveToPipeline(resultRequest, result)}
          onOpenOpportunity={() => {
            if (result.opportunity) {
              onSelectOpportunity(result.opportunity);
            }
          }}
        />
      ) : (
        <ResearchWorkspaceIdle />
      )}
    </div>
  );
}

function WorkspaceFilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="grid gap-1.5">
      <span className="text-xs font-semibold text-slate-500">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-10 rounded-md border border-white/10 bg-[#111a20] px-3 text-sm font-semibold text-white"
      >
        <option value="">Any {label.toLowerCase()}</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function ChatGPTAssistPanel({
  state,
  onCopyPrompt,
  onJsonChange,
  onImport,
  onDismiss,
}: {
  state: ChatGPTAssistState;
  onCopyPrompt: () => void;
  onJsonChange: (value: string) => void;
  onImport: () => void;
  onDismiss: () => void;
}) {
  const hasPrompt = state.status === "ready" || state.status === "importing";
  const pastedJson = hasPrompt ? state.pastedJson : "";
  const importing = state.status === "importing";

  return (
    <Panel
      title="ChatGPT Plus Assist"
      action={<StatusPill tone="cyan" label="No API usage" />}
    >
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="grid gap-4">
          <div className="rounded-md border border-cyan-300/20 bg-cyan-400/10 p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-sm font-semibold text-cyan-100">
                  Manual intelligence bridge for your ChatGPT Plus account
                </p>
                <p className="mt-2 text-sm leading-6 text-cyan-100/75">
                  MiSi creates the strict research prompt. You paste it into ChatGPT Plus, then paste the JSON result back here. MiSi validates and imports it without calling the OpenAI API.
                </p>
              </div>
              <button
                type="button"
                onClick={onDismiss}
                className="rounded-md border border-white/10 bg-white/[0.04] px-3 py-2 text-xs font-bold text-slate-300 transition hover:bg-white/[0.08] hover:text-white"
              >
                Dismiss
              </button>
            </div>
          </div>

          {state.status === "prompting" ? (
            <div className="rounded-md border border-white/10 bg-[#111a20] p-4">
              <div className="flex items-center gap-3">
                <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin text-cyan-200" />
                <p className="text-sm font-semibold text-white">Preparing a strict MiSi prompt for ChatGPT Plus...</p>
              </div>
              <SkeletonLine className="mt-4 h-3 w-full rounded-full" />
              <SkeletonLine className="mt-2 h-3 w-3/4 rounded-full" />
            </div>
          ) : null}

          {hasPrompt ? (
            <>
              <label className="grid gap-2">
                <span className="text-xs font-black uppercase text-slate-500">Prompt for ChatGPT Plus</span>
                <textarea
                  readOnly
                  value={state.promptResponse.prompt}
                  rows={8}
                  data-testid="chatgpt-assist-prompt"
                  className="min-h-48 rounded-md border border-white/10 bg-[#080d10] p-3 text-xs leading-5 text-slate-300 outline-none"
                />
              </label>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={onCopyPrompt}
                  disabled={importing}
                  data-testid="chatgpt-assist-copy-button"
                  className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-cyan-300/30 bg-cyan-400/10 px-3 py-2 text-sm font-bold text-cyan-100 transition hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <ClipboardList aria-hidden="true" className="h-4 w-4" />
                  {state.status === "ready" && state.copyStatus === "copied"
                    ? "Prompt Copied"
                    : "Copy Prompt"}
                </button>
                <a
                  href="https://chatgpt.com/"
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-white/10 bg-white/[0.04] px-3 py-2 text-sm font-bold text-slate-200 transition hover:bg-white/[0.08] hover:text-white"
                >
                  <Globe2 aria-hidden="true" className="h-4 w-4" />
                  Open ChatGPT
                </a>
                {state.status === "ready" && state.copyStatus === "failed" ? (
                  <p className="flex items-center text-xs font-semibold text-amber-200">
                    Clipboard blocked. Select the prompt and copy it manually.
                  </p>
                ) : null}
              </div>

              <label className="grid gap-2">
                <span className="text-xs font-black uppercase text-slate-500">Paste ChatGPT JSON result</span>
                <textarea
                  value={pastedJson}
                  onChange={(event) => onJsonChange(event.target.value)}
                  rows={9}
                  disabled={importing}
                  data-testid="chatgpt-assist-json"
                  className="min-h-52 rounded-md border border-mitie-lime/20 bg-[#080d10] p-3 text-sm leading-6 text-white outline-none placeholder:text-slate-600 focus:border-mitie-lime/60 disabled:opacity-60"
                  placeholder='Paste the full JSON object from ChatGPT here. MiSi will reject prose, partial JSON or unlabelled fields.'
                />
              </label>

              <button
                type="button"
                onClick={onImport}
                disabled={importing || pastedJson.trim().length < 2}
                data-testid="chatgpt-assist-import-button"
                className="inline-flex min-h-11 items-center justify-center gap-2 rounded-md border border-mitie-lime/30 bg-mitie-lime px-4 py-3 text-sm font-black text-[#07100b] transition hover:bg-[#d8ff62] disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/10 disabled:text-slate-400"
              >
                {importing ? (
                  <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                ) : (
                  <CheckCircle2 aria-hidden="true" className="h-4 w-4" />
                )}
                {importing ? "Validating And Importing" : "Validate And Save Intelligence Pack"}
              </button>
            </>
          ) : null}

          {state.status === "error" ? (
            <div className="flex gap-3 rounded-md border border-amber-300/20 bg-amber-400/10 p-4">
              <AlertTriangle aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0 text-amber-200" />
              <div>
                <p className="text-sm font-semibold text-amber-100">ChatGPT Assist needs attention</p>
                <p className="mt-2 text-sm leading-6 text-amber-100/80">{state.message}</p>
              </div>
            </div>
          ) : null}
        </div>

        <div className="grid content-start gap-3">
          <SourceRow label="Step 1" value="Copy MiSi's strict prompt" tone="cyan" />
          <SourceRow label="Step 2" value="Run it manually in ChatGPT Plus" tone="green" />
          <SourceRow label="Step 3" value="Paste JSON back into MiSi" tone="amber" />
          <SourceRow label="Step 4" value="MiSi validates and saves the pack" tone="green" />
          <div className="rounded-md border border-white/10 bg-[#111a20] p-4">
            <p className="text-xs font-black uppercase text-slate-500">Boundary</p>
            <p className="mt-2 text-sm leading-6 text-slate-300">
              No browser automation, no session scraping and no API call. This is a deliberate human approval bridge.
            </p>
          </div>
          {hasPrompt ? (
            <div className="rounded-md border border-white/10 bg-[#111a20] p-4">
              <p className="text-xs font-black uppercase text-slate-500">Safety note</p>
              <p className="mt-2 text-sm leading-6 text-slate-300">
                {state.promptResponse.safety_note}
              </p>
            </div>
          ) : null}
        </div>
      </div>
    </Panel>
  );
}

function ResearchWorkspaceIdle() {
  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
      <Panel title="MiSi Has Not Researched This Area Yet" action={<StatusPill tone="cyan" label="Ready" />}>
        <div className="rounded-md border border-mitie-lime/20 bg-mitie-lime/10 p-4">
          <p className="text-sm font-semibold leading-6 text-white">
            Start with a buyer, sector or tender phrase and MiSi will build the intelligence pack: value, risk, confidence, evidence and next best action.
          </p>
        </div>
        <div className="mt-4 grid gap-4 lg:grid-cols-3">
          <ResearchCapabilityCard
            title="No perfect data required"
            body="MiSi can begin from a buyer name, sector theme, tender phrase or renewal hypothesis."
            tone="green"
          />
          <ResearchCapabilityCard
            title="Every gap is labelled"
            body="Unknown values are shown with a reason and a recommended next check, not hidden as blank fields."
            tone="amber"
          />
          <ResearchCapabilityCard
            title="Evidence stays visible"
            body="Sources, rationale and confidence scores travel with the generated opportunity pack."
            tone="cyan"
          />
        </div>
      </Panel>
      <Panel title="Output Preview" action={<StatusPill tone="green" label="Commercial pack" />}>
        <div className="mb-4 rounded-md border border-white/10 bg-[#111a20] p-4">
          <p className="text-xs font-black uppercase text-slate-500">Leadership answer</p>
          <p className="mt-2 text-sm font-semibold leading-6 text-white">
            What is it, why it matters, what it is worth, what the risk is, and what Mitie should do next.
          </p>
        </div>
        <div className="grid gap-3">
          <MetricLine label="Opportunity card" value="Created after research" detail="Name, buyer, stage, value, risk and action" />
          <MetricLine label="Field intelligence" value="Always labelled" detail="Known, inferred, estimated, unknown or needs confirmation" />
          <MetricLine label="Executive action" value="Generated" detail="Leadership owner, due date, commercial value and reason" />
        </div>
      </Panel>
    </div>
  );
}

function ResearchCapabilityCard({
  title,
  body,
  tone,
}: {
  title: string;
  body: string;
  tone: Tone;
}) {
  return (
    <article className={`rounded-md border p-4 ${toneClasses[tone]}`}>
      <h3 className="text-sm font-semibold text-white">{title}</h3>
      <p className="mt-3 text-sm leading-6 text-slate-300">{body}</p>
    </article>
  );
}

function NextActionCallout({
  label = "Next best action",
  action,
  tone = "green",
}: {
  label?: string;
  action: string;
  tone?: Tone;
}) {
  return (
    <div className={`mt-4 rounded-md border p-4 ${toneClasses[tone]}`}>
      <div className="flex items-start gap-3">
        <Target aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0" />
        <div>
          <p className="text-xs font-black uppercase">{label}</p>
          <p className="mt-2 text-sm font-semibold leading-6 text-white">{action}</p>
        </div>
      </div>
    </div>
  );
}

function ResearchProgressPanel({
  stepIndex,
  saving,
}: {
  stepIndex: number;
  saving: boolean;
}) {
  const boundedStep = Math.min(Math.max(stepIndex, 0), researchProgressSteps.length - 1);
  const progressPercent = ((boundedStep + 1) / researchProgressSteps.length) * 100;

  return (
    <Panel
      title={saving ? "Saving Intelligence To Pipeline" : "MiSi Research In Progress"}
      action={<StatusPill tone="cyan" label={saving ? "Pipeline update" : "Live research"} />}
    >
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="grid gap-4">
          <div className="rounded-md border border-cyan-300/20 bg-cyan-400/10 p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-sm font-semibold text-cyan-100">
                  {researchProgressSteps[boundedStep]}
                </p>
                <p className="mt-2 text-sm leading-6 text-cyan-100/75">
                  {researchProgressDetails[boundedStep]}
                </p>
              </div>
              <div className="shrink-0">
                <ConfidenceOrbit score={progressPercent / 100} label={`${Math.round(progressPercent)}%`} />
              </div>
            </div>
            <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/10">
              <div
                className="h-full rounded-full bg-mitie-lime transition-all duration-500"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            {researchProgressSteps.map((step, index) => {
              const complete = index < boundedStep;
              const active = index === boundedStep;
              return (
                <div
                  key={step}
                  className={`misi-fade-up rounded-md border p-4 transition ${
                    active
                      ? "border-mitie-lime/50 bg-mitie-lime/10 shadow-[0_16px_42px_rgba(124,179,66,0.12)]"
                      : complete
                        ? "border-emerald-300/20 bg-emerald-400/10"
                        : "border-white/10 bg-[#111a20]"
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-xs font-black uppercase text-slate-500">
                      Step {index + 1}
                    </span>
                    {active ? (
                      <Activity aria-hidden="true" className="h-4 w-4 text-mitie-lime" />
                    ) : complete ? (
                      <CheckCircle2 aria-hidden="true" className="h-4 w-4 text-emerald-200" />
                    ) : (
                      <span className="h-2 w-2 rounded-full bg-slate-600" aria-hidden="true" />
                    )}
                  </div>
                  <p className={`mt-3 text-sm font-semibold leading-6 ${active || complete ? "text-white" : "text-slate-400"}`}>
                    {step}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
        <ResearchSkeletonPreview />
      </div>
    </Panel>
  );
}

function ResearchSkeletonPreview() {
  return (
    <div className="rounded-md border border-white/10 bg-[#111a20] p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-semibold text-white">Intelligence pack forming</p>
        <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin text-cyan-200" />
      </div>
      <div className="mt-4 grid gap-3">
        <SkeletonLine className="h-4 w-3/4 rounded-full" />
        <SkeletonLine className="h-8 w-full rounded-md" />
        <SkeletonLine className="h-8 w-5/6 rounded-md" />
      </div>
      <div className="mt-5 grid gap-3">
        {["Commercial value", "Risk", "Next best action"].map((label) => (
          <div key={label} className="rounded-md border border-white/10 bg-[#0d151a] p-3">
            <p className="text-xs font-black uppercase text-slate-500">{label}</p>
            <SkeletonLine className="mt-3 h-3 w-full rounded-full" />
            <SkeletonLine className="mt-2 h-3 w-2/3 rounded-full" />
          </div>
        ))}
      </div>
    </div>
  );
}

function SkeletonLine({ className }: { className: string }) {
  return <div className={`misi-shimmer bg-white/10 ${className}`} aria-hidden="true" />;
}

function ResearchWorkspaceResult({
  state,
  request,
  result,
  onSave,
  onOpenOpportunity,
}: {
  state: ResearchWorkspaceState["status"];
  request: ResearchWorkspaceRequest;
  result: ResearchOpportunityResponse;
  onSave: () => void;
  onOpenOpportunity: () => void;
}) {
  const [acceptedFieldNames, setAcceptedFieldNames] = useState<Set<string>>(
    () => new Set(),
  );
  const [editingFieldName, setEditingFieldName] = useState<string | null>(null);
  const [fieldOverrides, setFieldOverrides] = useState<Record<string, string>>({});

  useEffect(() => {
    setAcceptedFieldNames(new Set());
    setEditingFieldName(null);
    setFieldOverrides({});
  }, [result]);

  const fields = result.draft_field_intelligence.map((field) => {
    const view = researchFieldToView(field);
    const override = fieldOverrides[view.fieldName];
    if (override === undefined) {
      return view;
    }

    return {
      ...view,
      displayValue: override,
      rawValue: override,
      valueType: "user_provided" as const,
      confidenceScore: 1,
      rationale: "User-edited value in the AI Research Workspace review.",
      recommendedNextStep: "Confirm this edited value against the approved commercial source before bid governance.",
      needsUserConfirmation: false,
    };
  });
  const confidenceSummary = summariseFieldConfidence(fields);
  const saved = state === "saved" && result.opportunity !== null;
  const saving = state === "saving";
  const acceptedCount = acceptedFieldNames.size;
  const keyFields = [
    "estimated_total_contract_value",
    "estimated_annual_revenue",
    "estimated_gross_margin",
    "margin_percentage",
    "probability",
    "strategic_fit_score",
  ];

  return (
    <div className="grid gap-5">
      <Panel
        title="AI-Generated Opportunity Readout"
        action={<StatusPill tone={confidenceTone(result.overall_confidence)} label={`${percentage(result.overall_confidence)} confidence`} />}
      >
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <StatusPill tone={saved ? "green" : "amber"} label={saved ? "Saved to pipeline" : "Preview for review"} />
              <StatusPill tone="cyan" label={`${result.sources.length} sources`} />
              <StatusPill tone={confidenceSummary.unknownCount > 0 ? "amber" : "green"} label={`${confidenceSummary.unknownCount} unknowns`} />
              <StatusPill tone={acceptedCount > 0 ? "green" : "cyan"} label={`${acceptedCount} accepted`} />
            </div>
            <h3 className="mt-4 text-2xl font-semibold leading-9 text-white">
              {result.draft_opportunity.name || "Opportunity title unknown"}
            </h3>
            <p className="mt-2 text-sm font-semibold text-mitie-lime">
              {result.draft_opportunity.buyer_name || "Buyer unknown"} · {result.draft_opportunity.sector || "Sector unknown"} · {result.draft_opportunity.region || "Region unknown"}
            </p>
            <p className="mt-4 text-sm leading-6 text-slate-300">
              {result.draft_enrichment.opportunity_summary || "MiSi did not return an opportunity summary. Confirm the buyer and tender route, then rerun research."}
            </p>
            <NextActionCallout
              label="MiSi recommendation"
              action={result.draft_enrichment.executive_recommendation || "Confirm contract scope, buyer owner and procurement route before leadership review."}
            />
          </div>

          <div className="rounded-md border border-white/10 bg-[#111a20] p-4">
            <div className="mb-5 flex justify-center">
              <ConfidenceOrbit score={result.overall_confidence} label={percentage(result.overall_confidence)} />
            </div>
            <p className="text-xs font-black uppercase text-slate-500">Recommended next action</p>
            <p className="mt-3 text-base font-semibold leading-7 text-white">
              {result.draft_opportunity.recommended_action || "Confirm contract scope and asset schedule."}
            </p>
            <div className="mt-4 flex flex-col gap-2">
              <button
                type="button"
                onClick={onSave}
                disabled={saved || saving}
                data-testid="save-researched-opportunity"
                className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-mitie-lime/30 bg-mitie-lime px-3 py-2 text-sm font-black text-[#07100b] transition hover:bg-[#d8ff62] disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/10 disabled:text-slate-400"
              >
                {saving ? (
                  <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                ) : (
                  <CheckCircle2 aria-hidden="true" className="h-4 w-4" />
                )}
                {saved ? "Saved To Pipeline" : saving ? "Saving To Pipeline" : "Save To Pipeline"}
              </button>
              <button
                type="button"
                onClick={onOpenOpportunity}
                disabled={!saved}
                data-testid="open-intelligence-pack"
                className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-white/10 bg-white/[0.04] px-3 py-2 text-sm font-bold text-slate-200 transition hover:bg-white/[0.08] disabled:cursor-not-allowed disabled:text-slate-500"
              >
                Open Full Opportunity Intelligence Pack
                <ChevronRight aria-hidden="true" className="h-4 w-4" />
              </button>
            </div>
            <p className="mt-3 text-xs leading-5 text-slate-500">
              Review flow: accept strong AI values, edit weak values, then save only when the record is good enough for pipeline review.
            </p>
            <p className="mt-2 text-xs leading-5 text-slate-500">
              Query: {request.query}
            </p>
          </div>
        </div>
      </Panel>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {keyFields.map((fieldName) => (
          <IntelligenceMetric
            key={fieldName}
            field={fieldByName(fields, fieldName)}
            fallbackLabel={fieldName.replaceAll("_", " ")}
          />
        ))}
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
        <Panel
          title="Known, Inferred, Estimated And Unknown Fields"
          action={<StatusPill tone={confidenceTone(confidenceSummary.score)} label={`${percentage(confidenceSummary.score)} average confidence`} />}
        >
          <div className="grid gap-3">
            {fields.map((field) => (
              <ConfidenceFieldCard
                key={field.fieldName}
                field={field}
                accepted={acceptedFieldNames.has(field.fieldName)}
                editing={editingFieldName === field.fieldName}
                onAccept={() => {
                  setAcceptedFieldNames((current) => {
                    const next = new Set(current);
                    next.add(field.fieldName);
                    return next;
                  });
                }}
                onEdit={() => setEditingFieldName(field.fieldName)}
                onCancelEdit={() => setEditingFieldName(null)}
                onSaveEdit={(value) => {
                  setFieldOverrides((current) => ({
                    ...current,
                    [field.fieldName]: value,
                  }));
                  setEditingFieldName(null);
                }}
              />
            ))}
          </div>
        </Panel>

        <div className="grid content-start gap-5">
          <ResearchSourcesPanel sources={result.sources} />
          <ResearchIntelligencePanel result={result} />
        </div>
      </div>
    </div>
  );
}

function ResearchSourcesPanel({ sources }: { sources: ResearchOpportunityResponse["sources"] }) {
  return (
    <Panel title="Evidence Sources" action={<StatusPill tone={sources.length > 0 ? "cyan" : "amber"} label={`${sources.length} sources`} />}>
      {sources.length > 0 ? (
        <div className="grid gap-3">
          {sources.slice(0, 6).map((source, index) => (
            <a
              key={`${source.title}-${source.url}`}
              href={source.url}
              target="_blank"
              rel="noreferrer"
              className="group rounded-md border border-white/10 bg-[#111a20] p-3 text-sm leading-6 text-slate-300 transition hover:border-cyan-300/30 hover:bg-white/[0.05]"
            >
              <span className="text-xs font-black uppercase text-slate-500">Evidence {index + 1}</span>
              <span className="mt-1 block font-semibold text-cyan-100 group-hover:text-white">{source.title || "Untitled source"}</span>
              <span className="mt-1 block text-xs text-slate-500">{source.source_type || "Public source"} · {source.relevance || "Relevance to be confirmed"}</span>
              <span className="mt-2 block truncate text-xs font-semibold text-cyan-200">{source.url}</span>
            </a>
          ))}
        </div>
      ) : (
        <EmptyState
          title="No confirmed source evidence yet"
          message="MiSi can still label useful estimates, but this pack should not be used for bid governance until a tender notice, buyer page, portal result or approved internal source is attached."
        />
      )}
    </Panel>
  );
}

function ResearchIntelligencePanel({ result }: { result: ResearchOpportunityResponse }) {
  const enrichment = result.draft_enrichment;
  const unknowns = enrichment.unknowns.length > 0
    ? enrichment.unknowns
    : ["No critical unknowns were returned, but validate buyer, scope, value and incumbent before bid governance."];
  const nextSteps = enrichment.recommended_next_steps.length > 0
    ? enrichment.recommended_next_steps
    : ["Confirm procurement route, asset schedule, incumbent supplier and decision owner."];

  return (
    <Panel title="Commercial Intelligence Pack" action={<StatusPill tone="green" label="Board-ready shape" />}>
      <div className="grid gap-4">
        <DetailList title="Likely scope" items={enrichment.likely_scope.length > 0 ? enrichment.likely_scope : ["Scope unknown; confirm fire and security disciplines."]} />
        <DetailList title="Buyer drivers" items={enrichment.likely_buyer_drivers.length > 0 ? enrichment.likely_buyer_drivers : ["Buyer drivers unknown; confirm compliance, cost and estate priorities."]} />
        <DetailList title="Unknowns to resolve" items={unknowns} />
        <DetailList title="Next best steps" items={nextSteps} />
        <NextActionCallout
          label="Commercial control"
          action={nextSteps[0] || "Confirm procurement route and source evidence before committing bid resources."}
          tone="cyan"
        />
        <div className="rounded-md border border-white/10 bg-[#111a20] p-4">
          <p className="text-xs font-semibold uppercase text-slate-500">Self-delivery assessment</p>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            {enrichment.self_delivery_assessment || "Self-delivery fit unknown. Confirm disciplines, asset density and local engineering capacity."}
          </p>
        </div>
      </div>
    </Panel>
  );
}

function ExecutiveCommandView({
  data,
  onDataChanged,
  onSelectOpportunity,
}: {
  data: MisiDashboardData;
  onDataChanged: () => void;
  onSelectOpportunity: (opportunity: Opportunity) => void;
}) {
  const [briefingState, setBriefingState] = useState<LeadershipBriefingState>({
    status: "idle",
  });
  const [reportExportState, setReportExportState] = useState<ReportExportState>({
    status: "idle",
  });
  const selfDeliverySummary = useMemo(
    () => buildSelfDeliverySummary(data.opportunities),
    [data.opportunities],
  );

  useEffect(() => {
    return () => {
      if (reportExportState.status === "success") {
        revokeExecutiveReportExportUrls(reportExportState.urls);
      }
    };
  }, [reportExportState]);

  async function handleGenerateBriefing() {
    setBriefingState({ status: "loading" });

    try {
      const briefing = await generateExecutiveSummary();
      setBriefingState({ status: "success", briefing });
    } catch (error: unknown) {
      setBriefingState({
        status: "error",
        message: getExecutiveBriefingErrorMessage(error),
      });
    }
  }

  async function handleExportReport() {
    setReportExportState((current) => {
      if (current.status === "success") {
        revokeExecutiveReportExportUrls(current.urls);
      }

      return { status: "loading" };
    });

    try {
      const report = await fetchExecutiveReport();
      const urls = createExecutiveReportExportUrls(report);
      setReportExportState({ status: "success", report, urls });
    } catch (error: unknown) {
      setReportExportState({
        status: "error",
        message: getReportExportErrorMessage(error),
      });
    }
  }

  return (
    <div className="grid gap-5">
      <KpiCards dashboard={data.dashboard} />
      <LeadershipControlPanel
        data={data}
        selfDeliverySummary={selfDeliverySummary}
      />
      <AutofillMissingIntelligencePanel onDataChanged={onDataChanged} />

      <div className="grid gap-5 2xl:grid-cols-[minmax(0,1fr)_420px]">
        <div className="grid min-w-0 gap-5">
          <ExecutiveSummaryPanel dashboard={data.dashboard} />
          <ExecutiveReportExportPanel
            state={reportExportState}
            onExport={handleExportReport}
          />
          <LeadershipBriefingPanel
            state={briefingState}
            onGenerate={handleGenerateBriefing}
          />

          <Panel
            title="Priority Opportunity Control"
            action={<StatusPill tone="amber" label={`${data.opportunities.length} visible`} />}
          >
            <OpportunityTable
              opportunities={data.opportunities}
              onSelectOpportunity={onSelectOpportunity}
            />
          </Panel>
        </div>

        <div className="grid content-start gap-5">
          <Panel
            title="Pipeline and Margin Shape"
            action={<TrendingUp aria-hidden="true" className="h-5 w-5 text-cyan-200" />}
          >
            <PipelineChart
              revenue={data.dashboard.monthly_revenue_forecast}
              margin={data.dashboard.monthly_margin_forecast}
            />
          </Panel>
          <MarginChart
            dashboard={data.dashboard}
            financeSummary={data.financeSummary}
          />
          <MarketSignalsPanel marketSignals={data.marketSignals.slice(0, 3)} compact />
          <ExecutiveActionsList
            actions={data.dashboard.top_executive_actions}
            title="Leadership Actions"
          />
        </div>
      </div>
    </div>
  );
}

function KpiCards({ dashboard }: { dashboard: DashboardSummary }) {
  const cards = [
    {
      label: "Total live pipeline",
      display: compactCurrency(dashboard.total_pipeline_value),
      detail: `${dashboard.live_opportunity_count} live opportunities`,
      tone: "green" as Tone,
    },
    {
      label: "Weighted live pipeline",
      display: compactCurrency(dashboard.weighted_pipeline_value),
      detail: `${dashboard.strategic_must_win_count} strategic must-wins`,
      tone: "cyan" as Tone,
    },
    {
      label: "Gross margin value",
      display: compactCurrency(dashboard.estimated_gross_margin),
      detail: `${percentageValue(dashboard.average_margin_percentage)} blended margin`,
      tone: "amber" as Tone,
    },
    {
      label: "Leadership risk queue",
      display: String(dashboard.high_risk_count),
      detail: `${dashboard.urgent_deadline_count} urgent deadlines`,
      tone: "red" as Tone,
    },
  ];

  return (
    <section className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-4" aria-label="Executive KPIs">
      {cards.map((metric) => (
        <KpiTile key={metric.label} {...metric} />
      ))}
    </section>
  );
}

function LeadershipControlPanel({
  data,
  selfDeliverySummary,
}: {
  data: MisiDashboardData;
  selfDeliverySummary: SelfDeliverySummary;
}) {
  const topOpportunity = data.dashboard.top_opportunities[0] ?? data.opportunities[0] ?? null;
  const nextAction = data.dashboard.top_executive_actions[0]?.recommended_action;
  const financeReviewCount =
    data.financeSummary.margin_warnings.length + data.financeSummary.finance_review_items.length;
  const openToRiskDelta =
    data.financeSummary.open_weighted_revenue - data.financeSummary.risk_adjusted_revenue;
  const roleActions = [
    {
      role: "MD",
      headline:
        data.dashboard.strategic_must_win_count > 0
          ? `${data.dashboard.strategic_must_win_count} must-win sponsor decision${data.dashboard.strategic_must_win_count === 1 ? "" : "s"}`
          : data.dashboard.live_opportunity_count > 0
            ? "No must-win sponsor gaps"
            : "Awaiting researched pursuits",
      metric: topOpportunity ? compactCurrency(topOpportunity.weighted_pipeline_value) : "Research needed",
      action:
        nextAction ??
        (data.dashboard.live_opportunity_count > 0
          ? "Hold the weekly MD / FD / GSD control point on priority pursuits."
          : "Use AI Opportunity Builder or upload approved source data to create the first intelligence pack."),
      tone: data.dashboard.strategic_must_win_count > 0 ? "green" : "cyan",
    },
    {
      role: "FD",
      headline:
        financeReviewCount > 0
          ? `${financeReviewCount} LE1 review item${financeReviewCount === 1 ? "" : "s"}`
          : "LE1 controls clear",
      metric: compactCurrency(data.financeSummary.risk_adjusted_revenue),
      action:
        openToRiskDelta > 0
          ? `Challenge ${compactCurrency(openToRiskDelta)} removed by risk adjustment before forecast lock.`
          : "Confirm secured and open forecast assumptions remain supportable.",
      tone: financeReviewCount > 0 ? "amber" : "green",
    },
    {
      role: "GSD",
      headline: `${data.dashboard.live_opportunity_count} live pursuits to convert`,
      metric: compactCurrency(data.dashboard.weighted_pipeline_value),
      action:
        topOpportunity?.calculated_recommended_action ??
        "Confirm buyer access and close plans for the highest weighted pursuits.",
      tone: data.dashboard.high_risk_count > 0 ? "amber" : "green",
    },
    {
      role: "Bid",
      headline: `${data.dashboard.live_tender_count} live tender${data.dashboard.live_tender_count === 1 ? "" : "s"}`,
      metric: `${data.dashboard.urgent_deadline_count} urgent`,
      action:
        data.dashboard.urgent_deadline_count > 0
          ? "Escalate deadline ownership and unresolved clarifications today."
          : "Keep pricing, clarification and final review gates visible to leadership.",
      tone: data.dashboard.urgent_deadline_count > 0 ? "red" : "cyan",
    },
    {
      role: "Commercial",
      headline: `${selfDeliverySummary.routeOpportunities.length} self-delivery routes`,
      metric: compactCurrency(selfDeliverySummary.valueAtRisk),
      action:
        selfDeliverySummary.valueAtRisk > 0
          ? "Route strong-fit fire and security scope before third-party leakage is priced in."
          : "Maintain capture discipline on routed fire and security scope.",
      tone: selfDeliverySummary.valueAtRisk > 0 ? "red" : "green",
    },
  ] satisfies Array<{
    role: string;
    headline: string;
    metric: string;
    action: string;
    tone: Tone;
  }>;

  return (
    <Panel title="Leadership Control This Week" action={<StatusPill tone="green" label="Role-led actions" />}>
      <div className="grid gap-3 lg:grid-cols-5">
        {roleActions.map((item) => (
          <article key={item.role} className="rounded-md border border-white/10 bg-[#111a20] p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-xs font-black uppercase text-slate-500">{item.role}</p>
              <StatusPill tone={item.tone} label={item.metric} />
            </div>
            <h3 className="mt-4 text-sm font-semibold leading-6 text-white">{item.headline}</h3>
            <p className="mt-3 text-sm leading-6 text-slate-400">{item.action}</p>
          </article>
        ))}
      </div>
    </Panel>
  );
}

function AutofillMissingIntelligencePanel({
  onDataChanged,
}: {
  onDataChanged: () => void;
}) {
  const [state, setState] = useState<AutofillState>({ status: "idle" });
  const [limit, setLimit] = useState(10);
  const isLoading = state.status === "loading";

  async function handleAutofill() {
    setState({ status: "loading" });

    try {
      const result = await autofillOpportunities({
        only_incomplete: true,
        limit,
      });
      setState({ status: "success", result });
    } catch (error: unknown) {
      setState({
        status: "error",
        message: getAutofillErrorMessage(error),
      });
    }
  }

  const result = state.status === "success" ? state.result : null;
  const warningCount = result?.confidence_warnings.length ?? 0;

  return (
    <Panel
      title="AI Autofill Control"
      action={
        <button
          type="button"
          onClick={handleAutofill}
          disabled={isLoading}
          data-testid="autofill-missing-intelligence-button"
          className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-mitie-lime/30 bg-mitie-lime px-3 py-2 text-sm font-bold text-[#07100b] transition hover:bg-[#d8ff62] disabled:cursor-wait disabled:border-white/10 disabled:bg-white/10 disabled:text-slate-400"
        >
          {isLoading ? (
            <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw aria-hidden="true" className="h-4 w-4" />
          )}
          {isLoading ? "Autofilling Intelligence" : "Autofill missing intelligence"}
        </button>
      }
    >
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="rounded-md border border-cyan-300/20 bg-cyan-400/10 p-4">
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill tone="cyan" label="AI-first records" />
            <StatusPill tone="green" label="User values protected" />
            <StatusPill tone="amber" label="Confidence labelled" />
          </div>
          <h3 className="mt-4 text-lg font-semibold leading-7 text-white">
            Fill weak records without pretending the data is perfect.
          </h3>
          <p className="mt-2 text-sm leading-6 text-cyan-100/75">
            MiSi scans incomplete opportunities, researches available public evidence, fills missing commercial fields, and stores field-level rationale. Existing non-empty values are preserved unless a future run explicitly allows overwrite.
          </p>
        </div>

        <div className="grid content-start gap-3">
          <label className="grid gap-1.5">
            <span className="text-xs font-semibold text-slate-500">Batch limit</span>
            <input
              value={limit}
              onChange={(event) => {
                const nextValue = Number(event.target.value);
                setLimit(Number.isFinite(nextValue) ? Math.max(1, Math.min(nextValue, 50)) : 10);
              }}
              min={1}
              max={50}
              type="number"
              className="h-10 rounded-md border border-white/10 bg-[#111a20] px-3 text-sm font-semibold text-white"
            />
          </label>
          <MetricLine
            label="Mode"
            value="Incomplete only"
            detail="Blank, zero, unknown or review-required fields are targeted first"
          />
        </div>
      </div>

      {state.status === "loading" ? (
        <div className="mt-4 rounded-md border border-mitie-lime/20 bg-mitie-lime/10 p-4">
          <div className="flex items-center gap-3 text-sm font-semibold text-mitie-lime">
            <Loader2 aria-hidden="true" className="h-5 w-5 animate-spin" />
            Researching and labelling missing intelligence...
          </div>
          <p className="mt-2 text-sm leading-6 text-mitie-lime/80">
            MiSi is enriching records one by one. A failed record will be reported in the batch summary without stopping the rest of the run.
          </p>
        </div>
      ) : null}

      {state.status === "error" ? (
        <div
          className="mt-4 rounded-md border border-amber-300/20 bg-amber-400/10 p-4"
          role="alert"
        >
          <div className="flex gap-3">
            <AlertTriangle aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0 text-amber-200" />
            <div>
              <p className="text-sm font-semibold text-amber-100">Autofill was not completed</p>
              <p className="mt-2 text-sm leading-6 text-amber-100/80">{state.message}</p>
            </div>
          </div>
        </div>
      ) : null}

      {result ? (
        <div className="mt-4 grid gap-4">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <AutofillSummaryMetric
              label="Records scanned"
              value={String(result.records_scanned)}
              detail={`${result.records_skipped} already complete or protected`}
            />
            <AutofillSummaryMetric
              label="Records enriched"
              value={String(result.records_enriched)}
              detail={`${result.records_failed} failed without stopping batch`}
            />
            <AutofillSummaryMetric
              label="Fields filled"
              value={String(result.fields_filled)}
              detail="Known, inferred, estimated or calculated"
            />
            <AutofillSummaryMetric
              label="Still unknown"
              value={String(result.fields_still_unknown)}
              detail="Now labelled with next checks"
            />
            <AutofillSummaryMetric
              label="Warnings"
              value={String(warningCount)}
              detail="Confidence or confirmation items"
            />
          </div>

          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
            <div className="rounded-md border border-white/10 bg-[#111a20] p-4">
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-sm font-semibold text-white">Batch outcome</h3>
                <StatusPill
                  tone={result.records_failed > 0 ? "amber" : "green"}
                  label={result.records_failed > 0 ? "Partial success" : "Completed"}
                />
              </div>
              <div className="mt-4 grid gap-3">
                {result.results.length > 0 ? (
                  result.results.slice(0, 5).map((item) => (
                    <div
                      key={`${item.opportunity_id}-${item.enrichment_run_id ?? item.status}`}
                      className="rounded-md border border-white/10 bg-[#0d151a] p-3"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-sm font-semibold text-white">{item.opportunity_name}</p>
                        <StatusPill tone={autofillResultTone(item.status)} label={item.status} />
                      </div>
                      <p className="mt-2 text-xs leading-5 text-slate-400">
                        {item.fields_filled} filled · {item.fields_preserved} protected · {item.fields_still_unknown} still unknown
                      </p>
                      {item.error_message ? (
                        <p className="mt-2 text-xs leading-5 text-amber-100/80">{item.error_message}</p>
                      ) : null}
                    </div>
                  ))
                ) : (
                  <p className="text-sm leading-6 text-slate-400">
                    No incomplete opportunities were selected for enrichment. New research records will appear here after a batch run.
                  </p>
                )}
              </div>
            </div>

            <div className="grid content-start gap-3">
              <div className="rounded-md border border-amber-300/20 bg-amber-400/10 p-4">
                <p className="text-sm font-semibold text-amber-100">Confidence warnings</p>
                <div className="mt-3 grid gap-2">
                  {result.confidence_warnings.length > 0 ? (
                    result.confidence_warnings.slice(0, 4).map((warning) => (
                      <p key={warning} className="text-sm leading-6 text-amber-100/80">
                        {warning}
                      </p>
                    ))
                  ) : (
                    <p className="text-sm leading-6 text-amber-100/80">
                      No low-confidence field fills were reported. Continue to validate estimates before bid or forecast commitment.
                    </p>
                  )}
                </div>
              </div>
              <button
                type="button"
                onClick={onDataChanged}
                className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-white/10 bg-white/[0.04] px-3 py-2 text-sm font-bold text-slate-200 transition hover:bg-white/[0.08]"
              >
                <RefreshCw aria-hidden="true" className="h-4 w-4" />
                Refresh dashboard data
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </Panel>
  );
}

function ExecutiveSummaryPanel({ dashboard }: { dashboard: DashboardSummary }) {
  const summaryParts = splitSummary(dashboard.executive_summary_text);
  const moduleHealth = [
    {
      label: "Open opportunities",
      value: String(dashboard.live_opportunity_count),
      detail: "Live commercial pursuits in the API dataset",
    },
    {
      label: "Market signals",
      value: String(dashboard.market_signal_count),
      detail: "Public tender and watchlist indicators",
    },
    {
      label: "Strategic must-wins",
      value: String(dashboard.strategic_must_win_count),
      detail: "High-value pursuits above sponsor threshold",
    },
    {
      label: "Live tenders",
      value: String(dashboard.live_tender_count),
      detail: "PQQ, ITT, pricing, review or negotiation stages",
    },
  ];

  return (
    <Panel
      title="Executive Command Summary"
      action={<StatusPill tone="green" label="Live API" />}
    >
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_260px]">
        <div>
          <h2 className="text-xl font-semibold leading-8 text-white">
            {summaryParts[0]}
          </h2>
          <div className="mt-5 grid gap-3">
            {summaryParts.slice(1).map((point) => (
              <div key={point} className="flex gap-3 text-sm leading-6 text-slate-300">
                <CheckCircle2 aria-hidden="true" className="mt-1 h-4 w-4 shrink-0 text-mitie-lime" />
                <p>{point}</p>
              </div>
            ))}
          </div>
        </div>
        <div className="grid content-start gap-3">
          {moduleHealth.map((item) => (
            <MetricLine key={item.label} {...item} />
          ))}
        </div>
      </div>
    </Panel>
  );
}

function ExecutiveReportExportPanel({
  state,
  onExport,
}: {
  state: ReportExportState;
  onExport: () => void;
}) {
  const isLoading = state.status === "loading";

  return (
    <Panel
      title="Executive Report Export"
      action={
        <button
          type="button"
          onClick={onExport}
          disabled={isLoading}
          data-testid="export-executive-report-button"
          className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-white/10 bg-white px-3 py-2 text-sm font-bold text-[#10171b] transition hover:bg-slate-200 disabled:cursor-wait disabled:border-white/10 disabled:bg-white/10 disabled:text-slate-400"
        >
          {isLoading ? (
            <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
          ) : (
            <Download aria-hidden="true" className="h-4 w-4" />
          )}
          {isLoading ? "Exporting Report" : "Export Executive Report"}
        </button>
      }
    >
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
        <div className="rounded-md border border-white/10 bg-[#111a20] p-4">
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill tone="green" label="MD / FD / GSD" />
            <StatusPill tone="cyan" label="Report-ready JSON" />
            <StatusPill tone="amber" label="Printable HTML" />
          </div>
          <h3 className="mt-4 text-lg font-semibold leading-7 text-white">
            Board pack snapshot for commercial review
          </h3>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            Pulls live dashboard KPIs, leadership summary, top opportunities, LE1 finance, self-delivery, executive actions, risks and recommendations from the backend report endpoint.
          </p>
        </div>

        <div className="grid content-start gap-3">
          <MetricLine
            label="Report source"
            value="/api/reports/executive-summary"
            detail="Backend generated; no OpenAI key is exposed to the browser"
          />
          {state.status === "success" ? (
            <MetricLine
              label="Last export"
              value={shortDate(state.report.reporting_date)}
              detail={
                state.urls
                  ? "JSON download and printable report view are ready"
                  : "Report generated; export links are unavailable in this browser"
              }
            />
          ) : (
            <MetricLine
              label="Export format"
              value="JSON + HTML"
              detail="MVP report output for review and browser printing"
            />
          )}
        </div>
      </div>

      {state.status === "error" ? (
        <div
          className="mt-4 rounded-md border border-amber-300/20 bg-amber-400/10 p-4"
          role="alert"
        >
          <div className="flex gap-3">
            <AlertTriangle aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0 text-amber-200" />
            <div>
              <p className="text-sm font-semibold text-amber-100">Executive report was not exported</p>
              <p className="mt-2 text-sm leading-6 text-amber-100/80">{state.message}</p>
            </div>
          </div>
        </div>
      ) : null}

      {state.status === "success" ? (
        <div className="mt-4 rounded-md border border-emerald-300/20 bg-emerald-400/10 p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-semibold text-emerald-100">Executive report exported</p>
              <p className="mt-2 text-sm leading-6 text-emerald-100/80">
                {state.report.report_name} is ready for MD, FD and Group Sales Director review.
              </p>
            </div>
            {state.urls ? (
              <div className="flex flex-wrap items-center gap-2">
                <a
                  href={state.urls.jsonUrl}
                  download={state.urls.filename}
                  className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-emerald-200/30 bg-emerald-100 px-3 py-2 text-sm font-bold text-[#0b2f24] transition hover:bg-white"
                >
                  <Download aria-hidden="true" className="h-4 w-4" />
                  Download JSON
                </a>
                <a
                  href={state.urls.htmlUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-emerald-200/30 bg-[#0b2f24] px-3 py-2 text-sm font-bold text-emerald-50 transition hover:bg-[#134734]"
                >
                  <Printer aria-hidden="true" className="h-4 w-4" />
                  Open Printable Report
                </a>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
    </Panel>
  );
}

function LeadershipBriefingPanel({
  state,
  onGenerate,
}: {
  state: LeadershipBriefingState;
  onGenerate: () => void;
}) {
  const isLoading = state.status === "loading";

  return (
    <Panel
      title="Leadership Briefing"
      action={
        <button
          type="button"
          onClick={onGenerate}
          disabled={isLoading}
          data-testid="generate-leadership-briefing-button"
          className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-mitie-lime/30 bg-mitie-lime px-3 py-2 text-sm font-bold text-[#07100b] transition hover:bg-[#d8ff62] disabled:cursor-wait disabled:border-white/10 disabled:bg-white/10 disabled:text-slate-400"
        >
          {isLoading ? (
            <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw aria-hidden="true" className="h-4 w-4" />
          )}
          {isLoading ? "Generating Briefing" : "Generate Leadership Briefing"}
        </button>
      }
    >
      <div className="grid gap-4">
        {state.status === "idle" ? (
          <div className="rounded-md border border-cyan-300/20 bg-cyan-400/10 p-4">
            <p className="text-sm font-semibold text-cyan-100">Board-ready AI briefing</p>
            <p className="mt-2 text-sm leading-6 text-cyan-100/75">
              Generate a concise leadership view of pipeline position, weighted value, margin, urgent deadlines, must-wins, red risks, finance attention and this week&apos;s actions.
            </p>
          </div>
        ) : null}

        {state.status === "loading" ? (
          <div className="rounded-md border border-cyan-300/20 bg-cyan-400/10 p-4">
            <div className="flex items-center gap-3 text-sm font-semibold text-cyan-100">
              <Loader2 aria-hidden="true" className="h-5 w-5 animate-spin" />
              Building leadership briefing...
            </div>
            <p className="mt-2 text-sm leading-6 text-cyan-100/75">
              MiSi is asking the backend to convert the live dashboard into MD, FD, Sales and Bid Team action lanes.
            </p>
          </div>
        ) : null}

        {state.status === "error" ? (
          <div
            className="rounded-md border border-amber-300/20 bg-amber-400/10 p-4"
            role="alert"
          >
            <div className="flex gap-3">
              <AlertTriangle aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0 text-amber-200" />
              <div>
                <p className="text-sm font-semibold text-amber-100">Leadership briefing was not generated</p>
                <p className="mt-2 text-sm leading-6 text-amber-100/80">{state.message}</p>
              </div>
            </div>
          </div>
        ) : null}

        {state.status === "success" ? (
          <LeadershipBriefingResult briefing={state.briefing} />
        ) : null}
      </div>
    </Panel>
  );
}

function LeadershipBriefingResult({
  briefing,
}: {
  briefing: ExecutiveLeadershipBriefing;
}) {
  return (
    <div className="grid gap-4">
      <section className="rounded-md border border-white/10 bg-[#111a20] p-4">
        <div className="flex flex-wrap items-center gap-2">
          <StatusPill tone="green" label="Board-ready" />
          <StatusPill tone="cyan" label="Backend generated" />
        </div>
        <h3 className="mt-4 text-xl font-semibold leading-8 text-white">
          {briefing.headline}
        </h3>
        <p className="mt-3 text-sm leading-6 text-slate-300">{briefing.summary}</p>
      </section>

      <div className="grid gap-4 xl:grid-cols-2">
        <BriefingLane title="MD Attention" tone="green" items={briefing.md_attention} />
        <BriefingLane title="Finance Attention" tone="amber" items={briefing.finance_attention} />
        <BriefingLane title="Sales Attention" tone="cyan" items={briefing.sales_attention} />
        <BriefingLane title="Bid Team Attention" tone="cyan" items={briefing.bid_team_attention} />
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
        <BriefingLane title="Risk Warnings" tone="red" items={briefing.risk_warnings} />
        <BriefingLane title="Next Best Actions" tone="green" items={briefing.next_best_actions} />
      </div>
    </div>
  );
}

function BriefingLane({
  title,
  tone,
  items,
}: {
  title: string;
  tone: Tone;
  items: string[];
}) {
  const Icon = tone === "red" ? AlertTriangle : CheckCircle2;

  return (
    <section className="rounded-md border border-white/10 bg-[#111a20] p-4">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-white">{title}</h3>
        <StatusPill tone={tone} label={`${items.length} item${items.length === 1 ? "" : "s"}`} />
      </div>
      {items.length > 0 ? (
        <ul className="mt-3 grid gap-2">
          {items.map((item) => (
            <li key={item} className="flex gap-2 text-sm leading-6 text-slate-300">
              <Icon
                aria-hidden="true"
                className={`mt-1 h-4 w-4 shrink-0 ${tone === "red" ? "text-red-200" : "text-mitie-lime"}`}
              />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-sm leading-6 text-slate-500">No immediate attention items returned.</p>
      )}
    </section>
  );
}

function MarketRadarView({
  marketSignals,
  onDataChanged,
  onSelectOpportunity,
}: {
  marketSignals: MarketSignal[];
  onDataChanged: () => void;
  onSelectOpportunity: (opportunity: Opportunity) => void;
}) {
  const [researchType, setResearchType] = useState<InternetIntelligenceType>("market_radar");
  const [query, setQuery] = useState(
    "UK fire and security tender opportunities, competitor movement and buyer compliance signals",
  );
  const [researchState, setResearchState] = useState<InternetResearchState>({
    status: "idle",
  });
  const [opportunityResearchState, setOpportunityResearchState] = useState<OpportunityResearchState>({
    status: "idle",
  });
  const [conversionStates, setConversionStates] = useState<Record<number, MarketSignalConversionState>>({});
  const [opportunityResearchQuery, setOpportunityResearchQuery] = useState(
    "University of Leeds fire and security tender",
  );
  const isResearchLoading = researchState.status === "loading";
  const isOpportunityResearchLoading = opportunityResearchState.status === "loading";

  async function handleRunResearch() {
    const trimmedQuery = query.trim();
    if (trimmedQuery.length < 8 || isResearchLoading) {
      return;
    }

    setResearchState({ status: "loading" });
    const request: InternetIntelligenceRequest = {
      intelligence_type: researchType,
      query: trimmedQuery,
    };

    try {
      const result = await runInternetResearch(request);
      setResearchState({ status: "success", result });
    } catch (error: unknown) {
      setResearchState({
        status: "error",
        message: getInternetResearchErrorMessage(error),
      });
    }
  }

  async function handleResearchOpportunity() {
    const trimmedQuery = opportunityResearchQuery.trim();
    if (trimmedQuery.length < 4 || isOpportunityResearchLoading) {
      return;
    }

    setOpportunityResearchState({ status: "loading" });

    try {
      const result = await researchOpportunity({
        query: trimmedQuery,
        create_opportunity: true,
      });
      setOpportunityResearchState({ status: "success", result });
      onDataChanged();
    } catch (error: unknown) {
      setOpportunityResearchState({
        status: "error",
        message: getOpportunityResearchErrorMessage(error),
      });
    }
  }

  async function handleConvertSignal(signal: MarketSignal) {
    const currentState = conversionStates[signal.id];
    if (currentState?.status === "loading") {
      return;
    }

    setConversionStates((current) => ({
      ...current,
      [signal.id]: { status: "loading" },
    }));

    try {
      const result = await convertMarketSignal(signal.id);
      setConversionStates((current) => ({
        ...current,
        [signal.id]: { status: "success", result },
      }));
      onDataChanged();
    } catch (error: unknown) {
      setConversionStates((current) => ({
        ...current,
        [signal.id]: {
          status: "error",
          message: getMarketSignalConversionErrorMessage(error),
        },
      }));
    }
  }

  return (
    <div className="grid gap-5">
      <Panel
        title="AI Opportunity Builder"
        action={<StatusPill tone="green" label="Standing-start research" />}
      >
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
          <div className="grid gap-3">
            <label className="grid gap-1.5">
              <span className="text-xs font-semibold text-slate-500">Start with a rough phrase</span>
              <input
                value={opportunityResearchQuery}
                onChange={(event) => setOpportunityResearchQuery(event.target.value)}
                className="h-11 rounded-md border border-white/10 bg-[#111a20] px-3 text-sm text-white placeholder:text-slate-500"
                placeholder="Example: West Yorkshire Police estate maintenance"
              />
            </label>
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={handleResearchOpportunity}
                disabled={opportunityResearchQuery.trim().length < 4 || isOpportunityResearchLoading}
                data-testid="research-opportunity-button"
                className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-mitie-lime/30 bg-mitie-lime px-3 py-2 text-sm font-bold text-[#07100b] transition hover:bg-[#d8ff62] disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/10 disabled:text-slate-400"
              >
                {isOpportunityResearchLoading ? (
                  <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                ) : (
                  <Radar aria-hidden="true" className="h-4 w-4" />
                )}
                {isOpportunityResearchLoading ? "Building Intelligence Pack" : "Research And Create Opportunity"}
              </button>
              <StatusPill tone="cyan" label="Creates labelled field intelligence" />
            </div>
          </div>
          <div className="rounded-md border border-white/10 bg-[#111a20] p-4">
            <p className="text-sm font-semibold text-white">What MiSi will do</p>
            <p className="mt-2 text-sm leading-6 text-slate-400">
              Research public sources, infer missing context, estimate commercial values with rationale, mark unknowns with next steps, then refresh the dashboard.
            </p>
          </div>
        </div>
        <OpportunityResearchResultPanel state={opportunityResearchState} />
      </Panel>

      <Panel
        title="Internet Intelligence Scan"
        action={<StatusPill tone="cyan" label="OpenAI web search" />}
      >
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_300px]">
          <div className="grid gap-3">
            <label className="grid gap-1.5">
              <span className="text-xs font-semibold text-slate-500">Research brief</span>
              <textarea
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                rows={4}
                className="min-h-28 rounded-md border border-white/10 bg-[#111a20] px-3 py-3 text-sm leading-6 text-white placeholder:text-slate-500"
                placeholder="Example: UK fire alarm framework opportunities in local authority estates, incumbent competitors and buyer compliance drivers"
              />
            </label>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
              <label className="grid flex-1 gap-1.5">
                <span className="text-xs font-semibold text-slate-500">Intelligence lane</span>
                <select
                  value={researchType}
                  onChange={(event) =>
                    setResearchType(event.target.value as InternetIntelligenceType)
                  }
                  className="h-10 rounded-md border border-white/10 bg-[#111a20] px-3 text-sm font-semibold text-white"
                >
                  {internetIntelligenceTypes.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                onClick={handleRunResearch}
                disabled={query.trim().length < 8 || isResearchLoading}
                className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-mitie-lime/30 bg-mitie-lime px-3 py-2 text-sm font-bold text-[#07100b] transition hover:bg-[#d8ff62] disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/10 disabled:text-slate-400"
              >
                {isResearchLoading ? (
                  <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                ) : (
                  <Globe2 aria-hidden="true" className="h-4 w-4" />
                )}
                {isResearchLoading ? "Scanning The Web" : "Run Internet Scan"}
              </button>
            </div>
          </div>
          <div className="rounded-md border border-white/10 bg-[#111a20] p-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-white">
              <ShieldAlert aria-hidden="true" className="h-4 w-4 text-amber-200" />
              Research boundary
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-400">
              MiSi uses backend-only OpenAI web search for public internet research. It does not scrape private systems, bypass site terms or expose API keys to the browser.
            </p>
          </div>
        </div>
        <InternetResearchResultPanel state={researchState} />
      </Panel>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
        <Panel
          title="Market Radar"
          action={<StatusPill tone="cyan" label={`${marketSignals.length} signals`} />}
        >
          {marketSignals.length > 0 ? (
            <div className="grid gap-4 xl:grid-cols-2 2xl:grid-cols-3">
              {marketSignals.map((signal) => (
                <MarketSignalCard
                  key={signal.id}
                  signal={signal}
                  conversionState={conversionStates[signal.id] ?? { status: "idle" }}
                  onConvert={() => handleConvertSignal(signal)}
                  onOpenOpportunity={(opportunity) => onSelectOpportunity(opportunity)}
                />
              ))}
            </div>
          ) : (
            <EmptyState
              title="Awaiting source-attributed signals"
              message="MiSi has not researched this market area yet. Start with a buyer, sector or tender phrase and MiSi will build source-attributed signals with fit, disciplines, rationale and next action."
            />
          )}
        </Panel>
        <Panel title="Source Coverage" action={<Compass aria-hidden="true" className="h-5 w-5 text-mitie-lime" />}>
          <div className="grid gap-4">
            <SourceRow label="Find a Tender" value="Connector framework only until a live approved feed is wired" tone="amber" />
            <SourceRow label="Contracts Finder" value="Connector framework only until a live approved feed is wired" tone="amber" />
            <SourceRow label="Manual upload" value="Use source-attributed internal tracker data" tone="cyan" />
            <SourceRow label="Buyer watchlist" value="No aggressive scraping" tone="amber" />
          </div>
        </Panel>
      </div>
    </div>
  );
}

function InternetResearchResultPanel({ state }: { state: InternetResearchState }) {
  if (state.status === "idle") {
    return (
      <div className="mt-4 rounded-md border border-cyan-300/20 bg-cyan-400/10 p-4">
        <p className="text-sm font-semibold text-cyan-100">Search public internet intelligence</p>
        <p className="mt-2 text-sm leading-6 text-cyan-100/75">
          Use this to research public tender signals, buyer priorities, competitor movements, self-delivery opportunities and market context. Results are source-attributed research for review, not imported pipeline truth.
        </p>
      </div>
    );
  }

  if (state.status === "loading") {
    return (
      <div className="mt-4 rounded-md border border-cyan-300/20 bg-cyan-400/10 p-4">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-3 text-sm font-semibold text-cyan-100">
              <Loader2 aria-hidden="true" className="h-5 w-5 animate-spin" />
              Searching public internet sources...
            </div>
            <p className="mt-2 text-sm leading-6 text-cyan-100/75">
              MiSi is gathering source-attributed findings, checking evidence strength and translating them into commercial next actions.
            </p>
          </div>
          <ConfidenceOrbit score={0.54} label="Live" />
        </div>
        <div className="mt-4 grid gap-2">
          <SkeletonLine className="h-3 w-full rounded-full" />
          <SkeletonLine className="h-3 w-5/6 rounded-full" />
          <SkeletonLine className="h-3 w-2/3 rounded-full" />
        </div>
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div className="mt-4 rounded-md border border-amber-300/20 bg-amber-400/10 p-4" role="alert">
        <div className="flex gap-3">
          <AlertTriangle aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0 text-amber-200" />
          <div>
            <p className="text-sm font-semibold text-amber-100">Internet intelligence scan was not completed</p>
            <p className="mt-2 text-sm leading-6 text-amber-100/80">{state.message}</p>
          </div>
        </div>
      </div>
    );
  }

  const result = state.result;

  return (
    <div className="mt-4 grid gap-4">
      <section className="rounded-md border border-white/10 bg-[#111a20] p-4">
        <div className="flex flex-wrap items-center gap-2">
          <StatusPill tone="green" label={internetTypeLabel(result.intelligence_type)} />
          <StatusPill tone="cyan" label={`${result.findings.length} findings`} />
          <StatusPill tone="amber" label={`${result.source_urls.length} sources`} />
        </div>
        <h3 className="mt-4 text-xl font-semibold leading-8 text-white">{result.headline}</h3>
        <p className="mt-3 text-sm leading-6 text-slate-300">{result.summary}</p>
      </section>

      {result.findings.length > 0 ? (
        <div className="grid gap-4 xl:grid-cols-2">
          {result.findings.map((finding) => (
            <article key={`${finding.title}-${finding.recommended_action}`} className="rounded-md border border-white/10 bg-[#111a20] p-4">
              <div className="flex items-start justify-between gap-3">
                <h4 className="text-sm font-semibold leading-6 text-white">{finding.title}</h4>
                <StatusPill tone={confidenceTone(finding.confidence_score)} label={percentage(finding.confidence_score)} />
              </div>
              <p className="mt-3 text-sm leading-6 text-slate-300">{finding.finding}</p>
              <p className="mt-3 text-sm leading-6 text-cyan-100">{finding.so_what}</p>
              <p className="mt-3 border-t border-white/10 pt-3 text-sm font-semibold leading-6 text-mitie-lime">{finding.recommended_action}</p>
              {finding.source_urls.length > 0 ? (
                <div className="mt-3 grid gap-1">
                  {finding.source_urls.slice(0, 3).map((url) => (
                    <a key={url} href={url} target="_blank" rel="noreferrer" className="truncate text-xs font-semibold text-cyan-200 hover:text-white">
                      {url}
                    </a>
                  ))}
                </div>
              ) : null}
            </article>
          ))}
        </div>
      ) : (
        <EmptyState
          title="No strong public findings yet"
          message="MiSi did not find enough source-backed evidence for a useful finding. Try a more specific buyer, sector, region, discipline or tender phrase so weak signals can be labelled rather than hidden."
        />
      )}

      <div className="grid gap-4 xl:grid-cols-3">
        <BriefingLane title="Risk Warnings" tone="red" items={result.risk_warnings} />
        <BriefingLane title="Next Best Actions" tone="green" items={result.next_best_actions} />
        <BriefingLane title="Limitations" tone="amber" items={result.limitations} />
      </div>
    </div>
  );
}

function OpportunityResearchResultPanel({ state }: { state: OpportunityResearchState }) {
  if (state.status === "idle") {
    return (
      <div className="mt-4 rounded-md border border-emerald-300/20 bg-emerald-400/10 p-4">
        <p className="text-sm font-semibold text-emerald-100">AI-first opportunity creation</p>
        <p className="mt-2 text-sm leading-6 text-emerald-100/75">
          Start from an imperfect phrase. MiSi will research, infer, estimate, mark unknowns and create a reviewed commercial record with evidence.
        </p>
      </div>
    );
  }

  if (state.status === "loading") {
    return (
      <div className="mt-4 rounded-md border border-cyan-300/20 bg-cyan-400/10 p-4">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-3 text-sm font-semibold text-cyan-100">
              <Loader2 aria-hidden="true" className="h-5 w-5 animate-spin" />
              Researching and enriching opportunity...
            </div>
            <p className="mt-2 text-sm leading-6 text-cyan-100/75">
              MiSi is searching public sources, creating field-level confidence labels and preparing a dashboard-ready record.
            </p>
          </div>
          <ConfidenceOrbit score={0.68} label="AI" />
        </div>
        <div className="mt-4 grid gap-2">
          <SkeletonLine className="h-3 w-full rounded-full" />
          <SkeletonLine className="h-3 w-4/5 rounded-full" />
          <SkeletonLine className="h-3 w-3/5 rounded-full" />
        </div>
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div className="mt-4 rounded-md border border-amber-300/20 bg-amber-400/10 p-4" role="alert">
        <div className="flex gap-3">
          <AlertTriangle aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0 text-amber-200" />
          <div>
            <p className="text-sm font-semibold text-amber-100">Opportunity research was not completed</p>
            <p className="mt-2 text-sm leading-6 text-amber-100/80">{state.message}</p>
          </div>
        </div>
      </div>
    );
  }

  const result = state.result;
  const fields = result.draft_field_intelligence.map(researchFieldToView);
  const unknownCount = fields.filter((field) => field.valueType === "unknown").length;

  return (
    <div className="mt-4 grid gap-4">
      <section className="rounded-md border border-white/10 bg-[#111a20] p-4">
        <div className="flex flex-wrap items-center gap-2">
          <StatusPill tone="green" label={result.created_opportunity ? "Opportunity created" : "Preview only"} />
          <StatusPill tone={confidenceTone(result.overall_confidence)} label={`${percentage(result.overall_confidence)} confidence`} />
          <StatusPill tone={unknownCount > 0 ? "amber" : "green"} label={`${unknownCount} unknowns`} />
        </div>
        <h3 className="mt-4 text-xl font-semibold leading-8 text-white">
          {result.draft_opportunity.name || "AI researched opportunity"}
        </h3>
        <p className="mt-3 text-sm leading-6 text-slate-300">
          {result.draft_enrichment.opportunity_summary}
        </p>
        <p className="mt-3 text-sm font-semibold leading-6 text-mitie-lime">
          {result.draft_enrichment.executive_recommendation}
        </p>
      </section>

      <div className="grid gap-3 lg:grid-cols-3">
        {fields.slice(0, 6).map((field) => (
          <IntelligenceMetric
            key={field.fieldName}
            field={field}
            fallbackLabel={field.label}
          />
        ))}
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <BriefingLane
          title="Recommended Next Steps"
          tone="green"
          items={result.draft_enrichment.recommended_next_steps}
        />
        <section className="rounded-md border border-white/10 bg-[#111a20] p-4">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold text-white">Evidence Sources</h3>
            <StatusPill tone="cyan" label={`${result.sources.length} sources`} />
          </div>
          {result.sources.length > 0 ? (
            <div className="mt-3 grid gap-2">
              {result.sources.slice(0, 5).map((source) => (
                <a
                  key={source.url}
                  href={source.url}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-md border border-white/10 bg-[#0d151a] p-3 text-xs leading-5 text-slate-300 transition hover:bg-white/[0.04]"
                >
                  <span className="block font-semibold text-cyan-100">{source.title}</span>
                  <span className="mt-1 block text-slate-500">{source.source_type} · {source.relevance}</span>
                </a>
              ))}
            </div>
          ) : (
            <p className="mt-3 text-sm leading-6 text-slate-500">
              No source URLs were returned. Treat the pack as unverified until evidence is attached.
            </p>
          )}
        </section>
      </div>
    </div>
  );
}

function MarketSignalCard({
  signal,
  conversionState,
  onConvert,
  onOpenOpportunity,
}: {
  signal: MarketSignal;
  conversionState: MarketSignalConversionState;
  onConvert: () => void;
  onOpenOpportunity: (opportunity: Opportunity) => void;
}) {
  const isConverting = conversionState.status === "loading";
  const fitTone = fitToneForSignal(signal.likely_mitie_fit);
  const disciplines =
    signal.potential_disciplines.length > 0
      ? signal.potential_disciplines
      : ["Discipline unknown - confirm source scope"];
  const sourceLabel = signal.source_attribution || signal.source_type || "Source attribution required";

  return (
    <article className="rounded-md border border-white/10 bg-[#111a20] p-4 shadow-[0_18px_50px_rgba(0,0,0,0.2)]">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-white">{signal.buyer_name}</p>
          <p className="mt-1 text-xs text-slate-500">{signal.sector} · {signal.region}</p>
        </div>
        <StatusPill
          tone={confidenceTone(signal.confidence_score)}
          label={`${Math.round(signal.confidence_score * 100)}% confidence`}
        />
      </div>

      <h3 className="mt-4 text-base font-semibold leading-6 text-slate-100">{signal.title}</h3>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <DetailField label="Source" value={sourceLabel} />
        <DetailField label="Expected tender" value={signal.expected_tender_date ? shortDate(signal.expected_tender_date) : "Unknown - monitor source"} />
        <DetailField label="Estimated value" value={signal.estimated_value == null ? "Unknown - value not evidenced" : compactCurrency(signal.estimated_value)} />
        <DetailField label="Likely Mitie fit" value={signal.likely_mitie_fit || "Unknown - needs qualification"} />
      </div>

      <div className="mt-4 rounded-md border border-cyan-300/20 bg-cyan-400/10 p-3">
        <div className="flex flex-wrap items-center gap-2">
          <StatusPill tone={fitTone} label={`${signal.likely_mitie_fit || "Unknown"} fit`} />
          <StatusPill tone="cyan" label={`${disciplines.length} discipline${disciplines.length === 1 ? "" : "s"}`} />
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {disciplines.map((discipline) => (
            <span
              key={discipline}
              className="rounded-md border border-white/10 bg-white/[0.04] px-2.5 py-1 text-xs font-semibold text-slate-300"
            >
              {discipline}
            </span>
          ))}
        </div>
        <p className="mt-3 text-xs font-black uppercase text-cyan-100/70">AI rationale</p>
        <p className="mt-3 text-sm leading-6 text-cyan-100/80">
          {signal.ai_rationale || "MiSi has not yet attached rationale. Convert this signal to create field-level intelligence and an opportunity pack."}
        </p>
      </div>

      <div className="mt-4 rounded-md border border-white/10 bg-[#0d151a] p-3">
        <p className="text-xs font-black uppercase text-slate-500">Suggested action</p>
        <p className="mt-2 text-sm font-semibold leading-6 text-white">
          {signal.suggested_action || "Review source and qualify relevance."}
        </p>
      </div>

      {signal.source_url ? (
        <a
          href={signal.source_url}
          target="_blank"
          rel="noreferrer"
          className="mt-3 block truncate text-xs font-semibold text-cyan-200 hover:text-white"
        >
          {signal.source_url}
        </a>
      ) : (
        <p className="mt-3 text-xs leading-5 text-slate-500">
          Unknown source URL - attach source evidence before bid governance.
        </p>
      )}

      <div className="mt-4 border-t border-white/10 pt-4">
        <button
          type="button"
          onClick={onConvert}
          disabled={isConverting}
          data-testid={`convert-market-signal-${signal.id}`}
          className="inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-md border border-mitie-lime/30 bg-mitie-lime px-3 py-2 text-sm font-black text-[#07100b] transition hover:bg-[#d8ff62] disabled:cursor-wait disabled:border-white/10 disabled:bg-white/10 disabled:text-slate-400"
        >
          {isConverting ? (
            <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
          ) : (
            <ChevronRight aria-hidden="true" className="h-4 w-4" />
          )}
          {isConverting ? "Converting Signal" : "Convert to Opportunity"}
        </button>

        {conversionState.status === "error" ? (
          <div className="mt-3 rounded-md border border-amber-300/20 bg-amber-400/10 p-3" role="alert">
            <p className="text-sm font-semibold text-amber-100">Signal was not converted</p>
            <p className="mt-2 text-sm leading-6 text-amber-100/80">{conversionState.message}</p>
          </div>
        ) : null}

        {conversionState.status === "success" ? (
          <div className="mt-3 rounded-md border border-emerald-300/20 bg-emerald-400/10 p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-semibold text-emerald-100">Opportunity created</p>
              <StatusPill tone="green" label={`${conversionState.result.fields_filled} fields labelled`} />
            </div>
            <p className="mt-2 text-sm leading-6 text-emerald-100/80">
              {conversionState.result.conversion_summary}
            </p>
            <button
              type="button"
              onClick={() => onOpenOpportunity(conversionState.result.opportunity)}
              className="mt-3 inline-flex min-h-9 items-center justify-center gap-2 rounded-md border border-emerald-200/30 bg-[#0b2f24] px-3 py-2 text-sm font-bold text-emerald-50 transition hover:bg-[#134734]"
            >
              Open intelligence pack
              <ChevronRight aria-hidden="true" className="h-4 w-4" />
            </button>
          </div>
        ) : null}
      </div>
    </article>
  );
}

function TenderIntelligenceView({ opportunities }: { opportunities: Opportunity[] }) {
  const tenders = opportunities
    .filter((opportunity) => liveTenderStages.has(opportunity.stage))
    .sort((first, second) =>
      (first.submission_deadline ?? "9999-12-31").localeCompare(
        second.submission_deadline ?? "9999-12-31",
      ),
    );

  return (
    <div className="grid gap-5">
      <Panel title="Tender Intelligence" action={<StatusPill tone="red" label={`${tenders.length} live tenders`} />}>
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
                  <tr key={tender.id} className="align-top hover:bg-white/[0.03]">
                    <td className="px-4 py-4 text-sm font-semibold text-white">{tender.name}</td>
                    <td className="px-4 py-4 text-sm text-slate-300">{tender.buyer_name}</td>
                    <td className="px-4 py-4 text-sm font-semibold text-red-200">{shortDate(tender.submission_deadline)}</td>
                    <td className="px-4 py-4 text-sm text-slate-300">{tender.stage}</td>
                    <td className="px-4 py-4 text-sm text-slate-300">{tender.owner}</td>
                    <td className="px-4 py-4">
                      <RiskPill risk={tender.calculated_risk_rating || tender.risk_rating} />
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

function PipelineForecastView({ data }: { data: MisiDashboardData }) {
  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_400px]">
      <Panel title="Pipeline Forecast" action={<StatusPill tone="cyan" label="Dashboard API" />}>
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

function FinanceView({ financeSummary }: { financeSummary: FinanceForecastSummary }) {
  return (
    <div className="grid gap-5">
      <FinanceForecastPanel financeSummary={financeSummary} />
      <FinanceControlStrip financeSummary={financeSummary} />

      <div className="grid gap-5 xl:grid-cols-2">
        <Panel
          title="April-to-March Revenue Forecast"
          action={<StatusPill tone="cyan" label={`FY ${financeSummary.financial_year}`} />}
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
          action={<StatusPill tone="green" label={compactCurrency(financeSummary.forecast_margin_to_financial_year_end)} />}
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

function FinanceControlStrip({
  financeSummary,
}: {
  financeSummary: FinanceForecastSummary;
}) {
  const openDownside =
    financeSummary.open_weighted_revenue - financeSummary.risk_adjusted_revenue;
  const reviewCount =
    financeSummary.margin_warnings.length + financeSummary.finance_review_items.length;
  const securedMix =
    financeSummary.forecast_to_financial_year_end > 0
      ? financeSummary.secured_revenue / financeSummary.forecast_to_financial_year_end
      : 0;

  return (
    <Panel
      title="FD Forecast Control"
      action={<StatusPill tone={reviewCount > 0 ? "amber" : "green"} label={`${reviewCount} review item${reviewCount === 1 ? "" : "s"}`} />}
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
          value={compactCurrency(financeSummary.forecast_margin_to_financial_year_end)}
          danger={financeSummary.margin_warnings.length > 0}
        />
      </div>
      <div className="mt-5 rounded-md border border-amber-300/20 bg-amber-400/10 p-4">
        <p className="text-sm font-semibold text-amber-100">Finance decision required</p>
        <p className="mt-2 text-sm leading-6 text-amber-100/80">
          Validate margin warnings, probability weighting and risk adjustments before this forecast is used as an LE1 commitment. WON work remains separated from open opportunities.
        </p>
      </div>
    </Panel>
  );
}

function FinanceForecastPanel({
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
      action={<StatusPill tone="green" label={`April to March FY ${financeSummary.financial_year}`} />}
    >
      <div className={`grid gap-4 ${compact ? "md:grid-cols-3" : "md:grid-cols-3 2xl:grid-cols-6"}`}>
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
          <FinancialYearMonthStrip months={financeSummary.financial_year_months} />

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
                value={String(financeSummary.finance_review_items.length + financeSummary.margin_warnings.length)}
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

function FinancialYearMonthStrip({ months }: { months: string[] }) {
  if (months.length === 0) {
    return null;
  }

  return (
    <div className="mt-5 rounded-md border border-cyan-300/20 bg-cyan-300/10 p-4">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm font-semibold text-cyan-100">April-to-March financial year</p>
          <p className="mt-1 text-sm leading-5 text-cyan-100/75">
            Forecast window runs {monthYearLabel(months[0])} to {monthYearLabel(months[months.length - 1])}.
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

function FinanceRevenueMix({ financeSummary }: { financeSummary: FinanceForecastSummary }) {
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
          <p className="text-sm font-semibold text-white">Secured vs weighted open revenue</p>
          <p className="mt-1 text-sm leading-5 text-slate-500">
            LE1 separates committed WON work from open probability-weighted upside.
          </p>
        </div>
        <CircleDollarSign aria-hidden="true" className="h-5 w-5 shrink-0 text-mitie-lime" />
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

function FinanceSingleSeriesChart({
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
          <p className="mt-1 text-sm text-slate-500">April to March, sourced from /api/finance-forecast/summary.</p>
        </div>
        <p className="text-sm font-black text-white">{compactCurrency(total)}</p>
      </div>
      <div className="overflow-x-auto">
        <div className={`flex min-w-[560px] items-end gap-2 ${tall ? "h-80" : "h-60"} pb-1`}>
          {points.map((point) => {
            const height = (point.value / maxValue) * 100;

            return (
              <div key={point.month} className="flex h-full min-w-9 flex-1 flex-col justify-end gap-2">
                <div
                  aria-label={`${monthLabel(point.month)} ${label}: ${currency(point.value)}`}
                  className={`w-full rounded-t-sm ${barClass}`}
                  style={{ height: `${height}%` }}
                  title={`${monthYearLabel(point.month)} ${label.toLowerCase()} ${currency(point.value)}`}
                />
                <div className="text-center text-xs font-semibold text-slate-500">{monthLabel(point.month)}</div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function SecuredWorkTable({ items }: { items: SecuredWorkItem[] }) {
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
                <th className="px-4 py-3 font-semibold">Delivery start month</th>
                <th className="px-4 py-3 font-semibold">Discipline</th>
                <th className="px-4 py-3 font-semibold">Confidence</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/10">
              {sortedItems.map((item) => (
                <tr key={item.opportunity_id} className="align-top hover:bg-white/[0.03]">
                  <td className="px-4 py-4 text-sm font-semibold text-white">{item.opportunity_name}</td>
                  <td className="px-4 py-4 text-sm text-slate-300">{item.client}</td>
                  <td className="px-4 py-4 text-sm font-semibold text-white">{currency(item.won_revenue)}</td>
                  <td className="px-4 py-4 text-sm text-slate-300">{currency(item.won_gross_margin)}</td>
                  <td className="px-4 py-4 text-sm text-slate-300">{percentageValue(item.margin_percentage)}</td>
                  <td className="px-4 py-4 text-sm text-slate-300">{monthYearLabel(item.delivery_start_month)}</td>
                  <td className="px-4 py-4 text-sm text-slate-300">{item.discipline ?? "Discipline TBC"}</td>
                  <td className="px-4 py-4">
                    <StatusPill tone={confidenceTone(item.confidence)} label={percentage(item.confidence)} />
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

function OpenOpportunityForecastTable({ items }: { items: OpenForecastItem[] }) {
  const sortedItems = [...items].sort((first, second) => {
    const startOrder = first.forecast_start_month.localeCompare(second.forecast_start_month);
    return startOrder === 0 ? second.risk_adjusted_revenue - first.risk_adjusted_revenue : startOrder;
  });

  return (
    <Panel
      title="Open Opportunities"
      action={<StatusPill tone="cyan" label={`${items.length} forecast items`} />}
    >
      {sortedItems.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1180px] border-collapse text-left">
            <thead>
              <tr className="border-b border-white/10 text-sm text-slate-400">
                <th className="px-4 py-3 font-semibold">Opportunity</th>
                <th className="px-4 py-3 font-semibold">Client</th>
                <th className="px-4 py-3 font-semibold">Forecast start month</th>
                <th className="px-4 py-3 font-semibold">Revenue to FY end</th>
                <th className="px-4 py-3 font-semibold">Estimated margin</th>
                <th className="px-4 py-3 font-semibold">Margin %</th>
                <th className="px-4 py-3 font-semibold">Probability weighting</th>
                <th className="px-4 py-3 font-semibold">Risk adjustment</th>
                <th className="px-4 py-3 font-semibold">Risk-adjusted revenue</th>
                <th className="px-4 py-3 font-semibold">Forecast category</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/10">
              {sortedItems.map((item) => (
                <tr key={item.opportunity_id} className="align-top hover:bg-white/[0.03]">
                  <td className="px-4 py-4 text-sm font-semibold text-white">{item.opportunity_name}</td>
                  <td className="px-4 py-4 text-sm text-slate-300">{item.client}</td>
                  <td className="px-4 py-4 text-sm text-slate-300">{monthYearLabel(item.forecast_start_month)}</td>
                  <td className="px-4 py-4 text-sm font-semibold text-white">{currency(item.revenue_to_financial_year_end)}</td>
                  <td className="px-4 py-4 text-sm text-slate-300">{currency(item.estimated_margin)}</td>
                  <td className="px-4 py-4 text-sm text-slate-300">{percentageValue(item.margin_percentage)}</td>
                  <td className="px-4 py-4 text-sm text-slate-300">{percentage(item.probability_weighting)}</td>
                  <td className="px-4 py-4 text-sm text-slate-300">{percentage(item.risk_adjustment)}</td>
                  <td className="px-4 py-4 text-sm font-semibold text-mitie-lime">{currency(item.risk_adjusted_revenue)}</td>
                  <td className="px-4 py-4">
                    <StatusPill tone={forecastCategoryTone(item.forecast_category)} label={item.forecast_category} />
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

function FinanceWarningsPanel({
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
              <p className="text-sm font-semibold text-red-100">Margin threshold warnings</p>
              <div className="mt-3 grid gap-3">
                {warnings.map((warning) => (
                  <article
                    key={`warning-${warning.opportunity_id}`}
                    className="rounded-md border border-red-300/20 bg-red-500/10 p-4"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-white">{warning.opportunity_name}</p>
                        <p className="mt-1 text-xs text-red-100/70">{warning.client}</p>
                      </div>
                      <StatusPill tone="red" label={percentageValue(warning.margin_percentage)} />
                    </div>
                    <p className="mt-3 text-sm leading-6 text-red-100/80">{warning.reason}</p>
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
              <p className="text-sm font-semibold text-amber-100">FD / bid governance items</p>
              <div className="mt-3 grid gap-3">
                {reviewItems.map((item) => (
                  <article
                    key={`review-${item.opportunity_id}-${item.category}`}
                    className="rounded-md border border-white/10 bg-[#111a20] p-4"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-white">{item.opportunity_name}</p>
                        <p className="mt-1 text-xs text-slate-500">{item.client}</p>
                      </div>
                      <StatusPill tone={priorityTone(item.priority)} label={item.priority} />
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-300">{item.reason}</p>
                    <p className="mt-3 text-sm font-semibold text-mitie-lime">{item.recommended_action}</p>
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

function forecastCategoryTone(category: string): Tone {
  const normalisedCategory = category.toLowerCase();

  if (normalisedCategory.includes("committed") || normalisedCategory.includes("likely")) {
    return "green";
  }

  if (normalisedCategory.includes("best")) {
    return "cyan";
  }

  if (normalisedCategory.includes("at risk") || normalisedCategory.includes("excluded")) {
    return "red";
  }

  return "amber";
}

function priorityTone(priority: string): Tone {
  const normalisedPriority = priority.toLowerCase();

  if (normalisedPriority.includes("high") || normalisedPriority.includes("urgent")) {
    return "red";
  }

  if (normalisedPriority.includes("medium")) {
    return "amber";
  }

  return "cyan";
}

function relationshipTone(relationship: string): Tone {
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

function threatTone(threat: string): Tone {
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

function monthYearLabel(value: string | null): string {
  if (!value) {
    return "Not set";
  }

  const [year, month] = value.split("-");
  const yearNumber = Number(year);
  const monthNumber = Number(month);

  if (!Number.isInteger(yearNumber) || !Number.isInteger(monthNumber) || monthNumber < 1 || monthNumber > 12) {
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

function SelfDeliveryView({ opportunities }: { opportunities: Opportunity[] }) {
  const summary = useMemo(
    () => buildSelfDeliverySummary(opportunities),
    [opportunities],
  );
  const maxDisciplineValue = Math.max(
    ...summary.disciplineOpportunity.map((discipline) => discipline.value),
    1,
  );

  return (
    <div className="grid gap-5">
      <Panel
        title="Self-Delivery Intelligence"
        action={<StatusPill tone="green" label={`${summary.routeOpportunities.length} routed`} />}
      >
        <div className="grid gap-4 md:grid-cols-3 2xl:grid-cols-6">
          <MiniMetric label="Opportunity value" value={compactCurrency(summary.opportunityValue)} />
          <MiniMetric label="Value captured" value={compactCurrency(summary.valueCaptured)} />
          <MiniMetric label="Value at risk" value={compactCurrency(summary.valueAtRisk)} danger={summary.valueAtRisk > 0} />
          <MiniMetric label="Accepted opportunities" value={String(summary.acceptedCount)} />
          <MiniMetric label="Declined opportunities" value={String(summary.declinedCount)} danger={summary.declinedCount > 0} />
          <MiniMetric label="Conversion rate" value={percentage(summary.conversionRate)} />
        </div>

        <div className="mt-5 rounded-md border border-mitie-lime/20 bg-mitie-lime/10 p-4">
          <p className="text-sm font-semibold text-mitie-lime">Commercial readout</p>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            Route high-fit fire and security scopes into Mitie Fire & Security early, protect captured value through mobilisation governance, and challenge moderate-fit packages before third-party leakage becomes embedded in the bid.
          </p>
        </div>
      </Panel>

      <SelfDeliveryGovernancePanel summary={summary} />

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_390px]">
        <Panel
          title="Disciplines With Highest Opportunity"
          action={<StatusPill tone="cyan" label={`${summary.disciplineOpportunity.length} disciplines`} />}
        >
          {summary.disciplineOpportunity.length > 0 ? (
            <div className="grid gap-4">
              {summary.disciplineOpportunity.map((discipline) => (
                <ProgressRow
                  key={discipline.label}
                  label={`${discipline.label} (${discipline.count})`}
                  value={compactCurrency(discipline.value)}
                  width={(discipline.value / maxDisciplineValue) * 100}
                />
              ))}
            </div>
          ) : (
            <EmptyState
              title="No discipline opportunity"
              message="MiSi has not found enough discipline evidence yet. Research or upload opportunities and it will infer Fire & Security scope, fit and leakage risk."
            />
          )}
        </Panel>

        <div className="grid content-start gap-5">
          <SelfDeliverySupplierPanel suppliers={summary.topDisplacedSuppliers} />
          <SelfDeliveryDecisionPanel
            accepted={summary.acceptedOpportunities}
            declined={summary.declinedOpportunities}
          />
        </div>
      </div>

      <Panel
        title="Route To Mitie Fire & Security"
        action={<Target aria-hidden="true" className="h-5 w-5 text-mitie-lime" />}
      >
        <SelfDeliveryOpportunityList
          opportunities={summary.routeOpportunities}
          emptyTitle="No routed opportunities"
          emptyMessage="No opportunities currently meet the self-delivery routing threshold. MiSi will flag capture opportunities when fit, value and discipline evidence strengthen."
        />
      </Panel>

      <Panel
        title="Third-Party Leakage Risk"
        action={<StatusPill tone={summary.leakageOpportunities.length > 0 ? "red" : "green"} label={`${summary.leakageOpportunities.length} risks`} />}
      >
        <SelfDeliveryOpportunityList
          opportunities={summary.leakageOpportunities}
          emptyTitle="No leakage risks"
          emptyMessage="No third-party leakage risks are currently flagged. MiSi will warn when high-fit Fire & Security work appears likely to leave Mitie delivery."
        />
      </Panel>
    </div>
  );
}

function SelfDeliveryGovernancePanel({
  summary,
}: {
  summary: SelfDeliverySummary;
}) {
  const decisionCount = summary.acceptedCount + summary.declinedCount;
  const topRoute = summary.routeOpportunities[0];
  const topLeakage = summary.leakageOpportunities[0];

  const controls = [
    {
      label: "Route now",
      value: topRoute ? compactCurrency(topRoute.estimatedValue) : "No route",
      action: topRoute
        ? `${topRoute.buyerName}: route ${topRoute.discipline} scope through Mitie Fire & Security.`
        : "No strong-fit route candidates are visible in the current view.",
      tone: topRoute ? "green" : "cyan",
    },
    {
      label: "Protect value",
      value: compactCurrency(summary.valueCaptured),
      action: "Keep accepted scopes under Mitie Fire & Security ownership through mobilisation and handover.",
      tone: "cyan",
    },
    {
      label: "Challenge leakage",
      value: compactCurrency(summary.valueAtRisk),
      action: topLeakage
        ? `${topLeakage.buyerName}: challenge third-party dependency before commercial close.`
        : "No third-party leakage risks are flagged in the current view.",
      tone: summary.valueAtRisk > 0 ? "red" : "green",
    },
    {
      label: "Decision discipline",
      value: `${decisionCount} decisions`,
      action: "Accepted and declined positions should be explicit before bid sign-off.",
      tone: summary.declinedCount > 0 ? "amber" : "green",
    },
  ] satisfies Array<{
    label: string;
    value: string;
    action: string;
    tone: Tone;
  }>;

  return (
    <Panel title="Self-Delivery Capture Governance" action={<StatusPill tone="green" label="Commercial controls" />}>
      <div className="grid gap-3 lg:grid-cols-4">
        {controls.map((control) => (
          <article key={control.label} className="rounded-md border border-white/10 bg-[#111a20] p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-xs font-black uppercase text-slate-500">{control.label}</p>
              <StatusPill tone={control.tone} label={control.value} />
            </div>
            <p className="mt-4 text-sm leading-6 text-slate-300">{control.action}</p>
          </article>
        ))}
      </div>
    </Panel>
  );
}

function SelfDeliverySupplierPanel({
  suppliers,
}: {
  suppliers: SelfDeliveryAggregate[];
}) {
  const maxSupplierValue = Math.max(...suppliers.map((supplier) => supplier.value), 1);

  return (
    <Panel
      title="Top Displaced Suppliers"
      action={<ShieldAlert aria-hidden="true" className="h-5 w-5 text-amber-200" />}
    >
      {suppliers.length > 0 ? (
        <div className="grid gap-4">
          {suppliers.map((supplier) => (
            <ProgressRow
              key={supplier.label}
              label={`${supplier.label} (${supplier.count})`}
              value={compactCurrency(supplier.value)}
              width={(supplier.value / maxSupplierValue) * 100}
            />
          ))}
        </div>
      ) : (
        <EmptyState
          title="No supplier displacement"
          message="No self-delivery supplier displacement has been calculated from the backend opportunities."
        />
      )}
    </Panel>
  );
}

function SelfDeliveryDecisionPanel({
  accepted,
  declined,
}: {
  accepted: SelfDeliveryOpportunityInsight[];
  declined: SelfDeliveryOpportunityInsight[];
}) {
  return (
    <Panel title="Capture Decision Position" action={<StatusPill tone="cyan" label="Accepted / declined" />}>
      <div className="grid gap-5">
        <SelfDeliveryDecisionList
          title="Accepted self-delivery opportunities"
          items={accepted.slice(0, 4)}
          emptyMessage="No accepted self-delivery opportunities were found in the backend dataset."
        />
        <SelfDeliveryDecisionList
          title="Declined opportunities"
          items={declined.slice(0, 4)}
          emptyMessage="No declined or qualified-out self-delivery opportunities were found."
        />
      </div>
    </Panel>
  );
}

function SelfDeliveryDecisionList({
  title,
  items,
  emptyMessage,
}: {
  title: string;
  items: SelfDeliveryOpportunityInsight[];
  emptyMessage: string;
}) {
  return (
    <div>
      <h3 className="text-sm font-semibold text-white">{title}</h3>
      {items.length > 0 ? (
        <div className="mt-3 grid gap-3">
          {items.map((item) => (
            <div key={item.opportunityId} className="border-b border-white/10 pb-3 last:border-0 last:pb-0">
              <p className="text-sm font-semibold leading-5 text-slate-200">{item.buyerName}</p>
              <p className="mt-1 text-sm leading-5 text-slate-500">{item.discipline} | {compactCurrency(item.estimatedValue)}</p>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-3 text-sm leading-6 text-slate-500">{emptyMessage}</p>
      )}
    </div>
  );
}

function SelfDeliveryOpportunityList({
  opportunities,
  emptyTitle,
  emptyMessage,
}: {
  opportunities: SelfDeliveryOpportunityInsight[];
  emptyTitle: string;
  emptyMessage: string;
}) {
  if (opportunities.length === 0) {
    return <EmptyState title={emptyTitle} message={emptyMessage} />;
  }

  return (
    <div className="grid gap-3 xl:grid-cols-2">
      {opportunities.map((opportunity) => (
        <article key={opportunity.opportunityId} className="rounded-md border border-white/10 bg-[#111a20] p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-sm font-semibold text-mitie-lime">{opportunity.buyerName}</p>
              <h3 className="mt-1 text-base font-semibold leading-6 text-white">{opportunity.name}</h3>
            </div>
            <RiskPill risk={opportunity.riskRating} />
          </div>
          <div className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
            <DetailField label="Discipline" value={opportunity.discipline} />
            <DetailField label="Value" value={compactCurrency(opportunity.estimatedValue)} />
            <DetailField label="Stage" value={opportunity.stage} />
          </div>
          <div className="mt-4 rounded-md border border-white/10 bg-white/[0.03] p-3">
            <p className="text-xs font-semibold text-slate-500">Displaced supplier</p>
            <p className="mt-1 text-sm font-semibold leading-5 text-slate-200">{opportunity.displacedSupplier}</p>
          </div>
          <p className="mt-4 text-sm leading-6 text-slate-300">{opportunity.reason}</p>
          <p className="mt-3 text-sm leading-6 text-slate-500">{opportunity.recommendedAction}</p>
        </article>
      ))}
    </div>
  );
}

function BuyersView({ buyers }: { buyers: BuyerProfile[] }) {
  return (
    <Panel title="Buyer Intelligence" action={<StatusPill tone="cyan" label={`${buyers.length} API profiles`} />}>
      {buyers.length > 0 ? (
        <div className="grid gap-4 lg:grid-cols-3">
          {buyers.map((buyer) => (
            <article key={buyer.id} className="rounded-md border border-white/10 bg-[#111a20] p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-base font-semibold text-white">{buyer.buyer_name}</h3>
                  <p className="mt-1 text-sm text-slate-500">{buyer.sector} | {buyer.region}</p>
                </div>
                <StatusPill tone={relationshipTone(buyer.relationship_status)} label={buyer.relationship_status || "Unknown"} />
              </div>
              <DetailList title="Procurement drivers" items={buyer.procurement_drivers.slice(0, 3)} />
              <DetailList title="Pain points" items={buyer.pain_points.slice(0, 2)} />
              <p className="mt-4 border-t border-white/10 pt-3 text-sm font-semibold leading-6 text-mitie-lime">
                {buyer.next_best_action || "Confirm relationship owner and next best action."}
              </p>
            </article>
          ))}
        </div>
      ) : (
      <EmptyState
        title="No confirmed buyer intelligence yet"
        message="MiSi has not researched these buyers yet. Start with a buyer, sector or tender phrase and MiSi will infer drivers, pain points and next best action with confidence labels."
      />
      )}
    </Panel>
  );
}

function CompetitorsView({ competitors }: { competitors: CompetitorProfile[] }) {
  return (
    <Panel title="Competitor Intelligence" action={<StatusPill tone="amber" label={`${competitors.length} API profiles`} />}>
      {competitors.length > 0 ? (
        <div className="grid gap-4 lg:grid-cols-3">
          {competitors.map((competitor) => (
            <article key={competitor.id} className="rounded-md border border-white/10 bg-[#111a20] p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-base font-semibold text-white">{competitor.name}</h3>
                  <p className="mt-1 text-sm text-slate-500">{competitor.sectors.join(", ") || "Sectors TBC"}</p>
                </div>
                <StatusPill tone={threatTone(competitor.threat_level)} label={competitor.threat_level || "Unknown"} />
              </div>
              <DetailList title="Strengths" items={competitor.strengths.slice(0, 2)} />
              <DetailList title="Weaknesses" items={competitor.weaknesses.slice(0, 2)} />
              <p className="mt-4 text-sm leading-6 text-slate-400">{competitor.pricing_behaviour || "Pricing behaviour not yet captured."}</p>
              <p className="mt-4 border-t border-white/10 pt-3 text-sm font-semibold leading-6 text-mitie-lime">{competitor.counter_strategy || "Confirm counter-strategy before bid gate."}</p>
            </article>
          ))}
        </div>
      ) : (
        <EmptyState
          title="No confirmed competitor evidence yet"
          message="MiSi can infer likely competitor threat from sector, scope and incumbent patterns, then separate inferred threat from confirmed competitor evidence."
        />
      )}
    </Panel>
  );
}

function ExecutiveActionsView({ actions }: { actions: ExecutiveAction[] }) {
  return <ExecutiveActionsList actions={actions} title="Executive Action Centre" expanded />;
}

function SettingsView() {
  return (
    <div className="grid gap-5 xl:grid-cols-2">
      <Panel title="API Connection" action={<LockKeyhole aria-hidden="true" className="h-5 w-5 text-mitie-lime" />}>
        <div className="grid gap-3 text-sm leading-6 text-slate-300">
          <p>Frontend API base URL: <span className="font-semibold text-white">{getApiBaseUrl()}</span></p>
          <p>The browser only receives `NEXT_PUBLIC_API_BASE_URL`; OpenAI keys, prompts and connector credentials remain backend-only.</p>
          <p>For real-data mode, start from an empty database and upload only data you are allowed to process in this local environment.</p>
        </div>
      </Panel>
      <Panel title="Workspace Status" action={<StatusPill tone="cyan" label="Real-data ready" />}>
        <div className="grid gap-4">
          <SourceRow label="SQLite local database" value="Can run empty or seeded for demos" tone="green" />
          <SourceRow label="PostgreSQL migration path" value="Documented" tone="cyan" />
          <SourceRow label="OpenAI analysis" value="Backend endpoint only" tone="amber" />
          <SourceRow label="Authentication" value="Planned for Entra ID" tone="amber" />
        </div>
      </Panel>
    </div>
  );
}

function KpiTile({
  label,
  display,
  detail,
  tone,
}: {
  label: string;
  display: string;
  detail: string;
  tone: Tone;
}) {
  const Icon = tone === "green" ? Target : tone === "cyan" ? TrendingUp : tone === "amber" ? Landmark : AlertTriangle;

  return (
    <article className={`rounded-lg border p-4 shadow-[0_18px_60px_rgba(0,0,0,0.24)] ${toneClasses[tone]}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-300">{label}</p>
          <p className="mt-3 text-3xl font-semibold text-white">{display}</p>
        </div>
        <div className="flex h-10 w-10 items-center justify-center rounded-md bg-white/10">
          <Icon aria-hidden="true" className="h-5 w-5" />
        </div>
      </div>
      <p className="mt-4 text-sm leading-5 text-slate-300">{detail}</p>
    </article>
  );
}

function Panel({
  title,
  action,
  children,
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="min-w-0 rounded-lg border border-white/10 bg-[#0d151a] shadow-[0_20px_70px_rgba(0,0,0,0.28)]">
      <div className="flex min-h-16 items-center justify-between gap-4 border-b border-white/10 px-4 py-4 sm:px-5">
        <h2 className="text-base font-semibold text-white sm:text-lg">{title}</h2>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
      <div className="p-4 sm:p-5">{children}</div>
    </section>
  );
}

function StatusPill({ tone, label }: { tone: Tone; label: string }) {
  return (
    <span className={`inline-flex rounded-md border px-2.5 py-1 text-xs font-semibold ${toneClasses[tone]}`}>
      {label}
    </span>
  );
}

function ConfidenceOrbit({ score, label }: { score: number; label: string }) {
  const percent = Math.round(Math.min(Math.max(score, 0), 1) * 100);

  return (
    <div
      className="misi-confidence-glow rounded-full p-[3px]"
      style={{
        background: `conic-gradient(#7cb342 ${percent}%, rgba(255,255,255,0.12) 0)`,
      }}
      aria-label={`${label} confidence progress`}
    >
      <div className="flex h-16 w-16 items-center justify-center rounded-full border border-white/10 bg-[#0d151a]">
        <span className="text-sm font-black text-white">{label}</span>
      </div>
    </div>
  );
}

function RiskPill({ risk }: { risk: string }) {
  return <StatusPill tone={riskTone(risk)} label={normaliseRiskLabel(risk)} />;
}

function MetricLine({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="border-b border-white/10 pb-3 last:border-0 last:pb-0">
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-sm font-semibold text-slate-300">{label}</p>
        <p className="text-lg font-semibold text-white">{value}</p>
      </div>
      <p className="mt-1 text-sm leading-5 text-slate-500">{detail}</p>
    </div>
  );
}

function MiniMetric({
  label,
  value,
  danger = false,
}: {
  label: string;
  value: string;
  danger?: boolean;
}) {
  return (
    <div className="rounded-md border border-white/10 bg-[#111a20] p-4">
      <p className="text-sm font-semibold text-slate-400">{label}</p>
      <p className={`mt-2 text-2xl font-semibold ${danger ? "text-red-200" : "text-white"}`}>{value}</p>
    </div>
  );
}

function AutofillSummaryMetric({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="rounded-md border border-white/10 bg-[#111a20] p-4">
      <p className="text-xs font-black uppercase text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
      <p className="mt-2 text-xs leading-5 text-slate-500">{detail}</p>
    </div>
  );
}

type IntelligenceFieldView = {
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

function IntelligenceMetric({
  field,
  fallbackLabel,
  danger = false,
}: {
  field: IntelligenceFieldView | undefined;
  fallbackLabel: string;
  danger?: boolean;
}) {
  if (!field) {
    return (
      <div className="rounded-md border border-slate-400/20 bg-slate-400/5 p-4">
        <div className="flex items-start justify-between gap-3">
          <p className="text-sm font-semibold text-slate-400">{fallbackLabel}</p>
          <StatusPill tone="amber" label="Unknown" />
        </div>
        <p className="mt-2 text-2xl font-semibold text-amber-100">Needs evidence</p>
        <p className="mt-2 text-xs leading-5 text-slate-500">
          MiSi has not confirmed this field yet. Attach source evidence or run AI research to estimate it with confidence.
        </p>
      </div>
    );
  }

  return (
    <div className={`rounded-md border p-4 transition hover:border-white/20 ${fieldConfidenceBorder(field.valueType)}`}>
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-semibold text-slate-400">{field.label}</p>
        <ConfidenceBadge field={field} />
      </div>
      <p className={`mt-2 text-2xl font-semibold ${danger || field.valueType === "unknown" ? "text-amber-100" : "text-white"}`}>
        {field.displayValue}
      </p>
      <p className="mt-2 text-xs leading-5 text-slate-500">{field.rationale}</p>
    </div>
  );
}

function ConfidenceFieldCompact({
  field,
  label,
}: {
  field: IntelligenceFieldView | undefined;
  label: string;
}) {
  if (!field) {
    return <DetailField label={label} value="Unknown · evidence required" />;
  }

  return (
    <div>
      <div className="flex items-center gap-2">
        <p className="text-xs font-semibold text-slate-500">{label}</p>
        <ValueTypeDot valueType={field.valueType} />
      </div>
      <p className="mt-1 text-sm font-semibold leading-6 text-slate-200">
        {field.displayValue}
      </p>
      <p className="text-xs leading-5 text-slate-500">
        {valueTypeLabel(field.valueType)} · {percentage(field.confidenceScore)} confidence
      </p>
    </div>
  );
}

function ConfidenceFieldCard({
  field,
  accepted,
  editing,
  onAccept,
  onEdit,
  onCancelEdit,
  onSaveEdit,
}: {
  field: IntelligenceFieldView;
  accepted: boolean;
  editing: boolean;
  onAccept: () => void;
  onEdit: () => void;
  onCancelEdit: () => void;
  onSaveEdit: (value: string) => void;
}) {
  const [draftValue, setDraftValue] = useState(field.displayValue);

  useEffect(() => {
    setDraftValue(field.displayValue);
  }, [field.displayValue, editing]);

  return (
    <article className={`rounded-md border p-4 transition hover:border-white/20 ${fieldConfidenceBorder(field.valueType)}`}>
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-sm font-semibold text-white">{field.label}</h4>
            <ConfidenceBadge field={field} />
            {field.needsUserConfirmation ? (
              <StatusPill tone="amber" label="Needs confirmation" />
            ) : null}
            {accepted ? <StatusPill tone="green" label="Accepted in review" /> : null}
          </div>
          {editing ? (
            <label className="mt-3 block">
              <span className="sr-only">Edit {field.label}</span>
              <textarea
                value={draftValue}
                onChange={(event) => setDraftValue(event.target.value)}
                rows={2}
                className="w-full rounded-md border border-white/10 bg-[#0b1115] px-3 py-2 text-sm leading-6 text-white"
              />
            </label>
          ) : (
            <p className="mt-3 text-base font-semibold leading-7 text-slate-100">
              {field.displayValue}
            </p>
          )}
          <p className="mt-2 text-sm leading-6 text-slate-400">{field.rationale}</p>
          <div className="mt-3 rounded-md border border-mitie-lime/20 bg-mitie-lime/10 p-3">
            <p className="text-xs font-black uppercase text-mitie-lime">Next action</p>
            <p className="mt-1 text-sm font-semibold leading-6 text-white">
              {field.recommendedNextStep}
            </p>
          </div>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <button
            type="button"
            onClick={onAccept}
            disabled={accepted || field.valueType === "unknown"}
            className="inline-flex min-h-9 items-center justify-center gap-2 rounded-md border border-emerald-300/20 bg-emerald-400/10 px-3 text-xs font-bold text-emerald-100 transition hover:bg-emerald-400/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <CheckCircle2 aria-hidden="true" className="h-3.5 w-3.5" />
            {field.valueType === "unknown" ? "Evidence needed" : accepted ? "Accepted" : "Accept AI value"}
          </button>
          {editing ? (
            <>
              <button
                type="button"
                onClick={() => onSaveEdit(draftValue)}
                className="inline-flex min-h-9 items-center justify-center rounded-md border border-cyan-300/20 bg-cyan-400/10 px-3 text-xs font-bold text-cyan-100 transition hover:bg-cyan-400/20"
              >
                Save draft
              </button>
              <button
                type="button"
                onClick={onCancelEdit}
                className="inline-flex min-h-9 items-center justify-center rounded-md border border-white/10 bg-white/[0.04] px-3 text-xs font-bold text-slate-300 transition hover:bg-white/[0.08]"
              >
                Cancel
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={onEdit}
              className="inline-flex min-h-9 items-center justify-center rounded-md border border-white/10 bg-white/[0.04] px-3 text-xs font-bold text-slate-300 transition hover:bg-white/[0.08]"
            >
              Edit
            </button>
          )}
        </div>
      </div>

      <details className="mt-3 rounded-md border border-white/10 bg-[#0b1115] px-3 py-2">
        <summary className="cursor-pointer text-xs font-semibold text-slate-300">
          Evidence, confidence and rationale
        </summary>
        <div className="mt-3 grid gap-2 text-xs leading-5 text-slate-400">
          <p>{valueTypeDescription(field)}</p>
          {field.sourceUrls.length > 0 ? (
            <div className="grid gap-1">
              {field.sourceUrls.slice(0, 4).map((url, index) => (
                <a
                  key={url}
                  href={url}
                  target="_blank"
                  rel="noreferrer"
                  className="truncate font-semibold text-cyan-200 hover:text-white"
                >
                  {field.sourceTitles[index] ? `${field.sourceTitles[index]} · ` : ""}
                  {url}
                </a>
              ))}
            </div>
          ) : (
            <p>No source URL is attached; validate this against an approved source before using it commercially.</p>
          )}
        </div>
      </details>
    </article>
  );
}

function ConfidenceBadge({ field }: { field: IntelligenceFieldView }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-bold ${fieldConfidenceClass(field.valueType)}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${valueTypeDotClass(field.valueType)} ${field.valueType === "unknown" ? "" : "misi-confidence-glow"}`} aria-hidden="true" />
      {valueTypeLabel(field.valueType)} · {percentage(field.confidenceScore)}
    </span>
  );
}

function ValueTypeDot({ valueType }: { valueType: FieldIntelligence["value_type"] }) {
  return <span className={`h-2 w-2 rounded-full ${valueTypeDotClass(valueType)}`} aria-hidden="true" />;
}

function OpportunityTable({
  opportunities,
  onSelectOpportunity,
}: {
  opportunities: Opportunity[];
  onSelectOpportunity: (opportunity: Opportunity) => void;
}) {
  if (opportunities.length === 0) {
    return (
      <EmptyState
        title="MiSi has not researched matching opportunities yet"
        message="Start with a buyer, sector or tender phrase in the AI Research Workspace. MiSi will build the opportunity record, label weak fields and show the next best action."
      />
    );
  }

  return (
    <>
      <div className="grid gap-3 md:hidden">
        {opportunities.map((item) => (
          <button
            key={item.id}
            type="button"
            data-testid={`opportunity-card-${item.id}`}
            onClick={() => onSelectOpportunity(item)}
            className="rounded-md border border-white/10 bg-[#111a20] p-4 text-left outline-none transition hover:border-mitie-lime/30 hover:bg-white/[0.06] focus-visible:border-mitie-lime/60"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm font-semibold text-mitie-lime">{displayOpportunityValue("buyer_name", item.buyer_name)}</p>
                <p className="mt-1 text-sm font-semibold leading-6 text-white">{displayOpportunityValue("name", item.name)}</p>
                <p className="mt-1 text-xs font-semibold text-slate-500">{displayOpportunityValue("stage", item.stage)}</p>
              </div>
              <RiskPill risk={item.calculated_risk_rating || item.risk_rating} />
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {item.strategic_must_win ? <StatusPill tone="green" label="Strategic must-win" /> : null}
              {item.self_delivery_capture ? <StatusPill tone="cyan" label="Self-delivery capture" /> : null}
              {item.deadline_warning ? <StatusPill tone="red" label="Deadline warning" /> : null}
            </div>
            <div className="mt-4 grid grid-cols-3 gap-3 text-sm">
              <div>
                <p className="text-xs font-semibold text-slate-500">Value</p>
                <p className="mt-1 font-semibold text-white">{displayOpportunityValue("estimated_total_contract_value", item.estimated_total_contract_value)}</p>
              </div>
              <div>
                <p className="text-xs font-semibold text-slate-500">Prob.</p>
                <p className="mt-1 font-semibold text-slate-200">{displayOpportunityValue("probability", item.probability)}</p>
              </div>
              <div>
                <p className="text-xs font-semibold text-slate-500">Margin</p>
                <p className="mt-1 font-semibold text-slate-200">{displayOpportunityValue("margin_percentage", item.margin_percentage)}</p>
              </div>
            </div>
            <NextActionCallout
              action={displayOpportunityValue("recommended_action", item.calculated_recommended_action || item.recommended_action)}
              tone={item.executive_escalation ? "amber" : "green"}
            />
          </button>
        ))}
      </div>

      <div className="hidden overflow-x-auto md:block">
        <table className="w-full min-w-[860px] border-collapse text-left">
          <thead>
            <tr className="border-b border-white/10 text-sm text-slate-400">
              <th className="px-3 py-3 font-semibold">Buyer</th>
              <th className="px-3 py-3 font-semibold">Opportunity</th>
              <th className="px-3 py-3 font-semibold">Stage</th>
              <th className="px-3 py-3 font-semibold">Value</th>
              <th className="px-3 py-3 font-semibold">Prob.</th>
              <th className="px-3 py-3 font-semibold">Margin</th>
              <th className="px-3 py-3 font-semibold">Risk</th>
              <th className="px-3 py-3 font-semibold">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/10">
            {opportunities.map((item) => (
              <tr
                key={item.id}
                tabIndex={0}
                role="button"
                data-testid={`opportunity-row-${item.id}`}
                onClick={() => onSelectOpportunity(item)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onSelectOpportunity(item);
                  }
                }}
                className="cursor-pointer align-top outline-none transition hover:bg-white/[0.03] focus-visible:bg-white/[0.06]"
              >
                <td className="px-3 py-4 text-sm font-semibold text-white">{displayOpportunityValue("buyer_name", item.buyer_name)}</td>
                <td className="px-3 py-4 text-sm text-slate-300">
                  <div className="font-semibold text-white">{displayOpportunityValue("name", item.name)}</div>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {item.strategic_must_win ? <StatusPill tone="green" label="Strategic" /> : null}
                    {item.self_delivery_capture ? <StatusPill tone="cyan" label="Self-delivery" /> : null}
                    {item.margin_warning ? <StatusPill tone="amber" label="Margin" /> : null}
                  </div>
                </td>
                <td className="px-3 py-4 text-sm text-slate-300">{displayOpportunityValue("stage", item.stage)}</td>
                <td className="px-3 py-4 text-sm font-semibold text-white">{displayOpportunityValue("estimated_total_contract_value", item.estimated_total_contract_value)}</td>
                <td className="px-3 py-4 text-sm text-slate-300">{displayOpportunityValue("probability", item.probability)}</td>
                <td className="px-3 py-4 text-sm text-slate-300">{displayOpportunityValue("margin_percentage", item.margin_percentage)}</td>
                <td className="px-3 py-4">
                  <RiskPill risk={item.calculated_risk_rating || item.risk_rating} />
                </td>
                <td className="max-w-[230px] px-3 py-4 text-sm leading-6 text-slate-300">
                  {displayOpportunityValue("recommended_action", item.calculated_recommended_action || item.recommended_action)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function OpportunityDetailDrawer({
  contextData,
  opportunity,
  onAnalysisComplete,
  onClose,
}: {
  contextData: MisiDashboardData;
  opportunity: Opportunity;
  onAnalysisComplete: (opportunityId: number, analysis: OpportunityAIAnalysis) => void;
  onClose: () => void;
}) {
  const analysis = opportunity.latest_ai_analysis;
  const [analysisState, setAnalysisState] = useState<OpportunityAnalysisState>({
    status: "idle",
  });
  const [fieldState, setFieldState] = useState<FieldIntelligenceState>({
    status: "loading",
  });
  const [enrichmentState, setEnrichmentState] = useState<OpportunityEnrichmentState>({
    status: "loading",
  });
  const [acceptedFieldNames, setAcceptedFieldNames] = useState<Set<string>>(
    () => new Set(),
  );
  const [editingFieldName, setEditingFieldName] = useState<string | null>(null);
  const [fieldOverrides, setFieldOverrides] = useState<Record<string, string>>({});

  useEffect(() => {
    setAnalysisState({ status: "idle" });
    setAcceptedFieldNames(new Set());
    setEditingFieldName(null);
    setFieldOverrides({});
  }, [opportunity.id]);

  useEffect(() => {
    const controller = new AbortController();
    setFieldState({ status: "loading" });
    setEnrichmentState({ status: "loading" });

    fetchOpportunityFieldIntelligence(opportunity.id, controller.signal)
      .then((fields) => {
        setFieldState({ status: "success", fields });
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }

        setFieldState({
          status: "error",
          message:
            error instanceof Error
              ? error.message
              : "Could not load field-level confidence metadata.",
        });
      });

    fetchOpportunityEnrichments(opportunity.id, controller.signal)
      .then((enrichments) => {
        setEnrichmentState({ status: "success", enrichments });
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }

        setEnrichmentState({
          status: "error",
          message:
            error instanceof Error
              ? error.message
              : "Could not load opportunity enrichment pack.",
        });
      });

    return () => {
      controller.abort();
    };
  }, [opportunity.id]);

  async function handleRunAnalysis() {
    setAnalysisState({ status: "loading" });

    try {
      const result = await analyseOpportunity(opportunity.id);
      onAnalysisComplete(opportunity.id, {
        ...result,
        created_at: new Date().toISOString(),
      });
      setAnalysisState({ status: "idle" });
    } catch (error: unknown) {
      setAnalysisState({
        status: "error",
        message: getOpportunityAnalysisErrorMessage(error),
      });
    }
  }

  const intelligenceFields = buildOpportunityFieldViews(
    opportunity,
    fieldState.status === "success" ? fieldState.fields : [],
    fieldOverrides,
  );
  const confidenceSummary = summariseFieldConfidence(intelligenceFields);
  const latestEnrichment =
    enrichmentState.status === "success" ? enrichmentState.enrichments[0] ?? null : null;

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/65 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label="Opportunity intelligence pack">
      <button
        type="button"
        className="absolute inset-0 cursor-default"
        onClick={onClose}
        aria-label="Close opportunity intelligence pack"
      />
      <aside className="relative z-10 flex h-full w-full max-w-[1240px] flex-col overflow-y-auto border-l border-white/10 bg-[#080d10] shadow-[0_30px_90px_rgba(0,0,0,0.5)]">
        <div className="sticky top-0 z-20 border-b border-white/10 bg-[#080d10]/95 p-5 backdrop-blur">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-sm font-semibold text-mitie-lime">Opportunity Intelligence Pack</p>
              <h2 className="mt-2 text-2xl font-semibold leading-8 text-white">{displayOpportunityValue("name", opportunity.name)}</h2>
              <p className="mt-2 text-sm text-slate-500">
                {displayOpportunityValue("buyer_name", opportunity.buyer_name)} | {displayOpportunityValue("sector", opportunity.sector)} | {displayOpportunityValue("region", opportunity.region)} | {displayOpportunityValue("stage", opportunity.stage)}
              </p>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <StatusPill
                  tone={confidenceTone(confidenceSummary.score)}
                  label={`${percentage(confidenceSummary.score)} record confidence`}
                />
                <StatusPill tone="cyan" label={`${confidenceSummary.aiFieldCount} AI-labelled fields`} />
                <StatusPill
                  tone={latestEnrichment ? "green" : "amber"}
                  label={latestEnrichment ? "Enriched pack" : "Fallback pack"}
                />
                {confidenceSummary.unknownCount > 0 ? (
                  <StatusPill tone="amber" label={`${confidenceSummary.unknownCount} unknowns to confirm`} />
                ) : null}
              </div>
              <div className="mt-3 max-w-4xl rounded-md border border-mitie-lime/20 bg-mitie-lime/10 px-3 py-2">
                <p className="text-xs font-black uppercase text-mitie-lime">Next best action</p>
                <p className="mt-1 text-sm font-semibold leading-6 text-white">
                  {displayOpportunityValue("recommended_action", opportunity.calculated_recommended_action || opportunity.recommended_action)}
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-md border border-white/10 bg-white/[0.04] text-slate-300 transition hover:bg-white/[0.08] hover:text-white"
              aria-label="Close opportunity intelligence pack"
            >
              <X aria-hidden="true" className="h-5 w-5" />
            </button>
          </div>
        </div>

        <div className="grid gap-5 p-5">
          <OpportunityIntelligencePack
            acceptedFieldNames={acceptedFieldNames}
            analysis={analysis}
            contextData={contextData}
            editingFieldName={editingFieldName}
            enrichment={latestEnrichment}
            enrichmentState={enrichmentState}
            fieldState={fieldState}
            fields={intelligenceFields}
            onAcceptField={(fieldName) => {
              setAcceptedFieldNames((current) => {
                const next = new Set(current);
                next.add(fieldName);
                return next;
              });
            }}
            onCancelEdit={() => setEditingFieldName(null)}
            onEditField={setEditingFieldName}
            onSaveFieldEdit={(fieldName, value) => {
              setFieldOverrides((current) => ({
                ...current,
                [fieldName]: value,
              }));
              setEditingFieldName(null);
            }}
            opportunity={opportunity}
          />

          <section className="rounded-lg border border-white/10 bg-[#0d151a] p-4 shadow-[0_20px_70px_rgba(0,0,0,0.24)]">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h3 className="text-base font-semibold text-white">Refresh AI Analysis</h3>
                <p className="mt-1 text-sm leading-5 text-slate-500">
                  Run this when the opportunity record changes or when leadership wants a fresh structured bid/no-bid view.
                </p>
              </div>
              <div className="flex shrink-0 flex-wrap items-center gap-2">
                {analysis ? <StatusPill tone="green" label="Stored" /> : <StatusPill tone="amber" label="Not run" />}
                <button
                  type="button"
                  onClick={handleRunAnalysis}
                  disabled={analysisState.status === "loading"}
                  data-testid="run-ai-analysis-button"
                  className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-mitie-lime/30 bg-mitie-lime px-3 py-2 text-sm font-bold text-[#07100b] transition hover:bg-[#d8ff62] disabled:cursor-wait disabled:border-white/10 disabled:bg-white/10 disabled:text-slate-400"
                >
                  {analysisState.status === "loading" ? (
                    <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                  ) : (
                    <RefreshCw aria-hidden="true" className="h-4 w-4" />
                  )}
                  {analysisState.status === "loading" ? "Running AI Analysis" : "Run AI Analysis"}
                </button>
              </div>
            </div>

            {analysisState.status === "error" ? (
              <div
                className="mt-4 rounded-md border border-amber-300/20 bg-amber-400/10 p-4"
                role="alert"
              >
                <div className="flex gap-3">
                  <AlertTriangle aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0 text-amber-200" />
                  <div>
                    <p className="text-sm font-semibold text-amber-100">AI analysis was not completed</p>
                    <p className="mt-2 text-sm leading-6 text-amber-100/80">{analysisState.message}</p>
                  </div>
                </div>
              </div>
            ) : null}

            {analysisState.status === "loading" ? (
              <div className="mt-4 rounded-md border border-cyan-300/20 bg-cyan-400/10 p-4">
                <div className="flex items-center gap-3 text-sm font-semibold text-cyan-100">
                  <Loader2 aria-hidden="true" className="h-5 w-5 animate-spin" />
                  Building structured commercial analysis...
                </div>
                <p className="mt-2 text-sm leading-6 text-cyan-100/75">
                  MiSi is asking the backend to assess fit, risk, buyer drivers, margin and the next leadership action.
                </p>
              </div>
            ) : null}

            {analysis ? <OpportunityAnalysisPanel analysis={analysis} /> : null}

            {!analysis && analysisState.status !== "loading" ? (
              <EmptyState
                title="No separate AI analysis yet"
                message="The intelligence pack above still uses field evidence, enrichment records and rule-based fallbacks. Run AI Analysis to attach an additional structured OpenAI assessment."
              />
            ) : null}
          </section>
        </div>
      </aside>
    </div>
  );
}

function OpportunityIntelligencePack({
  acceptedFieldNames,
  analysis,
  contextData,
  editingFieldName,
  enrichment,
  enrichmentState,
  fieldState,
  fields,
  onAcceptField,
  onCancelEdit,
  onEditField,
  onSaveFieldEdit,
  opportunity,
}: {
  acceptedFieldNames: Set<string>;
  analysis: OpportunityAIAnalysis | null;
  contextData: MisiDashboardData;
  editingFieldName: string | null;
  enrichment: OpportunityEnrichment | null;
  enrichmentState: OpportunityEnrichmentState;
  fieldState: FieldIntelligenceState;
  fields: IntelligenceFieldView[];
  onAcceptField: (fieldName: string) => void;
  onCancelEdit: () => void;
  onEditField: (fieldName: string) => void;
  onSaveFieldEdit: (fieldName: string, value: string) => void;
  opportunity: Opportunity;
}) {
  const confidenceSummary = summariseFieldConfidence(fields);
  const buyerProfile = findBuyerProfileForOpportunity(contextData.buyerProfiles, opportunity);
  const openForecast = contextData.financeSummary.open_opportunities.find(
    (item) => item.opportunity_id === opportunity.id,
  );
  const securedWork = contextData.financeSummary.secured_work.find(
    (item) => item.opportunity_id === opportunity.id,
  );
  const relatedActions = contextData.executiveActions.filter(
    (action) => action.related_opportunity_id === opportunity.id,
  );
  const matchingCompetitors = findCompetitorsForOpportunity(
    contextData.competitorProfiles,
    opportunity,
  );
  const matchingSignals = findMarketSignalsForOpportunity(
    contextData.marketSignals,
    opportunity,
  );
  const sourceLinks = collectEvidenceLinks(fields);
  const likelyScope = listOrFallback(
    splitLikelyScope(enrichment?.likely_scope),
    ["Likely scope unknown. Confirm asset schedule, disciplines and procurement documents."],
  );
  const buyerDrivers = listOrFallback(
    enrichment?.likely_buyer_drivers,
    buyerProfile?.procurement_drivers,
    analysis?.likely_buyer_drivers,
    ["Buyer priorities unknown. Confirm compliance, cost, resilience and estate drivers with the buyer."],
  );
  const complianceDrivers = listOrFallback(
    enrichment?.compliance_drivers,
    ["Fire safety compliance, life-safety assurance and statutory inspection evidence should be validated."],
  );
  const recommendedSteps = listOrFallback(
    enrichment?.recommended_next_steps,
    relatedActions.map((action) => action.recommended_action),
    ["Confirm buyer owner, tender route, scope, incumbent, asset schedule and commercial gate before committing bid resources."],
  );
  const unknowns = listOrFallback(
    enrichment?.unknowns,
    fields
      .filter((field) => field.valueType === "unknown")
      .map((field) => `${field.label}: ${field.recommendedNextStep}`),
    ["No critical unknowns are recorded, but validate source evidence before bid governance."],
  );
  const commercialRisks = listOrFallback(
    analysis?.commercial_risks,
    enrichment?.commercial_assessment ? [enrichment.commercial_assessment] : [],
    opportunity.margin_warning
      ? ["Margin is below target. Finance should challenge cost build, self-delivery assumptions and risk allowance."]
      : [],
    ["Commercial risks not fully evidenced. Confirm value, margin, inflation, term and risk transfer."],
  );
  const mobilisationRisks = listOrFallback(
    analysis?.mobilisation_risks,
    enrichment?.mobilisation_assessment ? [enrichment.mobilisation_assessment] : [],
    ["Mobilisation risk unknown. Confirm asset count, geography, TUPE exposure, incumbent handover and engineer capacity."],
  );
  const competitorNames = listOrFallback(
    matchingCompetitors.map((competitor) => competitor.name),
    ["Likely competitors unknown. Check award history, buyer portal and incumbent contract notices."],
  );
  const highestThreat =
    analysis?.competitor_threat ||
    matchingCompetitors[0]?.threat_level ||
    "Unknown";
  const forecastCategory =
    openForecast?.forecast_category ||
    (securedWork ? "Committed" : "Unknown - finance forecast category not linked yet");
  const financialYearImpact = openForecast
    ? `${compactCurrency(openForecast.risk_adjusted_revenue)} risk-adjusted revenue to FY end`
    : securedWork
      ? `${compactCurrency(securedWork.won_revenue)} secured revenue from ${monthYearLabel(securedWork.delivery_start_month)}`
      : "Unknown - create or review LE1 forecast line";
  const sourceStatus =
    sourceLinks.length > 0
      ? `${sourceLinks.length} source link${sourceLinks.length === 1 ? "" : "s"} attached`
      : "No source URLs attached - validate against approved sources";

  return (
    <div className="grid gap-5">
      <section className="overflow-hidden rounded-lg border border-mitie-lime/20 bg-[#0d151a] shadow-[0_26px_90px_rgba(0,0,0,0.36)]">
        <div className="grid gap-0 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="p-5 sm:p-6">
            <div className="flex flex-wrap items-center gap-2">
              <RiskPill risk={opportunity.calculated_risk_rating || opportunity.risk_rating} />
              <StatusPill tone={confidenceTone(enrichment?.overall_confidence ?? confidenceSummary.score)} label={`${percentage(enrichment?.overall_confidence ?? confidenceSummary.score)} confidence`} />
              <StatusPill tone={sourceLinks.length > 0 ? "green" : "amber"} label={sourceStatus} />
              {opportunity.strategic_must_win ? <StatusPill tone="green" label="Strategic must-win" /> : null}
            </div>
            <h3 className="mt-5 text-2xl font-semibold leading-9 text-white">
              Executive Summary
            </h3>
            <div className="mt-5 grid gap-4 lg:grid-cols-3">
              <PackNarrativeCard
                label="What this opportunity is"
                text={firstUsefulText(
                  enrichment?.opportunity_summary,
                  analysis?.executive_summary,
                  `${displayOpportunityValue("name", opportunity.name)} for ${displayOpportunityValue("buyer_name", opportunity.buyer_name)}. Confirm scope and tender route before treating this as committed pipeline.`,
                )}
              />
              <PackNarrativeCard
                label="Why it matters"
                text={firstUsefulText(
                  enrichment?.commercial_assessment,
                  fieldByName(fields, "estimated_total_contract_value")?.rationale,
                  `${displayOpportunityValue("estimated_total_contract_value", opportunity.estimated_total_contract_value)} potential contract value with ${displayOpportunityValue("self_delivery_fit", opportunity.self_delivery_fit)} self-delivery fit.`,
                )}
              />
              <PackNarrativeCard
                label="What MiSi recommends"
                text={firstUsefulText(
                  enrichment?.executive_recommendation,
                  opportunity.calculated_recommended_action,
                  opportunity.recommended_action,
                  "Confirm buyer owner, source evidence, scope and bid governance route this week.",
                )}
                accent
              />
            </div>
          </div>
          <div className="border-t border-white/10 bg-[#111a20] p-5 xl:border-l xl:border-t-0">
            <p className="text-xs font-black uppercase text-slate-500">Leadership readout</p>
            <div className="mt-4 grid gap-3">
              <MetricLine label="Bid recommendation" value={displayOpportunityValue("bid_no_bid_recommendation", opportunity.calculated_bid_no_bid_recommendation || opportunity.bid_no_bid_recommendation)} detail="Review against fit, risk, margin and source confidence" />
              <MetricLine label="Strategic fit" value={displayOpportunityValue("strategic_fit_score", opportunity.strategic_fit_score)} detail={fieldByName(fields, "strategic_fit_score")?.rationale ?? "Confirm fit against Mitie sector and self-delivery priorities."} />
              <MetricLine label="Priority score" value={`${Math.round(opportunity.priority_score)}/100`} detail="Rule-based pursuit priority" />
            </div>
          </div>
        </div>
      </section>

      <OpportunityPackSection
        title="Commercial Snapshot"
        subtitle="Finance-quality view of value, margin, weighting and current forecast status."
        action={<StatusPill tone={openForecast || securedWork ? "green" : "amber"} label={forecastCategory} />}
      >
        <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-4">
          <IntelligenceMetric field={fieldByName(fields, "estimated_annual_revenue")} fallbackLabel="Annual revenue" />
          <IntelligenceMetric field={fieldByName(fields, "estimated_total_contract_value")} fallbackLabel="Total contract value" />
          <IntelligenceMetric field={fieldByName(fields, "estimated_gross_margin")} fallbackLabel="Estimated margin" danger={opportunity.margin_warning} />
          <IntelligenceMetric field={fieldByName(fields, "margin_percentage")} fallbackLabel="Margin percentage" danger={opportunity.margin_warning} />
          <IntelligenceMetric field={fieldByName(fields, "weighted_value")} fallbackLabel="Weighted value" />
          <PackMetricCard label="Forecast category" value={forecastCategory} detail="LE1 forecast status for this opportunity" tone={openForecast || securedWork ? "green" : "amber"} />
          <PackMetricCard label="Financial year impact" value={financialYearImpact} detail={enrichment?.finance_assessment || "Finance impact needs review before forecast commitment."} tone={openForecast || securedWork ? "cyan" : "amber"} />
          <PackMetricCard label="Forecast start" value={displayOpportunityValue("forecast_start_month", opportunity.forecast_start_month)} detail={fieldByName(fields, "forecast_start_month")?.rationale ?? "Confirm expected start month from procurement timetable."} tone="cyan" />
        </div>
      </OpportunityPackSection>

      <div className="grid gap-5 xl:grid-cols-2">
        <OpportunityPackSection title="Buyer Intelligence" subtitle="Buyer drivers, relationship context and decision criteria.">
          <PackNarrativeCard
            label="Buyer profile"
            text={firstUsefulText(
              enrichment?.buyer_summary,
              buyerProfile
                ? `${buyerProfile.buyer_name} is a ${buyerProfile.sector} buyer in ${buyerProfile.region}. ${buyerProfile.estate_size || "Estate size is not confirmed."}`
                : "Buyer profile unknown. Create or enrich the buyer record before relying on relationship assumptions.",
            )}
          />
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <PackList title="Likely priorities" items={buyerDrivers} />
            <PackList title="Compliance drivers" items={complianceDrivers} />
            <PackList title="Procurement drivers" items={listOrFallback(buyerProfile?.procurement_drivers, ["Procurement drivers unknown. Confirm route, evaluation weighting and incumbent position."])} />
            <PackList title="Decision criteria" items={listOrFallback(buyerProfile?.decision_criteria, ["Decision criteria unknown. Confirm price, quality, compliance, social value and mobilisation weighting."])} />
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <DetailField label="Relationship status" value={buyerProfile?.relationship_status || "Unknown - confirm CRM relationship owner"} />
            <DetailField label="Next best action" value={buyerProfile?.next_best_action || "Identify buyer contact, procurement owner and estates sponsor."} />
          </div>
        </OpportunityPackSection>

        <OpportunityPackSection title="Tender Intelligence" subtitle="Tender status, likely scope, source signals and missing bid information.">
          <div className="grid gap-4 md:grid-cols-2">
            <ConfidenceFieldCompact field={fieldByName(fields, "stage")} label="Likely stage" />
            <DetailField label="Deadline" value={opportunity.submission_deadline ? shortDate(opportunity.submission_deadline) : "Unknown - no deadline found in current sources"} />
            <ConfidenceFieldCompact field={fieldByName(fields, "forecast_start_month")} label="Expected start date" />
            <DetailField label="Source signals" value={matchingSignals.length > 0 ? `${matchingSignals.length} related market signal${matchingSignals.length === 1 ? "" : "s"}` : sourceStatus} />
          </div>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <PackList title="Likely scope" items={likelyScope} />
            <PackList title="Missing documents" items={deriveMissingDocuments(unknowns)} />
            <PackList title="Clarification questions needed" items={deriveClarificationQuestions(opportunity, unknowns)} />
            <PackList title="Source signals" items={listOrFallback(matchingSignals.map((signal) => `${signal.buyer_name}: ${signal.title}`), ["No related market signals loaded. Attach source notice, portal result or approved research evidence."])} />
          </div>
        </OpportunityPackSection>

        <OpportunityPackSection title="Competitor Intelligence" subtitle="Incumbent clues, likely posture and counter-strategy.">
          <div className="grid gap-4 md:grid-cols-2">
            <PackList title="Likely competitors" items={competitorNames} />
            <PackList title="Incumbent clues" items={listOrFallback([fieldByName(fields, "incumbent_supplier")?.displayValue].filter(Boolean) as string[], ["Incumbent unknown. Check award notices, buyer portal, CRM notes and prior framework data."])} />
            <PackList title="Likely competitor posture" items={listOrFallback(matchingCompetitors.map((competitor) => `${competitor.name}: ${competitor.pricing_behaviour || "Pricing posture unknown"}`), [enrichment?.competitor_assessment || "Competitor posture unknown. Confirm incumbent, regional specialists and national FM bidders."])} />
            <PackList title="Counter-strategy" items={listOrFallback(matchingCompetitors.map((competitor) => competitor.counter_strategy).filter(Boolean), ["Lead with compliance assurance, self-delivery control, mobilisation confidence and whole-estate evidence."])} />
          </div>
          <div className="mt-4 rounded-md border border-white/10 bg-[#111a20] p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-semibold text-white">Threat level</p>
              <StatusPill tone={threatTone(highestThreat)} label={highestThreat} />
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-400">
              {firstUsefulText(enrichment?.competitor_assessment, "Threat level is inferred from current competitor records and should be validated before bid strategy is locked.")}
            </p>
          </div>
        </OpportunityPackSection>

        <OpportunityPackSection title="Self-Delivery Intelligence" subtitle="Fit for Mitie Fire & Security delivery and leakage prevention.">
          <div className="grid gap-4 md:grid-cols-2">
            <ConfidenceFieldCompact field={fieldByName(fields, "self_delivery_fit")} label="Internal capability fit" />
            <PackMetricCard label="Leakage risk" value={opportunity.self_delivery_capture ? "High capture opportunity" : "Needs review"} detail={opportunity.self_delivery_capture ? "Strong fit and value should be routed internally." : "Confirm whether scope can be self-delivered before third-party route is assumed."} tone={opportunity.self_delivery_capture ? "green" : "amber"} />
            <PackList title="Relevant disciplines" items={deriveDisciplines(likelyScope)} />
            <PackList title="Operations input required" items={deriveOperationsInputs(opportunity, unknowns)} />
          </div>
          <PackNarrativeCard
            label="Recommended Mitie delivery route"
            text={firstUsefulText(enrichment?.self_delivery_assessment, "Route Fire & Security disciplines to Mitie delivery leads, validate regional engineering coverage and challenge any third-party leakage before pricing.")}
          />
        </OpportunityPackSection>

        <OpportunityPackSection title="Risk And Controls" subtitle="Commercial, mobilisation, compliance and margin risks with mitigation actions.">
          <div className="grid gap-4 md:grid-cols-2">
            <PackList title="Commercial risks" items={commercialRisks} />
            <PackList title="Mobilisation risks" items={mobilisationRisks} />
            <PackList title="Asset data risks" items={["Asset count, condition, age, cause-and-effect data and service history must be confirmed before final pricing."]} />
            <PackList title="Compliance risks" items={listOrFallback(enrichment?.compliance_drivers, ["Confirm statutory inspection history, remedial backlog and critical life-safety obligations."])} />
            <PackList title="Margin risks" items={opportunity.margin_warning ? ["Margin warning active. Recheck labour assumptions, specialist subcontract exposure and risk allowance."] : ["No margin warning active, but validate cost build and self-delivery assumptions."]} />
            <PackList title="Mitigation actions" items={recommendedSteps} />
          </div>
        </OpportunityPackSection>

        <OpportunityPackSection title="Executive Actions" subtitle="Clear leadership and functional actions for the next control point.">
          <div className="grid gap-3">
            <ExecutivePackAction role="MD attention required" action={deriveRoleAction("MD", relatedActions, opportunity, recommendedSteps)} tone={opportunity.strategic_must_win ? "green" : "cyan"} />
            <ExecutivePackAction role="Finance attention required" action={deriveRoleAction("Finance", relatedActions, opportunity, recommendedSteps, openForecast)} tone={opportunity.margin_warning ? "amber" : "green"} />
            <ExecutivePackAction role="Sales Director action" action={deriveRoleAction("Sales", relatedActions, opportunity, recommendedSteps)} tone="cyan" />
            <ExecutivePackAction role="Bid team action" action={deriveRoleAction("Bid", relatedActions, opportunity, recommendedSteps)} tone={opportunity.deadline_warning ? "red" : "amber"} />
            <ExecutivePackAction role="Commercial review" action={deriveRoleAction("Commercial", relatedActions, opportunity, recommendedSteps)} tone="amber" />
            <ExecutivePackAction role="Operations input" action={deriveRoleAction("Operations", relatedActions, opportunity, recommendedSteps)} tone="green" />
          </div>
        </OpportunityPackSection>
      </div>

      <OpportunityPackSection
        title="Evidence And Confidence"
        subtitle="Every important field is labelled as actual, inferred, estimated, unknown or needs confirmation."
        action={<StatusPill tone={confidenceTone(confidenceSummary.score)} label={`${percentage(confidenceSummary.score)} average confidence`} />}
      >
        {enrichmentState.status === "loading" ? (
          <div className="mb-4 rounded-md border border-cyan-300/20 bg-cyan-400/10 p-4">
            <div className="flex items-center gap-3 text-sm font-semibold text-cyan-100">
              <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
              Loading stored enrichment pack...
            </div>
            <div className="mt-4 grid gap-2">
              <SkeletonLine className="h-3 w-full rounded-full" />
              <SkeletonLine className="h-3 w-4/5 rounded-full" />
            </div>
          </div>
        ) : null}
        {enrichmentState.status === "error" ? (
          <div className="mb-4 rounded-md border border-amber-300/20 bg-amber-400/10 p-4 text-sm leading-6 text-amber-100">
            Enrichment record could not be loaded. MiSi is showing field evidence and fallback analysis. {enrichmentState.message}
          </div>
        ) : null}
        {fieldState.status === "loading" ? (
          <div className="mb-4 rounded-md border border-cyan-300/20 bg-cyan-400/10 p-4">
            <div className="flex items-center gap-3 text-sm font-semibold text-cyan-100">
              <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
              Loading field evidence...
            </div>
            <div className="mt-4 grid gap-2">
              <SkeletonLine className="h-3 w-11/12 rounded-full" />
              <SkeletonLine className="h-3 w-2/3 rounded-full" />
            </div>
          </div>
        ) : null}
        {fieldState.status === "error" ? (
          <div className="mb-4 rounded-md border border-amber-300/20 bg-amber-400/10 p-4 text-sm leading-6 text-amber-100">
            Field evidence could not be loaded. MiSi is showing inferred local explanations instead. {fieldState.message}
          </div>
        ) : null}

        <div className="grid gap-5 xl:grid-cols-[360px_minmax(0,1fr)]">
          <div className="grid content-start gap-4">
            <PackList title="Source links" items={sourceLinks.length > 0 ? sourceLinks.map((source) => source.title || source.url) : ["No source URLs attached. Add approved evidence before bid governance."]} />
            <PackList title="Known fields" items={fieldNamesByType(fields, ["known", "user_provided", "system_calculated"])} />
            <PackList title="Inferred fields" items={fieldNamesByType(fields, ["inferred"])} />
            <PackList title="Estimated fields" items={fieldNamesByType(fields, ["estimated"])} />
            <PackList title="Unknowns" items={unknowns} />
            <PackList title="Recommended next research steps" items={recommendedSteps} />
          </div>
          <div className="grid gap-3">
            {fields.map((field) => (
              <ConfidenceFieldCard
                key={field.fieldName}
                field={field}
                accepted={acceptedFieldNames.has(field.fieldName)}
                editing={editingFieldName === field.fieldName}
                onAccept={() => onAcceptField(field.fieldName)}
                onEdit={() => onEditField(field.fieldName)}
                onCancelEdit={onCancelEdit}
                onSaveEdit={(value) => onSaveFieldEdit(field.fieldName, value)}
              />
            ))}
          </div>
        </div>
      </OpportunityPackSection>
    </div>
  );
}

function PackNarrativeCard({
  label,
  text,
  accent = false,
}: {
  label: string;
  text: string;
  accent?: boolean;
}) {
  return (
    <article className={`rounded-md border p-4 ${accent ? "border-mitie-lime/25 bg-mitie-lime/10" : "border-white/10 bg-[#111a20]"}`}>
      <p className="text-xs font-black uppercase text-slate-500">{label}</p>
      <p className={`mt-3 text-sm font-semibold leading-6 ${accent ? "text-mitie-lime" : "text-slate-200"}`}>{text}</p>
    </article>
  );
}

function OpportunityPackSection({
  title,
  subtitle,
  action,
  children,
}: {
  title: string;
  subtitle: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="rounded-lg border border-white/10 bg-[#0d151a] shadow-[0_20px_70px_rgba(0,0,0,0.24)]">
      <div className="flex min-h-16 flex-col gap-3 border-b border-white/10 px-4 py-4 sm:flex-row sm:items-start sm:justify-between sm:px-5">
        <div>
          <h3 className="text-base font-semibold text-white sm:text-lg">{title}</h3>
          <p className="mt-1 text-sm leading-5 text-slate-500">{subtitle}</p>
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
      <div className="p-4 sm:p-5">{children}</div>
    </section>
  );
}

function PackMetricCard({
  label,
  value,
  detail,
  tone,
}: {
  label: string;
  value: string;
  detail: string;
  tone: Tone;
}) {
  return (
    <article className={`rounded-md border p-4 ${toneClasses[tone]}`}>
      <p className="text-sm font-semibold text-slate-300">{label}</p>
      <p className="mt-2 text-xl font-semibold leading-7 text-white">{value}</p>
      <p className="mt-2 text-xs leading-5 text-slate-300">{detail}</p>
    </article>
  );
}

function PackList({ title, items }: { title: string; items: string[] }) {
  const visibleItems = items.length > 0 ? items : ["Unknown - confirm with approved source evidence."];
  return (
    <div className="rounded-md border border-white/10 bg-[#111a20] p-4">
      <p className="text-xs font-black uppercase text-slate-500">{title}</p>
      <ul className="mt-3 grid gap-2">
        {visibleItems.map((item) => (
          <li key={item} className="flex gap-2 text-sm leading-6 text-slate-300">
            <CheckCircle2 aria-hidden="true" className="mt-1 h-4 w-4 shrink-0 text-mitie-lime" />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ExecutivePackAction({
  role,
  action,
  tone,
}: {
  role: string;
  action: string;
  tone: Tone;
}) {
  return (
    <article className="rounded-md border border-white/10 bg-[#111a20] p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm font-semibold text-white">{role}</p>
        <StatusPill tone={tone} label="Action" />
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-300">{action}</p>
    </article>
  );
}

function firstUsefulText(...values: Array<string | null | undefined>) {
  return (
    values.find((value) => typeof value === "string" && value.trim().length > 0)?.trim() ??
    "Unknown - MiSi needs more source evidence before this can be treated as confirmed."
  );
}

function listOrFallback(...lists: Array<string[] | null | undefined>) {
  for (const list of lists) {
    const cleaned = uniqueSorted(
      (list ?? [])
        .map((item) => (typeof item === "string" ? item.trim() : ""))
        .filter(Boolean),
    );
    if (cleaned.length > 0) {
      return cleaned;
    }
  }

  return ["Unknown - confirm with approved source evidence."];
}

function splitLikelyScope(value: string | null | undefined) {
  if (!value?.trim()) {
    return [];
  }

  return value
    .split(/[;\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function findBuyerProfileForOpportunity(
  buyers: BuyerProfile[],
  opportunity: Opportunity,
) {
  const buyerName = opportunity.buyer_name.toLowerCase();
  return (
    buyers.find((buyer) => buyer.buyer_name.toLowerCase() === buyerName) ??
    buyers.find(
      (buyer) =>
        buyer.sector === opportunity.sector &&
        (!opportunity.region || buyer.region === opportunity.region),
    ) ??
    null
  );
}

function findCompetitorsForOpportunity(
  competitors: CompetitorProfile[],
  opportunity: Opportunity,
) {
  const sector = opportunity.sector.toLowerCase();
  return competitors
    .filter((competitor) =>
      competitor.sectors.some((item) => item.toLowerCase() === sector),
    )
    .slice(0, 4);
}

function findMarketSignalsForOpportunity(
  marketSignals: MarketSignal[],
  opportunity: Opportunity,
) {
  const buyerName = opportunity.buyer_name.toLowerCase();
  return marketSignals
    .filter((signal) => {
      const signalBuyer = signal.buyer_name.toLowerCase();
      return (
        signalBuyer === buyerName ||
        signalBuyer.includes(buyerName) ||
        buyerName.includes(signalBuyer) ||
        (signal.sector === opportunity.sector && signal.region === opportunity.region)
      );
    })
    .slice(0, 4);
}

function collectEvidenceLinks(fields: IntelligenceFieldView[]) {
  const links = new Map<string, { url: string; title: string }>();
  fields.forEach((field) => {
    field.sourceUrls.forEach((url, index) => {
      if (!url.trim() || links.has(url)) {
        return;
      }
      links.set(url, {
        url,
        title: field.sourceTitles[index] || `${field.label} source`,
      });
    });
  });
  return Array.from(links.values());
}

function deriveMissingDocuments(unknowns: string[]) {
  const combined = unknowns.join(" ").toLowerCase();
  const documents = [
    combined.includes("deadline") || combined.includes("timetable")
      ? "Tender timetable and submission deadline"
      : "",
    combined.includes("asset") || combined.includes("scope")
      ? "Asset register, scope schedule and service specification"
      : "",
    combined.includes("incumbent")
      ? "Incumbent supplier evidence and current contract expiry"
      : "",
    combined.includes("margin") || combined.includes("value")
      ? "Commercial model, pricing assumptions and value evidence"
      : "",
  ].filter(Boolean);

  return listOrFallback(documents, [
    "Tender notice, specification, asset schedule, pricing schedule, mobilisation requirements and evaluation criteria.",
  ]);
}

function deriveClarificationQuestions(
  opportunity: Opportunity,
  unknowns: string[],
) {
  const questions = [
    "What exact fire and security disciplines are in scope, and what asset volumes apply?",
    "Is there a confirmed procurement route, framework or direct tender timetable?",
    "Who is the incumbent supplier and what is the current service performance position?",
    opportunity.margin_warning
      ? "Which cost assumptions must be challenged to restore target margin?"
      : "What commercial risks should be priced before final review?",
    unknowns.length > 0
      ? `Which unknowns can the buyer or source documents resolve first: ${unknowns.slice(0, 2).join("; ")}?`
      : "",
  ].filter(Boolean);

  return listOrFallback(questions);
}

function deriveDisciplines(likelyScope: string[]) {
  const scopeText = likelyScope.join(" ").toLowerCase();
  const matchedDisciplines = researchFilterOptions.disciplines.filter((discipline) =>
    scopeText.includes(discipline.toLowerCase()),
  );

  return listOrFallback(
    matchedDisciplines,
    likelyScope,
    ["Fire Alarms, Emergency Lighting, Extinguishers, CCTV, Access Control and Fire Risk Assessments should be confirmed against the scope."],
  );
}

function deriveOperationsInputs(opportunity: Opportunity, unknowns: string[]) {
  return listOrFallback([
    "Confirm regional engineering capacity, call-out model and mobilisation lead.",
    "Validate specialist subcontract exposure, access constraints and critical asset coverage.",
    opportunity.self_delivery_capture
      ? "Confirm self-delivery route before third-party leakage is priced into the bid."
      : "Assess whether scope can be routed to Mitie Fire & Security before bid/no-bid.",
    unknowns.some((item) => item.toLowerCase().includes("asset"))
      ? "Resolve asset register gaps before final pricing."
      : "",
  ]);
}

function deriveRoleAction(
  role: string,
  relatedActions: ExecutiveAction[],
  opportunity: Opportunity,
  recommendedSteps: string[],
  openForecast?: OpenForecastItem,
) {
  const roleMatch = relatedActions.find((action) =>
    [action.owner, action.category, action.reason, action.recommended_action]
      .join(" ")
      .toLowerCase()
      .includes(role.toLowerCase()),
  );
  if (roleMatch?.recommended_action) {
    return roleMatch.recommended_action;
  }

  const firstStep = recommendedSteps[0] || "Confirm source evidence and next commercial gate.";
  const roleKey = role.toLowerCase();
  if (roleKey.includes("md")) {
    return opportunity.strategic_must_win
      ? "Assign executive sponsor and confirm must-win governance before bid resources are committed."
      : firstStep;
  }
  if (roleKey.includes("finance")) {
    return openForecast
      ? `Review ${compactCurrency(openForecast.risk_adjusted_revenue)} risk-adjusted forecast, margin and probability weighting.`
      : "Create or validate LE1 forecast line, probability weighting, risk adjustment and margin assumptions.";
  }
  if (roleKey.includes("sales")) {
    return "Confirm buyer access, relationship owner, decision criteria and close plan.";
  }
  if (roleKey.includes("bid")) {
    return opportunity.deadline_warning
      ? "Escalate timetable, clarification ownership and final review readiness today."
      : "Confirm bid/no-bid evidence, clarifications and governance dates.";
  }
  if (roleKey.includes("commercial")) {
    return "Validate value, margin, risk transfer, scope exclusions and self-delivery assumptions.";
  }
  if (roleKey.includes("operations")) {
    return "Confirm mobilisation plan, engineering capacity, asset data quality and delivery route.";
  }

  return firstStep;
}

function fieldNamesByType(
  fields: IntelligenceFieldView[],
  valueTypes: FieldIntelligence["value_type"][],
) {
  const names = fields
    .filter((field) => valueTypes.includes(field.valueType))
    .map((field) => `${field.label} (${percentage(field.confidenceScore)})`);
  return listOrFallback(names, ["No fields in this category yet."]);
}

function OpportunityAnalysisPanel({ analysis }: { analysis: OpportunityAIAnalysis }) {
  return (
    <div className="mt-4 grid gap-4">
      <div className="rounded-md border border-white/10 bg-[#111a20] p-4">
        <div className="flex flex-wrap items-center gap-2">
          <RiskPill risk={analysis.risk_rating} />
          <StatusPill tone={analysis.competitor_threat === "High" ? "red" : analysis.competitor_threat === "Medium" ? "amber" : "green"} label={`${analysis.competitor_threat} competitor threat`} />
          <StatusPill tone="cyan" label={analysis.bid_no_bid_recommendation} />
        </div>
        <h4 className="mt-4 text-sm font-semibold text-white">Executive Summary</h4>
        <p className="mt-2 text-sm leading-6 text-slate-300">{analysis.executive_summary}</p>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <MiniMetric label="Strategic fit score" value={`${Math.round(analysis.strategic_fit_score)}/100`} />
        <MiniMetric label="Win probability" value={percentage(analysis.win_probability)} />
        <MiniMetric label="Risk rating" value={analysis.risk_rating} danger={analysis.risk_rating === "Red"} />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <DetailField label="Bid / no-bid recommendation" value={analysis.bid_no_bid_recommendation} />
        <DetailField label="Competitor threat" value={analysis.competitor_threat} />
      </div>

      <DetailField label="Margin commentary" value={analysis.margin_commentary} />
      <DetailList title="Buyer drivers" items={analysis.likely_buyer_drivers} />
      <DetailList title="Mobilisation risks" items={analysis.mobilisation_risks} />
      <DetailList title="Commercial risks" items={analysis.commercial_risks} />
      <DetailField label="Self-delivery assessment" value={analysis.self_delivery_assessment} />
      <DetailField label="Recommended action" value={analysis.recommended_action} />
    </div>
  );
}

function buildResearchPayload(
  request: ResearchWorkspaceRequest,
  createOpportunity: boolean,
): ResearchOpportunityRequest {
  const context = [
    request.filters.sector ? `sector: ${request.filters.sector}` : "",
    request.filters.region ? `region: ${request.filters.region}` : "",
    request.filters.discipline ? `discipline: ${request.filters.discipline}` : "",
    request.filters.buyerType ? `buyer type: ${request.filters.buyerType}` : "",
    request.filters.minimumValue
      ? `minimum commercial value: GBP ${request.filters.minimumValue}`
      : "",
  ].filter(Boolean);
  const query =
    context.length > 0
      ? `${request.query}. Research context filters: ${context.join("; ")}.`
      : request.query;

  return {
    query,
    sector_hint: request.filters.sector || undefined,
    region_hint: request.filters.region || undefined,
    buyer_hint: request.filters.buyerType || undefined,
    create_opportunity: createOpportunity,
  };
}

function getOpportunityAnalysisErrorMessage(error: unknown): string {
  const fallback =
    "The backend could not complete the structured analysis. Check the API is running and retry.";
  if (!(error instanceof Error)) {
    return fallback;
  }

  if (isOpenAIQuotaError(error.message)) {
    return "OpenAI accepted the backend key, but the project has insufficient quota. Add billing or credits to the OpenAI project attached to OPENAI_API_KEY, restart FastAPI, then rerun the analysis. The browser never receives the key.";
  }

  if (error.message.includes("OpenAI analysis is not configured")) {
    return "AI analysis is not configured yet. Add OPENAI_API_KEY to the backend environment, restart FastAPI, then rerun analysis. MiSi can still show rule-based fit, risk and next action while the key is missing. Never put OpenAI keys in frontend code.";
  }

  if (
    error.message.includes("OpenAI analysis request failed") ||
    error.message.includes("OpenAI opportunity analysis request failed") ||
    error.message.includes("OPENAI_MODEL")
  ) {
    return "MiSi could not complete the structured opportunity analysis. Confirm the backend has a valid OPENAI_API_KEY, the selected OPENAI_MODEL is available to that key, then restart FastAPI and rerun the analysis. The opportunity pack remains usable with rule-based confidence and field evidence.";
  }

  if (error.message.includes("Failed to fetch") || error.message.includes("fetch failed")) {
    return "MiSi could not reach the backend API. Start FastAPI, confirm /health returns OK, then retry the analysis.";
  }

  return error.message || fallback;
}

function getExecutiveBriefingErrorMessage(error: unknown): string {
  const fallback =
    "The backend could not complete the leadership briefing. Check the API is running and retry.";
  if (!(error instanceof Error)) {
    return fallback;
  }

  if (isOpenAIQuotaError(error.message)) {
    return "OpenAI accepted the backend key, but the project has insufficient quota. Add billing or credits to the OpenAI project attached to OPENAI_API_KEY, restart FastAPI, then generate the leadership briefing again.";
  }

  if (error.message.includes("OpenAI analysis is not configured")) {
    return "Leadership briefing AI is not configured yet. Add OPENAI_API_KEY to the backend environment and restart FastAPI. The dashboard and report export still work without a key; AI briefing waits until the backend can call OpenAI.";
  }

  if (
    error.message.includes("OpenAI executive summary request failed") ||
    error.message.includes("OPENAI_MODEL")
  ) {
    return "MiSi could not generate the leadership briefing because the backend OpenAI request failed. Confirm OPENAI_API_KEY is valid, the selected OPENAI_MODEL is available to that key, then restart FastAPI and rerun the briefing from current dashboard data.";
  }

  if (error.message.includes("Failed to fetch") || error.message.includes("fetch failed")) {
    return "MiSi could not reach the backend API. Start FastAPI, confirm /health returns OK, then retry the briefing.";
  }

  return error.message || fallback;
}

function getInternetResearchErrorMessage(error: unknown): string {
  const fallback =
    "The backend could not complete the internet intelligence scan. Check the API is running and retry.";
  if (!(error instanceof Error)) {
    return fallback;
  }

  if (isOpenAIQuotaError(error.message)) {
    return "OpenAI accepted the backend key, but the project has insufficient quota. Add billing or credits to the OpenAI project attached to OPENAI_API_KEY, restart FastAPI, then rerun the internet scan.";
  }

  if (error.message.includes("OpenAI analysis is not configured")) {
    return "Internet intelligence is not configured yet. Add OPENAI_API_KEY to the backend environment and restart FastAPI. The browser never receives OpenAI keys; MiSi only sends research requests through the backend.";
  }

  if (
    error.message.includes("OpenAI internet intelligence request failed") ||
    error.message.includes("OPENAI_MODEL")
  ) {
    return "Internet intelligence could not complete because the backend OpenAI request failed. Confirm the backend has a valid OPENAI_API_KEY, the selected OPENAI_MODEL is available to that key, then restart FastAPI and rerun with a specific buyer, sector or discipline phrase.";
  }

  if (error.message.includes("Failed to fetch") || error.message.includes("fetch failed")) {
    return "MiSi could not reach the backend API. Start FastAPI, confirm /health returns OK, then retry the internet scan.";
  }

  if (error.message.toLowerCase().includes("invalid structured json")) {
    return "The internet scan returned weak or malformed structured output. Try a narrower buyer, sector, region or discipline phrase so MiSi can attach stronger evidence and confidence.";
  }

  return error.message || fallback;
}

function getOpportunityResearchErrorMessage(error: unknown): string {
  const fallback =
    "The backend could not complete standing-start opportunity research. Check the API is running and retry.";
  if (!(error instanceof Error)) {
    return fallback;
  }

  if (isOpenAIQuotaError(error.message)) {
    return "OpenAI accepted the backend key, but the project has insufficient quota. Add billing or credits to the OpenAI project attached to OPENAI_API_KEY, restart FastAPI, then rerun the research. The browser never receives the key.";
  }

  if (error.message.includes("OpenAI analysis is not configured")) {
    return "AI opportunity research is not configured yet. Add OPENAI_API_KEY to the backend environment and restart FastAPI. MiSi can still show existing dashboard intelligence; standing-start research begins once the backend can call OpenAI.";
  }

  if (
    error.message.includes("OpenAI standing-start opportunity research failed") ||
    error.message.includes("OpenAI opportunity research request failed") ||
    error.message.includes("OPENAI_MODEL")
  ) {
    return "MiSi could not complete the AI research request. Confirm the backend has a valid OPENAI_API_KEY, the selected OPENAI_MODEL is available to that key, then restart FastAPI and try a specific buyer, sector, region or discipline phrase. The browser never receives the key.";
  }

  if (error.message.includes("Failed to fetch") || error.message.includes("fetch failed")) {
    return "MiSi could not reach the backend API. Start FastAPI, confirm /health returns OK, then retry opportunity research.";
  }

  if (error.message.toLowerCase().includes("invalid structured json")) {
    return "MiSi received weak or invalid structured research output. Tighten the research brief with a buyer, sector, region, discipline or known source, then rerun so unknowns can be labelled properly.";
  }

  return error.message || fallback;
}

function getChatGPTAssistErrorMessage(error: unknown): string {
  const fallback =
    "MiSi could not complete the ChatGPT Assist workflow. Check the backend API and retry.";
  if (!(error instanceof Error)) {
    return fallback;
  }

  if (
    error.message.includes("not valid MiSi structured JSON") ||
    error.message.toLowerCase().includes("json")
  ) {
    return "The pasted ChatGPT result was not valid MiSi JSON. Ask ChatGPT to return JSON only, with no markdown fence or explanation, then paste the full object back into MiSi.";
  }

  if (error.message.includes("Failed to fetch") || error.message.includes("fetch failed")) {
    return "MiSi could not reach the backend API. Start FastAPI, confirm /health returns OK, then retry ChatGPT Assist.";
  }

  return error.message || fallback;
}

function getAutofillErrorMessage(error: unknown): string {
  const fallback =
    "The backend could not complete the bulk intelligence autofill. Check the API is running and retry.";
  if (!(error instanceof Error)) {
    return fallback;
  }

  if (isOpenAIQuotaError(error.message)) {
    return "OpenAI accepted the backend key, but the project has insufficient quota. Add billing or credits to the OpenAI project attached to OPENAI_API_KEY, restart FastAPI, then rerun the autofill.";
  }

  if (error.message.includes("OpenAI analysis is not configured")) {
    return "Bulk AI autofill is not configured yet. Add OPENAI_API_KEY to the backend environment and restart FastAPI. Existing dashboard data remains available; autofill waits for backend-only OpenAI access.";
  }

  if (error.message.includes("Failed to fetch") || error.message.includes("fetch failed")) {
    return "MiSi could not reach the backend API. Start FastAPI, confirm /health returns OK, then retry the autofill run.";
  }

  return error.message || fallback;
}

function isOpenAIQuotaError(message: string): boolean {
  const lowerMessage = message.toLowerCase();
  return (
    lowerMessage.includes("insufficient quota") ||
    lowerMessage.includes("insufficient_quota") ||
    lowerMessage.includes("exceeded your current quota")
  );
}

function getMarketSignalConversionErrorMessage(error: unknown): string {
  const fallback =
    "MiSi could not convert this market signal. Check the backend API and retry.";
  if (!(error instanceof Error)) {
    return fallback;
  }

  if (error.message.includes("not found")) {
    return "This market signal no longer exists in the backend dataset. Refresh the dashboard and try another signal.";
  }

  if (error.message.includes("Failed to fetch") || error.message.includes("fetch failed")) {
    return "MiSi could not reach the backend API. Confirm FastAPI is running, then retry conversion.";
  }

  return error.message || fallback;
}

function getReportExportErrorMessage(error: unknown): string {
  const fallback =
    "The backend could not generate the executive report. Check the API is running and retry.";
  if (!(error instanceof Error)) {
    return fallback;
  }

  if (error.message.includes("Failed to fetch") || error.message.includes("fetch failed")) {
    return "MiSi could not reach the backend API. Confirm the FastAPI server is running, then retry the executive report export.";
  }

  return error.message || fallback;
}

function internetTypeLabel(value: InternetIntelligenceType): string {
  return (
    internetIntelligenceTypes.find((item) => item.value === value)?.label ??
    "Internet Intelligence"
  );
}

function DetailField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-semibold text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-semibold leading-6 text-slate-200">{value}</p>
    </div>
  );
}

function DetailList({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) {
    return null;
  }

  return (
    <div className="mt-4">
      <h4 className="text-xs font-semibold text-slate-500">{title}</h4>
      <ul className="mt-2 grid gap-2">
        {items.map((item) => (
          <li key={item} className="flex gap-2 text-sm leading-6 text-slate-300">
            <CheckCircle2 aria-hidden="true" className="mt-1 h-4 w-4 shrink-0 text-mitie-lime" />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function PipelineChart({
  revenue,
  margin,
  tall = false,
}: {
  revenue: ForecastPoint[];
  margin: ForecastPoint[];
  tall?: boolean;
}) {
  const monthRows = useMemo(() => mergeForecastSeries(revenue, margin), [revenue, margin]);
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
      <div className={`flex min-w-[520px] items-end gap-2 ${tall ? "h-96" : "h-64"} pb-1`}>
        {monthRows.map((item) => {
          const revenueHeight = (item.revenue / maxValue) * 100;
          const marginHeight = (item.margin / maxValue) * 100;

          return (
            <div key={item.month} className="flex h-full min-w-9 flex-1 flex-col justify-end gap-2">
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
              <div className="text-center text-xs font-semibold text-slate-500">{monthLabel(item.month)}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function MarginChart({
  dashboard,
  financeSummary,
}: {
  dashboard: DashboardSummary;
  financeSummary: FinanceForecastSummary;
}) {
  return (
    <Panel title="Margin Position" action={<StatusPill tone={dashboard.average_margin_percentage < 25 ? "red" : "green"} label={percentageValue(dashboard.average_margin_percentage)} />}>
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
          value={financeSummary.open_weighted_revenue > 0 ? percentageValue(financeSummary.open_weighted_margin / financeSummary.open_weighted_revenue) : "0%"}
          width={financeSummary.open_weighted_revenue > 0 ? Math.min((financeSummary.open_weighted_margin / financeSummary.open_weighted_revenue) * 100, 100) : 0}
        />
      </div>
      <div className="mt-5 rounded-md border border-amber-300/20 bg-amber-400/10 p-4">
        <p className="text-sm font-semibold text-amber-100">
          {financeSummary.margin_warnings.length} margin warning{financeSummary.margin_warnings.length === 1 ? "" : "s"}
        </p>
        <p className="mt-2 text-sm leading-5 text-amber-100/75">
          Review opportunities below threshold before final pricing or submission.
        </p>
      </div>
    </Panel>
  );
}

function MarketSignalsPanel({
  marketSignals,
  compact = false,
}: {
  marketSignals: MarketSignal[];
  compact?: boolean;
}) {
  return (
    <Panel title="Market Signals" action={<StatusPill tone="cyan" label={`${marketSignals.length} shown`} />}>
      {marketSignals.length > 0 ? (
        <div className="divide-y divide-white/10">
          {marketSignals.map((signal) => (
            <article key={signal.id} className="py-4 first:pt-0 last:pb-0">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-white">{signal.buyer_name}</p>
                  <p className="mt-1 text-sm text-slate-500">{signal.sector}</p>
                </div>
                <StatusPill tone={confidenceTone(signal.confidence_score)} label={`${Math.round(signal.confidence_score * 100)}%`} />
              </div>
              <p className="mt-3 text-sm leading-6 text-slate-300">{signal.title}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                <StatusPill tone={fitToneForSignal(signal.likely_mitie_fit)} label={`${signal.likely_mitie_fit || "Unknown"} fit`} />
                <StatusPill tone="cyan" label={signal.estimated_value == null ? "Value unknown" : compactCurrency(signal.estimated_value)} />
              </div>
              {!compact ? (
                <>
                  <p className="mt-2 text-sm leading-6 text-slate-500">{signal.suggested_action}</p>
                  <p className="mt-2 text-xs leading-5 text-slate-500">
                    {signal.ai_rationale || "Rationale not yet attached; convert or refresh the signal to create a fuller pack."}
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

function ExecutiveActionsList({
  actions,
  title,
  expanded = false,
}: {
  actions: ExecutiveAction[];
  title: string;
  expanded?: boolean;
}) {
  return (
    <Panel title={title} action={<StatusPill tone="red" label={`${actions.length} actions`} />}>
      {actions.length > 0 ? (
        <div className="grid gap-3">
          {actions.map((item) => (
            <div
              key={item.id}
              className={`grid gap-3 rounded-md border border-white/10 bg-[#111a20] p-4 ${
                expanded ? "md:grid-cols-[80px_130px_minmax(0,1fr)_150px_120px]" : ""
              }`}
            >
              <div className="text-sm font-black text-red-200">{item.priority.toUpperCase()}</div>
              <div className="text-sm font-semibold text-slate-300">{item.category}</div>
              <div>
                <p className="text-sm font-semibold text-white">{item.recommended_action}</p>
                <p className="mt-1 text-sm text-slate-500">{item.reason}</p>
              </div>
              {expanded ? <div className="text-sm text-slate-300">Due {shortDate(item.due_date)}</div> : null}
              {expanded ? <div className="text-sm font-semibold text-white">{item.commercial_value == null ? "Value TBC" : currency(item.commercial_value)}</div> : null}
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

function DashboardLoading() {
  return (
    <div className="grid gap-5">
      <section className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-4" aria-label="Loading KPIs">
        {["Pipeline", "Weighted", "Margin", "Risk"].map((label) => (
          <div key={label} className="rounded-lg border border-white/10 bg-white/[0.04] p-4">
            <SkeletonLine className="h-4 w-24 rounded-full" />
            <SkeletonLine className="mt-5 h-9 w-32 rounded-full" />
            <SkeletonLine className="mt-5 h-3 w-40 rounded-full" />
          </div>
        ))}
      </section>
      <Panel title="Preparing The Command Centre" action={<Loader2 aria-hidden="true" className="h-5 w-5 animate-spin text-cyan-200" />}>
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
          <div className="grid gap-3">
            <p className="text-sm font-semibold text-white">MiSi is loading pipeline, market signals, finance forecast and executive actions.</p>
            <SkeletonLine className="h-3 rounded-full" />
            <SkeletonLine className="h-3 w-5/6 rounded-full" />
            <SkeletonLine className="h-3 w-2/3 rounded-full" />
          </div>
          <div className="rounded-md border border-cyan-300/20 bg-cyan-400/10 p-4">
            <p className="text-xs font-black uppercase text-cyan-100">While loading</p>
            <p className="mt-2 text-sm leading-6 text-cyan-100/75">
              Empty fields will appear as unknown with a next step, not as silent blanks.
            </p>
          </div>
        </div>
      </Panel>
    </div>
  );
}

function DashboardError({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <Panel title="Backend Connection Error" action={<StatusPill tone="red" label="API unavailable" />}>
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div className="flex gap-3">
          <AlertTriangle aria-hidden="true" className="mt-1 h-5 w-5 shrink-0 text-red-200" />
          <div>
            <p className="text-sm font-semibold text-white">Could not load dashboard data from {getApiBaseUrl()}.</p>
            <p className="mt-2 text-sm leading-6 text-slate-400">{message}</p>
          </div>
        </div>
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-white/10 bg-white px-3 text-sm font-semibold text-[#10171b] transition hover:bg-slate-200"
        >
          <RefreshCw aria-hidden="true" className="h-4 w-4" />
          Retry
        </button>
      </div>
    </Panel>
  );
}

function EmptyState({ title, message }: { title: string; message: string }) {
  return (
    <div className="rounded-md border border-cyan-300/15 bg-[#111a20] p-6 text-center shadow-[0_18px_50px_rgba(0,0,0,0.18)]">
      <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-md border border-cyan-300/20 bg-cyan-400/10 text-cyan-100">
        <MapIcon aria-hidden="true" className="h-5 w-5" />
      </div>
      <p className="mt-4 text-sm font-semibold text-white">{title}</p>
      <p className="mx-auto mt-2 max-w-2xl text-sm leading-6 text-slate-400">{message}</p>
    </div>
  );
}

function SourceRow({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: Tone;
}) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-white/10 pb-3 last:border-0 last:pb-0">
      <div>
        <p className="text-sm font-semibold text-white">{label}</p>
        <p className="mt-1 text-sm text-slate-500">{value}</p>
      </div>
      <StatusPill tone={tone} label={tone === "green" ? "Ready" : tone === "cyan" ? "Available" : "Planned"} />
    </div>
  );
}

function ProgressRow({
  label,
  value,
  width,
}: {
  label: string;
  value: string;
  width: number;
}) {
  return (
    <div>
      <div className="flex items-center justify-between gap-3 text-sm">
        <span className="font-semibold text-slate-300">{label}</span>
        <span className="font-semibold text-white">{value}</span>
      </div>
      <div className="mt-2 h-2 rounded-full bg-white/10">
        <div className="h-2 rounded-full bg-mitie-lime" style={{ width: `${Math.min(Math.max(width, 0), 100)}%` }} />
      </div>
    </div>
  );
}

function buildFilteredDashboardData(
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
  const visibleOpportunityIds = new Set(opportunities.map((opportunity) => opportunity.id));
  const marketSignals = data.marketSignals.filter((signal) =>
    marketSignalMatchesFilters(signal, filters),
  );
  const executiveActions = data.executiveActions
    .filter((action) => executiveActionMatchesFilters(action, filters, visibleOpportunityIds))
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

function buildFilteredDashboardSummary(
  originalDashboard: DashboardSummary,
  opportunities: Opportunity[],
  marketSignals: MarketSignal[],
  executiveActions: ExecutiveAction[],
  filters: DashboardFilters,
): DashboardSummary {
  const liveOpportunities = opportunities.filter(
    (opportunity) => !["Won", "Lost", "Qualified out"].includes(opportunity.stage),
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
      normaliseRiskLabel(opportunity.calculated_risk_rating || opportunity.risk_rating) ===
      "Red",
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

function buildFilteredExecutiveSummaryText({
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

function buildFilterOptions(opportunities: Opportunity[]): FilterOptions {
  return {
    sectors: uniqueSorted(opportunities.map((opportunity) => opportunity.sector)),
    regions: uniqueSorted(opportunities.map((opportunity) => opportunity.region)),
    stages: uniqueSorted(opportunities.map((opportunity) => opportunity.stage)),
    riskRatings: uniqueSorted(
      opportunities.map((opportunity) =>
        normaliseRiskLabel(opportunity.calculated_risk_rating || opportunity.risk_rating),
      ),
    ),
    owners: uniqueSorted(opportunities.map((opportunity) => opportunity.owner)),
  };
}

function opportunityMatchesFilters(
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
    normaliseRiskLabel(opportunity.calculated_risk_rating || opportunity.risk_rating) !==
      filters.riskRating
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

function marketSignalMatchesFilters(
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

function executiveActionMatchesFilters(
  action: ExecutiveAction,
  filters: DashboardFilters,
  visibleOpportunityIds: Set<number>,
): boolean {
  const opportunityScoped =
    filters.sector || filters.region || filters.stage || filters.riskRating || filters.owner;
  if (
    opportunityScoped &&
    action.related_opportunity_id !== null
  ) {
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

function compareExecutiveActions(first: ExecutiveAction, second: ExecutiveAction) {
  const priorityDelta = priorityRank(first.priority) - priorityRank(second.priority);
  if (priorityDelta !== 0) {
    return priorityDelta;
  }

  return (first.due_date ?? "9999-12-31").localeCompare(
    second.due_date ?? "9999-12-31",
  );
}

function priorityRank(priority: string) {
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

function sumBy<T>(items: T[], getValue: (item: T) => number) {
  return items.reduce((total, item) => total + getValue(item), 0);
}

function textMatches(values: string[], search: string) {
  const query = search.trim().toLowerCase();
  if (!query) {
    return true;
  }

  return values.some((value) => value.toLowerCase().includes(query));
}

function uniqueSorted(values: string[]) {
  return Array.from(new Set(values.filter(Boolean))).sort((first, second) =>
    first.localeCompare(second),
  );
}

function activeFilterSummary(filters: DashboardFilters) {
  const labels = [
    filters.sector,
    filters.region,
    filters.stage,
    filters.riskRating,
    filters.owner,
    filters.search ? `"${filters.search}"` : "",
  ].filter(Boolean);

  return labels.length > 0 ? `Filtered view (${labels.join(", ")}).` : "Full view.";
}

function splitSummary(summary: string): string[] {
  const parts = summary
    .split(". ")
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => (part.endsWith(".") ? part : `${part}.`));

  return parts.length > 0 ? parts : ["No executive summary was returned by the backend."];
}

function mergeForecastSeries(revenue: ForecastPoint[], margin: ForecastPoint[]) {
  const valuesByMonth = new Map<string, { month: string; revenue: number; margin: number }>();

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

const opportunityFieldConfigs: Array<{
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
    nextStep: "Confirm the tender title, buyer project name or internal opportunity name.",
  },
  {
    fieldName: "buyer_name",
    label: "Buyer",
    getValue: (opportunity) => opportunity.buyer_name,
    format: textDisplay,
    unknownReason: "Buyer is not confirmed from the source data.",
    nextStep: "Confirm the contracting authority or client from an approved source.",
  },
  {
    fieldName: "sector",
    label: "Sector",
    getValue: (opportunity) => opportunity.sector,
    format: textDisplay,
    unknownReason: "Sector is not confirmed from the source data.",
    nextStep: "Confirm the buyer sector from CRM, tender notice or buyer profile.",
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
    unknownReason: "Annual revenue is not supported by a contract value, term or asset schedule.",
    nextStep: "Confirm contract term, asset count and annual service run-rate.",
  },
  {
    fieldName: "estimated_total_contract_value",
    label: "Contract value",
    getValue: (opportunity) => opportunity.estimated_total_contract_value,
    format: currencyDisplay,
    unknownReason: "Total contract value is not evidenced by public sources or internal tracker data.",
    nextStep: "Validate value against tender notice, spend history or buyer budget.",
  },
  {
    fieldName: "estimated_gross_margin",
    label: "Gross margin",
    getValue: (opportunity) => opportunity.estimated_gross_margin,
    format: currencyDisplay,
    unknownReason: "Gross margin cannot be supported without service mix and delivery assumptions.",
    nextStep: "Model labour mix, subcontract exposure, remedials and SLA assumptions.",
  },
  {
    fieldName: "margin_percentage",
    label: "Margin %",
    getValue: (opportunity) => opportunity.margin_percentage,
    format: percentageDisplay,
    unknownReason: "Margin percentage is not yet supported by pricing or cost assumptions.",
    nextStep: "Confirm pricing model, self-delivery content and commercial walkaway point.",
  },
  {
    fieldName: "probability",
    label: "Win probability",
    getValue: (opportunity) => opportunity.probability,
    format: probabilityDisplay,
    unknownReason: "Probability is not evidenced by stage, buyer access or incumbent position.",
    nextStep: "Confirm procurement stage, relationship strength and competitor threat.",
  },
  {
    fieldName: "weighted_value",
    label: "Weighted value",
    getValue: (opportunity) => opportunity.weighted_pipeline_value || opportunity.weighted_value,
    format: currencyDisplay,
    unknownReason: "Weighted value cannot be calculated until contract value and probability are credible.",
    nextStep: "Validate estimated value and probability, then let MiSi recalculate weighted pipeline.",
  },
  {
    fieldName: "forecast_start_month",
    label: "Forecast start month",
    getValue: (opportunity) => opportunity.forecast_start_month,
    format: monthDisplay,
    unknownReason: "Forecast start month is not known from the current evidence.",
    nextStep: "Confirm expected award date, mobilisation window and LE1 treatment.",
  },
  {
    fieldName: "self_delivery_fit",
    label: "Self-delivery fit",
    getValue: (opportunity) => opportunity.self_delivery_fit,
    format: textDisplay,
    unknownReason: "Self-delivery fit has not been assessed against Mitie Fire & Security capability.",
    nextStep: "Check discipline mix, regional coverage, accreditations and subcontract exposure.",
  },
  {
    fieldName: "risk_rating",
    label: "Risk rating",
    getValue: (opportunity) => opportunity.calculated_risk_rating || opportunity.risk_rating,
    format: riskDisplay,
    unknownReason: "Risk rating is not supported by enough commercial evidence.",
    nextStep: "Review value, margin, deadline, mobilisation and competitor risk.",
  },
  {
    fieldName: "strategic_fit_score",
    label: "Strategic fit",
    getValue: (opportunity) => opportunity.strategic_fit_score,
    format: scoreDisplay,
    unknownReason: "Strategic fit has not been scored against Mitie priorities.",
    nextStep: "Confirm sector priority, buyer relationship, self-delivery capture and margin quality.",
  },
  {
    fieldName: "bid_no_bid_recommendation",
    label: "Bid / no-bid",
    getValue: (opportunity) =>
      opportunity.calculated_bid_no_bid_recommendation ||
      opportunity.bid_no_bid_recommendation,
    format: textDisplay,
    unknownReason: "Bid/no-bid position has not been qualified.",
    nextStep: "Run bid/no-bid review with value, fit, risk, margin and deadline evidence.",
  },
  {
    fieldName: "recommended_action",
    label: "Recommended action",
    getValue: (opportunity) =>
      opportunity.calculated_recommended_action || opportunity.recommended_action,
    format: textDisplay,
    unknownReason: "Next action is not yet defined.",
    nextStep: "Confirm contract scope, asset schedule, buyer contact and next governance gate.",
  },
  {
    fieldName: "incumbent_supplier",
    label: "Incumbent supplier",
    getValue: () => null,
    format: textDisplay,
    unknownReason: "Incumbent supplier was not found in available MiSi data.",
    nextStep: "Check tender award history, buyer website, CRM notes or approved market sources.",
  },
];

function buildOpportunityFieldViews(
  opportunity: Opportunity,
  fieldIntelligence: FieldIntelligence[],
  overrides: Record<string, string>,
): IntelligenceFieldView[] {
  const fieldsByName = new Map(
    fieldIntelligence.map((field) => [field.field_name, field]),
  );

  return opportunityFieldConfigs.map((config) => {
    const sourceField = fieldsByName.get(config.fieldName);
    const rawValue = overrides[config.fieldName] ?? sourceField?.field_value ?? config.getValue(opportunity);
    const valueMissing = isMissingCommercialValue(config.fieldName, rawValue);
    const valueType =
      sourceField?.value_type ??
      (valueMissing ? "unknown" : "known");
    const confidenceScore =
      sourceField?.confidence_score ??
      (valueMissing ? 0 : 1);
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
          : "Actual value currently held in the MiSi opportunity record."),
      sourceUrls: sourceField?.source_urls ?? [],
      sourceTitles: sourceField?.source_titles ?? [],
      recommendedNextStep:
        sourceField?.recommended_next_step ||
        (valueMissing ? config.nextStep : "Keep this value under review as source evidence changes."),
      needsUserConfirmation:
        sourceField?.needs_user_confirmation ??
        (valueMissing || valueType !== "known"),
    };
  });
}

function researchFieldToView(field: {
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
  const config = opportunityFieldConfigs.find((item) => item.fieldName === field.field_name);
  const valueMissing = isMissingCommercialValue(field.field_name, field.field_value);

  return {
    fieldName: field.field_name,
    label: config?.label ?? field.field_name.replaceAll("_", " "),
    displayValue: valueMissing
      ? "Unknown"
      : config?.format(field.field_value) ?? textDisplay(field.field_value),
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

function fieldByName(fields: IntelligenceFieldView[], fieldName: string) {
  return fields.find((field) => field.fieldName === fieldName);
}

function displayOpportunityValue(
  fieldName: string,
  value: unknown,
) {
  const config = opportunityFieldConfigs.find((item) => item.fieldName === fieldName);
  if (!config) {
    return isMissingCommercialValue(fieldName, value) ? "Unknown" : textDisplay(value);
  }

  return isMissingCommercialValue(fieldName, value)
    ? "Unknown"
    : config.format(value);
}

function summariseFieldConfidence(fields: IntelligenceFieldView[]) {
  const aiFields = fields.filter((field) => field.sourceUrls.length > 0 || field.valueType !== "known");
  const average =
    fields.length > 0
      ? fields.reduce((total, field) => total + field.confidenceScore, 0) / fields.length
      : 0;

  return {
    score: average,
    aiFieldCount: aiFields.length,
    unknownCount: fields.filter((field) => field.valueType === "unknown").length,
  };
}

function isMissingCommercialValue(fieldName: string, value: unknown) {
  if (value == null) {
    return true;
  }
  if (typeof value === "string") {
    const trimmed = value.trim();
    return (
      trimmed.length === 0 ||
      ["unknown", "not set", "tbc", "n/a", "null"].includes(trimmed.toLowerCase())
    );
  }
  if (typeof value === "number") {
    return value === 0 && commercialZeroMeansUnknownFields.has(fieldName);
  }
  return false;
}

const commercialZeroMeansUnknownFields = new Set([
  "estimated_annual_revenue",
  "estimated_total_contract_value",
  "estimated_gross_margin",
  "margin_percentage",
  "probability",
  "weighted_value",
  "strategic_fit_score",
]);

function textDisplay(value: unknown) {
  return typeof value === "string" ? value : String(value ?? "Unknown");
}

function currencyDisplay(value: unknown) {
  return typeof value === "number" ? currency(value) : textDisplay(value);
}

function percentageDisplay(value: unknown) {
  return typeof value === "number" ? percentageValue(value) : textDisplay(value);
}

function probabilityDisplay(value: unknown) {
  return typeof value === "number" ? percentageValue(value) : textDisplay(value);
}

function monthDisplay(value: unknown) {
  return typeof value === "string" ? monthYearLabel(value) : textDisplay(value);
}

function riskDisplay(value: unknown) {
  return typeof value === "string" ? normaliseRiskLabel(value) : textDisplay(value);
}

function scoreDisplay(value: unknown) {
  return typeof value === "number" ? `${Math.round(value)}/100` : textDisplay(value);
}

function valueTypeLabel(valueType: FieldIntelligence["value_type"]) {
  if (valueType === "known" || valueType === "user_provided") {
    return "Actual";
  }
  if (valueType === "system_calculated") {
    return "Calculated";
  }
  return valueType.charAt(0).toUpperCase() + valueType.slice(1);
}

function valueTypeDescription(field: IntelligenceFieldView) {
  if (field.valueType === "unknown") {
    return `${field.label} is unknown because MiSi does not have enough evidence yet. ${field.recommendedNextStep}`;
  }
  if (field.valueType === "estimated") {
    return `${field.label} is an estimate. Treat it as useful for direction, not as confirmed commercial truth.`;
  }
  if (field.valueType === "inferred") {
    return `${field.label} is inferred from available evidence and should be confirmed before bid or forecast commitment.`;
  }
  if (field.valueType === "system_calculated") {
    return `${field.label} is calculated by MiSi from other commercial fields.`;
  }
  return `${field.label} is held as an actual value in MiSi.`;
}

function fieldConfidenceClass(valueType: FieldIntelligence["value_type"]) {
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

function fieldConfidenceBorder(valueType: FieldIntelligence["value_type"]) {
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

function valueTypeDotClass(valueType: FieldIntelligence["value_type"]) {
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

function riskTone(risk: string): Tone {
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

function fitToneForSignal(fit: string): Tone {
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

function autofillResultTone(status: "enriched" | "skipped" | "failed"): Tone {
  if (status === "enriched") {
    return "green";
  }
  if (status === "failed") {
    return "red";
  }
  return "cyan";
}

function normaliseRiskLabel(risk: string): string {
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

function confidenceTone(confidence: number): Tone {
  if (confidence >= 0.75) {
    return "green";
  }

  if (confidence >= 0.45) {
    return "amber";
  }

  return "red";
}
