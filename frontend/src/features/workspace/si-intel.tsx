"use client";
/**
 * The daily intelligence layer in the interface: your best opportunities (with the reasons, never a score), the guided
 * play for an account, its missing information as research you can start with one click, the buying committee with
 * contact confidence, and what discovery has led to. Every state shown here is read from the API, never assumed.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowRight, ArrowUpRight, Check, ChevronDown, CircleDashed, CircleDot, FileSearch, Loader2, RotateCcw, Search, UserSearch } from "lucide-react";
import { Pill } from "./ds";
import { safeUrl } from "./radar-model";
import { goto, pounds, si } from "./si-api";
import { newKey, type JobT } from "./si-people";

type Known = { text: string; source_url: string | null; date: string; basis: string };
export type BestItem = {
  key: string; organisation: string; account_id: number | null; type: "public" | "private" | "shadow"; kind: string; kind_label: string; title: string; site?: string | null;
  tier: "act_now" | "this_week" | "watch"; tier_label: string; reasons: string[]; cautions: string[]; why_customer: string[]; why_now: string; why_now_basis: string;
  known: Known[]; unknown: string[]; speak_to: { roles: string[]; routes_saved: number; summary: string }; next: string; timing: string | null; days: number | null;
  services: string[]; signals: { key: string; type: string; label: string; why_now: string }[];
  relationship: { status: string; open_deals: number; overdue: { title: string; due_on: string }[]; requirement: { text: string; on: string } | null; last_activity: string | null } | null;
};
type ProfileT = { basis: "stated" | "learned"; stated: { services: string[]; territory: string[]; sectors: string[] }; complete: boolean; caveat: string; won: number; minimum_won: number;
  learned: { sectors: { name: string; won: number }[]; services: { name: string; won: number }[]; median_total_value: number | null; median_days_to_win: number | null } | null };
type BestT = { as_of: string; items: BestItem[]; total: number; in_view: number; tiers: Record<string, number>; set_aside: { reason: string; count: number }[]; profile: ProfileT; method: string };
type Finding = { answer: string; text: string; quote: string; source_url: string; source_date: string; official: boolean };
export type GapReqT = { id: number; gap: string; subject: string; question: string; status: string; summary: string; findings: Finding[]; rejected: { text: string; source: string; reason: string }[];
  sources: number; job_id: number | null; cost_cents: number; created_at: string; resolved_at: string | null; job?: JobT | null; reused?: boolean };
type Person = { id: number; name: string | null; role: string; email?: string | null; phone?: string | null; level: number; label: string; detail: string; freshness: string; age_days: number | null; usable: boolean };
type Role = { key: string; label: string; part: string; status: "covered" | "route_only" | "gap"; people: Person[]; gap: { gap: string; subject: string } | null };
export type CommitteeT = { play: string; roles: Role[]; others: Person[]; best_level: number; best_label: string; levels: { level: number; label: string; detail: string }[] };
type Step = { key: string; label: string; state: "done" | "next" | "partial" | "todo"; detail: string; action?: string | null };
export type PlayT = { account_id: number; play: string; label: string; hypothesis: string; qualify: string[]; steps: Step[]; next: Step | null; done: number; total: number;
  gaps: { gap: string; subject: string; question: string; request: GapReqT | null; open: boolean }[]; committee: CommitteeT; outcome: { deal_id: number; stage: string } | null };
type SourceResult = { accounts: number; steps: { key: string; label: string; accounts: number }[]; won_value: Record<string, number>; research_cents: number;
  cost_per_researched_account: number; cost_per_account_with_contacts: number | null; cost_per_qualified: number | null; median_days_to_first_outreach: number | null };
type ResultsT = { sources: Record<string, SourceResult>; leads_presented: number; leads_opened: number; labels: Record<string, string>; note: string };

const TYPE_COLOUR: Record<string, string> = { public: "#2a78d6", shadow: "#eb6834", private: "#8e8b93" };
const dollars = (cents: number) => `$${(cents / 100).toFixed(2)}`;

// ------------------------------------------------------------------ Best opportunities (Today)

export function BestOpportunities({ notify }: { notify: (m: string, e?: boolean) => void }) {
  const [data, setData] = useState<BestT | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { si<BestT>("/best").then(setData).catch((e) => setError((e as Error).message)); }, []);
  // A lead counts as presented only once its card has been at least half on screen for a second, never because the list loaded.
  const list = useRef<HTMLOListElement>(null);
  useEffect(() => {
    const root = list.current;
    if (!data || !root || typeof IntersectionObserver === "undefined") return;
    const sent = new Set<string>();
    const pending = new Map<string, ReturnType<typeof setTimeout>>();
    let batch: string[] = [];
    let flush: ReturnType<typeof setTimeout> | null = null;
    const report = (key: string) => {
      if (sent.has(key)) return;
      sent.add(key); batch.push(key);
      if (!flush) flush = setTimeout(() => { const keys = batch; batch = []; flush = null; void si("/best/seen", { method: "POST", json: { keys } }).catch(() => {}); }, 400);
    };
    const observer = new IntersectionObserver((entries) => {
      for (const e of entries) {
        const key = (e.target as HTMLElement).dataset.lead;
        if (!key) continue;
        if (e.isIntersecting && !pending.has(key)) pending.set(key, setTimeout(() => report(key), 1000));
        if (!e.isIntersecting && pending.has(key)) { clearTimeout(pending.get(key)); pending.delete(key); }
      }
    }, { threshold: 0.5 });
    root.querySelectorAll<HTMLElement>("[data-lead]").forEach((el) => observer.observe(el));
    return () => { observer.disconnect(); pending.forEach(clearTimeout); if (flush) clearTimeout(flush); };
  }, [data]);

  async function investigate(x: BestItem) {
    if (x.account_id) return goto("clients", { account: x.account_id });
    setBusy(x.key);
    try {
      let account: number;
      if (x.type === "shadow") {
        account = (await si<{ account_id: number }>(`/radar/hypotheses/${x.key.slice(3)}/investigate`, { method: "POST", json: {}, headers: { "Idempotency-Key": newKey() } })).account_id;
      } else {
        account = (await si<{ account_id: number }>(`/discover/${x.key}/account`, { method: "POST", json: {} })).account_id;
        await si(`/accounts/${account}/investigate`, { method: "POST", json: {}, headers: { "Idempotency-Key": newKey() } });
      }
      notify(`Investigating ${x.organisation}. It keeps running if you leave this page.`);
      goto("clients", { account });
    } catch (e) { notify((e as Error).message, true); } finally { setBusy(null); }
  }

  let last = "";
  return (
    <section aria-label="Your best opportunities" className="space-y-3">
      <div className="si-section-head">
        <div><h2 className="!text-[15px]">Your best opportunities</h2>
          <p>{data ? <>{data.items.length} worth your time, ranked by the reasons shown; no score or probability is used.
            {data.in_view > 0 && <> {data.in_view} more are kept in view in <button className="font-medium text-ds-ink underline decoration-ds-border-strong underline-offset-2" onClick={() => goto("find")}>Discover</button>.</>}</> : "Ranking today's leads against your profile…"}</p></div>
        {data && <details className="relative text-right"><summary className="cursor-pointer text-[12px] font-medium text-ds-ink-2 hover:text-ds-ink">How these are chosen <ChevronDown size={12} className="si-chevron inline" /></summary>
          <div className="absolute right-0 z-10 mt-2 w-[min(420px,85vw)] rounded-[10px] border border-ds-border bg-white p-4 text-left text-[12.5px] leading-[19px] text-ds-ink-2 shadow-ds-lg">
            <p className="font-semibold text-ds-ink">{data.profile.basis === "learned" ? "Your stated profile and patterns in your won deals" : "Your stated profile"}</p>
            <p className="mt-1">{data.profile.caveat}</p>
            <p className="mt-2">{data.method}</p>
            {!!data.set_aside.length && <p className="mt-2 text-ds-muted">Set aside: {data.set_aside.map((s) => `${s.count} ${s.reason.toLowerCase()}`).join("; ")}.</p>}
            {!data.profile.complete && <button className="ds-btn sm mt-3" onClick={() => goto("settings")}>Complete your profile</button>}
          </div></details>}
      </div>
      {error && <p role="alert" className="text-[13px] text-ds-red">{error}</p>}
      {!data && !error && <div className="space-y-2">{[0, 1, 2].map((i) => <div key={i} className="ds-skeleton h-[118px] rounded-[10px]" />)}</div>}
      {data && !data.items.length && <p className="ds-card px-4 py-6 text-[13px] text-ds-muted">Nothing fits your profile today. Widen your services or territory, or run new research in Discover.</p>}
      <ol ref={list} className="si-stagger space-y-2">
        {data?.items.map((x) => {
          const head = x.tier_label !== last ? x.tier_label : null;
          last = x.tier_label;
          return (
            <li key={x.key}>
              {head && <p className={`si-eyebrow mb-2 mt-4 first:mt-0 ${x.tier === "act_now" ? "!text-[#c2410c]" : ""}`}>{head}</p>}
              <article aria-label={x.organisation} data-lead={x.key} className="ds-card si-best p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
                      <span className="si-type" style={{ ["--c" as string]: TYPE_COLOUR[x.type] }}><i aria-hidden="true" />{x.kind_label}</span>
                      {x.relationship?.status === "customer" && <Pill tone="green">Customer</Pill>}
                      {x.relationship?.open_deals ? <Pill>{x.relationship.open_deals} open deal{x.relationship.open_deals === 1 ? "" : "s"}</Pill> : null}
                    </p>
                    <h3 className="mt-1 text-[16px] font-semibold leading-snug text-ds-ink">{x.organisation}</h3>
                    {(x.site || x.title) && <p className="truncate text-[13px] text-ds-muted">{x.site || x.title}</p>}
                  </div>
                  <div className="flex flex-none gap-1.5">
                    <button className="ds-btn ghost sm" onClick={() => goto("find", { lead: x.key })}>Evidence</button>
                    <button className="ds-btn primary sm" disabled={busy === x.key} onClick={() => void investigate(x)} aria-label={`${x.account_id ? "Open" : "Investigate"} ${x.organisation}`}>
                      {busy === x.key ? <Loader2 size={14} className="ds-spin" /> : x.account_id ? <ArrowRight size={14} /> : <FileSearch size={14} />}{x.account_id ? "Open" : "Investigate"}</button>
                  </div>
                </div>
                <p className="mt-2.5 text-[13.5px] leading-[20px] text-ds-ink"><span className="font-semibold">Why now: </span>{x.why_now}
                  <span className={`ml-1.5 align-middle text-[10.5px] font-semibold uppercase tracking-wide ${x.why_now_basis === "Published" ? "text-ds-green" : "text-ds-amber"}`}>{x.why_now_basis}</span></p>
                {!!x.reasons.length && <ul className="mt-2 flex flex-wrap gap-1.5" aria-label="Why it is on your list">{x.reasons.slice(0, 4).map((r) => <li key={r} className="inline-flex items-center gap-1 rounded-[5px] bg-[#f1f0ec] px-2 py-0.5 text-[12px] text-ds-ink-2"><Check size={11} className="text-ds-green" aria-hidden="true" />{r}</li>)}</ul>}
                {!!x.cautions.length && <p className="mt-1.5 text-[12px] text-ds-amber">{x.cautions[0]}</p>}
                <details className="mt-2.5 border-t border-ds-border pt-2">
                  <summary className="flex cursor-pointer items-center gap-1 text-[12.5px] font-medium text-ds-ink-2 hover:text-ds-ink"><ChevronDown size={13} className="si-chevron" /> What we know, what we don&apos;t, who to speak to</summary>
                  <div className="mt-2 grid gap-4 text-[12.5px] leading-[19px] text-ds-ink-2 md:grid-cols-3">
                    <div><p className="si-eyebrow mb-1">What we know</p><ul className="space-y-1">{x.known.length ? x.known.map((k, i) => { const href = safeUrl(k.source_url || ""); return <li key={i}>{k.text}{href && <> <a className="font-medium text-ds-ink underline decoration-ds-border-strong underline-offset-2" href={href} target="_blank" rel="noreferrer">source</a></>}</li>; }) : <li>Only the signal above so far.</li>}</ul></div>
                    <div><p className="si-eyebrow mb-1">What we don&apos;t know</p><ul className="space-y-1">{x.unknown.map((u) => <li key={u}>{u}</li>)}</ul></div>
                    <div><p className="si-eyebrow mb-1">Who to speak to</p><ul className="space-y-1">{x.speak_to.roles.map((r) => <li key={r}>{r}</li>)}</ul><p className="mt-1 text-ds-muted">{x.speak_to.summary}</p></div>
                  </div>
                  <p className="mt-3 text-[12.5px]"><span className="font-semibold text-ds-ink">Next: </span>{x.next}</p>
                </details>
              </article>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

// ------------------------------------------------------------------ The guided play (account)

export function usePlay(accountId: number) {
  const [play, setPlay] = useState<PlayT | null>(null);
  const load = useCallback(async () => { try { setPlay(await si<PlayT>(`/accounts/${accountId}/play`)); } catch { /* shown by the account page */ } }, [accountId]);
  useEffect(() => { void load(); }, [load]);
  return [play, load] as const;
}

const STEP_ICON = { done: <Check size={12} strokeWidth={3} />, next: <CircleDot size={12} />, partial: <CircleDot size={12} />, todo: <CircleDashed size={12} /> };

export function PlayPanel({ play, onAction }: { play: PlayT; onAction: (action: string) => void }) {
  const next = play.next;
  const label: Record<string, string> = { investigate: "Investigate", people: "Find the right people", gaps: "Resolve missing information", engage: "Prepare the approach",
    log: "Log what happened", qualify: "Qualify into a deal" };
  return (
    <section aria-label="Play" className="ds-card overflow-hidden">
      <div className="flex flex-wrap items-start justify-between gap-3 px-4 pt-4">
        <div className="min-w-0"><p className="si-eyebrow">Play · {play.label}</p>
          <p className="mt-1 max-w-3xl text-[13.5px] leading-[20px] text-ds-ink-2">{play.hypothesis}</p></div>
        <div className="flex items-center gap-3">
          <span className="si-mono text-[12px] text-ds-muted">{play.done}/{play.total}</span>
          {next?.action && <button className="ds-btn primary sm" onClick={() => onAction(next.action!)}>{label[next.action] || next.label} <ArrowRight size={14} /></button>}
        </div>
      </div>
      <ol className="mt-3 flex gap-px overflow-x-auto border-t border-ds-border bg-ds-border" aria-label="Steps">
        {play.steps.map((s) => (
          <li key={s.key} aria-current={next?.key === s.key ? "step" : undefined}
            className={`relative min-w-[112px] flex-1 bg-white px-2.5 py-2.5 ${next?.key === s.key ? "!bg-[#fffaf6]" : ""}`}>
            <p className={`flex items-center gap-1.5 text-[12px] font-semibold ${s.state === "done" ? "text-ds-green" : next?.key === s.key ? "text-[#c2410c]" : s.state === "partial" ? "text-ds-amber" : "text-ds-muted"}`}>
              {STEP_ICON[s.state]}<span className="text-ds-ink">{s.label}</span><span className="sr-only"> ({s.state === "done" ? "done" : s.state === "partial" ? "in progress" : next?.key === s.key ? "next" : "to do"})</span></p>
            <p className="mt-0.5 text-[11.5px] leading-[16px] text-ds-muted">{s.detail}</p>
          </li>
        ))}
      </ol>
      <details className="border-t border-ds-border px-4 py-2.5">
        <summary className="flex cursor-pointer items-center gap-1 text-[12.5px] font-medium text-ds-ink-2 hover:text-ds-ink"><ChevronDown size={13} className="si-chevron" /> What qualifies this opportunity</summary>
        <ul className="mt-2 grid gap-1 text-[12.5px] text-ds-ink-2 md:grid-cols-2">{play.qualify.map((q) => <li key={q} className="flex gap-2"><span className="mt-[7px] h-1 w-1 flex-none rounded-full bg-ds-ink-2" />{q}</li>)}</ul>
      </details>
    </section>
  );
}

// ------------------------------------------------------------------ Missing information: resolve this gap

const OUTCOME: Record<string, [string, "green" | "amber" | "red" | "neutral" | "blue"]> = {
  queued: ["Waiting to start", "neutral"], running: ["Researching", "blue"], resolved: ["Resolved with evidence", "green"], partial: ["Partly resolved", "amber"],
  conflicting: ["Sources disagree", "amber"], not_found: ["Not found", "neutral"], provider_unavailable: ["Research unavailable here", "neutral"],
  needs_human: ["Needs a person to confirm", "amber"], failed: ["Did not complete", "red"],
};

function useGap(initial: GapReqT | null, onDone: () => void) {
  const [req, setReq] = useState(initial);
  const done = useRef(onDone);
  useEffect(() => { done.current = onDone; }, [onDone]);
  useEffect(() => setReq(initial), [initial]);
  useEffect(() => {
    if (!req || !["queued", "running"].includes(req.status)) return;
    const t = setInterval(async () => {
      try {
        const next = await si<GapReqT>(`/gaps/${req.id}`);
        setReq(next);
        if (!["queued", "running"].includes(next.status)) { clearInterval(t); done.current(); }
      } catch { clearInterval(t); }
    }, 1500);
    return () => clearInterval(t);
  }, [req]);
  return req;
}

function GapRow({ accountId, gap, onChanged, notify }: { accountId: number; gap: PlayT["gaps"][number]; onChanged: () => void; notify: (m: string, e?: boolean) => void }) {
  const req = useGap(gap.request, onChanged);
  const [busy, setBusy] = useState(false);
  async function ask(refresh = false) {
    setBusy(true);
    try {
      const r = await si<GapReqT>(`/accounts/${accountId}/gaps`, { method: "POST", json: { gap: gap.gap, subject: gap.subject, question: gap.question, refresh }, headers: { "Idempotency-Key": newKey() } });
      notify(r.reused ? "Already researched: showing what was found." : "Research started. It keeps running if you leave this page.");
      onChanged();
    } catch (e) { notify((e as Error).message, true); } finally { setBusy(false); }
  }
  const [label, tone] = (req ? OUTCOME[req.status] || [req.status, "neutral"] : ["Open", "neutral"]) as [string, "green" | "amber" | "red" | "neutral" | "blue"];
  const active = req && ["queued", "running"].includes(req.status);
  return (
    <li className="py-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 flex-1"><p className="text-[13.5px] font-semibold text-ds-ink">{gap.subject}</p><p className="text-[12.5px] text-ds-muted">{gap.question}</p></div>
        <div className="flex flex-none items-center gap-2">
          {req && <Pill tone={tone}>{active && <Loader2 size={11} className="ds-spin" />}{label}</Pill>}
          {!req && <button className="ds-btn sm" disabled={busy} onClick={() => void ask()} aria-label={`Resolve this gap: ${gap.subject}`}><Search size={13} /> Resolve this gap</button>}
          {req && !active && req.status !== "resolved" && <button className="ds-btn ghost sm" disabled={busy} onClick={() => void ask(true)} aria-label={`Ask again: ${gap.subject}`}><RotateCcw size={13} /> Ask again</button>}
        </div>
      </div>
      {req && !active && <div className="mt-2 rounded-[8px] bg-[#faf9f7] px-3 py-2.5 text-[12.5px] leading-[19px] text-ds-ink-2">
        <p>{req.summary}</p>
        {!!req.findings.length && <ul className="mt-2 space-y-2">{req.findings.map((f, i) => { const href = safeUrl(f.source_url); return (
          <li key={i}><span className="font-semibold text-ds-ink">{f.answer}</span>{f.quote && <span className="italic"> “{f.quote}”</span>}
            {href && <> <a className="inline-flex items-center gap-0.5 font-medium text-ds-ink underline decoration-ds-border-strong underline-offset-2" href={href} target="_blank" rel="noreferrer">{f.official ? "Official source" : "Third-party source"}<ArrowUpRight size={11} /></a></>}</li>); })}</ul>}
        <p className="mt-2 text-[11.5px] text-ds-muted">{req.sources} source{req.sources === 1 ? "" : "s"} checked · {req.cost_cents ? dollars(req.cost_cents) : "no AI cost"}{req.rejected.length ? ` · ${req.rejected.length} claim${req.rejected.length === 1 ? "" : "s"} rejected: ${req.rejected[0].reason}` : ""}</p>
      </div>}
    </li>
  );
}

export function GapsPanel({ play, onChanged, notify }: { play: PlayT; onChanged: () => void; notify: (m: string, e?: boolean) => void }) {
  return (
    <section id="si-gaps" aria-label="Missing information" className="ds-card scroll-mt-24 px-4 pt-3.5 pb-1">
      <div className="flex flex-wrap items-baseline justify-between gap-2"><h2 className="text-[14px] font-semibold text-ds-ink">Missing information</h2>
        <p className="text-[12px] text-ds-muted">Each question is researched from sources only. Not found stays not found.</p></div>
      <ul className="divide-y divide-ds-border">{play.gaps.map((g) => <GapRow key={`${g.gap}-${g.subject}-${g.request?.id || 0}`} accountId={play.account_id} gap={g} onChanged={onChanged} notify={notify} />)}</ul>
    </section>
  );
}

// ------------------------------------------------------------------ Buying committee

const LEVEL_TONE = (p: Person): "green" | "amber" | "red" | "neutral" | "blue" => !p.usable ? "red" : p.level <= 3 ? "green" : p.level === 4 ? "amber" : "neutral";

export function CommitteePanel({ play, onChanged, notify }: { play: PlayT; onChanged: () => void; notify: (m: string, e?: boolean) => void }) {
  const c = play.committee;
  const [busy, setBusy] = useState<string | null>(null);
  async function find(role: Role) {
    setBusy(role.key);
    try {
      const r = await si<GapReqT>(`/accounts/${play.account_id}/gaps`, { method: "POST", json: { gap: "find_role", subject: role.label }, headers: { "Idempotency-Key": newKey() } });
      notify(r.reused ? "Already searched for this role: see Missing information." : `Searching for the ${role.label.toLowerCase()}.`);
      onChanged();
    } catch (e) { notify((e as Error).message, true); } finally { setBusy(null); }
  }
  const asked = new Set(play.gaps.filter((g) => g.gap === "find_role" && g.request).map((g) => g.subject));
  return (
    <section aria-label="Buying committee" className="ds-card px-4 pt-3.5 pb-1">
      <div className="flex flex-wrap items-baseline justify-between gap-2"><h2 className="text-[14px] font-semibold text-ds-ink">Buying committee</h2>
        <details className="text-[12px]"><summary className="cursor-pointer font-medium text-ds-ink-2 hover:text-ds-ink">Contact confidence levels</summary>
          <ul className="mt-2 space-y-1 text-ds-ink-2">{c.levels.map((l) => <li key={l.level}><span className="si-mono">{l.level}</span> {l.label}: <span className="text-ds-muted">{l.detail}</span></li>)}</ul></details></div>
      <ul className="divide-y divide-ds-border">{c.roles.map((r) => (
        <li key={r.key} className="flex flex-wrap items-start justify-between gap-3 py-3">
          <div className="min-w-0 flex-1">
            <p className="text-[13.5px] font-semibold text-ds-ink">{r.label} <span className="ml-1 text-[12px] font-normal text-ds-muted">{r.part}</span></p>
            {!r.people.length ? <p className="text-[12.5px] text-ds-muted">Nobody on record for this role yet.</p> : <ul className="mt-1 space-y-1">{r.people.map((p) => (
              <li key={p.id} className="flex flex-wrap items-center gap-2 text-[12.5px] text-ds-ink-2"><span className="font-medium text-ds-ink">{p.name || p.role}</span>{p.name && <span className="text-ds-muted">{p.role}</span>}
                <Pill tone={LEVEL_TONE(p)}>{p.label}</Pill>{p.freshness === "stale" && <Pill tone="red">Stale</Pill>}{p.freshness === "ageing" && <span className="text-ds-muted">checked {p.age_days}d ago</span>}</li>))}</ul>}
          </div>
          {r.status !== "covered" && !asked.has(r.label) && <button className="ds-btn sm" disabled={busy === r.key} onClick={() => void find(r)} aria-label={`Find the ${r.label.toLowerCase()}`}><UserSearch size={13} /> Find this person</button>}
          {r.status !== "covered" && asked.has(r.label) && <span className="text-[12px] text-ds-muted">Searched: see Missing information</span>}
        </li>))}</ul>
    </section>
  );
}

// ------------------------------------------------------------------ Results (Deals)

export function ResultsView() {
  const [data, setData] = useState<ResultsT | null>(null);
  useEffect(() => { si<ResultsT>("/results").then(setData).catch(() => setData(null)); }, []);
  if (!data) return <div className="ds-skeleton h-60 rounded-xl" />;
  const sources = Object.entries(data.sources);
  if (!sources.length) return <p className="ds-card px-4 py-8 text-center text-[13px] text-ds-muted">Nothing recorded yet. Results appear as discovered leads become accounts, conversations and deals.</p>;
  const steps = sources[0][1].steps;
  return (
    <section aria-label="Results" className="space-y-3">
      <div className="ds-card overflow-x-auto">
        <table className="w-full min-w-[620px] text-left text-[13px]">
          <thead><tr className="border-b border-ds-border text-[12px] text-ds-muted"><th className="px-4 py-2.5 font-medium">Accounts reaching each step</th>{sources.map(([k]) => <th key={k} className="px-3 py-2.5 text-right font-medium">{data.labels[k] || k}</th>)}</tr></thead>
          <tbody>{steps.map((s, i) => <tr key={s.key} className="border-b border-ds-border last:border-0"><td className="px-4 py-2 text-ds-ink-2">{s.label}</td>
            {sources.map(([k, v]) => <td key={k} className="si-mono px-3 py-2 text-right text-ds-ink">{v.steps[i].accounts}</td>)}</tr>)}</tbody>
        </table>
      </div>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">{sources.map(([k, v]) => (
        <div key={k} className="ds-card p-4 text-[12.5px] text-ds-ink-2"><p className="si-eyebrow">{data.labels[k] || k}</p>
          <p className="mt-2">Research spend <span className="si-mono float-right text-ds-ink">{dollars(v.research_cents)}</span></p>
          <p>Per researched account <span className="si-mono float-right text-ds-ink">{v.cost_per_researched_account ? dollars(v.cost_per_researched_account) : "—"}</span></p>
          <p>Per account with contacts <span className="si-mono float-right text-ds-ink">{v.cost_per_account_with_contacts ? dollars(v.cost_per_account_with_contacts) : "—"}</span></p>
          <p>Per qualified deal <span className="si-mono float-right text-ds-ink">{v.cost_per_qualified ? dollars(v.cost_per_qualified) : "—"}</span></p>
          <p>Days to first outreach <span className="si-mono float-right text-ds-ink">{v.median_days_to_first_outreach ?? "—"}</span></p>
          {Object.entries(v.won_value).map(([basis, value]) => <p key={basis}>Won ({basis.replace(/_/g, " ")}) <span className="si-mono float-right text-ds-ink">{pounds(value)}</span></p>)}
        </div>))}</div>
      <p className="text-[12px] text-ds-muted">{data.leads_presented} lead{data.leads_presented === 1 ? "" : "s"} presented on Today, {data.leads_opened} opened. {data.note}</p>
    </section>
  );
}
