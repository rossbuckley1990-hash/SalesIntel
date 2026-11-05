"use client";
import { useCallback, useContext, useEffect, useState } from "react";
import { ArrowRight, BellRing, Briefcase, CalendarClock, ChevronDown, ChevronRight, FilePenLine, Inbox, Search, Sparkles } from "lucide-react";
import { DailyResearchBrief } from "./daily-research-brief";
import { EmptyState, Pill } from "./ds";
import { fieldLabel } from "./api";
import { relative } from "./radar-model";
import { ActivityForm, Panel, TaskRow } from "./si-shared";
import { STAGE_LABEL, dayLabel, goto, inDays, si, type DealCard, type DiscoverResult, type Lead, type QueueItem, type TodayT } from "./si-api";
import { Runway } from "./si-runway";
import { BestOpportunities } from "./si-intel";
import type { SharedProps } from "./types";
import { ViewerContext, useCountUp } from "./fluid";

const PER: Record<string, string> = { annual: "a year", quarterly: "a quarter", monthly: "a month" };

function Cell({ n, label, detail, hot, onClick }: { n: number | null; label: string; detail: string; hot?: boolean; onClick: () => void }) {
  const shown = useCountUp(n ?? 0);
  return (
    <button className={hot ? "hot" : ""} onClick={onClick}>
      <span className="k"><i className="si-ledger-dot" aria-hidden="true" />{label}</span>
      <span className="v">{n === null ? <span className="ds-skeleton inline-block h-7 w-10 align-middle" aria-hidden="true" /> : shown}</span>
      <span className="s">{detail}</span>
    </button>
  );
}

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
  const [q, setQ] = useState("");
  const [error, setError] = useState("");
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

  const target = viewer?.target;
  const money = (v: string) => `£${Number(v).toLocaleString("en-GB", { maximumFractionDigits: 0 })}`;

  return (
    <div className="ds-root space-y-6">
      <header className="si-stagger flex flex-wrap items-end justify-between gap-x-8 gap-y-4">
        <div className="min-w-0">
          <p className="si-eyebrow">{date} · Daily briefing</p>
          <h1 className="mt-2 text-[32px] font-semibold leading-[1.1] tracking-[-0.035em] text-ds-ink">{greeting()}{first ? `, ${first}` : ""}.</h1>
          <p className="mt-2 max-w-2xl text-[15px] leading-6 text-ds-muted" aria-live="polite">
            {!counts ? "Getting your day ready…" : counts.follow + counts.drafts + counts.deals === 0 ? "Nothing is waiting on you. Find your next opportunity below."
              : <>You have <strong className="font-semibold text-ds-ink">{counts.follow} follow-up{counts.follow === 1 ? "" : "s"}</strong> due, {counts.drafts} draft{counts.drafts === 1 ? "" : "s"} to finish and {counts.deals} deal{counts.deals === 1 ? "" : "s"} that need a next step.</>}
          </p>
        </div>
        {target?.amount && <div className="text-right">
          <p className="text-[12px] text-ds-muted">Your target</p>
          <p className="si-mono text-[20px] leading-tight text-ds-ink">{money(target.amount)}</p>
          <p className="text-[12px] text-ds-muted">{target.basis_label?.toLowerCase()} {PER[target.period || ""] || ""}</p>
        </div>}
      </header>

      <div className="si-ledger" role="group" aria-label="Your day at a glance">
        <Cell n={counts?.follow ?? null} hot={!!counts?.follow} label="Follow-ups due" detail="Promises you made" onClick={() => document.getElementById("si-queue")?.scrollIntoView({ behavior: "smooth", block: "start" })} />
        <Cell n={counts?.drafts ?? null} label="Drafts to finish" detail="Introductions in progress" onClick={() => goto("engage")} />
        <Cell n={counts?.deals ?? null} label="Deals needing a step" detail={`${openDeals.length} open in total`} onClick={() => goto("deals")} />
        <Cell n={today ? today.new_leads.length : null} label="New leads" detail="Newly found, worth a look" onClick={() => goto("find")} />
      </div>

      <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); goto("find", { q }); }} role="search">
        <div className="si-hero-search relative flex-1">
          <Search size={16} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-ds-muted" />
          <input className="ds-input !h-11 !pl-10 text-[14px]" aria-label="Find opportunities" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Find opportunities, e.g. fire alarm maintenance in Scotland" />
        </div>
        <button className="ds-btn primary !h-[42px] !px-4">Discover <ArrowRight size={14} /></button>
      </form>

      <BestOpportunities notify={notify} />

      {ahead && !!ahead.length && <section aria-label="Opening soon">
        <div className="si-section-head"><h2>Opening in the next six weeks</h2>
          <button className="text-[12px] font-medium text-ds-ink-2 hover:text-ds-ink hover:underline" onClick={() => goto("find", { layout: "runway" })}>Full runway</button></div>
        <Runway compact horizon={42} items={ahead} selected={null} onSelect={(key) => goto("find", { lead: key })} />
      </section>}
      {error && <p role="alert" className="rounded-lg border border-ds-red-line bg-ds-red-soft px-3 py-2 text-[13px] text-ds-red">{error}</p>}

      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_360px] [&>*]:min-w-0">
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
      </div>

      <details className="ds-card group" open>
        <summary className="flex cursor-pointer items-center gap-2 px-5 py-3.5 text-[14px] font-semibold text-ds-ink"><Sparkles size={15} className="text-ds-brand" /> Research follow-ups from AI Research<ChevronDown size={15} className="si-chevron ml-auto text-ds-muted" /></summary>
        <div className="border-t border-ds-border p-5"><DailyResearchBrief navigate={(v) => goto(v)} /></div>
      </details>
    </div>
  );
}
