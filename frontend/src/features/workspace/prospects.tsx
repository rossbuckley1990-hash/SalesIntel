"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowDownRight, ArrowLeft, ArrowUpRight, BriefcaseBusiness, Building2, Check, CheckCircle2, CircleSlash, Copy, Eye, FileSearch, Globe,
  Lightbulb, Loader2, Mail, MessageSquareQuote, Minus, MousePointerClick, Phone, RefreshCw, Search, ShieldCheck, Sparkles, Swords, Telescope, Users,
} from "lucide-react";
import { EmptyState, Pill } from "./ds";
import { hostOf, safeUrl } from "./radar-model";
import {
  GROUP_TONE, INFLUENCE_LABEL, LIGHT, PHASE_HELP, PLAYS, SERVICE_LABEL, SIGNAL_GROUP, monthLabel, prospectBase,
  type Prospect, type Search as SearchJob, type Timing, type TimingClue,
} from "./prospect-model";
import type { SharedProps } from "./types";

const STEPS = ["Reading news, trade press and company sites", "Checking registers, planning and enforcement records", "Finding the incumbent and competitors", "Identifying decision makers and published contacts", "Inferring timing from indirect clues", "Writing your prospect briefs"];

function useWide() {
  const [wide, setWide] = useState(true);
  useEffect(() => {
    const q = window.matchMedia("(min-width: 1180px)");
    const update = () => setWide(q.matches);
    update();
    q.addEventListener("change", update);
    return () => q.removeEventListener("change", update);
  }, []);
  return wide;
}

export function Prospects({ notify, navigate, refresh }: SharedProps) {
  const base = prospectBase();
  const wide = useWide();
  const [items, setItems] = useState<Prospect[] | null>(null);
  const [mode, setMode] = useState<"discover" | "company">("discover");
  const [query, setQuery] = useState("");
  const [job, setJob] = useState<SearchJob | null>(null);
  const [step, setStep] = useState(0);
  const [selected, setSelected] = useState<number | null>(null);
  const [light, setLight] = useState<"" | Timing["light"]>("");
  const [error, setError] = useState("");
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await fetch(base, { cache: "no-store" });
      if (!r.ok) throw new Error();
      const d = (await r.json()) as { items: Prospect[] };
      setItems(d.items);
      return d.items;
    } catch {
      setError("Prospects are unavailable. Check the SalesIntel API is running.");
      setItems([]);
      return [];
    }
  }, [base]);

  useEffect(() => {
    void load();
    fetch(`${base}/searches`, { cache: "no-store" }).then((r) => (r.ok ? r.json() : null)).then((d: { items: SearchJob[] } | null) => {
      const running = d?.items.find((s) => s.status === "running");
      if (running) setJob(running);
    }).catch(() => {});
    const lead = Number(new URL(window.location.href).searchParams.get("prospect"));
    if (lead > 0) setSelected(lead);
  }, [base, load]);

  // Poll a running search; reveal its results when it lands.
  useEffect(() => {
    if (!job || job.status !== "running") return;
    setStep(0);
    const stepper = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 25000);
    timer.current = setInterval(async () => {
      const r = await fetch(`${base}/searches/${job.id}`, { cache: "no-store" }).catch(() => null);
      if (!r?.ok) return;
      const next = (await r.json()) as SearchJob;
      if (next.status === "running") return;
      setJob(next);
      if (next.status === "complete") {
        await load();
        if (next.prospect_ids[0]) select(next.prospect_ids[0]);
        notify(`${next.prospect_ids.length} prospect${next.prospect_ids.length === 1 ? "" : "s"} researched from ${next.sources_reviewed} sources.`);
      }
    }, 5000);
    return () => { clearInterval(stepper); if (timer.current) clearInterval(timer.current); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job?.id, job?.status]);

  const visible = useMemo(() => (items || []).filter((p) => !light || p.timing.light === light), [items, light]);
  useEffect(() => {
    if (wide && visible.length && !visible.some((p) => p.id === selected)) setSelected(visible[0].id);
  }, [wide, visible, selected]);

  function select(id: number | null) {
    setSelected(id);
    const url = new URL(window.location.href);
    if (id) url.searchParams.set("prospect", String(id)); else url.searchParams.delete("prospect");
    window.history.replaceState({}, "", url);
  }
  async function start(text = query, chosen = mode, prospectId?: number) {
    const q = text.trim();
    if (q.length < 3) return;
    setError("");
    const r = await fetch(`${base}/searches`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ query: q, mode: chosen, ...(prospectId ? { prospect_id: prospectId } : {}) }) });
    const payload = await r.json().catch(() => null);
    if (!r.ok) return setError(typeof payload?.detail === "string" ? payload.detail : "Research could not start.");
    setQuery(q);
    setMode(chosen);
    setJob(payload as SearchJob);
  }
  async function setStatus(id: number, status: "watching" | "dismissed") {
    const r = await fetch(`${base}/${id}`, { method: "PATCH", headers: { "content-type": "application/json" }, body: JSON.stringify({ status }) });
    if (!r.ok) return notify("Could not save that.", true);
    notify(status === "dismissed" ? "Dismissed." : "Added to your watch list.");
    const next = await load();
    if (status === "dismissed") select(next[0]?.id ?? null);
  }
  async function promote(id: number) {
    const r = await fetch(`${base}/${id}/promote`, { method: "POST" });
    if (!r.ok) return notify("Could not add this to your pipeline.", true);
    const d = (await r.json()) as { created: boolean };
    notify(d.created ? "Added to your pipeline." : "Already in your pipeline.");
    await load();
    void refresh().catch(() => {});
  }

  const counts = useMemo(() => {
    const c = { green: 0, amber: 0, red: 0, grey: 0 } as Record<Timing["light"], number>;
    (items || []).forEach((p) => { c[p.timing.light] += 1; });
    return c;
  }, [items]);
  const current = (items || []).find((p) => p.id === selected) || null;
  const running = job?.status === "running";

  return (
    <div className="ds-root">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-[13px] font-semibold text-ds-brand">Private sector · AI research · inferred timing</p>
          <h1 className="mt-1 text-[28px] font-semibold leading-tight tracking-[-0.03em] text-ds-ink">Prospects</h1>
          <p className="mt-1.5 max-w-3xl text-[15px] leading-6 text-ds-muted">Companies showing signs they will need fire and security services, before they go to market. SalesIntel reads news, trade press, company sites and public registers, finds who decides, and infers when to engage from clues that are not the purchase itself.</p>
        </div>
      </header>

      <section className="mt-6 rounded-2xl border border-ds-border bg-gradient-to-br from-white via-white to-ds-brand-soft p-5 shadow-ds-xs" aria-label="Hunt for prospects">
        <div className="ds-tabs w-fit" role="group" aria-label="Research mode">
          <button aria-pressed={mode === "discover"} onClick={() => setMode("discover")}><Telescope size={15} /> Discover companies</button>
          <button aria-pressed={mode === "company"} onClick={() => setMode("company")}><Building2 size={15} /> Research a company</button>
        </div>
        <form className="mt-3 flex flex-col gap-3 sm:flex-row" onSubmit={(e) => { e.preventDefault(); void start(); }}>
          <div className="relative flex-1">
            <Search size={18} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-ds-brand" />
            <input className="ds-input !h-12 !pl-11 !text-[15px]" aria-label={mode === "discover" ? "Describe the prospects to find" : "Company name and location"} value={query} onChange={(e) => setQuery(e.target.value)} maxLength={1000}
              placeholder={mode === "discover" ? "e.g. Logistics companies opening new sites in the Midlands" : "e.g. Ocado Group, Hatfield"} disabled={running} />
          </div>
          <button type="submit" className="ds-btn primary !h-12 !px-5" disabled={running || query.trim().length < 3}>{running ? <Loader2 size={17} className="ds-spin" /> : <Sparkles size={17} />} {mode === "discover" ? "Find prospects" : "Research"}</button>
        </form>
        {mode === "discover" && <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="text-[12px] text-ds-muted">Plays:</span>
          {PLAYS.map((p) => <button key={p.label} disabled={running} onClick={() => { setQuery(p.query); void start(p.query, "discover"); }} className="rounded-full border border-ds-border bg-white px-3 py-1 text-[12px] font-medium text-ds-ink-2 transition hover:border-ds-brand-line hover:text-ds-brand disabled:opacity-50">{p.label}</button>)}
        </div>}
        {error && <p role="alert" className="mt-3 rounded-lg border border-ds-red-line bg-ds-red-soft px-3 py-2 text-[13px] text-ds-red">{error}</p>}
        {job && job.status !== "running" && job.status === "failed" && <p role="alert" className="mt-3 rounded-lg border border-ds-red-line bg-ds-red-soft px-3 py-2 text-[13px] text-ds-red">{job.error}</p>}
        {running && <div className="mt-4 rounded-xl border border-ds-brand-line bg-white p-4" role="status" aria-live="polite">
          <p className="text-[14px] font-semibold text-ds-ink">Researching “{job.query}”</p>
          <p className="text-[12px] text-ds-muted">Usually three to six minutes. You can leave this page; results are saved.</p>
          <ol className="mt-3 grid gap-2 sm:grid-cols-2">
            {STEPS.map((label, i) => <li key={label} className={`flex items-center gap-2.5 text-[13px] ${i <= step ? "text-ds-ink" : "text-ds-muted"}`}>
              {i < step ? <CheckCircle2 size={15} className="text-ds-green" /> : i === step ? <Loader2 size={15} className="ds-spin text-ds-brand" /> : <span className="h-[15px] w-[15px] rounded-full border border-ds-border-strong" />}{label}
            </li>)}
          </ol>
        </div>}
      </section>

      {!!items?.length && <section aria-label="Timing" className="mt-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {(["green", "amber", "red", "grey"] as const).map((l) => {
          const names = { green: "Engage now", amber: "Prepare", red: "Not yet", grey: "Timing unknown" };
          return <button key={l} onClick={() => setLight(light === l ? "" : l)} aria-pressed={light === l}
            className={`rounded-xl border bg-white p-4 text-left shadow-ds-xs transition hover:shadow-ds-sm ${light === l ? "border-ds-brand ring-4 ring-[rgba(59,79,216,.12)]" : "border-ds-border"}`}>
            <span className="flex items-center gap-2 text-[13px] font-medium text-ds-muted"><TrafficDot light={l} />{names[l]}</span>
            <span className="ds-num mt-2 block text-[28px] font-semibold leading-none text-ds-ink">{counts[l]}</span>
          </button>;
        })}
      </section>}

      <div className="mt-5 grid items-start gap-5 xl:grid-cols-[minmax(320px,400px)_minmax(0,1fr)]">
        <section aria-label="Prospect list" className="min-w-0">
          {items === null && <div className="space-y-2">{[0, 1, 2].map((i) => <div key={i} className="ds-skeleton h-[120px] rounded-xl" />)}</div>}
          {items && !items.length && !running && <div className="ds-card"><EmptyState icon={<Telescope size={20} />} title="Start your first hunt">Pick a play above or describe the companies you want. SalesIntel researches them and tells you who to call, why, and when.</EmptyState></div>}
          {items && !!items.length && <>
            <p className="mb-2 px-1 text-[12px] font-medium text-ds-muted">{visible.length} prospect{visible.length === 1 ? "" : "s"}, most timely first</p>
            <ul className="space-y-2">{visible.map((p) => <li key={p.id}><ProspectRow p={p} active={p.id === selected} onClick={() => select(p.id)} /></li>)}</ul>
          </>}
        </section>
        {wide ? (
          <aside aria-label="Selected prospect" className="ds-card sticky top-[76px] h-[calc(100vh-96px)] min-h-[560px] overflow-hidden">
            {current ? <ProspectDetail key={current.id} p={current} onPromote={promote} onStatus={setStatus} onRefresh={() => void start(`${current.name}${current.location ? `, ${current.location.split(/[.;]/)[0]}` : ""}`, "company", current.id)} onOpenPipeline={() => navigate("opportunities")} />
              : <EmptyState icon={<MousePointerClick size={20} />} title="Select a prospect">See the signals, when to engage, who decides and how to open the conversation.</EmptyState>}
          </aside>
        ) : current && (
          <div className="fixed inset-0 z-50 flex bg-[rgba(16,24,40,.35)]" role="dialog" aria-modal="true" aria-label="Prospect detail">
            <div className="ds-fade ml-auto h-full w-full max-w-[760px] bg-white shadow-ds-lg">
              <ProspectDetail key={current.id} p={current} onPromote={promote} onStatus={setStatus} onClose={() => select(null)} onRefresh={() => void start(current.name, "company", current.id)} onOpenPipeline={() => navigate("opportunities")} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export function TrafficDot({ light, size = 10 }: { light: Timing["light"]; size?: number }) {
  const l = LIGHT[light];
  return <span aria-hidden="true" className="inline-block flex-none rounded-full" style={{ width: size, height: size, background: l.dot, boxShadow: `0 0 0 3px ${l.ring}` }} />;
}

export function TrafficLight({ timing, large }: { timing: Timing; large?: boolean }) {
  const l = LIGHT[timing.light];
  const window = timing.window ? `${timing.window.start <= timing.as_of ? "Now" : monthLabel(timing.window.start)} – ${monthLabel(timing.window.end)}` : timing.blocked_until ? `Locked until ${monthLabel(timing.blocked_until)}` : "";
  return (
    <span className={`inline-flex items-center gap-2 rounded-full border font-semibold ${large ? "px-3.5 py-1.5 text-[14px]" : "px-2.5 py-0.5 text-[12px]"}`} style={{ background: l.soft, color: l.text, borderColor: l.ring }}>
      <TrafficDot light={timing.light} size={large ? 11 : 8} />{timing.label}{window && <span className="font-medium opacity-80">· {window}</span>}
    </span>
  );
}

function ProspectRow({ p, active, onClick }: { p: Prospect; active: boolean; onClick: () => void }) {
  const groups = p.signal_groups.slice(0, 3);
  return (
    <button onClick={onClick} aria-current={active ? "true" : undefined}
      className={`w-full rounded-xl border bg-white px-4 py-3.5 text-left transition ${active ? "border-ds-brand shadow-ds-sm ring-4 ring-[rgba(59,79,216,.10)]" : "border-ds-border shadow-ds-xs hover:border-ds-border-strong hover:shadow-ds-sm"} ${p.status === "dismissed" ? "opacity-60" : ""}`}>
      <span className="flex items-center justify-between gap-2"><TrafficLight timing={p.timing} />{p.status === "pipeline" ? <Pill tone="green">In pipeline</Pill> : p.status === "watching" ? <Pill>Watching</Pill> : null}</span>
      <span className="mt-2 block truncate text-[14px] font-semibold text-ds-ink">{p.name}</span>
      <span className="mt-0.5 line-clamp-2 block text-[13px] leading-5 text-ds-muted">{p.headline}</span>
      <span className="mt-2 flex flex-wrap items-center gap-1.5">
        {groups.map((g) => <Pill key={g} tone={GROUP_TONE[g] || "neutral"}>{g}</Pill>)}
        <span className="ml-auto flex items-center gap-3 text-[12px] text-ds-muted"><span className="flex items-center gap-1"><Users size={13} />{p.people.length}</span><span className="flex items-center gap-1"><Phone size={13} />{p.contact_routes.length}</span></span>
      </span>
    </button>
  );
}

type Tab = "overview" | "signals" | "timing" | "people" | "approach";

function ProspectDetail({ p, onPromote, onStatus, onClose, onRefresh, onOpenPipeline }: {
  p: Prospect; onPromote: (id: number) => void; onStatus: (id: number, s: "watching" | "dismissed") => void; onClose?: () => void; onRefresh: () => void; onOpenPipeline: () => void;
}) {
  const [tab, setTab] = useState<Tab>("overview");
  const site = safeUrl(p.website);
  const tabs: [Tab, string, number | null][] = [["overview", "Overview", null], ["signals", "Signals", p.signals.length], ["timing", "Timing", p.timing.clues.length], ["people", "People & contacts", p.people.length + p.contact_routes.length], ["approach", "Approach", null]];
  return (
    <article className="flex h-full flex-col" aria-label={p.name}>
      <header className="border-b border-ds-border px-6 pb-0 pt-5">
        {onClose && <button className="ds-btn ghost sm -ml-2 mb-2" onClick={onClose}><ArrowLeft size={15} /> All prospects</button>}
        <TrafficLight timing={p.timing} large />
        <h2 className="mt-3 text-[22px] font-semibold leading-tight tracking-[-0.02em] text-ds-ink">{p.name}</h2>
        <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[13px] text-ds-muted">
          {p.sector && <span>{p.sector}</span>}{p.location && <span className="line-clamp-1 max-w-full" title={p.location}>{p.location}</span>}
          {site && <a href={site} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 font-medium text-ds-brand hover:underline"><Globe size={13} />{hostOf(site)}</a>}
          {p.company_number && <a href={`https://find-and-update.company-information.service.gov.uk/company/${encodeURIComponent(p.company_number)}`} target="_blank" rel="noreferrer" className="hover:text-ds-brand hover:underline">Company {p.company_number}</a>}
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          {p.status === "pipeline" ? <button className="ds-btn" onClick={onOpenPipeline}><Check size={16} className="text-ds-green" /> In your pipeline</button>
            : <button className="ds-btn primary" onClick={() => onPromote(p.id)}><BriefcaseBusiness size={16} /> Add to pipeline</button>}
          <button className="ds-btn" onClick={onRefresh} title="Research this company again in depth"><RefreshCw size={15} /> Deepen research</button>
          {p.status !== "watching" && p.status !== "pipeline" && <button className="ds-btn ghost" onClick={() => onStatus(p.id, "watching")}><Eye size={16} /> Watch</button>}
          <button className="ds-btn ghost" onClick={() => onStatus(p.id, "dismissed")}><CircleSlash size={16} /> Dismiss</button>
        </div>
        <div className="ds-underline-tabs mt-5" role="tablist" aria-label="Prospect detail">
          {tabs.map(([id, label, count]) => <button key={id} role="tab" aria-selected={tab === id} onClick={() => setTab(id)}>{label}{count !== null && count > 0 && <span className="rounded-full bg-ds-subtle px-1.5 text-[11px] text-ds-muted">{count}</span>}</button>)}
        </div>
      </header>
      <div className="ds-scroll flex-1 overflow-y-auto px-6 py-5">
        {tab === "overview" && <Overview p={p} go={setTab} />}
        {tab === "signals" && <Signals p={p} />}
        {tab === "timing" && <TimingView timing={p.timing} />}
        {tab === "people" && <PeopleView p={p} />}
        {tab === "approach" && <ApproachView p={p} />}
      </div>
    </article>
  );
}

function Overview({ p, go }: { p: Prospect; go: (t: Tab) => void }) {
  const l = LIGHT[p.timing.light];
  const top = [...p.signals].filter((s) => s.direction !== "against").slice(0, 4);
  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-ds-brand-line bg-ds-brand-soft p-4">
        <p className="flex items-center gap-2 text-[13px] font-semibold text-ds-brand"><Lightbulb size={15} /> Why approach them</p>
        <p className="mt-1.5 text-[15px] font-medium leading-6 text-ds-ink">{p.headline}</p>
        <p className="mt-1.5 text-[14px] leading-6 text-ds-ink-2">{p.summary}</p>
      </div>
      <section className="rounded-xl border p-4" style={{ borderColor: l.ring, background: l.soft }}>
        <p className="flex items-center gap-2 text-[13px] font-semibold" style={{ color: l.text }}><TrafficDot light={p.timing.light} /> When: {p.timing.label}</p>
        <p className="mt-1 text-[13px] text-ds-ink-2">{PHASE_HELP[p.timing.phase]}</p>
        <ul className="mt-2 space-y-1.5">{p.timing.reasons.slice(0, 3).map((r) => <li key={r} className="flex gap-2 text-[13px] leading-5 text-ds-ink-2"><span className="mt-[7px] h-1.5 w-1.5 flex-none rounded-full bg-ds-faint" />{r}</li>)}</ul>
        <button className="mt-2 text-[12px] font-semibold text-ds-brand hover:underline" onClick={() => go("timing")}>See the timing inference →</button>
      </section>
      {top.length > 0 && <section>
        <h3 className="mb-2.5 text-[14px] font-semibold text-ds-ink">Strongest signals</h3>
        <ul className="space-y-2">{top.map((s, i) => <SignalItem key={i} s={s} labels={p.signal_labels} />)}</ul>
        {p.signals.length > top.length && <button className="mt-2 text-[12px] font-semibold text-ds-brand hover:underline" onClick={() => go("signals")}>All {p.signals.length} signals →</button>}
      </section>}
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg bg-ds-canvas px-3.5 py-3">
          <p className="text-[12px] font-medium text-ds-muted">Current provider</p>
          <p className="mt-1 text-[14px] font-semibold text-ds-ink">{p.incumbent?.name || "Not found in public sources"}</p>
          {p.incumbent?.detail && <p className="mt-1 text-[12px] leading-[18px] text-ds-muted">{p.incumbent.detail} {p.incumbent.source_url && <Cite url={p.incumbent.source_url} />}</p>}
        </div>
        <div className="rounded-lg bg-ds-canvas px-3.5 py-3">
          <p className="text-[12px] font-medium text-ds-muted">Who to talk to</p>
          <p className="mt-1 text-[14px] font-semibold text-ds-ink">{p.people[0] ? `${p.people[0].name}, ${p.people[0].role}` : "Roles only; no named source found"}</p>
          <button className="mt-1 text-[12px] font-semibold text-ds-brand hover:underline" onClick={() => go("people")}>{p.people.length} people · {p.contact_routes.length} contact routes →</button>
        </div>
      </div>
      {p.services.length > 0 && <section><h3 className="mb-2 text-[14px] font-semibold text-ds-ink">Services to lead with</h3><div className="flex flex-wrap gap-1.5">{p.services.map((s) => <Pill key={s} tone="brand">{SERVICE_LABEL[s] || s}</Pill>)}</div></section>}
      {p.competitors.length > 0 && <section>
        <h3 className="mb-2 flex items-center gap-2 text-[14px] font-semibold text-ds-ink"><Swords size={15} className="text-ds-muted" /> Competitors in the picture</h3>
        <ul className="space-y-1.5">{p.competitors.map((c) => <li key={c.name} className="text-[13px] leading-5 text-ds-ink-2"><strong className="font-semibold text-ds-ink">{c.name}</strong> · {c.relation} {c.source_url && <Cite url={c.source_url} />}</li>)}</ul>
      </section>}
      {p.unknowns.length > 0 && <div className="rounded-xl border border-ds-amber-line bg-ds-amber-soft p-4"><p className="text-[13px] font-semibold text-ds-amber">Still unknown</p><ul className="mt-1.5 list-disc space-y-1 pl-5 text-[13px] leading-5 text-ds-ink-2">{p.unknowns.map((u) => <li key={u}>{u}</li>)}</ul></div>}
      <p className="text-[12px] leading-[18px] text-ds-muted">Researched {p.researched_at ? monthLabel(p.researched_at) : ""} from {p.sources_reviewed ?? 0} public sources{p.checks && (p.checks.people + p.checks.contact_routes) > 0 ? `; ${p.checks.people + p.checks.contact_routes} unverifiable name or contact detail removed` : ""}. Decision support, not a verified record.</p>
    </div>
  );
}

function SignalItem({ s, labels }: { s: Prospect["signals"][number]; labels: Record<string, string> }) {
  const group = SIGNAL_GROUP[s.type] || "Strategy";
  return (
    <li className="flex gap-3 rounded-lg border border-ds-border bg-white px-3.5 py-3">
      <span className={`mt-0.5 grid h-6 w-6 flex-none place-items-center rounded-full ${s.direction === "supports" ? "bg-ds-green-soft text-ds-green" : s.direction === "against" ? "bg-ds-red-soft text-ds-red" : "bg-ds-subtle text-ds-muted"}`}>
        {s.direction === "supports" ? <ArrowUpRight size={14} /> : s.direction === "against" ? <ArrowDownRight size={14} /> : <Minus size={14} />}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-1.5"><Pill tone={GROUP_TONE[group] || "neutral"}>{labels[s.type] || s.type}</Pill>{s.date && <span className="text-[12px] text-ds-muted">{monthLabel(s.date.length === 4 ? `${s.date}-07-01` : s.date)}</span>}</div>
        <p className="mt-1 text-[14px] font-semibold leading-5 text-ds-ink">{s.title}</p>
        <p className="mt-0.5 text-[13px] leading-5 text-ds-ink-2">{s.detail} <span className="text-[12px] text-ds-muted">· {s.basis === "stated" ? "stated in source" : "inferred"}</span> {s.source_url && <Cite url={s.source_url} />}</p>
      </div>
    </li>
  );
}

function Signals({ p }: { p: Prospect }) {
  const groups = Array.from(new Set(p.signals.map((s) => SIGNAL_GROUP[s.type] || "Strategy")));
  if (!p.signals.length) return <p className="rounded-lg bg-ds-canvas px-4 py-6 text-center text-[13px] text-ds-muted">No sourced signals were found.</p>;
  return <div className="space-y-5">{groups.map((g) => <section key={g}><h3 className="mb-2 text-[13px] font-semibold text-ds-muted">{g}</h3><ul className="space-y-2">{p.signals.filter((s) => (SIGNAL_GROUP[s.type] || "Strategy") === g).map((s, i) => <SignalItem key={i} s={s} labels={p.signal_labels} />)}</ul></section>)}</div>;
}

const DAY = 86_400_000;
function TimingView({ timing }: { timing: Timing }) {
  const today = new Date(`${timing.as_of}T00:00:00Z`).getTime();
  const clues = timing.clues;
  const min = Math.min(today - 365 * DAY, ...clues.map((c) => new Date(`${c.start}T00:00:00Z`).getTime()).filter((t) => t > today - 3 * 365 * DAY));
  const max = Math.max(today + 2 * 365 * DAY, ...clues.map((c) => Math.min(new Date(`${c.end}T00:00:00Z`).getTime(), today + 5 * 365 * DAY)));
  const pos = (iso: string) => Math.max(0, Math.min(100, ((new Date(`${iso}T00:00:00Z`).getTime() - min) / (max - min)) * 100));
  const years: number[] = [];
  for (let y = new Date(min).getUTCFullYear() + 1; y <= new Date(max).getUTCFullYear(); y++) years.push(y);
  const conv = timing.convergence;
  return (
    <div className="space-y-6">
      <div>
        <TrafficLight timing={timing} large />
        <p className="mt-2 text-[13px] leading-5 text-ds-ink-2">{PHASE_HELP[timing.phase]}</p>
      </div>
      {clues.length > 0 ? <section className="rounded-xl border border-ds-border bg-white p-4" aria-label="Timing timeline">
        <div className="relative ml-[132px] h-6 text-[11px] text-ds-muted">
          {years.map((y) => <span key={y} className="absolute -translate-x-1/2" style={{ left: `${pos(`${y}-01-01`)}%` }}>{y}</span>)}
        </div>
        <div className="relative">
          <div className="pointer-events-none absolute inset-y-0 left-[132px] right-0">
            {conv && <div className="absolute inset-y-0 rounded-md bg-ds-green-soft" style={{ left: `${pos(conv.start)}%`, width: `${Math.max(1, pos(conv.end) - pos(conv.start))}%` }} />}
            {years.map((y) => <div key={y} className="absolute inset-y-0 w-px bg-ds-border" style={{ left: `${pos(`${y}-01-01`)}%` }} />)}
            <div className="absolute inset-y-0 w-0.5 bg-ds-brand" style={{ left: `${pos(timing.as_of)}%` }}><span className="absolute -top-5 -translate-x-1/2 rounded bg-ds-brand px-1 text-[10px] font-semibold text-white">Today</span></div>
          </div>
          <ul className="relative space-y-2 py-1">
            {clues.map((c, i) => <TimelineRow key={i} c={c} pos={pos} />)}
          </ul>
        </div>
        <p className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-ds-muted">
          <span className="flex items-center gap-1.5"><span className="h-2 w-5 rounded bg-[#12b76a]" /> Window open</span>
          <span className="flex items-center gap-1.5"><span className="h-2 w-5 rounded bg-[#a6f4c5]" /> Window ahead</span>
          <span className="flex items-center gap-1.5"><span className="h-2 w-5 rounded bg-[#f97066]" /> Holds them back</span>
          {conv && <span className="flex items-center gap-1.5"><span className="h-2 w-5 rounded bg-ds-green-soft ring-1 ring-ds-green-line" /> Clues converge</span>}
        </p>
      </section> : <p className="rounded-lg bg-ds-canvas px-4 py-6 text-center text-[13px] text-ds-muted">No dated clues yet. Use Deepen research to look for building dates, supplier appointments and leadership changes.</p>}
      <section>
        <h3 className="mb-2 text-[14px] font-semibold text-ds-ink">How this was inferred</h3>
        <ul className="space-y-2">{timing.reasons.map((r) => <li key={r} className="flex gap-2.5 text-[13px] leading-5 text-ds-ink-2"><span className="mt-[7px] h-1.5 w-1.5 flex-none rounded-full bg-ds-brand" />{r}</li>)}</ul>
      </section>
      {clues.length > 0 && <section>
        <h3 className="mb-2 text-[14px] font-semibold text-ds-ink">The clues</h3>
        <ul className="space-y-2">{clues.map((c, i) => (
          <li key={i} className="rounded-lg border border-ds-border bg-white px-3.5 py-3">
            <div className="flex flex-wrap items-center gap-1.5"><Pill tone={c.context_only ? "neutral" : c.polarity < 0 ? "red" : c.status === "active" ? "green" : c.status === "upcoming" ? "amber" : "neutral"} dot>{c.label}</Pill><Pill>{c.context_only ? "context only" : `${c.strength} · ${c.basis}`}</Pill><span className="text-[12px] text-ds-muted">observed {monthLabel(c.observed)}</span></div>
            {c.detail && <p className="mt-1.5 text-[13px] leading-5 text-ds-ink">{c.detail} {c.source_url && <Cite url={c.source_url} />}</p>}
            <p className="mt-1 text-[12px] leading-[18px] text-ds-muted">Rule: {c.rule}. Window {monthLabel(c.start)} – {monthLabel(c.end)}.</p>
          </li>))}</ul>
      </section>}
      <p className="text-[12px] leading-[18px] text-ds-muted">{timing.method}</p>
    </div>
  );
}

function TimelineRow({ c, pos }: { c: TimingClue; pos: (iso: string) => number }) {
  const left = pos(c.start), right = pos(c.end);
  const color = c.context_only ? "#d0d5dd" : c.polarity < 0 ? "#f97066" : c.status === "active" ? "#12b76a" : c.status === "upcoming" ? "#a6f4c5" : "#d0d5dd";
  return (
    <li className="flex items-center gap-3">
      <span className="w-[120px] flex-none truncate text-right text-[12px] font-medium text-ds-ink-2" title={c.label}>{c.label}</span>
      <span className="relative h-5 flex-1">
        <span className="absolute top-1/2 h-2.5 -translate-y-1/2 rounded-full" style={{ left: `${left}%`, width: `${Math.max(1.2, right - left)}%`, background: color, opacity: c.strength === "weak" ? 0.7 : 1 }} title={`${c.label}: ${monthLabel(c.start)} – ${monthLabel(c.end)}`} />
      </span>
    </li>
  );
}

function PeopleView({ p }: { p: Prospect }) {
  return (
    <div className="space-y-6">
      <section>
        <h3 className="mb-2.5 flex items-center gap-2 text-[14px] font-semibold text-ds-ink"><Users size={16} className="text-ds-muted" /> Decision makers and influencers</h3>
        {!p.people.length && <p className="rounded-lg bg-ds-canvas px-4 py-4 text-[13px] text-ds-muted">No person is named in a public source for this company. Approach through the contact routes below and ask for the estates, facilities or security lead.</p>}
        <ul className="grid gap-2.5 2xl:grid-cols-2">{p.people.map((person) => (
          <li key={person.name} className="rounded-xl border border-ds-border bg-white p-4">
            <div className="flex items-start gap-3">
              <span className="grid h-10 w-10 flex-none place-items-center rounded-full bg-ds-brand-soft text-[14px] font-semibold text-ds-brand">{person.name.split(" ").map((x) => x[0]).slice(0, 2).join("")}</span>
              <div className="min-w-0">
                <p className="text-[14px] font-semibold text-ds-ink">{person.name}</p>
                <p className="text-[13px] text-ds-ink-2">{person.role}</p>
                <div className="mt-1"><Pill tone={person.influence === "decision_maker" ? "brand" : "neutral"}>{INFLUENCE_LABEL[person.influence]}</Pill></div>
              </div>
            </div>
            <p className="mt-2.5 text-[13px] leading-5 text-ds-ink-2">{person.why}</p>
            <p className="mt-2 flex gap-1.5 text-[12px] italic leading-[18px] text-ds-muted"><MessageSquareQuote size={13} className="mt-0.5 flex-none not-italic" />“{person.quote}” <Cite url={person.source_url} /></p>
          </li>))}</ul>
      </section>
      <section>
        <h3 className="mb-2.5 flex items-center gap-2 text-[14px] font-semibold text-ds-ink"><Phone size={16} className="text-ds-muted" /> Published contact routes</h3>
        {!p.contact_routes.length && <p className="rounded-lg bg-ds-canvas px-4 py-4 text-[13px] text-ds-muted">No business contact detail was published in the sources found. Try Deepen research, or use the company website.</p>}
        <ul className="space-y-2">{p.contact_routes.map((c) => <ContactRow key={`${c.kind}${c.value}`} c={c} />)}</ul>
      </section>
      <p className="flex items-start gap-2 rounded-lg bg-ds-canvas px-3.5 py-3 text-[12px] leading-[18px] text-ds-muted"><ShieldCheck size={14} className="mt-0.5 flex-none" />Only names and contact details that a public source states for business use are shown, each with its source. Nothing is guessed. Confirm details before use, keep to business contacts, and honour any request not to be contacted (UK GDPR and PECR).</p>
    </div>
  );
}

function ContactRow({ c }: { c: Prospect["contact_routes"][number] }) {
  const [copied, setCopied] = useState(false);
  const Icon = c.kind === "email" ? Mail : c.kind === "web_form" ? Globe : Phone;
  const href = c.kind === "email" ? `mailto:${c.value}` : c.kind === "web_form" ? safeUrl(c.value) : `tel:${c.value.replace(/[^\d+]/g, "")}`;
  return (
    <li className="flex items-center gap-3 rounded-xl border border-ds-border bg-white px-3.5 py-3">
      <span className="grid h-9 w-9 flex-none place-items-center rounded-lg bg-ds-subtle text-ds-muted"><Icon size={16} /></span>
      <div className="min-w-0 flex-1">
        <a href={href} target={c.kind === "web_form" ? "_blank" : undefined} rel="noreferrer" className="block truncate text-[14px] font-semibold text-ds-ink hover:text-ds-brand">{c.kind === "web_form" ? hostOf(c.value) : c.value}</a>
        <p className="truncate text-[12px] text-ds-muted">{c.label || c.kind.replace("_", " ")} · <Cite url={c.source_url} label="source" /></p>
      </div>
      <button className="ds-btn ghost sm" aria-label={`Copy ${c.value}`} onClick={() => { void navigator.clipboard?.writeText(c.value); setCopied(true); setTimeout(() => setCopied(false), 1500); }}>{copied ? <Check size={14} /> : <Copy size={14} />}</button>
    </li>
  );
}

function ApproachView({ p }: { p: Prospect }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="space-y-5">
      <section className="rounded-xl border border-ds-border bg-white p-4"><h3 className="text-[13px] font-semibold text-ds-muted">The angle</h3><p className="mt-1 text-[15px] leading-6 text-ds-ink">{p.approach.angle}</p></section>
      {p.approach.opening_line && <section className="rounded-xl border border-ds-brand-line bg-ds-brand-soft p-4">
        <div className="flex items-center justify-between"><h3 className="text-[13px] font-semibold text-ds-brand">Opening line</h3><button className="ds-btn ghost sm" onClick={() => { void navigator.clipboard?.writeText(p.approach.opening_line); setCopied(true); setTimeout(() => setCopied(false), 1500); }}>{copied ? <Check size={14} /> : <Copy size={14} />} Copy</button></div>
        <p className="mt-1 text-[15px] italic leading-6 text-ds-ink">“{p.approach.opening_line}”</p>
      </section>}
      {p.approach.offer && <section className="rounded-xl border border-ds-border bg-white p-4"><h3 className="text-[13px] font-semibold text-ds-muted">What to offer</h3><p className="mt-1 text-[14px] leading-6 text-ds-ink-2">{p.approach.offer}</p></section>}
      {p.approach.questions.length > 0 && <section className="rounded-xl border border-ds-border bg-white p-4"><h3 className="mb-2 text-[13px] font-semibold text-ds-muted">Questions for the first conversation</h3>
        <ol className="space-y-2">{p.approach.questions.map((q, i) => <li key={q} className="flex gap-2.5 text-[14px] leading-6 text-ds-ink-2"><span className="mt-0.5 grid h-5 w-5 flex-none place-items-center rounded-full bg-ds-subtle text-[11px] font-semibold text-ds-muted">{i + 1}</span>{q}</li>)}</ol>
      </section>}
      <p className="flex items-center gap-2 text-[12px] text-ds-muted"><FileSearch size={14} /> Built from the signals and timing on this prospect. Adapt it; never claim knowledge you could not have.</p>
    </div>
  );
}

function Cite({ url, label = "source" }: { url: string; label?: string }) {
  const href = safeUrl(url);
  if (!href) return null;
  return <a href={href} target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 whitespace-nowrap text-[12px] font-medium not-italic text-ds-brand hover:underline">{label}<ArrowUpRight size={11} /></a>;
}
