"use client";

import { useState } from "react";
import { Copy } from "lucide-react";
import { safeSource } from "./api";
import { Button } from "./ui";

type PrepObservation = { id: string; source_title: string; source_url: string; published_date: string | null; fact: string };
type PrepOpportunity = { organisation: string; location: string; headline: string; thesis: string; supporting_observation_ids: string[]; counter_observation_ids: string[]; unknowns: string[]; contact_name: string; contact_role: string; engagement: string; verification_action: string; potential_solution?: string };

/** Prepare only material already in the research, explicitly preserving uncertainty. */
export function buildConversationPrep(opportunity: PrepOpportunity, observations: PrepObservation[]): string {
  const observationsFor = (ids: string[]) => ids.map((id) => observations.find((item) => item.id === id)).filter((item): item is PrepObservation => Boolean(item));
  const sourceLine = (item: PrepObservation) => `- ${item.fact}\n  ${item.source_title || "Source"} · ${item.published_date || "date not provided"}${safeSource(item.source_url) ? ` · ${item.source_url}` : " · source link unavailable"}`;
  const supporting = observationsFor(opportunity.supporting_observation_ids);
  const alternative = observationsFor(opportunity.counter_observation_ids);
  const lines = [
    `${opportunity.organisation}${opportunity.location ? ` · ${opportunity.location}` : ""}`,
    opportunity.headline,
    "",
    "Research hypothesis — verify before use",
    opportunity.thesis || "Not established.",
    "",
    "Who to approach — confirm the current person and role",
    [opportunity.contact_name, opportunity.contact_role].filter(Boolean).join(" · ") || "Not established.",
    "",
    "Opening conversation to adapt",
    opportunity.engagement || "Not established.",
    "",
    "Next verification",
    opportunity.verification_action || "Not established.",
    "",
    "Unknowns",
    ...(opportunity.unknowns.length ? opportunity.unknowns.map((item) => `- ${item}`) : ["- None recorded; review the evidence for gaps."]),
    "",
    "Supporting observations — check original sources and dates",
    ...(supporting.length ? supporting.map(sourceLine) : ["- None recorded."]),
    "",
    "Alternative context",
    ...(alternative.length ? alternative.map(sourceLine) : ["- None recorded; this does not rule out other explanations."]),
  ];
  if (opportunity.potential_solution) lines.push("", "Possible solution to explore — not a confirmed requirement or delivery capability", opportunity.potential_solution);
  lines.push("", "Review the sources, current arrangements and contact details before engagement. Do not treat hypotheses as confirmed requirements.");
  return lines.join("\n");
}

export function ConversationPrep({ opportunity, observations }: { opportunity: PrepOpportunity; observations: PrepObservation[] }) {
  const [message, setMessage] = useState("");
  const [open, setOpen] = useState(false);
  const prep = buildConversationPrep(opportunity, observations);
  return <details onToggle={(event) => setOpen(event.currentTarget.open)} className="mt-5 border-t border-[var(--misi-border)] pt-5"><summary className="cursor-pointer text-sm font-semibold text-[var(--misi-ink)]">Prepare for a conversation</summary>{open && <><p className="mt-2 text-xs leading-5 text-[var(--misi-muted)]">A reviewable briefing assembled from this research, including unknowns and alternative evidence. Verify it before use.</p><pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-[var(--misi-surface-secondary)] p-4 font-sans text-sm leading-6 text-[var(--misi-ink)]">{prep}</pre><Button className="mt-3" onClick={() => { void navigator.clipboard.writeText(prep).then(() => setMessage("Briefing copied. Review and tailor it before use.")).catch(() => setMessage("Copy unavailable. Select and copy the briefing above.")); }}><Copy size={14} aria-hidden="true" /> Copy briefing</Button>{message && <p className="mt-2 text-xs text-[var(--misi-ink)]" role="status">{message}</p>}</>}</details>;
}
