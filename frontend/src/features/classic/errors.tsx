"use client";

import {
  type InternetIntelligenceType,
  type ResearchOpportunityRequest,
} from "@/lib/api";
import { ResearchWorkspaceRequest, internetIntelligenceTypes } from "./shared";

export function buildResearchPayload(
  request: ResearchWorkspaceRequest,
  createOpportunity: boolean,
): ResearchOpportunityRequest {
  const context = [
    request.filters.sector ? `sector: ${request.filters.sector}` : "",
    request.filters.region ? `region: ${request.filters.region}` : "",
    request.filters.discipline
      ? `discipline: ${request.filters.discipline}`
      : "",
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

export function getOpportunityAnalysisErrorMessage(error: unknown): string {
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

  if (
    error.message.includes("Failed to fetch") ||
    error.message.includes("fetch failed")
  ) {
    return "MiSi could not reach the backend API. Start FastAPI, confirm /health returns OK, then retry the analysis.";
  }

  return error.message || fallback;
}

export function getExecutiveBriefingErrorMessage(error: unknown): string {
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

  if (
    error.message.includes("Failed to fetch") ||
    error.message.includes("fetch failed")
  ) {
    return "MiSi could not reach the backend API. Start FastAPI, confirm /health returns OK, then retry the briefing.";
  }

  return error.message || fallback;
}

export function getInternetResearchErrorMessage(error: unknown): string {
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

  if (
    error.message.includes("Failed to fetch") ||
    error.message.includes("fetch failed")
  ) {
    return "MiSi could not reach the backend API. Start FastAPI, confirm /health returns OK, then retry the internet scan.";
  }

  if (error.message.toLowerCase().includes("invalid structured json")) {
    return "The internet scan returned weak or malformed structured output. Try a narrower buyer, sector, region or discipline phrase so MiSi can attach stronger evidence and confidence.";
  }

  return error.message || fallback;
}

export function getOpportunityResearchErrorMessage(error: unknown): string {
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
    error.message.includes(
      "OpenAI standing-start opportunity research failed",
    ) ||
    error.message.includes("OpenAI opportunity research request failed") ||
    error.message.includes("OPENAI_MODEL")
  ) {
    return "MiSi could not complete the AI research request. Confirm the backend has a valid OPENAI_API_KEY, the selected OPENAI_MODEL is available to that key, then restart FastAPI and try a specific buyer, sector, region or discipline phrase. The browser never receives the key.";
  }

  if (
    error.message.includes("Failed to fetch") ||
    error.message.includes("fetch failed")
  ) {
    return "MiSi could not reach the backend API. Start FastAPI, confirm /health returns OK, then retry opportunity research.";
  }

  if (error.message.toLowerCase().includes("invalid structured json")) {
    return "MiSi received weak or invalid structured research output. Tighten the research brief with a buyer, sector, region, discipline or known source, then rerun so unknowns can be labelled properly.";
  }

  return error.message || fallback;
}

export function getChatGPTAssistErrorMessage(error: unknown): string {
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

  if (
    error.message.includes("Failed to fetch") ||
    error.message.includes("fetch failed")
  ) {
    return "MiSi could not reach the backend API. Start FastAPI, confirm /health returns OK, then retry ChatGPT Assist.";
  }

  return error.message || fallback;
}

export function getAutofillErrorMessage(error: unknown): string {
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

  if (
    error.message.includes("Failed to fetch") ||
    error.message.includes("fetch failed")
  ) {
    return "MiSi could not reach the backend API. Start FastAPI, confirm /health returns OK, then retry the autofill run.";
  }

  return error.message || fallback;
}

export function isOpenAIQuotaError(message: string): boolean {
  const lowerMessage = message.toLowerCase();
  return (
    lowerMessage.includes("insufficient quota") ||
    lowerMessage.includes("insufficient_quota") ||
    lowerMessage.includes("exceeded your current quota")
  );
}

export function getMarketSignalConversionErrorMessage(error: unknown): string {
  const fallback =
    "MiSi could not convert this market signal. Check the backend API and retry.";
  if (!(error instanceof Error)) {
    return fallback;
  }

  if (error.message.includes("not found")) {
    return "This market signal no longer exists in the backend dataset. Refresh the dashboard and try another signal.";
  }

  if (
    error.message.includes("Failed to fetch") ||
    error.message.includes("fetch failed")
  ) {
    return "MiSi could not reach the backend API. Confirm FastAPI is running, then retry conversion.";
  }

  return error.message || fallback;
}

export function getReportExportErrorMessage(error: unknown): string {
  const fallback =
    "The backend could not generate the executive report. Check the API is running and retry.";
  if (!(error instanceof Error)) {
    return fallback;
  }

  if (
    error.message.includes("Failed to fetch") ||
    error.message.includes("fetch failed")
  ) {
    return "MiSi could not reach the backend API. Confirm the FastAPI server is running, then retry the executive report export.";
  }

  return error.message || fallback;
}

export function internetTypeLabel(value: InternetIntelligenceType): string {
  return (
    internetIntelligenceTypes.find((item) => item.value === value)?.label ??
    "Internet Intelligence"
  );
}
