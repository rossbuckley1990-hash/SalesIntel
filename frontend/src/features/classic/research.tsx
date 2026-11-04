"use client";

import {
  generateChatGPTAssistPrompt,
  importChatGPTAssistResult,
  researchOpportunity,
  type Opportunity,
  type ResearchOpportunityResponse,
} from "@/lib/api";
import { percentage } from "@/lib/format";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  ClipboardList,
  Globe2,
  Loader2,
  Search,
  Target,
} from "lucide-react";
import { useEffect, useState } from "react";
import {
  buildResearchPayload,
  getChatGPTAssistErrorMessage,
  getOpportunityResearchErrorMessage,
} from "./errors";
import {
  confidenceTone,
  fieldByName,
  researchFieldToView,
  summariseFieldConfidence,
} from "./evidence";
import {
  ChatGPTAssistState,
  ResearchWorkspaceFilters,
  ResearchWorkspaceRequest,
  ResearchWorkspaceState,
  Tone,
  emptyResearchFilters,
  researchExamples,
  researchFilterOptions,
  researchProgressDetails,
  researchProgressSteps,
  toneClasses,
} from "./shared";
import {
  ConfidenceFieldCard,
  ConfidenceOrbit,
  DetailList,
  EmptyState,
  IntelligenceMetric,
  MetricLine,
  Panel,
  SourceRow,
  StatusPill,
} from "./ui";

export function AIResearchWorkspaceView({
  onDataChanged,
  onSelectOpportunity,
}: {
  onDataChanged: () => void;
  onSelectOpportunity: (opportunity: Opportunity) => void;
}) {
  const [query, setQuery] = useState("");
  const [filters, setFilters] =
    useState<ResearchWorkspaceFilters>(emptyResearchFilters);
  const [workspaceState, setWorkspaceState] = useState<ResearchWorkspaceState>({
    status: "idle",
  });
  const [chatgptAssistState, setChatgptAssistState] =
    useState<ChatGPTAssistState>({
      status: "idle",
    });
  const trimmedQuery = query.trim();
  const canResearch =
    trimmedQuery.length >= 6 &&
    workspaceState.status !== "loading" &&
    workspaceState.status !== "saving";
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
              stepIndex: Math.min(
                current.stepIndex + 1,
                researchProgressSteps.length - 2,
              ),
            }
          : current,
      );
    }, 900);

    try {
      const result = await researchOpportunity(
        buildResearchPayload(request, false),
      );
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
              stepIndex: Math.min(
                current.stepIndex + 1,
                researchProgressSteps.length - 1,
              ),
            }
          : current,
      );
    }, 800);

    try {
      const savedResult = await researchOpportunity(
        buildResearchPayload(request, true),
      );
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
      await navigator.clipboard.writeText(
        chatgptAssistState.promptResponse.prompt,
      );
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
              Start with a rough phrase. SalesIntel builds the evidence-backed
              commercial readout.
            </h2>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
              Known facts, inferred context, estimated value and unresolved
              unknowns stay visibly separate so leadership can act without
              pretending the data is perfect.
            </p>

            <div className="mt-6 grid gap-3">
              <label className="grid gap-2">
                <span className="text-xs font-semibold uppercase text-slate-500">
                  Ask SalesIntel
                </span>
                <textarea
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  rows={4}
                  data-testid="ai-research-query"
                  className="min-h-36 rounded-lg border border-mitie-lime/25 bg-[#080d10] px-4 py-4 text-lg font-semibold leading-8 text-white outline-none ring-0 placeholder:text-slate-500 transition focus:border-mitie-lime/70 focus:shadow-[0_0_0_4px_rgba(124,179,66,0.12)]"
                  placeholder="Ask SalesIntel to research a buyer, tender, market, sector or opportunity..."
                />
              </label>

              <div
                className="flex flex-wrap gap-2"
                aria-label="Example research prompts"
              >
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
                <span className="text-xs font-semibold text-slate-500">
                  Minimum value
                </span>
                <input
                  value={filters.minimumValue}
                  onChange={(event) =>
                    updateResearchFilter("minimumValue", event.target.value)
                  }
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
                  <Loader2
                    aria-hidden="true"
                    className="h-4 w-4 animate-spin"
                  />
                ) : (
                  <Search aria-hidden="true" className="h-4 w-4" />
                )}
                {workspaceState.status === "loading"
                  ? "Researching with SalesIntel"
                  : "Research with SalesIntel"}
              </button>
              <button
                type="button"
                onClick={handleGenerateChatGPTAssistPrompt}
                disabled={!canUseChatGPTAssist}
                data-testid="chatgpt-assist-prompt-button"
                className="inline-flex min-h-12 items-center justify-center gap-2 rounded-md border border-cyan-300/30 bg-cyan-400/10 px-4 py-3 text-sm font-black text-cyan-100 transition hover:border-cyan-200/60 hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/5 disabled:text-slate-500"
              >
                {chatgptAssistState.status === "prompting" ? (
                  <Loader2
                    aria-hidden="true"
                    className="h-4 w-4 animate-spin"
                  />
                ) : (
                  <ClipboardList aria-hidden="true" className="h-4 w-4" />
                )}
                {chatgptAssistState.status === "prompting"
                  ? "Preparing ChatGPT Prompt"
                  : "Use ChatGPT Plus Assist"}
              </button>
              <p className="text-sm leading-6 text-slate-500">
                API path uses backend OpenAI. Assist path uses your manual
                ChatGPT Plus session and pasted JSON.
              </p>
            </div>
          </div>

          <aside className="border-t border-white/10 bg-[#111a20] p-5 xl:border-l xl:border-t-0">
            <div className="rounded-md border border-mitie-lime/20 bg-mitie-lime/10 p-4">
              <p className="text-xs font-black uppercase text-mitie-lime">
                30-second leadership read
              </p>
              <p className="mt-2 text-sm font-semibold leading-6 text-white">
                What is it, why does it matter, what is it worth, what is the
                risk, and what should Mitie do next?
              </p>
            </div>
            <h3 className="mt-5 text-sm font-semibold text-white">
              What SalesIntel creates
            </h3>
            <div className="mt-4 grid gap-3">
              <SourceRow
                label="Opportunity record"
                value="Commercial values, stage, risk and next action"
                tone="green"
              />
              <SourceRow
                label="Field evidence"
                value="Known, inferred, estimated and unknown labels"
                tone="cyan"
              />
              <SourceRow
                label="Executive action"
                value="Owner, priority, value and reason"
                tone="amber"
              />
              <SourceRow
                label="Dashboard update"
                value="Saved records feed the SalesIntel command centre"
                tone="green"
              />
            </div>
          </aside>
        </div>
      </section>

      {workspaceState.status === "loading" ||
      workspaceState.status === "saving" ? (
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
        <Panel
          title="Research Needs Attention"
          action={<StatusPill tone="amber" label="Not completed" />}
        >
          <div className="flex gap-3 rounded-md border border-amber-300/20 bg-amber-400/10 p-4">
            <AlertTriangle
              aria-hidden="true"
              className="mt-0.5 h-5 w-5 shrink-0 text-amber-200"
            />
            <div>
              <p className="text-sm font-semibold text-amber-100">
                SalesIntel could not complete this research run.
              </p>
              <p className="mt-2 text-sm leading-6 text-amber-100/80">
                {workspaceState.message}
              </p>
              <p className="mt-2 text-sm leading-6 text-amber-100/70">
                Check the backend OpenAI configuration, then retry with a
                specific buyer, sector, region or discipline.
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

export function WorkspaceFilterSelect({
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

export function ChatGPTAssistPanel({
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
                  SalesIntel creates the strict research prompt. You paste it into
                  ChatGPT Plus, then paste the JSON result back here. SalesIntel
                  validates and imports it without calling the OpenAI API.
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
                <Loader2
                  aria-hidden="true"
                  className="h-4 w-4 animate-spin text-cyan-200"
                />
                <p className="text-sm font-semibold text-white">
                  Preparing a strict SalesIntel prompt for ChatGPT Plus...
                </p>
              </div>
              <SkeletonLine className="mt-4 h-3 w-full rounded-full" />
              <SkeletonLine className="mt-2 h-3 w-3/4 rounded-full" />
            </div>
          ) : null}

          {hasPrompt ? (
            <>
              <label className="grid gap-2">
                <span className="text-xs font-black uppercase text-slate-500">
                  Prompt for ChatGPT Plus
                </span>
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
                <span className="text-xs font-black uppercase text-slate-500">
                  Paste ChatGPT JSON result
                </span>
                <textarea
                  value={pastedJson}
                  onChange={(event) => onJsonChange(event.target.value)}
                  rows={9}
                  disabled={importing}
                  data-testid="chatgpt-assist-json"
                  className="min-h-52 rounded-md border border-mitie-lime/20 bg-[#080d10] p-3 text-sm leading-6 text-white outline-none placeholder:text-slate-600 focus:border-mitie-lime/60 disabled:opacity-60"
                  placeholder="Paste the full JSON object from ChatGPT here. SalesIntel will reject prose, partial JSON or unlabelled fields."
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
                  <Loader2
                    aria-hidden="true"
                    className="h-4 w-4 animate-spin"
                  />
                ) : (
                  <CheckCircle2 aria-hidden="true" className="h-4 w-4" />
                )}
                {importing
                  ? "Validating And Importing"
                  : "Validate And Save Intelligence Pack"}
              </button>
            </>
          ) : null}

          {state.status === "error" ? (
            <div className="flex gap-3 rounded-md border border-amber-300/20 bg-amber-400/10 p-4">
              <AlertTriangle
                aria-hidden="true"
                className="mt-0.5 h-5 w-5 shrink-0 text-amber-200"
              />
              <div>
                <p className="text-sm font-semibold text-amber-100">
                  ChatGPT Assist needs attention
                </p>
                <p className="mt-2 text-sm leading-6 text-amber-100/80">
                  {state.message}
                </p>
              </div>
            </div>
          ) : null}
        </div>

        <div className="grid content-start gap-3">
          <SourceRow
            label="Step 1"
            value="Copy SalesIntel's strict prompt"
            tone="cyan"
          />
          <SourceRow
            label="Step 2"
            value="Run it manually in ChatGPT Plus"
            tone="green"
          />
          <SourceRow
            label="Step 3"
            value="Paste JSON back into SalesIntel"
            tone="amber"
          />
          <SourceRow
            label="Step 4"
            value="SalesIntel validates and saves the pack"
            tone="green"
          />
          <div className="rounded-md border border-white/10 bg-[#111a20] p-4">
            <p className="text-xs font-black uppercase text-slate-500">
              Boundary
            </p>
            <p className="mt-2 text-sm leading-6 text-slate-300">
              No browser automation, no session scraping and no API call. This
              is a deliberate human approval bridge.
            </p>
          </div>
          {hasPrompt ? (
            <div className="rounded-md border border-white/10 bg-[#111a20] p-4">
              <p className="text-xs font-black uppercase text-slate-500">
                Safety note
              </p>
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

export function ResearchWorkspaceIdle() {
  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
      <Panel
        title="SalesIntel Has Not Researched This Area Yet"
        action={<StatusPill tone="cyan" label="Ready" />}
      >
        <div className="rounded-md border border-mitie-lime/20 bg-mitie-lime/10 p-4">
          <p className="text-sm font-semibold leading-6 text-white">
            Start with a buyer, sector or tender phrase and SalesIntel will build the
            intelligence pack: value, risk, confidence, evidence and next best
            action.
          </p>
        </div>
        <div className="mt-4 grid gap-4 lg:grid-cols-3">
          <ResearchCapabilityCard
            title="No perfect data required"
            body="SalesIntel can begin from a buyer name, sector theme, tender phrase or renewal hypothesis."
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
      <Panel
        title="Output Preview"
        action={<StatusPill tone="green" label="Commercial pack" />}
      >
        <div className="mb-4 rounded-md border border-white/10 bg-[#111a20] p-4">
          <p className="text-xs font-black uppercase text-slate-500">
            Leadership answer
          </p>
          <p className="mt-2 text-sm font-semibold leading-6 text-white">
            What is it, why it matters, what it is worth, what the risk is, and
            what Mitie should do next.
          </p>
        </div>
        <div className="grid gap-3">
          <MetricLine
            label="Opportunity card"
            value="Created after research"
            detail="Name, buyer, stage, value, risk and action"
          />
          <MetricLine
            label="Field intelligence"
            value="Always labelled"
            detail="Known, inferred, estimated, unknown or needs confirmation"
          />
          <MetricLine
            label="Executive action"
            value="Generated"
            detail="Leadership owner, due date, commercial value and reason"
          />
        </div>
      </Panel>
    </div>
  );
}

export function ResearchCapabilityCard({
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

export function NextActionCallout({
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
          <p className="mt-2 text-sm font-semibold leading-6 text-white">
            {action}
          </p>
        </div>
      </div>
    </div>
  );
}

export function ResearchProgressPanel({
  stepIndex,
  saving,
}: {
  stepIndex: number;
  saving: boolean;
}) {
  const boundedStep = Math.min(
    Math.max(stepIndex, 0),
    researchProgressSteps.length - 1,
  );
  const progressPercent =
    ((boundedStep + 1) / researchProgressSteps.length) * 100;

  return (
    <Panel
      title={
        saving ? "Saving Intelligence To Pipeline" : "SalesIntel Research In Progress"
      }
      action={
        <StatusPill
          tone="cyan"
          label={saving ? "Pipeline update" : "Live research"}
        />
      }
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
                <ConfidenceOrbit
                  score={progressPercent / 100}
                  label={`${Math.round(progressPercent)}%`}
                />
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
                      <Activity
                        aria-hidden="true"
                        className="h-4 w-4 text-mitie-lime"
                      />
                    ) : complete ? (
                      <CheckCircle2
                        aria-hidden="true"
                        className="h-4 w-4 text-emerald-200"
                      />
                    ) : (
                      <span
                        className="h-2 w-2 rounded-full bg-slate-600"
                        aria-hidden="true"
                      />
                    )}
                  </div>
                  <p
                    className={`mt-3 text-sm font-semibold leading-6 ${active || complete ? "text-white" : "text-slate-400"}`}
                  >
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

export function ResearchSkeletonPreview() {
  return (
    <div className="rounded-md border border-white/10 bg-[#111a20] p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-semibold text-white">
          Intelligence pack forming
        </p>
        <Loader2
          aria-hidden="true"
          className="h-4 w-4 animate-spin text-cyan-200"
        />
      </div>
      <div className="mt-4 grid gap-3">
        <SkeletonLine className="h-4 w-3/4 rounded-full" />
        <SkeletonLine className="h-8 w-full rounded-md" />
        <SkeletonLine className="h-8 w-5/6 rounded-md" />
      </div>
      <div className="mt-5 grid gap-3">
        {["Commercial value", "Risk", "Next best action"].map((label) => (
          <div
            key={label}
            className="rounded-md border border-white/10 bg-[#0d151a] p-3"
          >
            <p className="text-xs font-black uppercase text-slate-500">
              {label}
            </p>
            <SkeletonLine className="mt-3 h-3 w-full rounded-full" />
            <SkeletonLine className="mt-2 h-3 w-2/3 rounded-full" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function SkeletonLine({ className }: { className: string }) {
  return (
    <div
      className={`misi-shimmer bg-white/10 ${className}`}
      aria-hidden="true"
    />
  );
}

export function ResearchWorkspaceResult({
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
  const [fieldOverrides, setFieldOverrides] = useState<Record<string, string>>(
    {},
  );

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
      recommendedNextStep:
        "Confirm this edited value against the approved commercial source before bid governance.",
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
        action={
          <StatusPill
            tone={confidenceTone(result.overall_confidence)}
            label={`${percentage(result.overall_confidence)} confidence`}
          />
        }
      >
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <StatusPill
                tone={saved ? "green" : "amber"}
                label={saved ? "Saved to pipeline" : "Preview for review"}
              />
              <StatusPill
                tone="cyan"
                label={`${result.sources.length} sources`}
              />
              <StatusPill
                tone={confidenceSummary.unknownCount > 0 ? "amber" : "green"}
                label={`${confidenceSummary.unknownCount} unknowns`}
              />
              <StatusPill
                tone={acceptedCount > 0 ? "green" : "cyan"}
                label={`${acceptedCount} accepted`}
              />
            </div>
            <h3 className="mt-4 text-2xl font-semibold leading-9 text-white">
              {result.draft_opportunity.name || "Opportunity title unknown"}
            </h3>
            <p className="mt-2 text-sm font-semibold text-mitie-lime">
              {result.draft_opportunity.buyer_name || "Buyer unknown"} ·{" "}
              {result.draft_opportunity.sector || "Sector unknown"} ·{" "}
              {result.draft_opportunity.region || "Region unknown"}
            </p>
            <p className="mt-4 text-sm leading-6 text-slate-300">
              {result.draft_enrichment.opportunity_summary ||
                "SalesIntel did not return an opportunity summary. Confirm the buyer and tender route, then rerun research."}
            </p>
            <NextActionCallout
              label="SalesIntel recommendation"
              action={
                result.draft_enrichment.executive_recommendation ||
                "Confirm contract scope, buyer owner and procurement route before leadership review."
              }
            />
          </div>

          <div className="rounded-md border border-white/10 bg-[#111a20] p-4">
            <div className="mb-5 flex justify-center">
              <ConfidenceOrbit
                score={result.overall_confidence}
                label={percentage(result.overall_confidence)}
              />
            </div>
            <p className="text-xs font-black uppercase text-slate-500">
              Recommended next action
            </p>
            <p className="mt-3 text-base font-semibold leading-7 text-white">
              {result.draft_opportunity.recommended_action ||
                "Confirm contract scope and asset schedule."}
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
                  <Loader2
                    aria-hidden="true"
                    className="h-4 w-4 animate-spin"
                  />
                ) : (
                  <CheckCircle2 aria-hidden="true" className="h-4 w-4" />
                )}
                {saved
                  ? "Saved To Pipeline"
                  : saving
                    ? "Saving To Pipeline"
                    : "Save To Pipeline"}
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
              Review flow: accept strong AI values, edit weak values, then save
              only when the record is good enough for pipeline review.
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
          action={
            <StatusPill
              tone={confidenceTone(confidenceSummary.score)}
              label={`${percentage(confidenceSummary.score)} average confidence`}
            />
          }
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

export function ResearchSourcesPanel({
  sources,
}: {
  sources: ResearchOpportunityResponse["sources"];
}) {
  return (
    <Panel
      title="Evidence Sources"
      action={
        <StatusPill
          tone={sources.length > 0 ? "cyan" : "amber"}
          label={`${sources.length} sources`}
        />
      }
    >
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
              <span className="text-xs font-black uppercase text-slate-500">
                Evidence {index + 1}
              </span>
              <span className="mt-1 block font-semibold text-cyan-100 group-hover:text-white">
                {source.title || "Untitled source"}
              </span>
              <span className="mt-1 block text-xs text-slate-500">
                {source.source_type || "Public source"} ·{" "}
                {source.relevance || "Relevance to be confirmed"}
              </span>
              <span className="mt-2 block truncate text-xs font-semibold text-cyan-200">
                {source.url}
              </span>
            </a>
          ))}
        </div>
      ) : (
        <EmptyState
          title="No confirmed source evidence yet"
          message="SalesIntel can still label useful estimates, but this pack should not be used for bid governance until a tender notice, buyer page, portal result or approved internal source is attached."
        />
      )}
    </Panel>
  );
}

export function ResearchIntelligencePanel({
  result,
}: {
  result: ResearchOpportunityResponse;
}) {
  const enrichment = result.draft_enrichment;
  const unknowns =
    enrichment.unknowns.length > 0
      ? enrichment.unknowns
      : [
          "No critical unknowns were returned, but validate buyer, scope, value and incumbent before bid governance.",
        ];
  const nextSteps =
    enrichment.recommended_next_steps.length > 0
      ? enrichment.recommended_next_steps
      : [
          "Confirm procurement route, asset schedule, incumbent supplier and decision owner.",
        ];

  return (
    <Panel
      title="Commercial Intelligence Pack"
      action={<StatusPill tone="green" label="Board-ready shape" />}
    >
      <div className="grid gap-4">
        <DetailList
          title="Likely scope"
          items={
            enrichment.likely_scope.length > 0
              ? enrichment.likely_scope
              : ["Scope unknown; confirm fire and security disciplines."]
          }
        />
        <DetailList
          title="Buyer drivers"
          items={
            enrichment.likely_buyer_drivers.length > 0
              ? enrichment.likely_buyer_drivers
              : [
                  "Buyer drivers unknown; confirm compliance, cost and estate priorities.",
                ]
          }
        />
        <DetailList title="Unknowns to resolve" items={unknowns} />
        <DetailList title="Next best steps" items={nextSteps} />
        <NextActionCallout
          label="Commercial control"
          action={
            nextSteps[0] ||
            "Confirm procurement route and source evidence before committing bid resources."
          }
          tone="cyan"
        />
        <div className="rounded-md border border-white/10 bg-[#111a20] p-4">
          <p className="text-xs font-semibold uppercase text-slate-500">
            Self-delivery assessment
          </p>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            {enrichment.self_delivery_assessment ||
              "Self-delivery fit unknown. Confirm disciplines, asset density and local engineering capacity."}
          </p>
        </div>
      </div>
    </Panel>
  );
}
