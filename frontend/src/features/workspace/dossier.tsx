"use client";
import { useEffect, useRef, useState } from "react";
import {
  AlertTriangle, ArrowDownRight, ArrowUpRight, Building2, CalendarClock, CheckCircle2, CircleHelp, Compass, FileSearch,
  Lightbulb, ListChecks, Loader2, Minus, RefreshCw, ShieldAlert, Sparkles, Target, Users,
} from "lucide-react";
import { Pill, SourceLink } from "./ds";
import { formatDate, radarBase, safeUrl, type Dossier, type Tone } from "./radar-model";

const STANCE: Record<string, { label: string; tone: Tone; line: string }> = {
  pursue: { label: "Pursue", tone: "green", line: "Worth active pursuit now." },
  qualify: { label: "Qualify", tone: "amber", line: "Promising. Close the gaps before committing bid effort." },
  monitor: { label: "Monitor", tone: "neutral", line: "Not yet. Keep watching for a trigger." },
  step_back: { label: "Step back", tone: "red", line: "The evidence does not support pursuit now." },
};
const STEPS = ["Reading MiSi's record and published notices", "Searching the buyer's news, strategy and estate", "Checking contract history and incumbents", "Weighing signals for and against", "Writing your dossier"];

export function DeepResearch({ id, customer }: { id: number; customer: string }) {
  const [dossier, setDossier] = useState<Dossier | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [step, setStep] = useState(0);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoaded(false); setDossier(null); setError("");
    fetch(`${radarBase()}/${id}/dossier`, { cache: "no-store", signal: controller.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d: { dossier: Dossier | null }) => { setDossier(d.dossier); setLoaded(true); })
      .catch(() => { if (!controller.signal.aborted) setLoaded(true); });
    return () => controller.abort();
  }, [id]);
  useEffect(() => () => { if (timer.current) clearInterval(timer.current); }, []);

  async function run() {
    setRunning(true); setError(""); setStep(0);
    timer.current = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 16000);
    try {
      const response = await fetch(`${radarBase()}/${id}/dossier`, { method: "POST" });
      const payload = await response.json().catch(() => null);
      if (!response.ok) throw new Error(typeof payload?.detail === "string" ? payload.detail : "Research could not complete. Try again.");
      setDossier(payload.dossier);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      if (timer.current) clearInterval(timer.current);
      setRunning(false);
    }
  }

  if (!loaded) return <div className="space-y-3 py-2" aria-busy="true"><div className="ds-skeleton h-24" /><div className="ds-skeleton h-40" /></div>;

  if (running) return (
    <div className="rounded-xl border border-ds-brand-line bg-gradient-to-b from-ds-brand-soft to-white p-6" role="status" aria-live="polite">
      <div className="flex items-center gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-full bg-white text-ds-brand shadow-ds-sm"><Sparkles size={18} /></span>
        <div><p className="text-[15px] font-semibold text-ds-ink">Researching {customer}</p><p className="text-[13px] text-ds-muted">Usually one to three minutes. You can keep working; stay on this opportunity to see it land.</p></div>
      </div>
      <ol className="mt-5 space-y-2.5">
        {STEPS.map((label, index) => (
          <li key={label} className={`flex items-center gap-3 text-[13px] ${index <= step ? "text-ds-ink" : "text-ds-muted"}`}>
            {index < step ? <CheckCircle2 size={16} className="text-ds-green" /> : index === step ? <Loader2 size={16} className="ds-spin text-ds-brand" /> : <span className="h-4 w-4 rounded-full border border-ds-border-strong" />}
            {label}
          </li>
        ))}
      </ol>
    </div>
  );

  if (!dossier) return (
    <div className="rounded-xl border border-dashed border-ds-border-strong bg-white p-6 text-center">
      <span className="mx-auto grid h-12 w-12 place-items-center rounded-xl bg-ds-brand-soft text-ds-brand"><FileSearch size={22} /></span>
      <h3 className="mt-4 text-[16px] font-semibold text-ds-ink">Get a deep research dossier</h3>
      <p className="mx-auto mt-1.5 max-w-md text-[13px] leading-5 text-ds-muted">Claude searches the public web for {customer}: strategy, estate, recent developments, contract history and who decides. You get a recommendation, a win angle, risks and the questions to ask. Every claim links to its source.</p>
      {error && <p role="alert" className="mx-auto mt-4 max-w-md rounded-lg border border-ds-red-line bg-ds-red-soft px-3 py-2 text-[13px] text-ds-red">{error}</p>}
      <button className="ds-btn primary mt-5" onClick={() => void run()}><Sparkles size={16} /> Run deep research</button>
      <p className="mt-3 text-[12px] text-ds-muted">Public sources only. Uses your Anthropic API credit.</p>
    </div>
  );

  const stance = STANCE[dossier.recommendation.stance] || STANCE.qualify;
  return (
    <div className="ds-fade space-y-5">
      <div className="rounded-xl border border-ds-border bg-gradient-to-br from-white to-ds-brand-soft p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2"><Pill tone={stance.tone} dot>{stance.label}</Pill><span className="text-[12px] text-ds-muted">{stance.line}</span></div>
          <button className="ds-btn ghost sm" onClick={() => void run()} title="Run the research again"><RefreshCw size={14} /> Refresh</button>
        </div>
        <h3 className="mt-3 text-[18px] font-semibold leading-snug tracking-[-0.015em] text-ds-ink">{dossier.headline}</h3>
        <p className="mt-2 text-[14px] leading-6 text-ds-ink-2">{dossier.summary}</p>
        <p className="mt-3 border-t border-ds-border pt-3 text-[13px] leading-5 text-ds-ink-2"><strong className="font-semibold text-ds-ink">Why: </strong>{dossier.recommendation.rationale}</p>
        <p className="mt-3 text-[12px] text-ds-muted">Researched {formatDate(dossier.created_at)} · {dossier.sources.length} sources cited{dossier.sources_reviewed ? ` of ${dossier.sources_reviewed} reviewed` : ""} · decision support, not a verified record</p>
      </div>
      {error && <p role="alert" className="rounded-lg border border-ds-red-line bg-ds-red-soft px-3 py-2 text-[13px] text-ds-red">{error}</p>}

      <Block icon={<Target size={16} />} title="How to win it">
        <p className="text-[14px] leading-6 text-ds-ink-2">{dossier.win_strategy.angle}</p>
        {dossier.win_strategy.themes.length > 0 && <div className="mt-3"><p className="text-[12px] font-semibold text-ds-muted">Lead with</p><ul className="mt-1.5 flex flex-wrap gap-1.5">{dossier.win_strategy.themes.map((t) => <li key={t}><Pill tone="brand">{t}</Pill></li>)}</ul></div>}
        {dossier.win_strategy.proof_points.length > 0 && <div className="mt-3"><p className="text-[12px] font-semibold text-ds-muted">Proof points to prepare</p><Bullets items={dossier.win_strategy.proof_points} /></div>}
      </Block>

      <div className="grid gap-5 2xl:grid-cols-2">
        <Block icon={<Building2 size={16} />} title="The buyer">
          <p className="text-[13px] leading-[22px] text-ds-ink-2">{dossier.buyer.overview}</p>
          {dossier.buyer.estate && <p className="mt-2 text-[13px] leading-[22px] text-ds-ink-2"><strong className="font-semibold text-ds-ink">Estate: </strong>{dossier.buyer.estate}</p>}
          {dossier.buyer.priorities.length > 0 && <><p className="mt-3 text-[12px] font-semibold text-ds-muted">Stated priorities</p><Bullets items={dossier.buyer.priorities} /></>}
        </Block>
        <Block icon={<CalendarClock size={16} />} title="The contract">
          <dl className="space-y-2 text-[13px] leading-5">
            {([["Position", dossier.contract.position], ["Incumbent", dossier.contract.incumbent], ["Timeline", dossier.contract.timeline], ["Route", dossier.contract.route]] as const).map(([k, v]) => v && <div key={k}><dt className="text-[12px] font-semibold text-ds-muted">{k}</dt><dd className="text-ds-ink-2">{v}</dd></div>)}
          </dl>
        </Block>
      </div>

      {dossier.buyer.developments.length > 0 && <Block icon={<Compass size={16} />} title="Recent developments">
        <ol className="relative space-y-4 border-l border-ds-border pl-5">
          {dossier.buyer.developments.map((d, i) => (
            <li key={i} className="relative">
              <span className="absolute -left-[25px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-white bg-ds-brand ring-1 ring-ds-brand-line" />
              <p className="text-[12px] font-semibold text-ds-muted">{d.date}</p>
              <p className="text-[13px] font-medium leading-5 text-ds-ink">{d.development}</p>
              <p className="text-[13px] leading-5 text-ds-muted">{d.relevance} {d.source_url && <Cite url={d.source_url} />}</p>
            </li>
          ))}
        </ol>
      </Block>}

      {dossier.signals.length > 0 && <Block icon={<Lightbulb size={16} />} title="Signals for and against">
        <ul className="divide-y divide-ds-border">
          {dossier.signals.map((s, i) => (
            <li key={i} className="flex gap-3 py-2.5 first:pt-0 last:pb-0">
              <span className={`mt-0.5 grid h-6 w-6 flex-none place-items-center rounded-full ${s.direction === "supports" ? "bg-ds-green-soft text-ds-green" : s.direction === "against" ? "bg-ds-red-soft text-ds-red" : "bg-ds-subtle text-ds-muted"}`}>
                {s.direction === "supports" ? <ArrowUpRight size={14} /> : s.direction === "against" ? <ArrowDownRight size={14} /> : <Minus size={14} />}
              </span>
              <div className="min-w-0 text-[13px] leading-5 text-ds-ink-2">{s.signal} <span className="text-[12px] text-ds-muted">· {s.basis === "stated" ? "stated in source" : "inference"}</span> {s.source_url && <Cite url={s.source_url} />}</div>
            </li>
          ))}
        </ul>
      </Block>}

      <div className="grid gap-5 2xl:grid-cols-2">
        {dossier.decision_roles.length > 0 && <Block icon={<Users size={16} />} title="Who decides">
          <ul className="space-y-2.5">{dossier.decision_roles.map((r) => <li key={r.role}><p className="text-[13px] font-semibold text-ds-ink">{r.role}</p><p className="text-[13px] leading-5 text-ds-muted">{r.why}</p></li>)}</ul>
          <p className="mt-3 text-[12px] text-ds-muted">Roles only. Confirm names through the buyer's published structure or your own network.</p>
        </Block>}
        {dossier.risks.length > 0 && <Block icon={<ShieldAlert size={16} />} title="Risks and mitigations">
          <ul className="space-y-2.5">{dossier.risks.map((r) => <li key={r.risk}><p className="flex gap-2 text-[13px] font-semibold text-ds-ink"><AlertTriangle size={14} className="mt-0.5 flex-none text-ds-amber" />{r.risk}</p><p className="pl-6 text-[13px] leading-5 text-ds-muted">{r.mitigation}</p></li>)}</ul>
        </Block>}
      </div>

      <div className="grid gap-5 2xl:grid-cols-2">
        {dossier.questions.length > 0 && <Block icon={<CircleHelp size={16} />} title="Questions for the first conversation"><Bullets items={dossier.questions} numbered /></Block>}
        {dossier.next_steps.length > 0 && <Block icon={<ListChecks size={16} />} title="Next steps">
          <ul className="space-y-2">{dossier.next_steps.map((s) => <li key={s.step} className="flex items-start gap-3 text-[13px] leading-5"><span className="mt-0.5 h-4 w-4 flex-none rounded border border-ds-border-strong bg-white" /><span className="text-ds-ink-2">{s.step}{s.when && <span className="ml-1.5 text-ds-muted">· {s.when}</span>}</span></li>)}</ul>
        </Block>}
      </div>

      {dossier.unknowns.length > 0 && <div className="rounded-xl border border-ds-amber-line bg-ds-amber-soft p-4">
        <p className="text-[13px] font-semibold text-ds-amber">Still unknown</p>
        <ul className="mt-1.5 list-disc space-y-1 pl-5 text-[13px] leading-5 text-ds-ink-2">{dossier.unknowns.map((u) => <li key={u}>{u}</li>)}</ul>
      </div>}

      {dossier.sources.length > 0 && <Block icon={<FileSearch size={16} />} title={`Sources (${dossier.sources.length})`}>
        <div className="grid gap-2 2xl:grid-cols-2">{dossier.sources.map((s) => <SourceLink key={s.url} url={s.url} title={s.title} />)}</div>
      </Block>}
    </div>
  );
}

function Block({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-ds-border bg-white p-4">
      <h4 className="mb-2.5 flex items-center gap-2 text-[14px] font-semibold text-ds-ink"><span className="text-ds-muted">{icon}</span>{title}</h4>
      {children}
    </section>
  );
}

function Bullets({ items, numbered }: { items: string[]; numbered?: boolean }) {
  return (
    <ul className="mt-1.5 space-y-1.5">
      {items.map((item, i) => (
        <li key={item} className="flex gap-2.5 text-[13px] leading-5 text-ds-ink-2">
          {numbered ? <span className="grid h-5 w-5 flex-none place-items-center rounded-full bg-ds-subtle text-[11px] font-semibold text-ds-muted">{i + 1}</span> : <span className="mt-2 h-1 w-1 flex-none rounded-full bg-ds-faint" />}
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

function Cite({ url }: { url: string }) {
  const href = safeUrl(url);
  if (!href) return null;
  return <a href={href} target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 whitespace-nowrap text-[12px] font-medium text-ds-brand hover:underline">source<ArrowUpRight size={11} /></a>;
}
