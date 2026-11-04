"use client";
import { useState } from "react";
import {
  AlertTriangle, ArrowLeft, BriefcaseBusiness, CalendarClock, Check, CircleSlash, Clock3, FileText, Lightbulb,
  Link2, ListChecks, Sparkles, Swords,
} from "lucide-react";
import { DeepResearch } from "./dossier";
import { Fact, Pill, SourceLink } from "./ds";
import {
  CATEGORY, DECISIONS, EVIDENCE_STATES, EXPLANATION_STATES, REVIEW_STATES, formatDate, relative, safeUrl, signalsOf,
  timingLabel, titleCase, urgencyTone, valueLine, type Item, type Signal,
} from "./radar-model";

type Tab = "overview" | "evidence" | "signals" | "research";

export function OpportunityDetail({ item, onPromote, onReview, onClose }: {
  item: Item; onPromote: (id: number) => void; onReview: (id: number, state: string) => void; onClose?: () => void;
}) {
  const [tab, setTab] = useState<Tab>("overview");
  const x = item.suggestion;
  const meta = CATEGORY[x.category] || { short: x.category_label, tone: "neutral" as const, help: "" };
  const signals = signalsOf(x);
  const when = relative(x.timing);
  const inPipeline = item.review_state === "investigate";
  const tabs: [Tab, string, number | null][] = [["overview", "Overview", null], ["evidence", "Evidence", x.evidence.length], ["signals", "Signals", signals.length], ["research", "Deep research", null]];

  return (
    <article className="flex h-full flex-col" aria-label={`${x.customer}: ${x.title}`}>
      <header className="border-b border-ds-border px-6 pb-0 pt-5">
        {onClose && <button className="ds-btn ghost sm -ml-2 mb-2" onClick={onClose}><ArrowLeft size={15} /> All opportunities</button>}
        <div className="flex flex-wrap items-center gap-1.5">
          <Pill tone={meta.tone} dot>{meta.short}</Pill>
          <Pill tone={x.priority.tier === 1 ? "brand" : "neutral"}>Tier {x.priority.tier}</Pill>
          <Pill>{x.nation}</Pill>
          {item.review_state !== "unreviewed" && <Pill tone={inPipeline ? "green" : "neutral"}>{REVIEW_STATES[item.review_state] || item.review_state}</Pill>}
        </div>
        <p className="mt-3 text-[13px] font-semibold text-ds-muted">{titleCase(x.customer)}</p>
        <h2 className="mt-0.5 text-[20px] font-semibold leading-[1.3] tracking-[-0.02em] text-ds-ink">{x.title}</h2>
        <div className="mt-4 flex flex-wrap gap-2">
          <button className="ds-btn primary" onClick={() => onPromote(item.id)} disabled={inPipeline}>{inPipeline ? <><Check size={16} /> In your pipeline</> : <><BriefcaseBusiness size={16} /> Add to pipeline</>}</button>
          <button className="ds-btn" onClick={() => setTab("research")}><Sparkles size={16} className="text-ds-brand" /> Deep research</button>
          <button className="ds-btn ghost" onClick={() => onReview(item.id, "defer")} title="Hide for now"><Clock3 size={16} /> Later</button>
          <button className="ds-btn ghost" onClick={() => onReview(item.id, "dismiss")} title="Not relevant"><CircleSlash size={16} /> Dismiss</button>
        </div>
        <div className="ds-underline-tabs mt-5" role="tablist" aria-label="Opportunity detail">
          {tabs.map(([id, label, count]) => (
            <button key={id} role="tab" aria-selected={tab === id} onClick={() => setTab(id)}>
              {id === "research" && <Sparkles size={14} />}{label}{count !== null && count > 0 && <span className="rounded-full bg-ds-subtle px-1.5 text-[11px] text-ds-muted">{count}</span>}
            </button>
          ))}
        </div>
      </header>

      <div className="ds-scroll flex-1 overflow-y-auto px-6 py-5">
        <div hidden={tab !== "overview"} className="space-y-6">
          <div className="rounded-xl border border-ds-brand-line bg-ds-brand-soft p-4">
            <p className="flex items-center gap-2 text-[13px] font-semibold text-ds-brand"><Lightbulb size={15} /> Why this is worth your time</p>
            <p className="mt-1.5 text-[14px] leading-6 text-ds-ink-2">{x.brief.why_it_matters}</p>
            {x.priority.reasons.length > 0 && <ul className="mt-2.5 flex flex-wrap gap-1.5">{x.priority.reasons.map((r) => <li key={r}><span className="inline-block rounded-md bg-white px-2 py-0.5 text-[12px] text-ds-ink-2 ring-1 ring-ds-brand-line">{r}</span></li>)}</ul>}
          </div>

          <dl className="grid gap-2.5 sm:grid-cols-2">
            <Fact label={timingLabel(x.timing_basis, x.end_estimated)} hint={x.timing ? x.timing_basis : undefined}>
              <span className="flex flex-wrap items-center gap-2">{x.timing ? formatDate(x.timing) : "Not published"}{when && <Pill tone={urgencyTone(x.timing)}>{when}</Pill>}</span>
            </Fact>
            <Fact label="Value" hint={[x.value.basis, x.value.scope_note].filter(Boolean).join(" ")}>{valueLine(x.value)}</Fact>
            <Fact label="Current supplier">{x.supplier || "Not published"}</Fact>
            <Fact label="Procurement route">{x.brief.procurement_route || "Not published"}</Fact>
            <Fact label="Contract term">{x.brief.contract_lifecycle || "Not published"}</Fact>
            <Fact label="Fit with Mitie" hint={meta.help}>{x.fit === "core" ? "Core service" : x.fit === "framework" ? "Framework" : x.fit === "bundled" ? "Bundled in wider scope" : "To be confirmed"}</Fact>
          </dl>

          <section>
            <h3 className="mb-2.5 flex items-center gap-2 text-[14px] font-semibold text-ds-ink"><ListChecks size={16} className="text-ds-muted" /> Recommended next steps</h3>
            <ol className="space-y-2">
              {x.next_actions.map((a, i) => (
                <li key={a} className="flex gap-3 rounded-lg border border-ds-border bg-white px-3.5 py-2.5 text-[14px] leading-[22px] text-ds-ink-2">
                  <span className={`grid h-[22px] w-[22px] flex-none place-items-center rounded-full text-[12px] font-semibold ${i === 0 ? "bg-ds-brand text-white" : "bg-ds-subtle text-ds-muted"}`}>{i + 1}</span>{a}
                </li>
              ))}
            </ol>
          </section>

          {x.counter_evidence.length > 0 && <section className="rounded-xl border border-ds-amber-line bg-ds-amber-soft p-4">
            <h3 className="flex items-center gap-2 text-[13px] font-semibold text-ds-amber"><AlertTriangle size={15} /> Check before you invest time</h3>
            <ul className="mt-1.5 list-disc space-y-1 pl-5 text-[13px] leading-5 text-ds-ink-2">{x.counter_evidence.map((c) => <li key={c}>{c}</li>)}</ul>
          </section>}

          {x.brief.missing_information.length > 0 && <section>
            <h3 className="mb-2 text-[14px] font-semibold text-ds-ink">Gaps to close</h3>
            <ul className="space-y-1.5">{x.brief.missing_information.map((m) => <li key={m} className="flex gap-2.5 text-[13px] leading-5 text-ds-ink-2"><span className="mt-[7px] h-1.5 w-1.5 flex-none rounded-full bg-ds-faint" />{m}</li>)}</ul>
          </section>}

          {!!x.plausible_competitors?.length && <section>
            <h3 className="mb-2 flex items-center gap-2 text-[14px] font-semibold text-ds-ink"><Swords size={16} className="text-ds-muted" /> Likely competitors</h3>
            <div className="flex flex-wrap gap-1.5">{x.plausible_competitors.map((c) => <Pill key={c}>{c}</Pill>)}</div>
            <p className="mt-1.5 text-[12px] text-ds-muted">Based on published work of this kind. Their participation is not confirmed.</p>
          </section>}

          {signals.length > 0 && <button className="flex w-full items-center justify-between rounded-xl border border-ds-violet-line bg-ds-violet-soft px-4 py-3 text-left" onClick={() => setTab("signals")}>
            <span className="text-[13px] text-ds-violet"><strong className="font-semibold">{signals.length} inferred signal{signals.length > 1 ? "s" : ""}</strong> · {signals[0].label}</span>
            <span className="text-[12px] font-semibold text-ds-violet">Review →</span>
          </button>}
        </div>

        <div hidden={tab !== "evidence"} className="space-y-6">
          <section>
            <h3 className="mb-2.5 flex items-center gap-2 text-[14px] font-semibold text-ds-ink"><FileText size={16} className="text-ds-muted" /> Published records</h3>
            <div className="grid gap-2">{x.evidence.map((e) => <SourceLink key={e.source_revision_id} url={e.source_url} title={`${e.source} notice ${e.record_key}`} meta={e.published_at ? `Published ${formatDate(e.published_at)}` : undefined} />)}</div>
            {!x.evidence.length && <p className="text-[13px] text-ds-muted">No published record is attached.</p>}
          </section>
          <dl className="grid gap-2.5 sm:grid-cols-2">
            <Fact label="Record linking" hint={`${x.link.records} record${x.link.records === 1 ? "" : "s"} from ${x.link.sources.join(" and ") || "one source"}`}><span className="flex items-center gap-2"><Link2 size={14} className="text-ds-muted" />{x.link.confidence} match</span></Fact>
            <Fact label="Date basis">{x.timing_basis}</Fact>
            {x.extension && <Fact label="Extension wording">{x.extension}</Fact>}
            {x.latest_end && <Fact label="Latest possible end">{formatDate(x.latest_end)}</Fact>}
          </dl>
          <p className="flex items-start gap-2 rounded-lg bg-ds-canvas px-3.5 py-3 text-[12px] leading-[18px] text-ds-muted"><CalendarClock size={14} className="mt-0.5 flex-none" /> Every line here comes from a published notice. It is a lead to check, not a confirmed requirement. Nothing in MiSi contacts anyone.</p>
        </div>

        <div hidden={tab !== "signals"} className="space-y-4">
          {signals.length ? signals.map((s) => <SignalCard key={s.hypothesis_id} signal={s} />) : <p className="rounded-lg bg-ds-canvas px-4 py-6 text-center text-[13px] text-ds-muted">No inferred signals for this opportunity. The published notices are the evidence.</p>}
        </div>

        <div hidden={tab !== "research"}><DeepResearch key={item.id} id={item.id} customer={titleCase(x.customer)} /></div>
      </div>
    </article>
  );
}

function SignalCard({ signal }: { signal: Signal }) {
  const decision = DECISIONS[signal.decision] || { label: signal.decision, tone: "neutral" as const };
  return (
    <section className="rounded-xl border border-ds-border bg-white p-4">
      <div className="flex flex-wrap items-center gap-1.5"><Pill tone={decision.tone} dot>{decision.label}</Pill><Pill>{EVIDENCE_STATES[signal.evidence_state] || signal.evidence_state}</Pill></div>
      <h3 className="mt-2.5 text-[15px] font-semibold text-ds-ink">{signal.label}</h3>
      <p className="mt-1 text-[13px] leading-5 text-ds-muted">{signal.decision_reasons.join(" ")} {signal.link}</p>
      <p className="mt-4 text-[12px] font-semibold text-ds-muted">What was observed</p>
      <ol className="mt-2 space-y-2 border-l border-ds-border pl-4">
        {signal.supporting.map((o) => (
          <li key={o.fingerprint} className="text-[13px] leading-5 text-ds-ink-2">
            <span className="font-semibold text-ds-ink">{formatDate(o.occurred_on)}</span> · {safeUrl(o.source_url) ? <a href={safeUrl(o.source_url)} target="_blank" rel="noreferrer" className="hover:text-ds-brand hover:underline">{o.statement}</a> : o.statement}
          </li>
        ))}
      </ol>
      {signal.contradicting.length > 0 && <><p className="mt-4 text-[12px] font-semibold text-ds-red">Evidence against</p><ul className="mt-1.5 space-y-1 text-[13px] leading-5 text-ds-ink-2">{signal.contradicting.map((o) => <li key={o.fingerprint}>{formatDate(o.occurred_on)} · {o.statement}</li>)}</ul></>}
      {signal.explanations.length > 0 && <>
        <p className="mt-4 text-[12px] font-semibold text-ds-muted">Possible explanations</p>
        <ul className="mt-2 space-y-2">{signal.explanations.map((e) => {
          const state = EXPLANATION_STATES[e.status] || { label: e.status, tone: "neutral" as const };
          return <li key={e.explanation} className="rounded-lg bg-ds-canvas px-3 py-2"><div className="flex flex-wrap items-center justify-between gap-2"><span className="text-[13px] font-medium text-ds-ink">{e.label}</span><Pill tone={state.tone}>{state.label}</Pill></div><p className="mt-0.5 text-[12px] leading-[18px] text-ds-muted">{e.test}</p></li>;
        })}</ul>
      </>}
      <p className="mt-3 text-[12px] leading-[18px] text-ds-muted">{signal.caution} Sources: {signal.independent_sources.join(", ")}.</p>
    </section>
  );
}
