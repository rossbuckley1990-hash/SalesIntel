"use client";
/** The Living Opportunity: one source-backed brief per lead or account (GET /api/si/brief/{key}), and the Action Dock that
 *  runs its one recommended next move. Every number, date and name comes from the API; nothing here is inferred. */
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { AlertTriangle, ArrowUpRight, Briefcase, CalendarPlus, Check, ChevronDown, CircleDot, Clock3, FilePenLine, FileSearch, History, Loader2, Minus, MessageSquare, Search, Sparkles,
  TrendingDown, TrendingUp, Users, Wallet } from "lucide-react";
import { hostOf, safeUrl } from "./radar-model";
import { SERVICES, dayLabel, goto, inDays, si, VERDICTS, ensureRep, repName, type VerdictT, type VerdictValue } from "./si-api";
import { ActivityForm } from "./si-shared";
import { JobStatus, newKey, useJob, type JobT } from "./si-people";
import { FieldView, NoticeFacts, type FieldT, type NoticeT } from "./si-notice";
import { authMode } from "@/lib/session";
import "./living.css";

export type BriefEvent = { date: string; date_kind: string; title: string; detail: string; source: { url: string; label: string } | null; basis: string; establishes: string;
  not_established: string; effect: "supports" | "weakens" | "context"; recorded: string | null; new: boolean };
export type BriefGap = { gap: string; subject: string; question: string; value: "decisive" | "timing" | "access"; value_label: string; why: string;
  status: "open" | "researching" | "resolved" | "stale" | "not_found" | "conflicting" | "partial"; request_id: number | null; job_id: number | null; answer: string;
  findings: { text?: string; source_url?: string; quote?: string }[]; researched: string | null; action: "research" | "ask_customer" | null; cost_cents: number; answered_from?: "notice" | "records" };
export type BriefAction = { action: string; label: string; why: string; produces: string; available: boolean; unavailable_reason: string; params: Record<string, string | number>;
  cost_cents: number; blocked?: { label: string; reason: string }[] };
export type BriefT = {
  key: string; account_id: number | null; source_key: string | null; kind: string; kind_label: string;
  organisation: { name: string; sector?: string | null; location?: string | null; website?: string | null; company_number?: string | null };
  reveal: { headline: string; happened: { text: string; detail: string; date: string; source: string; basis: string } | null; why: string; heuristic: string | null;
    services: { family: string; label: string; status: "named" | "possible"; basis: string }[]; disprove: string[]; key_question: BriefGap | null;
    freshness: { latest_evidence: string; first_seen: string | null; last_researched: string | null; stale: boolean; note: string } };
  next: BriefAction; alternatives: BriefAction[]; research: { available: boolean; reason: string }; gaps: BriefGap[]; evidence: BriefEvent[];
  relationships: { kind: string; label: string; name: string; basis: string; source: string }[]; journey: { label: string; state: "done" | "current" | "later" }[];
  story: { date: string; kind: string; text: string; detail: string }[]; stakeholders: { name: string; role: string; status: string; source: string | null; route: string }[];
  unknowns: string[]; recorded_requirement: string; sources: { key: string; title: string }[]; since_last_review: { since: string | null; new_events: number };
  notice?: NoticeT | null; field?: FieldT | null;
  /** Whether this record came from a lead (only a lead can be judged), and the standing verdict on it. */
  judgeable?: boolean; verdict?: VerdictT | null;
};
type Notify = (m: string, e?: boolean) => void;
type Running = { label: string; job: JobT; gapRequestId?: number };
type GapReq = { id: number; status: string; summary?: string; reused?: boolean; job: JobT | null };

const LEAD_KEY = /^(sh|mo|pr|mc):\d+$/;
const money = (cents: number) => `$${(cents / 100).toFixed(2)}`;
const DATE_KIND: Record<string, string> = { reported: "Reported", event: "Event", first_seen: "First seen", published: "Published", researched: "Researched", recorded: "Recorded" };
const BASIS: Record<string, string> = { stated: "Stated in source", published: "Published", inferred: "Inferred", research: "SalesIntel research", recorded: "Recorded by your team", reported: "Reported" };
const GAP_STATUS: Record<BriefGap["status"], [string, string]> = {
  open: ["Open", "open"], researching: ["Researching", "running"], resolved: ["Answered", "done"], stale: ["Answer is old: check again", "warn"],
  not_found: ["Not published: ask the customer", "warn"], conflicting: ["Sources disagree: ask the customer", "warn"], partial: ["Partly answered", "warn"] };

function month(iso: string) {
  if (!iso) return "Undated";
  if (/^\d{4}$/.test(iso)) return iso;
  const d = new Date(`${iso.length === 7 ? `${iso}-01` : iso.slice(0, 10)}T00:00:00`);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("en-GB", iso.length === 7 ? { month: "short", year: "numeric" } : { day: "numeric", month: "short", year: "numeric" });
}
function sinceLabel(iso: string) {
  const then = new Date(`${iso.slice(0, 10)}T00:00:00`), today = new Date();
  today.setHours(0, 0, 0, 0);
  const days = Math.round((today.getTime() - then.getTime()) / 86_400_000);
  if (days <= 0) return "Nothing new since you looked earlier today";
  return `Nothing new since you looked ${days === 1 ? "yesterday" : days < 14 ? `${days} days ago` : `on ${month(iso.slice(0, 10))}`}`;
}
const future = (iso: string) => !!iso && iso.slice(0, 10) > new Date().toISOString().slice(0, 10);

function Source({ url, label }: { url: string; label?: string }) {
  const href = safeUrl(url);
  if (!href) return null;
  return <a className="lo-source" href={href} target="_blank" rel="noreferrer">{label || hostOf(href)}<ArrowUpRight size={12} aria-hidden="true" /></a>;
}

/** The brief plus the actions that change it. One instance is shared by the brief and its dock, so both always agree. */
export function useOpportunity(key: string | null, notify: Notify, { markReviewed = true, onChanged }: { markReviewed?: boolean; onChanged?: () => void } = {}) {
  const [brief, setBrief] = useState<BriefT | null>(null);
  const [error, setError] = useState("");
  const [running, setRunning] = useState<Running | null>(null);
  const [form, setForm] = useState<null | "log" | "follow" | "qualify">(null);
  const [busy, setBusy] = useState("");
  const latest = useRef(key);
  const shownAt = useRef(0);
  const changed = useRef(onChanged);
  changed.current = onChanged;

  const load = useCallback(async () => {
    if (!key) return;
    try {
      const who = await ensureRep();
      const b = await si<BriefT>(`/brief/${key}${who ? `?${new URLSearchParams({ rep: who })}` : ""}`);
      if (latest.current !== key) return; // a slower answer for a lead no longer selected
      setBrief(b); setError("");
      shownAt.current = shownAt.current || Date.now();
    } catch (e) { if (latest.current === key) setError((e as Error).message); }
  }, [key]);
  useEffect(() => {
    latest.current = key;
    shownAt.current = 0;
    setBrief(null); setRunning(null); setForm(null); void load();
    // Marked as reviewed when you move on after reading it (not a glance), so "new since you last looked" stays true while you read.
    const seen = () => {
      if (key && markReviewed && shownAt.current && Date.now() - shownAt.current > 1500) void si(`/brief/${key}/reviewed`, { method: "POST", keepalive: true }).catch(() => {});
    };
    window.addEventListener("pagehide", seen);
    return () => { window.removeEventListener("pagehide", seen); seen(); };
  }, [load, key, markReviewed]);

  // Research already running (started here, on another screen, or before a reload) is picked up again: the job is durable.
  useEffect(() => {
    if (running || !brief) return;
    const g = brief.gaps.find((x) => x.status === "researching" && x.job_id);
    if (!g?.job_id) return;
    si<JobT>(`/research-jobs/${g.job_id}`).then(async (job) => {
      if (["queued", "running"].includes(job.status)) return setRunning({ label: g.question, job, gapRequestId: g.request_id || undefined });
      // It finished between the two reads: bring the question's status up to date instead of watching a finished job.
      if (g.request_id) await si(`/gaps/${g.request_id}`).catch(() => {});
      await load();
    }).catch(() => {});
  }, [brief, running, load]);

  const refresh = useCallback(async () => { await load(); changed.current?.(); }, [load]);

  async function ensureAccount(): Promise<number> {
    if (brief?.account_id) return brief.account_id;
    if (!brief?.source_key) throw new Error("This record cannot be saved as an account.");
    const linked = await si<{ account_id: number; created: boolean; basis: string }>(`/discover/${brief.source_key}/account`, { method: "POST", json: {} });
    notify(linked.created ? `Saved ${brief.organisation.name} as an account.` : linked.basis === "same_name"
      ? `Linked to the existing ${brief.organisation.name} account by name. Confirm it is the same organisation.` : `Linked to the existing ${brief.organisation.name} account.`);
    return linked.account_id;
  }

  async function research(gap: Pick<BriefGap, "gap" | "subject" | "question">, refreshAnswer = false) {
    setBusy(`gap:${gap.gap}`);
    try {
      const id = await ensureAccount();
      const lead = brief?.source_key && LEAD_KEY.test(brief.source_key) ? brief.source_key : null;
      const r = await si<GapReq>(`/accounts/${id}/gaps`, { method: "POST", headers: { "Idempotency-Key": newKey() },
        json: { gap: gap.gap, subject: gap.subject, question: gap.question, lead_key: lead, refresh: refreshAnswer } });
      if (r.job && ["queued", "running"].includes(r.job.status)) {
        setRunning({ label: gap.question, job: r.job, gapRequestId: r.id });
        notify(r.reused ? "This question is already being researched." : "Research started. It keeps running if you leave or refresh this page.");
      } else notify(r.reused ? "Already researched: showing the saved answer." : "Research finished.");
      await refresh();
    } catch (e) { notify((e as Error).message, true); } finally { setBusy(""); }
  }

  async function run(a: BriefAction) {
    if (!a.available || !brief) return;
    if (["log_contact", "complete_follow_up"].includes(a.action)) {
      if (form === "log") return setForm(null);
      if (!brief.account_id) {
        setBusy(a.action);
        try { await ensureAccount(); await refresh(); } catch (e) { notify((e as Error).message, true); return; } finally { setBusy(""); }
      }
      return setForm("log");
    }
    if (a.action === "set_follow_up") return setForm(form === "follow" ? null : "follow");
    if (a.action === "qualify") {
      if (form === "qualify") return setForm(null);
      if (!brief.account_id) { // a deal belongs to an account, so the organisation is saved first
        setBusy(a.action);
        try { await ensureAccount(); await refresh(); } catch (e) { notify((e as Error).message, true); return; } finally { setBusy(""); }
      }
      return setForm("qualify");
    }
    if (a.action === "open_notice") { // reading the buyer's own documents: a new tab, nothing recorded
      const href = safeUrl(String(a.params.url || ""));
      if (href) window.open(href, "_blank", "noopener,noreferrer"); else notify("The notice does not give a link to open.", true);
      return;
    }
    if (a.action === "research_gap") return research(a.params as { gap: string; subject: string; question: string });
    setBusy(a.action);
    try {
      if (a.action === "open_account") { await ensureAccount(); await refresh(); }
      else if (a.action === "find_people") {
        const id = await ensureAccount();
        const job = await si<JobT & { reused: boolean }>(`/accounts/${id}/people-search`, { method: "POST", json: { refresh: false }, headers: { "Idempotency-Key": newKey() } });
        setRunning({ label: "Finding the right people", job });
        await refresh();
      } else if (a.action === "prepare_introduction") {
        const id = await ensureAccount();
        const intro = await si<{ subject: string; body: string; gaps: string[]; evidence: unknown[] }>(`/accounts/${id}/introduction`, { method: "POST", json: { source_key: brief.source_key && LEAD_KEY.test(brief.source_key) ? brief.source_key : null } });
        const draft = await si<{ id: number }>(`/accounts/${id}/drafts`, { method: "POST", json: { subject: intro.subject, body: intro.body, evidence: intro.evidence, gaps: intro.gaps } });
        notify("Introduction drafted from the evidence. Nothing is sent: review it first.");
        goto("engage", { account: id, draft: draft.id, source: brief.source_key && LEAD_KEY.test(brief.source_key) ? brief.source_key : null });
      } else if (a.action === "investigate") {
        const shadow = brief.source_key?.startsWith("sh:") && !brief.account_id;
        const r = shadow
          ? await si<{ account_id: number; job: JobT & { reused: boolean } }>(`/radar/hypotheses/${brief.source_key!.slice(3)}/investigate`, { method: "POST", json: {}, headers: { "Idempotency-Key": newKey() } })
          : await si<{ job: JobT & { reused: boolean } }>(`/accounts/${await ensureAccount()}/investigate`, { method: "POST", json: {}, headers: { "Idempotency-Key": newKey() } });
        setRunning({ label: "Deep investigation", job: r.job });
        notify(r.job.reused ? "Opening the investigation already saved." : "Investigation started. It keeps running if you leave this page.");
        await refresh();
      }
    } catch (e) { notify((e as Error).message, true); } finally { setBusy(""); }
  }

  /** One tap. The server stores it with the evidence shown; "Wrong" hides the lead, and tapping a verdict again takes it back. */
  async function judge(verdict: VerdictValue | "cleared") {
    if (!brief || !key) return;
    const was = brief.verdict?.value;
    setBusy("verdict");
    try {
      const r = await si<{ verdict: VerdictT | null }>(`/brief/${key}/verdict`, { method: "POST", json: { verdict, rep: repName() } });
      setBrief((b) => (b ? { ...b, verdict: r.verdict } : b));
      notify(verdict === "cleared" ? "Verdict taken back." : verdict === "wrong" ? "Marked wrong. It is hidden from your lists." : "Verdict recorded.");
      if (verdict === "wrong" || was === "wrong") changed.current?.();
    } catch (e) { notify((e as Error).message, true); } finally { setBusy(""); }
  }

  const finished = useCallback(async () => {
    const gapId = running?.gapRequestId;
    if (gapId) await si(`/gaps/${gapId}`).catch(() => {}); // brings the request's status up to date with its job
    setRunning(null);
    await refresh();
  }, [running, refresh]);

  return { key, brief, error, running, finished, form, setForm, busy, run, research, judge, ensureAccount, refresh, reload: load, notify };
}
export type Opportunity = ReturnType<typeof useOpportunity>;

/** A ref to attach, and whether that element is at least `px` wide: decides whether the dock sits beside the brief or just
 *  under its reveal. A callback ref, so it measures whenever the element appears (after loading, not only on first render). */
export function useWide(px: number) {
  const [el, setEl] = useState<HTMLElement | null>(null);
  const [wide, setWide] = useState(false);
  useLayoutEffect(() => {
    if (!el) return;
    const measure = () => setWide(el.getBoundingClientRect().width >= px);
    measure();
    const watch = new ResizeObserver(measure);
    watch.observe(el);
    return () => watch.disconnect();
  }, [el, px]);
  return [setEl, wide] as const;
}

// ------------------------------------------------------------------ the brief

export function OpportunityBrief({ op, children, afterReveal }: { op: Opportunity; children?: ReactNode; afterReveal?: ReactNode }) {
  const b = op.brief;
  if (op.error) return <p role="alert" className="rounded-lg border border-ds-red-line bg-ds-red-soft px-3 py-2 text-[13px] text-ds-red">{op.error}</p>;
  if (!b) return <div className="space-y-3" aria-busy="true"><div className="ds-skeleton h-8 w-3/4" /><div className="ds-skeleton h-40" /><div className="ds-skeleton h-56" /></div>;
  return (
    <article className="lo" aria-label={`Opportunity: ${b.organisation.name}`}>
      <Reveal b={b} op={op} />
      {afterReveal}
      {b.notice && <NoticeFacts n={b.notice} />}
      {b.field && <FieldView f={b.field} own={b.source_key || undefined} />}
      <Gaps op={op} />
      <River b={b} />
      <div className="lo-split">
        <Relationships b={b} />
        <Journey b={b} />
      </div>
      <Story b={b} />
      {children}
    </article>
  );
}

function Reveal({ b, op }: { b: BriefT; op: Opportunity }) {
  const [all, setAll] = useState(false);
  const r = b.reveal;
  const f = r.freshness;
  const named = r.services.filter((s) => s.status === "named");
  const possible = r.services.filter((s) => s.status === "possible");
  const since = b.since_last_review;
  const kq = r.key_question;
  return (
    <header className="lo-reveal" aria-label="Opportunity at a glance">
      <p className="lo-eyebrow">{b.kind_label}<span aria-hidden="true"> · </span>{b.organisation.name}
        {since.since && <span className={`lo-since ${since.new_events ? "new" : ""}`}>{since.new_events ? `${since.new_events} new since you last looked` : sinceLabel(since.since)}</span>}</p>
      <h2 className="lo-headline">{r.headline}</h2>
      {r.happened && <p className="lo-happened">
        {r.happened.detail && <span>{r.happened.detail} </span>}
        <span className="lo-meta">{month(r.happened.date)} · {BASIS[r.happened.basis] || r.happened.basis}{r.happened.source && <> · <Source url={r.happened.source} /></>}</span></p>}
      {f.stale && <p className="lo-warn" role="note"><AlertTriangle size={14} aria-hidden="true" />{f.note}</p>}

      <div className="lo-grid">
        <section aria-label="Why it could matter">
          <h3 className="lo-q">Why it could matter</h3>
          <p>{r.why}</p>
          {r.heuristic && <p className="lo-heuristic"><span>Rule of thumb, not a fact</span>{r.heuristic}</p>}
        </section>
        <section aria-label="What could be sold">
          <h3 className="lo-q">What could be sold</h3>
          {!r.services.length ? <p className="lo-muted">Nothing identifiable from the evidence yet.</p> : <>
            {!!named.length && <ul className="lo-tags" aria-label="Named in a source">{named.map((s) => <li key={s.family} className="lo-tag named" title={s.basis}><Check size={12} aria-hidden="true" />{s.label}</li>)}</ul>}
            {!!possible.length && <ul className="lo-tags" aria-label="Possible, not stated">{possible.map((s) => <li key={s.family} className="lo-tag possible" title={s.basis}>{s.label}</li>)}</ul>}
            <p className="lo-note">{named.length ? "Ticked: named in a source. " : ""}{possible.length ? "Dashed: possible, not stated by any source." : ""}</p></>}
        </section>
        <section aria-label="What could make it irrelevant">
          <h3 className="lo-q">What could make it irrelevant</h3>
          {!r.disprove.length ? <p className="lo-muted">Nothing recorded against it yet.</p> : <ul className="lo-list">
            {(all ? r.disprove : r.disprove.slice(0, 3)).map((d) => <li key={d} className={d.startsWith("Contrary evidence") || d.startsWith("Your deep investigation") ? "against" : ""}>{d}</li>)}</ul>}
          {r.disprove.length > 3 && <button className="lo-more" onClick={() => setAll(!all)} aria-expanded={all}>{all ? "Show fewer" : `Show all ${r.disprove.length}`}</button>}
        </section>
        <section aria-label="What to find out next">
          <h3 className="lo-q">What to find out next</h3>
          {!kq ? <p className="lo-muted">No open question.</p> : <>
            <p className="lo-key">{kq.question}</p>
            <p className="lo-note"><strong>{kq.value_label}.</strong> {kq.why}</p>
            {kq.status !== "open" && <p className="lo-note">Status: {GAP_STATUS[kq.status][0]}</p>}
            {op.brief && kq.action === "research" && <button className="lo-link" onClick={() => document.getElementById(`lo-gaps-${b.key}`)?.scrollIntoView({ behavior: "smooth", block: "start" })}>See every open question</button>}</>}
        </section>
      </div>
      <Verdict op={op} />
      <p className="lo-fresh"><Clock3 size={12} aria-hidden="true" />Latest sourced evidence {f.latest_evidence ? month(f.latest_evidence) : "none dated"}
        {f.first_seen && <> · first seen {month(f.first_seen)}</>} · {f.last_researched ? `last researched ${month(f.last_researched)}` : "not researched yet"}</p>
    </header>
  );
}

/** The rep's verdict, asked right after what was read. It is the measure of whether a lead was worth showing. */
export function Verdict({ op, compact = false }: { op: Pick<Opportunity, "brief" | "busy" | "judge">; compact?: boolean }) {
  const b = op.brief;
  if (!b?.judgeable) return null;
  const given = b.verdict?.value;
  return (
    <section className={`lo-verdict${compact ? " compact" : ""}`} aria-label="Your verdict">
      {!compact && <h3 className="lo-q">Your verdict</h3>}
      <div className="lo-verdict-row" role="group" aria-label="Verdict on this lead">
        {VERDICTS.map(([id, label]) => <button key={id} type="button" className={id === "wrong" ? "no" : ""} aria-pressed={given === id} disabled={op.busy === "verdict"}
          onClick={() => void op.judge(given === id ? "cleared" : id)}>{label}</button>)}
      </div>
      {!compact && <p className="lo-note">{given ? "Recorded with the evidence shown here. Tap it again to take it back." : "One tap. It is stored with the evidence shown here, and never changes the order of a list."}</p>}
    </section>
  );
}

function GapRow({ g, op }: { g: BriefGap; op: Opportunity }) {
  const [label, tone] = GAP_STATUS[g.status];
  const running = op.running?.gapRequestId && op.running.gapRequestId === g.request_id;
  const research = op.brief?.research;
  return (
    <li className="lo-gap" data-status={g.status}>
      <div className="lo-gap-head">
        <span className="lo-value" data-value={g.value}>{g.value === "decisive" ? "Decisive" : g.value === "timing" ? "Timing" : "Access"}</span>
        <span className={`lo-state ${tone}`}>{tone === "running" && <Loader2 size={11} className="ds-spin" aria-hidden="true" />}{label}</span>
      </div>
      <p className="lo-gap-q">{g.question}</p>
      <p className="lo-note">{g.why}</p>
      {g.answer && <p className="lo-answer"><span className="lo-q">{g.answered_from === "notice" ? "From the published notice" : g.answered_from === "records" ? "From published contract records" : `Answer${g.researched ? `, ${month(g.researched)}` : ""}`}</span>{g.answer}
        {g.findings.filter((x) => x.source_url).slice(0, 3).map((x, i) => <Source key={i} url={x.source_url!} />)}</p>}
      {running && op.running && <JobWatch op={op} />}
      {!running && g.action === "research" && <div className="lo-gap-act">
        {research?.available ? <button className="ds-btn sm" disabled={!!op.busy} onClick={() => void op.research(g, g.status === "stale")}><Search size={13} aria-hidden="true" />{g.status === "stale" ? "Check again" : "Research this"}<span className="lo-cost">up to {money(g.cost_cents)}</span></button>
          : <p className="lo-note">{research?.reason || "Research is not available here."}</p>}
      </div>}
      {!running && g.action === "ask_customer" && <div className="lo-gap-act"><button className="ds-btn sm" onClick={() => op.setForm("log")}><MessageSquare size={13} aria-hidden="true" />Record the customer’s answer</button></div>}
    </li>
  );
}

function Gaps({ op }: { op: Opportunity }) {
  const b = op.brief!;
  if (!b.gaps.length) return null;
  const answered = b.gaps.filter((g) => g.status === "resolved").length;
  return (
    <section id={`lo-gaps-${b.key}`} className="lo-section" aria-label="Questions that decide this opportunity">
      <div className="lo-section-head"><h3>Questions that decide it</h3><span className="lo-meta">{answered} of {b.gaps.length} answered · ranked by what they could change</span></div>
      <ol className="lo-gaps">{b.gaps.map((g) => <GapRow key={`${g.gap}-${g.subject}`} g={g} op={op} />)}</ol>
    </section>
  );
}

const EFFECT: Record<BriefEvent["effect"], [string, typeof TrendingUp]> = { supports: ["Supports", TrendingUp], weakens: ["Weakens", TrendingDown], context: ["Context", Minus] };

function River({ b }: { b: BriefT }) {
  const [open, setOpen] = useState<number | null>(null);
  const [all, setAll] = useState(false);
  const shown = all ? b.evidence : b.evidence.slice(0, 8);
  return (
    <section className="lo-section" aria-label="Evidence, newest first">
      <div className="lo-section-head"><h3>Evidence, newest first</h3><span className="lo-meta">Each date says what kind of date it is</span></div>
      {!b.evidence.length ? <p className="lo-muted">No dated evidence yet.</p> : <ol className="lo-river">
        {shown.map((e, i) => {
          const [effect, Icon] = EFFECT[e.effect];
          const expanded = open === i;
          const ahead = e.date_kind === "event" && future(e.date);
          return (
            <li key={`${e.date}-${i}`} className="lo-event" data-effect={e.effect} data-new={e.new || undefined}>
              <span className="when"><span>{month(e.date)}</span><small>{ahead ? "Expected" : DATE_KIND[e.date_kind] || e.date_kind}</small></span>
              <span className="rail" aria-hidden="true"><i /></span>
              <div className="body">
                <button className="lo-event-title" aria-expanded={expanded} onClick={() => setOpen(expanded ? null : i)}>
                  <span>{e.title}</span>{e.new && <span className="lo-new">New</span>}<ChevronDown size={14} aria-hidden="true" className={expanded ? "rot" : ""} /></button>
                <p className="lo-event-meta"><span className={`lo-effect ${e.effect}`}><Icon size={12} aria-hidden="true" />{effect}</span> · {BASIS[e.basis] || e.basis}
                  {e.source?.url && <> · <Source url={e.source.url} /></>}</p>
                {expanded && <dl className="lo-event-detail">
                  {e.detail && <div><dt>Detail</dt><dd>{e.detail}</dd></div>}
                  {e.establishes && <div><dt>What it establishes</dt><dd>{e.establishes}</dd></div>}
                  {e.not_established && <div><dt>What it does not establish</dt><dd>{e.not_established}</dd></div>}
                  {e.source?.url && <div><dt>Source</dt><dd><Source url={e.source.url} label={`${e.source.label} · ${hostOf(safeUrl(e.source.url) || "")}`} /></dd></div>}
                </dl>}
              </div>
            </li>);
        })}
      </ol>}
      {b.evidence.length > 8 && <button className="lo-more" onClick={() => setAll(!all)} aria-expanded={all}>{all ? "Show the latest only" : `Show all ${b.evidence.length}`}</button>}
    </section>
  );
}

function Relationships({ b }: { b: BriefT }) {
  const people = b.stakeholders.filter((s) => s.name && !b.relationships.some((r) => r.kind === "person" && r.name === s.name));
  const rows = [...b.relationships.map((r) => ({ name: r.name, label: r.label, basis: BASIS[r.basis] || r.basis, source: r.source })),
    ...people.map((p) => ({ name: p.name, label: [p.role, p.status].filter(Boolean).join(" · "), basis: p.status === "named by a source" ? "Stated in source" : "On the account", source: p.source || "" }))];
  return (
    <section className="lo-section" aria-label="Who is involved">
      <div className="lo-section-head"><h3>Who is involved</h3><span className="lo-meta">Only what a source or your team recorded</span></div>
      {!rows.length ? <p className="lo-muted">Nobody is named in the sources yet. Who maintains the systems today is still unknown.</p> : <ul className="lo-rels">
        {rows.map((r) => <li key={`${r.name}-${r.label}`}><span className="lo-mark" aria-hidden="true">{r.name.split(/\s+/).slice(0, 2).map((w) => w[0]).join("").toUpperCase()}</span>
          <span className="min-w-0"><span className="name">{r.name}</span><span className="role">{r.label}</span></span>
          <span className="lo-rel-basis">{r.basis}{r.source && <Source url={r.source} />}</span></li>)}
      </ul>}
      {!!b.unknowns.length && <div className="lo-unknowns"><h4 className="lo-q">Still unknown</h4><ul className="lo-list">{b.unknowns.map((u) => <li key={u}>{u}</li>)}</ul></div>}
    </section>
  );
}

function Journey({ b }: { b: BriefT }) {
  return (
    <section className="lo-section" aria-label="Path to a deal">
      <div className="lo-section-head"><h3>Path to a deal</h3><span className="lo-meta">For a {b.kind_label.toLowerCase()}</span></div>
      <ol className="lo-journey">{b.journey.map((s, i) => <li key={s.label} data-state={s.state} aria-current={s.state === "current" ? "step" : undefined}>
        <span className="dot" aria-hidden="true">{s.state === "done" ? <Check size={11} /> : i + 1}</span><span>{s.label}<span className="sr-only">{s.state === "done" ? " (done)" : s.state === "current" ? " (current step)" : ""}</span></span></li>)}</ol>
      <p className="lo-note">Each step is ticked only from what is recorded: a saved finding, a draft, a logged conversation or a deal.</p>
    </section>
  );
}

const STORY_ICON: Record<string, typeof History> = { discovered: Sparkles, research: FileSearch, contact: Users, draft: FilePenLine, interaction: MessageSquare, deal: Briefcase };

function Story({ b }: { b: BriefT }) {
  return (
    <section className="lo-section" aria-label="Deal story">
      <div className="lo-section-head"><h3>The story so far</h3><span className="lo-meta">Built from what was recorded, in order</span></div>
      {!b.story.length ? <p className="lo-muted">Nothing recorded yet. The story starts when you save, research or contact this organisation.</p> : <ol className="lo-story">
        {b.story.map((s, i) => { const Icon = STORY_ICON[s.kind] || CircleDot; return <li key={i}><Icon size={14} aria-hidden="true" /><span className="when">{month(s.date.slice(0, 10))}</span>
          <span className="min-w-0"><span className="text">{s.text}</span>{s.detail && <span className="detail">{s.detail}</span>}</span></li>; })}
      </ol>}
    </section>
  );
}

// ------------------------------------------------------------------ the Action Dock

function JobWatch({ op }: { op: Opportunity }) {
  const [job] = useJob(op.running!.job, op.finished as () => void);
  if (!job) return null;
  return <div className="lo-job"><p className="lo-note">{op.running!.label}</p><JobStatus job={job} /></div>;
}

const ACTION_ICON: Record<string, typeof Search> = { research_gap: Search, find_people: Users, prepare_introduction: FilePenLine, log_contact: MessageSquare, complete_follow_up: Check,
  set_follow_up: CalendarPlus, qualify: Briefcase, investigate: FileSearch, open_account: Briefcase, open_notice: ArrowUpRight };

export function ActionDock({ op, onAccountPage = false }: { op: Opportunity; onAccountPage?: boolean }) {
  const b = op.brief;
  if (!b) return <div className="lo-dock" aria-busy="true"><div className="ds-skeleton m-4 h-24" /></div>;
  const n = b.next;
  const Icon = ACTION_ICON[n.action] || Sparkles;
  const budget = (reason: string) => /budget/i.test(reason) && authMode === "local";
  const runningElsewhere = op.running && !b.gaps.some((g) => g.request_id && g.request_id === op.running?.gapRequestId);
  const alternatives = b.alternatives.filter((a) => a.action !== "open_account"); // saving is always one click away, at the foot
  return (
    <section className="lo-dock" aria-label="Next move">
      <div className="lo-dock-main">
        <p className="lo-eyebrow">Next move</p>
        <p className="lo-dock-label">{n.label}</p>
        <p className="lo-dock-why">{n.why}</p>
        <p className="lo-dock-produces"><span>You get</span>{n.produces}</p>
        {!!n.cost_cents && <p className="lo-dock-cost"><Wallet size={13} aria-hidden="true" />Up to {money(n.cost_cents)} from the approved research budget, only if it runs</p>}
        <button className="ds-btn primary lo-dock-go" disabled={!n.available || !!op.busy} onClick={() => void op.run(n)}>
          {op.busy === n.action || op.busy === `gap:${n.params.gap}` ? <Loader2 size={15} className="ds-spin" aria-hidden="true" /> : <Icon size={15} aria-hidden="true" />}
          {n.action === "research_gap" ? "Research the key question" : n.label.replace(/ \(due .*\)$/, "")}</button>
        {!n.available && n.unavailable_reason && <p className="lo-note">{n.unavailable_reason}</p>}
        {runningElsewhere && <JobWatch op={op} />}
        {!!n.blocked?.length && <div className="lo-blocked" role="note">
          <p className="lo-q">Would come first, but cannot run here</p>
          {n.blocked.map((x) => <p key={x.label}><strong>{x.label.replace(/^Research: /, "Research: ")}</strong> {x.reason}
            {budget(x.reason) && <button className="lo-link" onClick={() => goto("budget")}>Open the research budget</button>}</p>)}
        </div>}
      </div>
      {op.form === "log" && b.account_id !== null && <div className="lo-dock-form"><ActivityForm compact accountId={b.account_id} notify={op.notify}
        onSaved={async () => { const t = n.action === "complete_follow_up" ? n.params.task_id : null; if (t) await si(`/tasks/${t}/complete`, { method: "POST" }).catch(() => {}); op.setForm(null); await op.refresh(); }} /></div>}
      {op.form === "log" && b.account_id === null && <NeedsAccount op={op} />}
      {op.form === "follow" && b.account_id !== null && <FollowUpForm accountId={b.account_id} notify={op.notify} onDone={async () => { op.setForm(null); await op.refresh(); }} />}
      {op.form === "qualify" && b.account_id !== null && <div className="lo-dock-form"><QualifyForm accountId={b.account_id} sources={b.sources} requirement={b.recorded_requirement}
        notify={op.notify} onCancel={() => op.setForm(null)} title={n.action === "qualify" ? n.label : "Qualify into a deal"} /></div>}
      {!!alternatives.length && <div className="lo-alts">
        <p className="lo-q">Or instead</p>
        <ul>{alternatives.map((a) => { const AIcon = ACTION_ICON[a.action] || Sparkles; return <li key={a.action}>
          <button className="lo-alt" disabled={!a.available || !!op.busy} onClick={() => void op.run(a)}><AIcon size={14} aria-hidden="true" /><span><span className="t">{a.label}</span>
            <span className="d">{a.available ? a.why : a.unavailable_reason}</span></span>{!!a.cost_cents && <span className="lo-cost">{money(a.cost_cents)}</span>}</button></li>; })}</ul>
      </div>}
      {!b.account_id && n.action !== "open_account" && <button className="lo-dock-foot" disabled={!!op.busy} onClick={() => void op.run({ action: "open_account", label: "Save as an account", why: "", produces: "", available: true, unavailable_reason: "", params: {}, cost_cents: 0 })}>
        <Briefcase size={13} aria-hidden="true" />Save as an account</button>}
      {b.account_id && !onAccountPage && <button className="lo-dock-foot" onClick={() => goto("clients", { account: b.account_id })}>Open the full account<ArrowUpRight size={13} aria-hidden="true" /></button>}
    </section>
  );
}

function NeedsAccount({ op }: { op: Opportunity }) {
  return <div className="lo-dock-form"><p className="lo-note">Recording a conversation saves this organisation as an account first.</p>
    <button className="ds-btn sm" onClick={async () => { try { await op.ensureAccount(); await op.refresh(); } catch (e) { op.notify((e as Error).message, true); } }}>Save as an account and continue</button></div>;
}

function FollowUpForm({ accountId, notify, onDone }: { accountId: number; notify: Notify; onDone: () => void }) {
  const [title, setTitle] = useState("");
  const [due, setDue] = useState(inDays(3));
  const [busy, setBusy] = useState(false);
  return (
    <form className="lo-dock-form space-y-2" aria-label="Set the next follow-up" onSubmit={async (e) => {
      e.preventDefault(); setBusy(true);
      try { await si(`/accounts/${accountId}/tasks`, { method: "POST", json: { title: title.trim(), due_on: due } }); notify(`Follow-up set for ${dayLabel(due).toLowerCase()}.`); onDone(); }
      catch (err) { notify((err as Error).message, true); } finally { setBusy(false); }
    }}>
      <label className="block"><span className="ds-label">Follow-up</span><input className="ds-input mt-1" required value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Call back about the Swindon depot" /></label>
      <label className="block"><span className="ds-label">Due</span><input type="date" className="ds-input mt-1" required value={due} onChange={(e) => setDue(e.target.value)} /></label>
      <button className="ds-btn primary sm" disabled={busy || !title.trim()}>Save follow-up</button>
    </form>
  );
}

/** Qualify into a deal: only what the customer confirmed; anything not known stays blank. Used by the dock and the account page. */
export function QualifyForm({ accountId, sources, requirement = "", notify, onCancel, title = "Qualify into a deal" }: {
  accountId: number; sources: { key: string; title?: string | null }[]; requirement?: string; notify: Notify; onCancel: () => void; title?: string;
}) {
  const submission = useRef(newKey()); // one key per form, so a double-click creates one deal
  const [source, setSource] = useState(sources[0]?.key || "");
  const [q, setQ] = useState({ requirement, decision_maker: "", timing: "", budget: "", incumbent: "", drivers: "" });
  const [services, setServices] = useState<string[]>([]);
  const [work, setWork] = useState("ppm");
  const [busy, setBusy] = useState(false);
  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const deal = await si<{ id: number }>(`/accounts/${accountId}/deals`, { method: "POST", headers: { "Idempotency-Key": submission.current }, json: { source_key: source || null, services, work_type: work, qualification: q } });
      notify("Deal created with its evidence and history.");
      goto("deals", { deal: deal.id });
    } catch (err) { notify((err as Error).message, true); } finally { setBusy(false); }
  }
  const box = (k: keyof typeof q, label: string, hint: string) => <label className="block"><span className="ds-label">{label}</span><input className="mt-1 block h-10 w-full rounded-lg border border-ds-border-strong px-2.5 text-[14px]" placeholder={hint} value={q[k]} onChange={(e) => setQ({ ...q, [k]: e.target.value })} required={k === "requirement"} /></label>;
  return (
    <form onSubmit={create} className="space-y-3" aria-label="Qualify into a deal">
      <h3 className="text-[15px] font-semibold text-ds-ink">{title}</h3>
      <p className="text-[13px] text-ds-muted">Record what you have confirmed with the customer. Leave anything you do not know blank; it stays unknown.</p>
      {box("requirement", "Customer requirement (confirmed)", "e.g. Annual PPM for fire alarms at two sites")}
      <div className="grid gap-3 sm:grid-cols-2">{box("decision_maker", "Decision maker", "Role or name")}{box("timing", "Timing", "e.g. Decision by March")}{box("budget", "Budget", "Only if stated")}{box("incumbent", "Current provider", "Only if confirmed")}</div>
      <div><span className="ds-label">Services</span><div className="mt-1 flex flex-wrap gap-1.5">{SERVICES.map(([v, l]) => <button type="button" key={v} aria-pressed={services.includes(v)} onClick={() => setServices((s) => (s.includes(v) ? s.filter((x) => x !== v) : [...s, v]))}
        className={`rounded-full border px-3 py-1 text-[12px] font-medium ${services.includes(v) ? "border-ds-brand bg-ds-brand-soft text-ds-brand" : "border-ds-border bg-white text-ds-ink-2"}`}>{l}</button>)}</div></div>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block"><span className="ds-label">Type of work</span><select className="ds-select mt-1 w-full" value={work} onChange={(e) => setWork(e.target.value)}>
          {[["ppm", "Planned preventative maintenance"], ["reactive", "Reactive maintenance"], ["remedial", "Remedial works"], ["installation", "Installation project"], ["multi_site", "Multi-site agreement"], ["monitoring", "Monitoring"]].map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
        <label className="block"><span className="ds-label">Based on</span><select className="ds-select mt-1 w-full" value={source} onChange={(e) => setSource(e.target.value)}><option value="">My own conversations</option>{sources.map((s) => <option key={s.key} value={s.key}>{s.title?.slice(0, 70) || s.key}</option>)}</select></label>
      </div>
      <div className="flex gap-2"><button className="ds-btn primary" disabled={busy}>Create deal</button><button type="button" className="ds-btn ghost" onClick={onCancel}>Cancel</button></div>
    </form>
  );
}
