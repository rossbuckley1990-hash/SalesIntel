"use client";

import { HealthIndicator } from "@/components/health-indicator";
import {
  fetchMisiDashboardData,
  type MisiDashboardData,
  type Opportunity,
  type OpportunityAIAnalysis,
} from "@/lib/api";
import {
  ChevronRight,
  LockKeyhole,
  RefreshCw,
  Search,
  SlidersHorizontal,
} from "lucide-react";
import { useDeferredValue, useEffect, useMemo, useState } from "react";
import {
  BuyersView,
  CompetitorsView,
  ExecutiveActionsView,
  SettingsView,
} from "./directories";
import { ExecutiveCommandView } from "./executive";
import { buildFilterOptions, buildFilteredDashboardData } from "./filters";
import {
  FinanceView,
  PipelineForecastView,
  TenderIntelligenceView,
} from "./finance";
import { MarketRadarView } from "./market";
import { OpportunityDetailDrawer } from "./opportunity";
import { AIResearchWorkspaceView } from "./research";
import { SelfDeliveryView } from "./self-delivery";
import {
  DashboardFilters,
  FilterOptions,
  LoadState,
  NavigationItem,
  ViewId,
  emptyFilters,
  moduleDescriptions,
  navigation,
} from "./shared";
import { DashboardError, DashboardLoading } from "./ui";

export function DashboardShell() {
  const [activeView, setActiveView] = useState<ViewId>("research");
  const [filters, setFilters] = useState<DashboardFilters>(emptyFilters);
  const [selectedOpportunity, setSelectedOpportunity] =
    useState<Opportunity | null>(null);
  const { state, reload, updateOpportunityAnalysis } = useMisiData();
  const activeModule =
    navigation.find((item) => item.id === activeView) ?? navigation[0];
  const deferredFilters = useDeferredValue(filters);
  const filteredData = useMemo(
    () =>
      state.status === "success"
        ? buildFilteredDashboardData(state.data, deferredFilters)
        : null,
    [state, deferredFilters],
  );
  const filterOptions = useMemo(
    () =>
      state.status === "success"
        ? buildFilterOptions(state.data.opportunities)
        : null,
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
      current?.id === opportunityId
        ? { ...current, latest_ai_analysis: analysis }
        : current,
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
            <MobileModuleTabs
              activeView={activeView}
              onSelect={setActiveView}
            />
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
                {renderView(
                  activeView,
                  filteredData,
                  setSelectedOpportunity,
                  reload,
                )}
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

export function useMisiData() {
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
            : "Unable to connect to the SalesIntel backend.";
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
              top_opportunities:
                current.data.dashboard.top_opportunities.map(updateOpportunity),
            },
          },
        };
      });
    },
  };
}

export function Sidebar({
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
              <div className="text-xl font-semibold text-white">SalesIntel</div>
              <div className="mt-1 text-sm text-slate-400">
                SalesIntel
              </div>
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
                {active ? (
                  <ChevronRight
                    aria-hidden="true"
                    className="h-4 w-4 shrink-0"
                  />
                ) : null}
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
              Dashboard data is read from the SalesIntel API. OpenAI credentials stay
              on the backend.
            </p>
          </div>
        </div>
      </div>
    </aside>
  );
}

export function Header({
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
            SalesIntel
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
            <span className="sr-only">
              Search buyers, tenders and opportunities
            </span>
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

export function DashboardFilterBar({
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
    <section
      className="rounded-lg border border-white/10 bg-[#0d151a] p-4 shadow-[0_20px_70px_rgba(0,0,0,0.22)]"
      aria-label="Dashboard filters"
    >
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-sm font-semibold text-white">
            <SlidersHorizontal
              aria-hidden="true"
              className="h-4 w-4 text-mitie-lime"
            />
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

export function FilterSelect({
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

export function MobileModuleTabs({
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

export function renderView(
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
