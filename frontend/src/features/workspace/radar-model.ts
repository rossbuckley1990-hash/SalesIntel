import { getApiBaseUrl } from "@/lib/api";

export type Evidence = { source_revision_id: number; source_url: string; source: string; record_key: string; published_at: string | null };
export type Value = { published_total: number | null; estimated_annualised: number | null; framework_ceiling: number | null; type: string; basis: string; scope_note: string };
export type Brief = { customer: string; service_requirement: string; incumbent: string; commercial_value: string; contract_lifecycle: string; procurement_route: string; timing: string; why_it_matters: string; missing_information: string[]; next_action: string };
export type Observation = { fingerprint: string; label: string; statement: string; occurred_on: string; source_group: string; source_url: string; capture: string };
export type Explanation = { explanation: string; label: string; status: string; test: string };
export type Signal = { hypothesis_id: number; label: string; decision: string; decision_reasons: string[]; evidence_state: string; independent_sources: string[]; link: string; supporting: Observation[]; contradicting: Observation[]; explanations: Explanation[]; unknowns: string[]; caution: string };
export type Suggestion = {
  category: string; category_label: string; customer: string; title: string; supplier: string | null; timing: string | null; timing_basis: string; end_estimated: boolean; latest_end: string | null;
  nation: string; fit: string; value: Value; priority: { tier: number; reasons: string[] }; counter_evidence: string[]; next_actions: string[]; extension: string;
  link: { confidence: string; records: number; sources: string[] }; brief: Brief; evidence: Evidence[]; signal?: Signal; signals?: Signal[]; plausible_competitors?: string[] | null;
};
export type Item = { id: number; review_state: string; researched?: boolean; suggestion: Suggestion };
export type Page = { items: Item[]; total: number };
export type Health = { source_key: string; status: string; last_success_at: string | null };
export type Summary = {
  as_of?: string; opportunities: number; by_category: Record<string, number>; by_tier: Record<string, number>; by_nation?: Record<string, number>; renewals_within_months: Record<string, number>;
  value: { estimated_annualised: number; estimated_annualised_core_only: number; unknown_value_renewals: number }; find_a_tender_unbroken_from: string | null; health: Health[]; limits: string[];
};
export type Dossier = {
  id: number; created_at: string; model: string; headline: string; summary: string;
  recommendation: { stance: "pursue" | "qualify" | "monitor" | "step_back"; rationale: string };
  buyer: { overview: string; estate: string; priorities: string[]; developments: { date: string; development: string; relevance: string; source_url: string }[] };
  contract: { position: string; incumbent: string; timeline: string; route: string };
  signals: { signal: string; basis: "stated" | "inferred"; direction: "supports" | "against" | "neutral"; source_url: string }[];
  decision_roles: { role: string; why: string }[];
  win_strategy: { angle: string; themes: string[]; proof_points: string[] };
  risks: { risk: string; mitigation: string }[];
  questions: string[]; next_steps: { step: string; when: string }[]; unknowns: string[];
  sources: { title: string; url: string }[]; sources_reviewed?: number;
};

export const radarBase = () => `${getApiBaseUrl()}/api/market-network/opportunities`;

export type Tone = "red" | "amber" | "green" | "blue" | "violet" | "brand" | "neutral";
export const CATEGORY: Record<string, { label: string; short: string; tone: Tone; help: string }> = {
  contract_defence: { label: "Contract defence", short: "Defend", tone: "red", help: "The Mitie group holds this contract. Protect it before it is re-tendered." },
  live_procurement: { label: "Live tenders", short: "Live tender", tone: "blue", help: "A tender is open now with a published deadline." },
  official_early_signal: { label: "Early notices", short: "Early notice", tone: "brand", help: "The buyer has published an early notice before a tender." },
  pre_tender: { label: "Pre-tender", short: "Pre-tender", tone: "green", help: "A competitor's contract is ending. Engage before the tender is written." },
  inferred_signal: { label: "AI signals", short: "AI signal", tone: "violet", help: "Public evidence suggests a need before any tender. Verify before acting." },
  verify_first: { label: "Verify first", short: "Verify", tone: "amber", help: "Timing or scope is uncertain. Check the facts before investing time." },
};
export const CATEGORY_ORDER = ["contract_defence", "live_procurement", "official_early_signal", "pre_tender", "inferred_signal", "verify_first"];
export const NATIONS = ["England", "Scotland", "Wales", "Northern Ireland", "Not stated"];
export const SOURCE_NAMES: Record<string, string> = { find_a_tender: "Find a Tender", contracts_finder: "Contracts Finder", public_contracts_scotland: "Public Contracts Scotland", renewal_radar: "Radar evaluation", market_inference: "Public signals (GOV.UK, Gazette)" };
export const DECISIONS: Record<string, { label: string; tone: Tone }> = { pursue: { label: "Pursue", tone: "green" }, verify: { label: "Verify", tone: "amber" }, monitor: { label: "Monitor", tone: "neutral" }, dismiss: { label: "Dismiss", tone: "neutral" } };
export const EVIDENCE_STATES: Record<string, string> = { independently_corroborated: "Independent sources agree", same_source_repeated: "One source, repeated", single_source: "One source", contradicted: "Contradicted" };
export const EXPLANATION_STATES: Record<string, { label: string; tone: Tone }> = {
  supported: { label: "Supported", tone: "green" }, possible: { label: "Possible", tone: "neutral" }, not_established: { label: "Not established", tone: "neutral" },
  contradicted: { label: "Contradicted", tone: "red" }, supported_by_published_attribution: { label: "Published attribution", tone: "green" },
};
export const REVIEW_STATES: Record<string, string> = { unreviewed: "New", investigate: "In pipeline", defer: "Deferred", dismiss: "Dismissed" };

export const pounds = (value: number | null | undefined) => (value ? `£${Math.round(value).toLocaleString("en-GB")}` : "Not published");
export function compactPounds(value: number | null | undefined) {
  if (!value) return null;
  if (value >= 1_000_000) return `£${(value / 1_000_000).toFixed(value >= 10_000_000 ? 0 : 1)}m`;
  if (value >= 1_000) return `£${Math.round(value / 1_000)}k`;
  return `£${Math.round(value)}`;
}

export function valueLine(value: Value) {
  if (value.type === "estimated_annualised") return `${pounds(value.estimated_annualised)} a year (estimated)`;
  if (value.type === "published_total") return `${pounds(value.published_total)} published total`;
  if (value.type === "framework_ceiling") return `${pounds(value.framework_ceiling)} framework ceiling`;
  return "Value not published";
}

export function shortValue(value: Value) {
  if (value.type === "estimated_annualised") return value.estimated_annualised ? `${compactPounds(value.estimated_annualised)}/yr` : null;
  if (value.type === "published_total") return compactPounds(value.published_total);
  if (value.type === "framework_ceiling") return value.framework_ceiling ? `≤ ${compactPounds(value.framework_ceiling)}` : null;
  return null;
}

export function timingLabel(basis: string, estimated: boolean) {
  if (basis.includes("deadline")) return "Tender deadline";
  if (basis.includes("expected")) return "Expected tender";
  if (basis === "none" || !basis) return "Timing";
  return estimated ? "Contract ends (estimated)" : "Contract ends";
}

const DAY = 86_400_000;
export function daysUntil(date: string | null, today = new Date()) {
  if (!date) return null;
  const target = new Date(`${date.slice(0, 10)}T00:00:00Z`).getTime();
  const now = Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate());
  return Math.round((target - now) / DAY);
}

/** A short, honest countdown: "Today", "in 6 days", "in 7 months", "2 months ago". */
export function relative(date: string | null, today = new Date()) {
  const days = daysUntil(date, today);
  if (days === null) return null;
  if (days === 0) return "Today";
  if (days === 1) return "Tomorrow";
  const abs = Math.abs(days);
  const unit = abs < 45 ? `${abs} day${abs === 1 ? "" : "s"}` : abs < 548 ? `${Math.round(abs / 30.4)} months` : `${(abs / 365).toFixed(1)} years`;
  return days > 0 ? `in ${unit}` : `${unit} ago`;
}

export function urgencyTone(date: string | null, today = new Date()): Tone {
  const days = daysUntil(date, today);
  if (days === null) return "neutral";
  if (days < 0) return "neutral";
  if (days <= 14) return "red";
  if (days <= 120) return "amber";
  return "neutral";
}

export function formatDate(date: string | null | undefined) {
  if (!date) return "Not published";
  const parsed = new Date(`${date.slice(0, 10)}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return date;
  return new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }).format(parsed);
}

export function titleCase(name: string) {
  // Some registers publish buyers in capitals; present them as people write them.
  if (name !== name.toUpperCase()) return name;
  return name.toLowerCase().replace(/\b([a-z])/g, (m) => m.toUpperCase()).replace(/\b(Nhs|Uk|Plc|Ltd)\b/g, (m) => m.toUpperCase().replace("LTD", "Ltd"));
}

export function signalsOf(s: Suggestion) {
  return [...(s.signal ? [s.signal] : []), ...(s.signals || [])];
}

export function safeUrl(url: string | null | undefined) {
  if (!url) return undefined;
  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" || parsed.protocol === "http:" ? parsed.toString() : undefined;
  } catch {
    return undefined;
  }
}

export function hostOf(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}
