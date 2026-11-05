import { getApiBaseUrl } from "@/lib/api";
import { api } from "@/lib/session";
import type { Value } from "./radar-model";

export const siBase = () => `${getApiBaseUrl()}/api/si`;

/** Every SalesIntel call goes through the shared client, which adds the signed-in session in hosted mode. */
export function si<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  return api<T>(`/api/si${path}`, init);
}

export type LeadStatus = "new" | "watching" | "investigating" | "dismissed";
export type Lead = {
  key: string; type: "public" | "private"; source_label: string; organisation: string; title: string; why_now: string; category: string; category_label: string;
  basis: "published" | "inferred"; timing: string | null; days: number | null; timing_label: string; light?: "green" | "amber" | "red" | "grey";
  nation: string | null; region?: string | null; tier: number | null; services: string[]; supplier: string | null; value: Value | null;
  status: LeadStatus; account_id: number | null; link_basis: string | null; people?: number; contact_routes?: number;
  kind: "published_procurement" | "contract_ending" | "private_signal" | "customer_expansion" | "unverified_candidate"; kind_label: string; brief: Brief;
};
export type Brief = {
  why_customer: string[]; fit: { matched: string[]; gaps: string[]; unknown: string[] }; why_now: string; why_now_basis: string; inferred_timing: string;
  known: { text: string; source_url: string | null; date: string; basis: string }[]; unknown: string[];
  who: { roles: string[]; routes_saved: number; people_in_research: number; summary: string }; next: string;
};
export type DiscoverResult = { items: Lead[]; total: number; counts: { public: number; private: number }; interpreted: { nations: string[]; services: string[]; regions: string[]; keywords: string[] }; gaps: string[] };
export type Evidence = { label: string; url: string; date?: string; basis?: string };
export type SourceSummary = {
  key: string; type: "public" | "private"; title: string; why_now: string; category_label: string; light?: string; timing: string | null; supplier: string | null;
  value: Value | null; basis: string; evidence: Evidence[]; missing: string[]; link_basis: string; confirmed: boolean; name_seen: string;
};
export type ContactT = { id: number; name: string | null; role: string; email: string | null; phone: string | null; label: string; basis: "published" | "user_entered"; source_url: string | null; source_quote: string | null; status: "unverified" | "verified" | "do_not_contact"; influence: string };
export type ActivityT = { id: number; kind: string; direction: string; summary: string; outcome: string; requirements: string; objections: string; commitments: string; occurred_at: string; contact_id: number | null; deal_id: number | null; draft_id: number | null };
export type TaskT = { id: number; title: string; due_on: string; status: "open" | "done" | "cancelled"; account_id: number; deal_id: number | null; account?: string };
export type DraftT = { id: number; account_id: number; contact_id: number | null; deal_id: number | null; channel: string; subject: string; body: string; evidence: Evidence[]; gaps: string[]; status: "draft" | "approved" | "logged" | "suppressed"; updated_at: string; account?: string };
export type AccountT = {
  id: number; name: string; kind: string; company_number: string | null; website: string | null; sector: string | null; region: string | null; status: string; watched: boolean; notes: string;
  identities: { name_seen: string; entity_type: string; entity_id: number; basis: string; confirmed: boolean }[];
  sources: SourceSummary[]; known: { text: string; basis: string; source: string }[]; to_confirm: string[]; next_step: string;
  contacts: ContactT[]; sites: { id: number; name: string; address: string; postcode: string | null; uprn: string | null; basis: string; source_url: string | null }[];
  activities: ActivityT[]; tasks: TaskT[]; drafts: DraftT[]; deals: { id: number; title: string; stage: string; opportunity_id: number; value_total: number | null; value_basis: string }[];
};
export type AccountRow = { id: number; name: string; kind: string; region: string | null; sector: string | null; status: string; watched: boolean; sources: number; contacts: number; open_deals: number; next_due: string | null; overdue: boolean; last_activity: string | null };
export type QueueItem = { kind: "follow_up" | "draft" | "deal" | "intelligence"; priority: number; title: string; why: string; account: string | null; account_id: number; deal_id?: number | null; task_id?: number; draft_id?: number; due_on?: string };
export type TodayT = { queue: QueueItem[]; upcoming: TaskT[]; new_leads: Lead[]; as_of: string };
export type ScopeItem = { service: string; field: string; question: string; unit: string; value: string | number | null; basis: string | null };
export type QuoteLine = { key: string; description: string; quantity: number | null; quantity_basis: string | null; unit: string; rate: string | null; total: string | null; warning: string };
export type Approval = { version: number; reviewer: string; approved_at: string; subtotal: string | null; superseded_at?: string; superseded_reason?: string };
export type DealT = {
  id: number; title: string; stage: string; stages: string[]; account_id: number; account: string; opportunity_id: number; origin_type: string | null; origin: Partial<SourceSummary> & { captured_at?: string };
  services: string[]; work_type: string; work_types: Record<string, string>; qualification: Record<string, string>; value_annual: number | null; value_total: number | null; value_basis: string;
  next_step: string; scope: ScopeItem[]; quote: { status?: "draft" | "approved" | "superseded"; version?: number; lines?: QuoteLine[]; rates?: Record<string, string>; missing?: string[]; subtotal?: string | null; partial_total?: string | null; approved_by?: string | null; terms_note?: string; approvals?: Approval[]; superseded_reason?: string | null };
  handover: Record<string, unknown>; outcome_reason: string; activities: ActivityT[]; tasks: TaskT[]; service_labels: Record<string, string>;
};
export type DealCard = { id: number; title: string; account: string | null; account_id: number; stage: string; services: string[]; value_total: number | null; value_annual: number | null; value_basis: string; next_step: string; quote_status: string | null; updated_at: string };
export type Prefs = { territory: string[]; services: string[]; company_name: string; sender_name: string };

export const SERVICES: [string, string][] = [["fire_alarm", "Fire alarm"], ["cctv", "CCTV"], ["access_control", "Access control"], ["intruder", "Intruder"], ["emergency_lighting", "Emergency lighting"], ["sprinkler", "Sprinklers"], ["monitoring", "Monitoring"]];
export const SERVICE_NAME: Record<string, string> = Object.fromEntries(SERVICES);
export const STAGE_LABEL: Record<string, string> = { qualify: "Qualify", engage: "Engage", survey: "Survey", proposal: "Proposal", bid_review: "Bid review", negotiation: "Negotiation", approval: "Approval", won: "Won", lost: "Lost" };
export const OUTCOMES: [string, string][] = [["", "No outcome"], ["connected", "Spoke to them"], ["no_answer", "No answer"], ["left_message", "Left a message"], ["interested", "Interested"], ["not_interested", "Not interested"], ["meeting_booked", "Meeting booked"], ["requirement_captured", "Requirement captured"], ["call_back", "Asked to call back"]];
export const BASIS_LABEL: Record<string, string> = { company_number: "Same company number", same_name: "Same name (unconfirmed)", user_confirmed: "Confirmed by you", created_from: "Account created from this record" };

export function goto(view: string, params: Record<string, string | number | null> = {}) {
  const url = new URL(window.location.href);
  url.search = "";
  url.searchParams.set("view", view);
  for (const [k, v] of Object.entries(params)) if (v !== null && v !== undefined && v !== "") url.searchParams.set(k, String(v));
  window.history.pushState({}, "", url);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export function param(name: string) {
  return typeof window === "undefined" ? null : new URL(window.location.href).searchParams.get(name);
}

/** A local calendar date n days from today. Not toISOString(), which is UTC and lands on the wrong day just after midnight in summer. */
export const inDays = (n: number) => {
  const d = new Date(); d.setDate(d.getDate() + n);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
export function dayLabel(iso: string | null | undefined) {
  if (!iso) return "";
  const d = new Date(`${iso.slice(0, 10)}T00:00:00`);
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const diff = Math.round((d.getTime() - today.getTime()) / 86_400_000);
  if (diff === 0) return "Today";
  if (diff === 1) return "Tomorrow";
  if (diff === -1) return "Yesterday";
  if (diff < 0) return `${-diff} days overdue`;
  if (diff < 7) return d.toLocaleDateString("en-GB", { weekday: "long" });
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}
export const when = (iso: string) => new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

/** Show an exact amount (a decimal string from the API) without passing it through floating point. */
export function pounds(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") return "Unknown";
  const [whole, fraction = ""] = String(value).split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const pence = fraction.length === 0 ? "" : `.${fraction.padEnd(2, "0")}`;
  return `£${grouped}${pence}`;
}
