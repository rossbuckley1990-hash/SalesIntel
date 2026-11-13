"use client";
import { useCallback, useContext, useEffect, useState } from "react";
import { ArrowRight, BellRing, Briefcase, CalendarClock, ChevronDown, ChevronRight, FilePenLine, Inbox, Sparkles } from "lucide-react";
import { DailyResearchBrief } from "./daily-research-brief";
import { EmptyState, Pill } from "./ds";
import { fieldLabel } from "./api";
import { ActivityForm, Panel, TaskRow } from "./si-shared";
import { STAGE_LABEL, dayLabel, goto, inDays, si, type ClockRow, type DealCard, type DiscoverResult, type Lead, type QueueItem, type SignalRow, type TodayT, type VerdictSummary } from "./si-api";
import { daysLabel } from "./si-notice";
import { relative } from "./radar-model";
import { Runway } from "./si-runway";
import { BestOpportunities } from "./si-intel";
import { PatchBrief } from "./si-patch";
import type { SharedProps } from "./types";
import { ViewerContext } from "./fluid";
import "./living.css";

type DigestRow = { account_id: number; name: string; headline: string; next: string; new_events: number; since: string | null; latest: string };
type Digest = { changed: DigestRow[]; watching: DigestRow[] };

/** The intelligence briefing: five short lists, each built only from what is recorded. Nothing here is a forecast. */
function Briefing({ today, deals, digest }: { today: TodayT | null; deals: DealCard[]; digest: Digest | null }) {
  const pounds = (v: number) => `£${Math.round(v).toLocaleString("en-GB")}`;
  const money = [...deals].filter((d) => !["won", "lost"].includes(d.stage)).sort((a, b) => (b.value_total ?? -1) - (a.value_total ?? -1)).slice(0, 3);
  const col = (title: string, detail: string, n: number | null, items: React.ReactNode, empty: string) => (
    <section aria-label={title} className="lo-brief-col">
      <h2><span>{title}</span><span className="n">{n ?? "…"}</span></h2>
      <p className="lo-brief-detail">{detail}</p>
      {n === null ? <div className="ds-skeleton mt-2 h-14" /> : n === 0 ? <p className="lo-brief-empty">{empty}</p> : <ul>{items}</ul>}
    </section>);
  return (
    <div className="lo-briefing" role="group" aria-label="Intelligence briefing">
      {col("Discovered", "New leads, most time-sensitive first", today ? today.new_leads.length : null,
        today?.new_leads.slice(0, 3).map((l) => {
          const due = l.facts?.deadline && l.facts.deadline.days >= 0 ? l.facts.deadline : null;
          const stated = [l.worth?.label, due && `${due.label} ${daysLabel(due.days)}`].filter(Boolean).join(" · ");
          return <li key={l.key}><button onClick={() => goto("find", { lead: l.key })}><strong>{l.organisation}</strong>{stated && <em>{stated}</em>}<span>{l.why_now}</span></button></li>;
        }),
        "Nothing new found since your last search.")}
      {col("Changed", "New evidence or activity since you last looked", digest ? digest.changed.length : null,
        digest?.changed.slice(0, 3).map((r) => <li key={r.account_id}><button onClick={() => goto("clients", { account: r.account_id })}><strong>{r.name}</strong><span>{r.new_events} new{r.latest ? `: ${r.latest}` : ""}</span></button></li>),
        "Nothing has changed on the accounts you reviewed.")}
      {col("Needs action", "What you committed to, by due date", today ? today.queue.length : null,
        today?.queue.slice(0, 3).map((q) => <li key={`${q.kind}-${q.task_id || q.draft_id || q.deal_id || q.account_id}`}><button onClick={() => document.getElementById("si-queue")?.scrollIntoView({ behavior: "smooth", block: "start" })}>
          <strong>{q.title}</strong><span>{q.account ? `${q.account} · ` : ""}{q.due_on ? dayLabel(q.due_on) : q.why}</span></button></li>), "Nothing is due.")}
      {col("Could move revenue", "Open deals, largest recorded value first", money.length,
        money.map((d) => <li key={d.id}><button onClick={() => goto("deals", { deal: d.id })}><strong>{d.title}</strong>
          <span>{d.value_total !== null ? `${pounds(d.value_total)} recorded` : "No value recorded"} · {STAGE_LABEL[d.stage] || d.stage}</span></button></li>), "No open deals yet.")}
      {col("Worth watching", "Accounts you watch, with their next move", digest ? digest.watching.length : null,
        digest?.watching.slice(0, 3).map((r) => <li key={r.account_id}><button onClick={() => goto("clients", { account: r.account_id })}><strong>{r.name}</strong><span>Next: {r.next}</span></button></li>),
        "Watch an account to keep it here.")}
    </div>
  );
}

const fullDate = (iso: string) => new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }).format(new Date(`${iso}T00:00:00Z`));

/** The dates the published record sets: tender deadlines still ahead, and the largest published contracts by their published end.
 * Every row is a stored notice; none is a forecast, and a contract's end date is the published one, not a prediction of a re-tender. */
function Deadlines({ today }: { today: TodayT | null }) {
  const closing = today?.closing || [], ending = today?.ending || [];
  if (!closing.length && !ending.length) return null;
  const row = (r: ClockRow, kind: "closing" | "ending") => (
    <li key={r.key}><button onClick={() => goto("find", { lead: r.key })}>
      <span className={`lo-clock-when${kind === "closing" && r.days <= 14 ? " urgent" : ""}`}><b>{kind === "closing" ? daysLabel(r.days) : fullDate(r.date)}</b><span>{kind === "closing" ? fullDate(r.date) : daysLabel(r.days)}</span></span>
      <span className="lo-clock-main"><strong>{r.organisation}</strong>
        {r.title && r.title !== r.organisation && <span className="t">{r.title}</span>}
        <span className="lo-rowfacts">
          {kind === "closing" && <span>{r.step}</span>}
          {r.worth && <b>{r.worth.label}</b>}
          {kind === "ending" && r.supplier ? <span>Published supplier: {r.supplier}</span> : r.place ? <span>{r.place}</span> : null}
          {r.lots > 1 && <span>{r.lots} lots</span>}
          {r.same_day > 0 && <span>+{r.same_day} more from this buyer on the same date</span>}
        </span></span>
    </button></li>);
  const col = (title: string, detail: string, rows: ClockRow[], total: number, kind: "closing" | "ending", empty: string, all: string, sort: string) => (
    <section aria-label={title} className="lo-clock-col">
      <h3>{title}</h3>
      <p>{detail}</p>
      {rows.length ? <ul>{rows.map((r) => row(r, kind))}</ul> : <p className="lo-brief-empty">{empty}</p>}
      {total > rows.length && <button className="lo-clock-all" onClick={() => goto("find", { sort })}>{all} <ArrowRight size={13} /></button>}
    </section>);
  return (
    <section aria-label="Deadlines and end dates">
      <div className="si-section-head"><h2>Deadlines and end dates</h2><p>From published notices. Nothing here is a forecast.</p></div>
      <div className="lo-clock">
        {col("Closing soonest", "Tenders and market engagements with a published deadline still ahead", closing, today?.closing_total || 0, "closing",
          "No stored tender states a deadline that is still ahead.", `All ${today?.closing_total || 0}, by next published date`, "closing")}
        {col("Largest contracts ending", "Published contracts that end in the next 12 months, largest published value first", ending, today?.ending_total || 0, "ending",
          "No stored contract with a published value ends in the next 12 months.", `All ${today?.ending_total || 0}, by published value`, "value")}
      </div>
    </section>);
}

/** Ways in before any tender: public records that give a reason to ask. Each row is a stored record with its source; none is a
 * requirement, and the order is by evidence (more than one independent source first), then by the newest record. */
function Signals({ today }: { today: TodayT | null }) {
  const rows = today?.signals || [], total = today?.signals_total || 0;
  if (!rows.length) return null;
  const row = (r: SignalRow) => (
    <li key={r.key}><button onClick={() => goto("find", { lead: r.key })}>
      <span className="lo-clock-when"><b>{r.date ? fullDate(r.date) : "Not dated"}</b><span>{r.date ? relative(r.date) : ""}</span></span>
      <span className="lo-clock-main"><strong>{r.organisation}</strong>
        <span className="t two">{r.headline}</span>
        <span className="lo-rowfacts"><span>{r.source}</span>{r.corroborated ? <b>{r.strength}</b> : <span>{r.strength}</span>}{r.account_id ? <span>Account open</span> : null}</span></span>
    </button></li>);
  return (
    <section aria-label="Before any tender">
      <div className="si-section-head"><h2>Before any tender</h2><p>Public records that give a reason to ask. None is a published requirement.</p></div>
      <div className="lo-clock solo">
        <section aria-label="Public signals" className="lo-clock-col lo-signals">
          <h3>Public signals</h3>
          <p>A regulator’s finding, a fire authority’s notice, an early notice or a press report. More than one independent source first, then the newest.</p>
          <ul>{rows.map(row)}</ul>
          {total > rows.length && <button className="lo-clock-all" onClick={() => goto("find", { category: "inferred_signal" })}>All {total} public signals <ArrowRight size={13} /></button>}
        </section>
      </div>
    </section>);
}

/** What was said about the leads shown: the measure of whether SalesIntel told a rep something worth a call. Counts, not rates. */
function Verdicts({ said }: { said: VerdictSummary | null }) {
  if (!said?.judged) return null;
  return (
    <section aria-label="Verdicts">
      <div className="si-section-head"><h2>Verdicts</h2><p>What was said about the leads shown. A verdict never changes the order of a list.</p></div>
      <div className="lo-clock solo">
        <section aria-label="Verdicts so far" className="lo-clock-col">
          <h3>{said.headline}</h3>
          <p>{said.knew_already} knew already · {said.wrong} wrong</p>
          <ul className="lo-tally">{said.by_kind.map((k) => <li key={k.kind}><span>{k.label}</span><b>{k.worth_a_call} of {k.judged} worth a call</b></li>)}</ul>
        </section>
      </div>
    </section>);
}

const PER: Record<string, string> = { annual: "a year", quarterly: "a quarter", monthly: "a month" };

const ICON = { follow_up: CalendarClock, draft: FilePenLine, deal: Briefcase, intelligence: BellRing };

function greeting() {
  const hour = Number(new Intl.DateTimeFormat("en-GB", { hour: "numeric", hourCycle: "h23", timeZone: "Europe/London" }).format(new Date()));
  return hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
}

export function SiToday({ data, notify, inspect }: SharedProps) {
  const viewer = useContext(ViewerContext);
  const first = viewer?.name.trim().split(/\s+/)[0] || "";
  const [today, setToday] = useState<TodayT | null>(null);
  const [deals, setDeals] = useState<DealCard[]>([]);
  const [ahead, setAhead] = useState<Lead[] | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [digest, setDigest] = useState<Digest | null>(null);
  const [said, setSaid] = useState<VerdictSummary | null>(null);
  const [quietResearch, setQuietResearch] = useState(false);
  const refreshVerdicts = useCallback(() => { si<VerdictSummary>("/brief/verdicts").then(setSaid).catch(() => setSaid(null)); }, []);
  useEffect(() => { refreshVerdicts(); }, [refreshVerdicts]);
  useEffect(() => { si<Digest>("/brief/digest").then(setDigest).catch(() => setDigest({ changed: [], watching: [] })); }, []);
  const load = useCallback(async () => {
    try {
      const [t, d] = await Promise.all([si<TodayT>("/today"), si<{ items: DealCard[] }>("/deals")]);
      setToday(t); setDeals(d.items); setError("");
    } catch (e) { setError((e as Error).message); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => { si<DiscoverResult>("/discover?status=active&limit=100").then((d) => setAhead(d.items)).catch(() => setAhead([])); }, []);

  async function act(item: QueueItem, action: "done" | "tomorrow" | "week") {
    if (!item.task_id) return;
    try {
      if (action === "done") await si(`/tasks/${item.task_id}/complete`, { method: "POST" });
      else await si(`/tasks/${item.task_id}`, { method: "PATCH", json: { due_on: inDays(action === "tomorrow" ? 1 : 7) } });
      notify(action === "done" ? "Marked done." : `Moved to ${action === "tomorrow" ? "tomorrow" : "next week"}.`);
      void load();
    } catch (e) { notify((e as Error).message, true); }
  }

  const date = new Intl.DateTimeFormat("en-GB", { weekday: "long", day: "numeric", month: "long", timeZone: "Europe/London" }).format(new Date());
  const counts = today ? { follow: today.queue.filter((x) => x.kind === "follow_up").length, drafts: today.queue.filter((x) => x.kind === "draft").length, deals: today.queue.filter((x) => x.kind === "deal").length } : null;
  const openDeals = deals.filter((d) => !["won", "lost"].includes(d.stage));
  // Worked: something has been set, drafted, qualified or watched. Until then the page is the patch brief and the published record.
  const worked = !!today && (today.queue.length > 0 || today.upcoming.length > 0 || deals.length > 0 || !!digest?.changed.length || !!digest?.watching.length);

  const target = viewer?.target;
  const money = (v: string) => `£${Number(v).toLocaleString("en-GB", { maximumFractionDigits: 0 })}`;

  return (
    <div className="ds-root space-y-6">
      <header className="si-stagger flex flex-wrap items-end justify-between gap-x-8 gap-y-4">
        <div className="min-w-0">
          <p className="si-eyebrow">{date} · Daily briefing</p>
          <h1 className="mt-2 text-[32px] font-semibold leading-[1.1] tracking-[-0.035em] text-ds-ink">{greeting()}{first ? `, ${first}` : ""}.</h1>
          <p className="mt-2 max-w-2xl text-[15px] leading-6 text-ds-muted" aria-live="polite">
            {!counts ? "Getting your day ready…" : counts.follow + counts.drafts + counts.deals === 0
              ? "Nothing is due. Your patch brief is below: say what you think of each lead with one tap."
              : <>You have <strong className="font-semibold text-ds-ink">{counts.follow} follow-up{counts.follow === 1 ? "" : "s"}</strong> due, {counts.drafts} draft{counts.drafts === 1 ? "" : "s"} to finish and {counts.deals} deal{counts.deals === 1 ? "" : "s"} that need a next step.</>}
          </p>
        </div>
        {target?.amount && <div className="text-right">
          <p className="text-[12px] text-ds-muted">Your target</p>
          <p className="si-mono text-[20px] leading-tight text-ds-ink">{money(target.amount)}</p>
          <p className="text-[12px] text-ds-muted">{target.basis_label?.toLowerCase()} {PER[target.period || ""] || ""}</p>
        </div>}
      </header>

      <PatchBrief notify={notify} onChanged={refreshVerdicts} />

      {worked && <Briefing today={today} deals={deals} digest={digest} />}

      <Deadlines today={today} />

      <Signals today={today} />

      <Verdicts said={said} />

      <BestOpportunities notify={notify} />

      {worked && ahead && !!ahead.length && <section aria-label="Opening soon">
        <div className="si-section-head"><h2>Opening in the next six weeks</h2>
          <button className="text-[12px] font-medium text-ds-ink-2 hover:text-ds-ink hover:underline" onClick={() => goto("find", { layout: "runway" })}>Full runway</button></div>
        <Runway compact horizon={42} items={ahead} selected={null} onSelect={(key) => goto("find", { lead: key })} />
      </section>}
      {error && <p role="alert" className="rounded-lg border border-ds-red-line bg-ds-red-soft px-3 py-2 text-[13px] text-ds-red">{error}</p>}

      {/* First run: nothing has been worked yet, so the queue is one line and the empty side panels are left out. */}
      {!worked && today && <section id="si-queue" aria-label="Your queue" className="ds-card scroll-mt-24 px-5 py-3.5">
        <h2 className="text-[15px] font-semibold text-ds-ink">Your queue</h2>
        <p className="text-[13px] text-ds-muted">Nothing is due. Follow-ups you set, drafts you start and deals that stall will appear here.</p>
      </section>}
      {worked && <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_360px] [&>*]:min-w-0">
        <section id="si-queue" aria-label="Your queue" className="ds-card scroll-mt-24 overflow-hidden">
          <div className="flex items-center justify-between border-b border-ds-border px-5 py-3.5">
            <div><h2 className="text-[15px] font-semibold text-ds-ink">Your queue</h2><p className="text-[12px] text-ds-muted">Ordered by what you committed to and recorded deadlines</p></div>
          </div>
          {!today && <div className="space-y-3 p-5">{[0, 1, 2].map((i) => <div key={i} className="ds-skeleton h-14" />)}</div>}
          {today && !today.queue.length && <EmptyState icon={<Inbox size={20} />} title="You're all caught up" action={<button className="ds-btn primary" onClick={() => goto("find")}>Find opportunities <ArrowRight size={15} /></button>}>Follow-ups you schedule, drafts you start and deals that stall will appear here.</EmptyState>}
          {today && !!today.queue.length && <ul className="si-stagger divide-y divide-ds-border">
            {today.queue.map((item) => {
              const Icon = ICON[item.kind];
              const id = `${item.kind}-${item.task_id || item.draft_id || item.deal_id || item.account_id}`;
              const overdue = item.kind === "follow_up" && item.priority === 0;
              return (
                <li key={id} className="si-queue-item px-5 py-3.5">
                  <div className="flex items-start gap-3">
                    <span className={`mt-0.5 grid h-9 w-9 flex-none place-items-center rounded-lg ${overdue ? "bg-ds-red-soft text-ds-red" : "bg-ds-brand-soft text-ds-brand"}`}><Icon size={17} /></span>
                    <div className="min-w-0 flex-1">
                      <p className="text-[14px] font-semibold text-ds-ink">{item.title}{item.account && <button className="ml-1.5 font-medium text-ds-brand hover:underline" onClick={() => goto("clients", { account: item.account_id })}>· {item.account}</button>}</p>
                      <p className="text-[13px] text-ds-muted">{item.why}</p>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {item.kind === "follow_up" && <>
                          <button className="ds-btn primary sm" onClick={() => setOpen(open === id ? null : id)}>Log what happened</button>
                          <button className="ds-btn sm" onClick={() => void act(item, "done")}>Done</button>
                          <button className="ds-btn ghost sm" onClick={() => void act(item, "tomorrow")}>Tomorrow</button>
                          <button className="ds-btn ghost sm" onClick={() => void act(item, "week")}>Next week</button>
                        </>}
                        {item.kind === "draft" && <button className="ds-btn primary sm" onClick={() => goto("engage", { account: item.account_id, draft: item.draft_id ?? null })}>Open draft</button>}
                        {item.kind === "deal" && <button className="ds-btn primary sm" onClick={() => goto("deals", { deal: item.deal_id ?? null })}>Open deal</button>}
                        {item.kind === "intelligence" && <button className="ds-btn primary sm" onClick={() => { void si(`/accounts/${item.account_id}/seen`, { method: "POST" }); goto("clients", { account: item.account_id }); }}>Review</button>}
                      </div>
                      {open === id && item.task_id && <div className="mt-3 rounded-xl border border-ds-border p-3">
                        <ActivityForm compact accountId={item.account_id} dealId={item.deal_id} notify={notify} onSaved={async () => { await si(`/tasks/${item.task_id}/complete`, { method: "POST" }).catch(() => {}); setOpen(null); void load(); }} />
                      </div>}
                    </div>
                    {item.due_on && <span className={`flex-none text-[12px] font-semibold ${overdue ? "text-ds-red" : "text-ds-muted"}`}>{dayLabel(item.due_on)}</span>}
                  </div>
                </li>
              );
            })}
          </ul>}
        </section>

        <div className="space-y-5">
          <Panel title="Coming up this week">
            {!today?.upcoming.length ? <p className="text-[13px] text-ds-muted">No follow-ups in the next seven days.</p>
              : <ul className="divide-y divide-ds-border">{today.upcoming.map((t) => <TaskRow key={t.id} t={t} account />)}</ul>}
          </Panel>
          <Panel title="Deals" action={<button className="text-[13px] font-semibold text-ds-brand hover:underline" onClick={() => goto("deals")}>Board</button>}>
            {!openDeals.length ? <p className="text-[13px] text-ds-muted">No open deals yet. Qualify an opportunity to create one.</p> : <ul className="space-y-2">
              {openDeals.slice(0, 5).map((d) => <li key={d.id}><button className="flex w-full items-center justify-between gap-2 text-left" onClick={() => goto("deals", { deal: d.id })}>
                <span className="min-w-0"><span className="block truncate text-[13px] font-semibold text-ds-ink">{d.title}</span><span className="text-[12px] text-ds-muted">{d.account}</span></span>
                <Pill>{STAGE_LABEL[d.stage]}</Pill></button></li>)}
            </ul>}
          </Panel>
          {data.changes.current && <Panel title="What changed" action={<span className="text-[12px] text-ds-muted">Accepted snapshots</span>}>
            {!data.changes.changes.length ? <p className="text-[13px] text-ds-muted">{data.changes.message}</p> : <ul className="space-y-2">{data.changes.changes.slice(0, 4).map((c, i) => <li key={i}>
              <button className="w-full text-left" onClick={() => inspect(c.opportunity_id)}><span className="block truncate text-[13px] font-medium text-ds-ink">{c.name}</span>
                <span className="text-[12px] text-ds-muted">{fieldLabel(c.field)}: {String(c.before ?? "Unknown")} → {String(c.after ?? "Unknown")} <ChevronRight size={11} className="inline" /></span></button></li>)}</ul>}
          </Panel>}
        </div>
      </div>}

      <details className="ds-card group" open hidden={quietResearch}>
        <summary className="flex cursor-pointer items-center gap-2 px-5 py-3.5 text-[14px] font-semibold text-ds-ink"><Sparkles size={15} className="text-ds-brand" /> Research follow-ups from AI Research<ChevronDown size={15} className="si-chevron ml-auto text-ds-muted" /></summary>
        <div className="border-t border-ds-border p-5"><DailyResearchBrief navigate={(v) => goto(v)} onEmpty={setQuietResearch} /></div>
      </details>
    </div>
  );
}
