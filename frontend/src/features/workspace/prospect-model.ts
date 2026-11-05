import { getApiBaseUrl } from "@/lib/api";
import type { Tone } from "./radar-model";

export type ProspectSignal = { type: string; title: string; detail: string; date: string; basis: "stated" | "inferred"; direction: "supports" | "against" | "neutral"; source_url: string };
export type TimingClue = {
  kind: string; label: string; detail: string; basis: string; strength: "strong" | "moderate" | "weak"; observed: string; precision: string;
  source_url: string; system_family: string; polarity: number; start: string; end: string; rule: string; status: "active" | "upcoming" | "past"; context_only?: boolean;
};
export type Timing = {
  phase: "engage_now" | "prepare" | "not_yet" | "unknown"; light: "green" | "amber" | "red" | "grey"; label: string;
  window: { start: string; end: string } | null; convergence: { start: string; end: string; kinds: string[]; labels: string[] } | null;
  blocked_until: string | null; reasons: string[]; clues: TimingClue[]; as_of: string; method: string;
};
export type Person = { name: string; role: string; influence: "decision_maker" | "influencer" | "user" | "gatekeeper"; why: string; source_url: string; quote: string };
export type ContactRoute = { kind: "email" | "phone" | "web_form" | "switchboard"; value: string; label: string; source_url: string; quote: string };
export type Prospect = {
  id: number; name: string; status: "new" | "watching" | "pipeline" | "dismissed"; opportunity_id: number | null; created_at: string; updated_at: string;
  website: string; sector: string; location: string; company_number: string; size: string; headline: string; summary: string;
  signals: ProspectSignal[]; incumbent: { name: string; detail: string; basis: string; source_url: string };
  competitors: { name: string; relation: string; source_url: string }[]; people: Person[]; contact_routes: ContactRoute[];
  approach: { angle: string; opening_line: string; offer: string; questions: string[] }; services: string[]; unknowns: string[];
  checks?: { people: number; contact_routes: number; links: number }; researched_at?: string; sources_reviewed?: number; brief?: string;
  timing: Timing; signal_groups: string[]; signal_labels: Record<string, string>;
};
export type Search = { id: number; query: string; mode: "discover" | "company"; status: "running" | "complete" | "failed"; error: string | null; prospect_ids: number[]; sources_reviewed: number; created_at: string; finished_at: string | null };

export const prospectBase = () => `${getApiBaseUrl()}/api/prospects`;

export const LIGHT: Record<Timing["light"], { tone: Tone; dot: string; ring: string; text: string; soft: string }> = {
  green: { tone: "green", dot: "#12b76a", ring: "#d1fadf", text: "var(--ds-green)", soft: "var(--ds-green-soft)" },
  amber: { tone: "amber", dot: "#f79009", ring: "#fef0c7", text: "var(--ds-amber)", soft: "var(--ds-amber-soft)" },
  red: { tone: "red", dot: "#f04438", ring: "#fee4e2", text: "var(--ds-red)", soft: "var(--ds-red-soft)" },
  grey: { tone: "neutral", dot: "#98a2b3", ring: "#eaecf0", text: "var(--ds-muted)", soft: "var(--ds-subtle)" },
};
export const PHASE_HELP: Record<Timing["phase"], string> = {
  engage_now: "Clues say they are likely to be deciding now. Make contact.",
  prepare: "A buying window is opening soon, or only weak clues are active. Build the relationship.",
  not_yet: "Recently contracted or the window is more than a year away. Watch for a trigger.",
  unknown: "No dated clue yet. Research further before investing time.",
};
export const GROUP_TONE: Record<string, Tone> = { Growth: "green", Change: "brand", Risk: "red", Estate: "amber", Incumbent: "violet", Requirement: "blue", Strategy: "neutral" };
export const SIGNAL_GROUP: Record<string, string> = {
  expansion: "Growth", new_site: "Growth", acquisition: "Growth", investment: "Growth", hiring_fm_security: "Growth",
  leadership_change: "Change", outsourcing_or_restructure: "Change", relocation: "Change",
  security_incident: "Risk", fire_incident: "Risk", enforcement_action: "Risk", insurance_or_audit_pressure: "Risk", regulatory_deadline: "Risk",
  refurbishment: "Estate", planning_application: "Estate", ageing_systems: "Estate",
  incumbent_poor_performance: "Incumbent", incumbent_distress: "Incumbent", contract_change: "Incumbent", competitor_activity: "Incumbent",
  stated_requirement: "Requirement", customer_complaints: "Requirement",
  cost_consolidation: "Strategy", technology_strategy: "Strategy", esg_strategy: "Strategy", peak_risk_event: "Strategy",
};
export const INFLUENCE_LABEL: Record<Person["influence"], string> = { decision_maker: "Decision maker", influencer: "Influencer", user: "User", gatekeeper: "Gatekeeper" };
export const SERVICE_LABEL: Record<string, string> = { fire_alarm: "Fire alarm", cctv: "CCTV", access_control: "Access control", intruder: "Intruder", emergency_lighting: "Emergency lighting", sprinkler: "Sprinklers", general: "Fire & security" };

export const PLAYS = [
  { label: "New warehouses & distribution centres", query: "UK logistics, warehousing and distribution companies opening or expanding sites in 2026 and 2027" },
  { label: "Retailers facing rising theft", query: "UK retailers and shopping centre owners publicly reporting rising theft, violence against staff or security investment" },
  { label: "PSTN switch-off exposure", query: "UK multi-site businesses whose fire and intruder alarms likely still signal over analogue phone lines ahead of the PSTN switch-off on 31 January 2027" },
  { label: "New head of facilities or security", query: "UK private companies that appointed a new head of facilities, estates, property or security in the last nine months" },
  { label: "Competitor in difficulty", query: "UK fire and security maintenance companies in financial difficulty, administration or losing contracts, and the customers they serve" },
  { label: "Data centres & life sciences", query: "Data centre, laboratory and life sciences developments under construction or recently opened in the UK" },
  { label: "Hotels & leisure refurbishments", query: "UK hotel, leisure and hospitality groups refurbishing or opening sites in 2026 and 2027" },
  { label: "Building safety remediation", query: "UK private landlords, build-to-rent and student accommodation operators with building safety or fire remediation programmes" },
];

export function monthLabel(iso: string | null | undefined) {
  if (!iso) return "";
  const d = new Date(`${iso.slice(0, 10)}T00:00:00Z`);
  return Number.isNaN(d.getTime()) ? iso : new Intl.DateTimeFormat("en-GB", { month: "short", year: "numeric", timeZone: "UTC" }).format(d);
}
