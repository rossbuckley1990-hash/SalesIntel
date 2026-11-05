"use client";
import { useCallback, useEffect, useState } from "react";
import { ArrowRight, BellRing, Briefcase, CalendarClock, ChevronRight, FilePenLine, Inbox, Search, Sparkles } from "lucide-react";
import { DailyResearchBrief } from "./daily-research-brief";
import { EmptyState, Pill } from "./ds";
import { fieldLabel } from "./api";
import { relative } from "./radar-model";
import { ActivityForm, Panel, TaskRow } from "./si-shared";
import { STAGE_LABEL, dayLabel, goto, inDays, si, type DealCard, type QueueItem, type TodayT } from "./si-api";
import type { SharedProps } from "./types";

const ICON = { follow_up: CalendarClock, draft: FilePenLine, deal: Briefcase, intelligence: BellRing };

function greeting() {
  const hour = Number(new Intl.DateTimeFormat("en-GB", { hour: "numeric", hourCycle: "h23", timeZone: "Europe/London" }).format(new Date()));
  return hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
}

export function SiToday({ data, notify, inspect }: SharedProps) {
  const [today, setToday] = useState<TodayT | null>(null);
  const [deals, setDeals] = useState<DealCard[]>([]);
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

  return (
    <div className="ds-root space-y-6">
      <header>
        <p className="text-[13px] font-medium text-ds-muted">{date}</p>
        <h1 className="mt-0.5 text-[28px] font-semibold leading-tight tracking-[-0.03em] text-ds-ink">{greeting()}.</h1>
        <p className="mt-1 text-[15px] text-ds-muted" aria-live="polite">
          {!counts ? "Getting your day ready…" : counts.follow + counts.drafts + counts.deals === 0 ? "Nothing is waiting on you. Find your next opportunity below."
            : <>You have <strong className="font-semibold text-ds-ink">{counts.follow} follow-up{counts.follow === 1 ? "" : "s"}</strong> due, {counts.drafts} draft{counts.drafts === 1 ? "" : "s"} to finish and {counts.deals} deal{counts.deals === 1 ? "" : "s"} that need a next step.</>}
        </p>
      </header>

      <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); goto("find", { q }); }} role="search">
        <div className="relative flex-1">
          <Search size={17} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-ds-faint" />
          <input className="ds-input !h-11 !pl-10" aria-label="Find opportunities" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Find opportunities, e.g. fire alarm maintenance in Scotland" />
        </div>
        <button className="ds-btn primary !h-11">Discover</button>
      </form>
      {error && <p role="alert" className="rounded-lg border border-ds-red-line bg-ds-red-soft px-3 py-2 text-[13px] text-ds-red">{error}</p>}

      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_360px] [&>*]:min-w-0">
        <section aria-label="Your queue" className="ds-card overflow-hidden">
          <div className="flex items-center justify-between border-b border-ds-border px-5 py-3.5">
            <div><h2 className="text-[15px] font-semibold text-ds-ink">Your queue</h2><p className="text-[12px] text-ds-muted">Ordered by what you committed to and recorded deadlines</p></div>
          </div>
          {!today && <div className="space-y-3 p-5">{[0, 1, 2].map((i) => <div key={i} className="ds-skeleton h-14" />)}</div>}
          {today && !today.queue.length && <EmptyState icon={<Inbox size={20} />} title="You're all caught up" action={<button className="ds-btn primary" onClick={() => goto("find")}>Find opportunities <ArrowRight size={15} /></button>}>Follow-ups you schedule, drafts you start and deals that stall will appear here.</EmptyState>}
          {today && !!today.queue.length && <ul className="divide-y divide-ds-border">
            {today.queue.map((item) => {
              const Icon = ICON[item.kind];
              const id = `${item.kind}-${item.task_id || item.draft_id || item.deal_id || item.account_id}`;
              const overdue = item.kind === "follow_up" && item.priority === 0;
              return (
                <li key={id} className="px-5 py-3.5">
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
          <Panel title="New leads worth a look" action={<button className="text-[13px] font-semibold text-ds-brand hover:underline" onClick={() => goto("find")}>All</button>}>
            {!today?.new_leads.length ? <p className="text-[13px] text-ds-muted">No new urgent leads. Discover has the full list.</p> : <ul className="space-y-3">
              {today.new_leads.map((l) => <li key={l.key}><button className="group w-full text-left" onClick={() => goto("find", { lead: l.key })}>
                <span className="flex items-center gap-1.5"><Pill tone={l.type === "public" ? "blue" : "violet"}>{l.type === "public" ? "Public" : "Private"}</Pill>{l.timing && l.type === "public" && <span className="text-[12px] font-semibold text-ds-amber">{l.days !== null && l.days < 0 ? relative(l.timing) : dayLabel(l.timing)}</span>}</span>
                <span className="mt-1 block truncate text-[14px] font-semibold text-ds-ink group-hover:text-ds-brand">{l.organisation}</span>
                <span className="line-clamp-2 block text-[12px] leading-[18px] text-ds-muted">{l.why_now}</span>
              </button></li>)}
            </ul>}
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
        <summary className="flex cursor-pointer items-center gap-2 px-5 py-3.5 text-[14px] font-semibold text-ds-ink"><Sparkles size={15} className="text-ds-muted" /> Research follow-ups from AI Research</summary>
        <div className="border-t border-ds-border p-5"><DailyResearchBrief navigate={(v) => goto(v)} /></div>
      </details>
    </div>
  );
}
