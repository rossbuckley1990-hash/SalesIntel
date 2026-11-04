"use client";
import { useEffect, useState } from "react";
import {
  ArrowRight, ArrowUpRight, BriefcaseBusiness, CalendarClock, CheckCircle2, Circle, Gavel, Hourglass, Radar, Search, Sparkles, Target,
} from "lucide-react";
import { DailyResearchBrief } from "./daily-research-brief";
import { EmptyState, Pill } from "./ds";
import { fieldLabel, money } from "./api";
import {
  CATEGORY, SOURCE_NAMES, compactPounds, radarBase, relative, shortValue, titleCase, urgencyTone, type Item, type Page, type Summary,
} from "./radar-model";
import type { SharedProps } from "./types";

const PROMPTS = [
  "NHS trusts in the North West with fire alarm contracts ending in 2027",
  "Universities planning campus security upgrades",
  "Housing associations with building-safety remediation programmes",
];

function greeting(now: Date) {
  const hour = Number(new Intl.DateTimeFormat("en-GB", { hour: "numeric", hourCycle: "h23", timeZone: "Europe/London" }).format(now));
  return hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
}

export function Home({ data, navigate, ask, inspect }: SharedProps) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [top, setTop] = useState<Item[] | null>(null);
  const [question, setQuestion] = useState("");
  const now = new Date(data.as_of);

  useEffect(() => {
    const base = radarBase();
    fetch(`${base}/summary`, { cache: "no-store" }).then((r) => (r.ok ? r.json() : null)).then(setSummary).catch(() => {});
    fetch(`${base}?tier=1&limit=6`, { cache: "no-store" }).then((r) => (r.ok ? r.json() : null)).then((p: Page | null) => setTop(p?.items.filter((i) => i.review_state === "unreviewed" || i.review_state === "investigate") ?? [])).catch(() => setTop([]));
  }, []);

  function openLead(id: number) {
    const url = new URL(window.location.href);
    url.searchParams.set("lead", String(id));
    window.history.replaceState({}, "", url);
    navigate("radar");
  }
  function openFinder(params: Record<string, string>) {
    const url = new URL(window.location.href);
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
    window.history.replaceState({}, "", url);
    navigate("radar");
  }
  function submit(text: string) {
    const q = text.trim();
    if (q.length < 4) return;
    if (ask) ask(q); else navigate("discover");
  }

  const active = data.opportunities.filter((o) => !["Won", "Lost"].includes(o.stage));
  const stages = Object.entries(active.reduce<Record<string, number>>((acc, o) => ({ ...acc, [o.stage]: (acc[o.stage] || 0) + 1 }), {}));
  const actions = data.actions.filter((a) => a.status !== "completed").sort((a, b) => (a.due_date || "9999").localeCompare(b.due_date || "9999")).slice(0, 4);
  const date = new Intl.DateTimeFormat("en-GB", { weekday: "long", day: "numeric", month: "long", timeZone: "Europe/London" }).format(now);
  const ready = summary?.by_tier["1"] ?? null;

  const stats = [
    { icon: Target, label: "Ready to work", value: ready, detail: "Tier 1 leads", go: () => openFinder({ tier: "1" }) },
    { icon: Gavel, label: "Live tenders", value: summary?.by_category.live_procurement ?? null, detail: "Open now", go: () => openFinder({ category: "live_procurement" }) },
    { icon: Hourglass, label: "Renewals in 12 months", value: summary?.renewals_within_months["12"] ?? null, detail: summary ? `${compactPounds(summary.value.estimated_annualised_core_only) || "£0"}/yr core value` : "", go: () => openFinder({ category: "pre_tender" }) },
    { icon: BriefcaseBusiness, label: "Open pipeline", value: active.length, detail: `${money(data.pulse.weighted_contract_value.value, true)} weighted`, go: () => navigate("opportunities") },
  ];

  return (
    <div className="ds-root space-y-8">
      <header>
        <p className="text-[13px] font-medium text-ds-muted">{date}</p>
        <h1 className="mt-1 text-[30px] font-semibold leading-tight tracking-[-0.03em] text-ds-ink">{greeting(now)}.</h1>
        <p className="mt-1.5 text-[15px] text-ds-muted">
          {ready === null ? "Gathering today's opportunities…" : ready > 0 ? <>You have <strong className="font-semibold text-ds-ink">{ready} high-priority opportunities</strong> ready to work. Start with the most urgent below.</> : "No high-priority opportunities right now. Use AI Research to look wider."}
        </p>
      </header>

      <section aria-label="Ask MiSi" className="rounded-2xl border border-ds-border bg-gradient-to-br from-white via-white to-ds-brand-soft p-5 shadow-ds-xs">
        <form onSubmit={(e) => { e.preventDefault(); submit(question); }} className="flex flex-col gap-3 sm:flex-row">
          <div className="relative flex-1">
            <Sparkles size={18} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-ds-brand" />
            <input className="ds-input !h-12 !pl-11 !text-[15px]" aria-label="Ask MiSi to find opportunities" placeholder="Ask MiSi to find opportunities, public or private…" value={question} onChange={(e) => setQuestion(e.target.value)} maxLength={500} />
          </div>
          <button type="submit" className="ds-btn primary !h-12 !px-5" disabled={question.trim().length < 4}><Search size={17} /> Research</button>
        </form>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="text-[12px] text-ds-muted">Try:</span>
          {PROMPTS.map((p) => <button key={p} onClick={() => submit(p)} className="rounded-full border border-ds-border bg-white px-3 py-1 text-[12px] font-medium text-ds-ink-2 transition hover:border-ds-brand-line hover:text-ds-brand">{p}</button>)}
        </div>
      </section>

      <section aria-label="At a glance" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {stats.map((s) => (
          <button key={s.label} onClick={s.go} className="group rounded-xl border border-ds-border bg-white p-4 text-left shadow-ds-xs transition hover:border-ds-brand-line hover:shadow-ds-sm">
            <span className="flex items-center justify-between"><span className="text-[13px] font-medium text-ds-muted">{s.label}</span><s.icon size={16} className="text-ds-muted group-hover:text-ds-brand" /></span>
            {s.value === null ? <span className="ds-skeleton mt-2 block h-7 w-12" /> : <span className="ds-num mt-2 block text-[28px] font-semibold leading-none tracking-[-0.02em] text-ds-ink">{s.value}</span>}
            <span className="mt-2 flex items-center justify-between text-[12px] text-ds-muted">{s.detail}<ArrowRight size={13} className="opacity-0 transition group-hover:opacity-100" /></span>
          </button>
        ))}
      </section>

      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <section aria-label="Act on these first" className="ds-card overflow-hidden">
          <div className="flex items-center justify-between gap-4 border-b border-ds-border px-5 py-4">
            <div><h2 className="text-[16px] font-semibold text-ds-ink">Act on these first</h2><p className="text-[13px] text-ds-muted">Highest-priority opportunities, most urgent first</p></div>
            <button className="ds-btn sm" onClick={() => navigate("radar")}>Open Finder <ArrowRight size={14} /></button>
          </div>
          {top === null && <div className="space-y-3 p-5">{[0, 1, 2].map((i) => <div key={i} className="ds-skeleton h-14" />)}</div>}
          {top && !top.length && <EmptyState icon={<Radar size={20} />} title="You're clear for now" action={<button className="ds-btn primary" onClick={() => navigate("discover")}><Sparkles size={16} /> Find new opportunities</button>}>No new tier 1 opportunities. MiSi refreshes public sources every day.</EmptyState>}
          {top && !!top.length && <ul className="divide-y divide-ds-border">
            {top.map(({ id, suggestion: x, review_state }) => {
              const meta = CATEGORY[x.category];
              const when = relative(x.timing);
              const tone = urgencyTone(x.timing);
              return (
                <li key={id}>
                  <button onClick={() => openLead(id)} className="group flex w-full items-center gap-4 px-5 py-3.5 text-left transition hover:bg-ds-hover">
                    <span className={`hidden h-10 w-10 flex-none place-items-center rounded-lg sm:grid ${tone === "red" ? "bg-ds-red-soft text-ds-red" : tone === "amber" ? "bg-ds-amber-soft text-ds-amber" : "bg-ds-subtle text-ds-muted"}`}><CalendarClock size={18} /></span>
                    <span className="min-w-0 flex-1">
                      <span className="flex items-center gap-2"><span className="truncate text-[14px] font-semibold text-ds-ink">{titleCase(x.customer)}</span>{review_state === "investigate" && <Pill tone="green">In pipeline</Pill>}</span>
                      <span className="block truncate text-[13px] text-ds-muted">{x.title}</span>
                    </span>
                    <span className="hidden flex-none md:block">{meta && <Pill tone={meta.tone} dot>{meta.short}</Pill>}</span>
                    <span className="w-24 flex-none text-right">
                      <span className={`ds-num block text-[13px] font-semibold ${tone === "red" ? "text-ds-red" : tone === "amber" ? "text-ds-amber" : "text-ds-ink-2"}`}>{when || "No date"}</span>
                      <span className="ds-num block text-[12px] text-ds-muted">{shortValue(x.value) || "Value n/a"}</span>
                    </span>
                    <ArrowUpRight size={16} className="flex-none text-ds-faint group-hover:text-ds-brand" />
                  </button>
                </li>
              );
            })}
          </ul>}
        </section>

        <div className="space-y-6">
          <section className="ds-card p-5" aria-label="Your next actions">
            <div className="mb-3 flex items-center justify-between"><h2 className="text-[15px] font-semibold text-ds-ink">Your next actions</h2><button className="text-[13px] font-semibold text-ds-brand hover:underline" onClick={() => navigate("actions")}>All</button></div>
            {!actions.length && <p className="flex items-center gap-2 text-[13px] text-ds-muted"><CheckCircle2 size={16} className="text-ds-green" /> Nothing outstanding.</p>}
            <ul className="space-y-3">
              {actions.map((a) => (
                <li key={a.id}>
                  <button className="flex w-full gap-3 text-left" onClick={() => (a.related_opportunity_id ? inspect(a.related_opportunity_id) : navigate("actions"))}>
                    <Circle size={16} className="mt-0.5 flex-none text-ds-border-strong" />
                    <span className="min-w-0">
                      <span className="line-clamp-2 text-[13px] font-medium leading-5 text-ds-ink">{a.recommended_action}</span>
                      <span className="text-[12px] text-ds-muted">{a.due_date ? `Due ${relative(a.due_date)}` : "No due date"} · {a.owner}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </section>

          <section className="ds-card p-5" aria-label="Pipeline">
            <div className="mb-3 flex items-center justify-between"><h2 className="text-[15px] font-semibold text-ds-ink">Pipeline</h2><button className="text-[13px] font-semibold text-ds-brand hover:underline" onClick={() => navigate("opportunities")}>Open</button></div>
            {!stages.length ? <p className="text-[13px] text-ds-muted">Add opportunities from the Finder to start your pipeline.</p> : (
              <ul className="space-y-2">{stages.map(([stage, count]) => (
                <li key={stage} className="flex items-center gap-3 text-[13px]">
                  <span className="w-28 truncate text-ds-ink-2">{stage}</span>
                  <span className="h-2 flex-1 overflow-hidden rounded-full bg-ds-subtle"><span className="block h-full rounded-full bg-ds-brand" style={{ width: `${Math.max(8, (count / active.length) * 100)}%` }} /></span>
                  <span className="ds-num w-6 text-right font-semibold text-ds-ink">{count}</span>
                </li>
              ))}</ul>
            )}
          </section>

          <section className="ds-card p-5" aria-label="What changed">
            <div className="mb-1 flex items-center justify-between"><h2 className="text-[15px] font-semibold text-ds-ink">What changed</h2><button className="text-[13px] font-semibold text-ds-brand hover:underline" onClick={() => navigate("finance")}>Compare</button></div>
            <p className="mb-3 text-[12px] text-ds-muted">{data.changes.current ? `Accepted snapshots · ${data.changes.previous?.label || "Awaiting baseline"}` : "Compared saved states, never live-market claims"}</p>
            {!data.changes.changes.length && <p className="text-[13px] text-ds-muted">{data.changes.message}</p>}
            <ul className="space-y-2.5">
              {data.changes.changes.slice(0, 4).map((c, i) => (
                <li key={i}>
                  <button className="w-full text-left" onClick={() => inspect(c.opportunity_id)}>
                    <span className="block truncate text-[13px] font-medium text-ds-ink">{c.name}</span>
                    <span className="block text-[12px] text-ds-muted">{fieldLabel(c.field)}: <span className="line-through">{c.before ?? "Unknown"}</span> → <span className="font-semibold text-ds-ink-2">{c.after ?? "Unknown"}</span></span>
                  </button>
                </li>
              ))}
            </ul>
          </section>

          {summary && <section className="ds-card p-5" aria-label="Data sources">
            <h2 className="mb-3 text-[15px] font-semibold text-ds-ink">Data sources</h2>
            <ul className="space-y-2">{summary.health.map((h) => (
              <li key={h.source_key} className="flex items-center justify-between gap-3 text-[13px]">
                <span className="flex items-center gap-2 text-ds-ink-2"><span className={`h-2 w-2 rounded-full ${h.status === "fresh" ? "bg-[#12b76a]" : h.status === "failing" ? "bg-[#f04438]" : "bg-[#f79009]"}`} />{SOURCE_NAMES[h.source_key] || h.source_key}</span>
                <span className="text-[12px] text-ds-muted">{h.last_success_at ? relative(h.last_success_at.slice(0, 10)) : h.status}</span>
              </li>
            ))}</ul>
          </section>}
        </div>
      </div>

      <DailyResearchBrief navigate={navigate} />
    </div>
  );
}
