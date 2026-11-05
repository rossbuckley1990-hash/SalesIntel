"use client";
/**
 * Shadow Radar in Discover and on the account: an unadvertised opportunity, the evidence behind it, what is
 * verified, inferred and unknown, the rival explanations, and the actions that move it forward.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowUpRight, Briefcase, CheckCircle2, ChevronDown, CircleHelp, Eye, FileSearch, Lightbulb, MailPlus, Radar, ShieldAlert, Users, XCircle } from "lucide-react";
import { Pill } from "./ds";
import { safeUrl } from "./radar-model";
import { SERVICE_NAME, goto, si, type Lead } from "./si-api";
import { JobStatus, newKey, useJob, type JobT } from "./si-people";

const STATE_TONE: Record<string, "green" | "amber" | "blue" | "red" | "neutral" | "violet"> = { corroborated: "green", indicated: "violet", surfaced: "blue", challenged: "red", closed: "neutral" };
const ROLE: Record<string, { label: string; tone: "brand" | "green" | "red" | "blue" | "neutral"; dot: string }> = {
  anchor: { label: "Signal", tone: "brand", dot: "#c2410c" }, supports: { label: "Supports", tone: "green", dot: "#1d6b47" }, challenges: { label: "Against", tone: "red", dot: "#a8291c" },
  advertised: { label: "Now advertised", tone: "blue", dot: "#1e5a85" }, related: { label: "Related, may differ", tone: "neutral", dot: "#8e8b93" } };
const fmt = (d: string | null | undefined) => (d ? new Date(`${d.slice(0, 10)}T00:00:00`).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : "");
type Detail = { assessment: Lead["shadow"]; revisions: { as_of: string; state: string; recorded: string }[]; account_id: number | null;
  relationship: { kind: string; summary: string; outcome: string; occurred_at: string }[]; feedback: { decision: string; reason: string; at: string }[] };

export function ShadowCard({ lead, notify, onChanged }: { lead: Lead; notify: (m: string, e?: boolean) => void; onChanged: () => void }) {
  const a = lead.shadow!;
  const id = Number(lead.key.slice(3));
  const [detail, setDetail] = useState<Detail | null>(null);
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [dismissing, setDismissing] = useState(false);
  const [reason, setReason] = useState("");
  const key = useRef(newKey());
  useEffect(() => {
    si<Detail>(`/radar/hypotheses/${id}`).then(setDetail).catch(() => {});
    si<{ reasons: Record<string, string> }>("/radar/sensors").then((r) => setReasons(r.reasons)).catch(() => {});
  }, [id]);
  async function investigate() {
    try {
      const r = await si<{ account_id: number; job: JobT & { reused: boolean } }>(`/radar/hypotheses/${id}/investigate`, { method: "POST", json: {}, headers: { "Idempotency-Key": key.current } });
      key.current = newKey();
      notify(r.job.reused ? "Opening the investigation already saved for this account." : "Investigation started. It keeps running if you leave this page.");
      goto("clients", { account: r.account_id });
    } catch (e) { notify((e as Error).message, true); }
  }
  async function open(then: "clients" | "engage") {
    try {
      const r = await si<{ account_id: number }>(`/discover/${lead.key}/account`, { method: "POST", json: {} });
      goto(then, { account: r.account_id, source: lead.key });
    } catch (e) { notify((e as Error).message, true); }
  }
  async function feedback(decision: "relevant" | "not_relevant" | "disproved", why = "") {
    try {
      await si("/radar/feedback", { method: "POST", json: { lead_key: lead.key, decision, reason: why } });
      notify(decision === "relevant" ? "Marked relevant. It counts towards this sensor's record." : "Recorded and hidden for your workspace. The reason is used to evaluate the radar.");
      setDismissing(false); onChanged();
    } catch (e) { notify((e as Error).message, true); }
  }
  async function watch() {
    try { await si(`/discover/${lead.key}/status`, { method: "POST", json: { status: "watching" } }); notify("Watching."); onChanged(); } catch (e) { notify((e as Error).message, true); }
  }
  const timeline = a.timeline;
  return (
    <article className="p-5" aria-label={lead.organisation}>
      <div className="flex flex-wrap items-center gap-1.5">
        <Pill tone="violet"><Radar size={12} /> Shadow Radar</Pill>
        <Pill tone={STATE_TONE[a.state] || "neutral"}>{["corroborated", "surfaced"].includes(a.state) && <span className="si-live-dot" aria-hidden="true" />}{a.state_label}</Pill>
        <Pill tone="amber">Inferred, not advertised</Pill>
      </div>
      <h2 className="si-serif mt-3 text-[28px] leading-[1.08] text-ds-ink">{lead.organisation}</h2>
      {a.site && <p className="mt-0.5 text-[14px] text-ds-ink-2">{a.site}{a.postcode ? ` · ${a.postcode}` : ""}</p>}

      <section aria-label="Potential requirement" className="si-callout mt-4 p-4">
        <p className="si-eyebrow">{a.sensor_name}</p>
        <p className="mt-1.5 text-[15px] font-medium leading-6 text-ds-ink">{a.hypothesis}</p>
        <p className="mt-2 text-[13px] text-ds-ink-2"><strong>Why now:</strong> {timeline.find((e) => e.role === "anchor")?.statement}</p>
        {a.main_contractor && <p className="mt-1 text-[13px] text-ds-ink-2"><strong>Main contractor:</strong> {a.main_contractor} <span className="text-ds-muted">(published on the award)</span></p>}
      </section>

      {!!a.competing?.length && <section aria-label="Competing hypotheses" className="mt-3 rounded-xl border border-ds-border p-3">
        <p className="si-section-title text-ds-muted">Another reading of the same evidence</p>
        {a.competing.map((c) => <div key={c.key} className="mt-1.5"><p className="text-[14px] font-medium text-ds-ink">{c.sensor_name}: {c.hypothesis}</p>
          <p className="text-[12px] text-ds-muted">{c.state_label} · window {fmt(c.window[0])} to {fmt(c.window[1])}. First step: {c.first_action}</p></div>)}
        <p className="mt-1.5 text-[12px] text-ds-muted">Both can be true. The investigation tests the first; its findings bear on both.</p>
      </section>}

      <dl className="mt-3 grid gap-2.5 sm:grid-cols-2">
        <div className="rounded-lg bg-ds-canvas px-3 py-2.5"><dt className="text-[12px] text-ds-muted">Possible investigation window</dt>
          <dd className="text-[14px] font-semibold text-ds-ink">{fmt(a.window[0])} to {fmt(a.window[1])}</dd><dd className="text-[11px] text-ds-muted">A rule of thumb, not a prediction</dd></div>
        <div className="rounded-lg bg-ds-canvas px-3 py-2.5"><dt className="text-[12px] text-ds-muted">Evidence</dt>
          <dd className="text-[14px] font-semibold text-ds-ink">{a.independent_sources} independent source{a.independent_sources === 1 ? "" : "s"}</dd>
          <dd className="text-[11px] text-ds-muted">First published {fmt(a.first_published_on)}{a.first_seen ? `, first seen by SalesIntel ${fmt(a.first_seen)}` : ""}</dd></div>
      </dl>
      <div className="mt-3 flex flex-wrap gap-1.5" aria-label="Relevant services">{a.services.map((s) => <Pill key={s} tone="brand">{SERVICE_NAME[s] || s.replace(/_/g, " ")}</Pill>)}</div>
      {lead.brief?.fit && <p className="mt-2 text-[13px] text-ds-ink-2"><strong>Fit:</strong> {[...lead.brief.fit.matched, ...lead.brief.fit.gaps].join(" · ") || "Set your services, territory and sectors to see fit."}</p>}

      <section aria-label="Evidence timeline" className="mt-4">
        <h3 className="si-section-title text-ds-muted">Evidence timeline</h3>
        <ol className="si-timeline">{timeline.map((e, i) => { const href = safeUrl(e.source_url); return (
          <li key={i} className="text-[13px]" style={{ ["--dot" as string]: ROLE[e.role].dot }}><span className="flex flex-wrap items-center gap-1.5"><span className="font-semibold text-ds-ink">{fmt(e.published)}</span><Pill tone={ROLE[e.role].tone}>{ROLE[e.role].label}</Pill>
            <span className="text-ds-muted">{e.label}{e.basis === "derived" ? " (derived by SalesIntel)" : ""}</span></span>
            <span className="mt-0.5 block text-ds-ink-2">{e.statement}</span>
            {href && <a className="inline-flex items-center gap-0.5 text-[12px] font-medium text-ds-brand hover:underline" href={href} target="_blank" rel="noreferrer">Source <ArrowUpRight size={11} /></a>}</li>); })}</ol>
      </section>

      <div className="mt-4 grid gap-2.5 2xl:grid-cols-2">
        <section aria-label="What is verified" className="rounded-[9px] border border-ds-border bg-white p-3"><h3 className="si-section-title text-ds-green"><CheckCircle2 size={13} /> Verified (published)</h3>
          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-[13px] text-ds-ink-2">{a.verified.map((x) => <li key={x}>{x}</li>)}</ul></section>
        <section aria-label="What is inferred" className="rounded-[9px] border border-ds-border bg-white p-3"><h3 className="si-section-title text-ds-amber"><Lightbulb size={13} /> Inferred</h3>
          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-[13px] text-ds-ink-2">{a.inferred.map((x) => <li key={x}>{x}</li>)}</ul></section>
        <section aria-label="What is unknown" className="rounded-[9px] border border-ds-border bg-white p-3"><h3 className="si-section-title text-ds-muted"><CircleHelp size={13} /> Unknown</h3>
          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-[13px] text-ds-ink-2">{a.unknown.map((x) => <li key={x}>{x}</li>)}</ul></section>
        <section aria-label="Alternative explanations" className="rounded-[9px] border border-ds-border bg-white p-3"><h3 className="si-section-title text-ds-red"><ShieldAlert size={13} /> Other explanations</h3>
          <ul className="mt-1 space-y-1 text-[13px]">{a.alternatives.map((x) => <li key={x.explanation}><span className="text-ds-ink">{x.explanation}.</span> <span className="text-ds-muted">Check: {x.test}</span></li>)}</ul></section>
      </div>

      {!!detail?.relationship.length && <section aria-label="Relationship history" className="mt-4"><h3 className="si-section-title text-ds-muted">Your history with them</h3>
        <ul className="mt-1 space-y-0.5 text-[13px] text-ds-ink-2">{detail.relationship.map((r, i) => <li key={i}>{fmt(r.occurred_at)} · {r.kind}: {r.summary}</li>)}</ul></section>}

      <section aria-label="Best next action" className="mt-4 rounded-[10px] border border-ds-border bg-[#faf9f7] p-4">
        <p className="si-eyebrow">Best next action</p>
        <p className="mt-1 text-[15px] font-semibold leading-6 text-ds-ink">{a.first_action}</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <button className="ds-btn primary" onClick={() => void investigate()}><FileSearch size={15} /> Investigate</button>
          <button className="ds-btn" onClick={() => void open("clients")}><Users size={15} /> Find the right people</button>
          <button className="ds-btn" onClick={() => void open("engage")}><MailPlus size={15} /> Prepare outreach</button>
          <button className="ds-btn ghost" onClick={() => void open("clients")}><Briefcase size={15} /> Qualify</button>
          {lead.status !== "watching" && <button className="ds-btn ghost" onClick={() => void watch()}><Eye size={15} /> Watch</button>}
          <button className="ds-btn ghost" onClick={() => setDismissing((v) => !v)}><XCircle size={15} /> Not relevant</button>
        </div>
        {dismissing && <div className="mt-3 flex flex-wrap items-end gap-2" role="group" aria-label="Why it is not relevant">
          <label className="block"><span className="ds-label">Why?</span><select className="ds-select mt-1" aria-label="Reason" value={reason} onChange={(e) => setReason(e.target.value)}>
            <option value="">Choose a reason…</option>{Object.entries(reasons).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
          <button className="ds-btn sm" disabled={!reason} onClick={() => void feedback(reason === "evidence_wrong" ? "disproved" : "not_relevant", reason)}>Record and hide</button>
        </div>}
      </section>

      <details className="mt-4 text-[12px] text-ds-muted"><summary className="flex cursor-pointer items-center gap-1 font-semibold hover:text-ds-ink"><ChevronDown size={12} className="si-chevron" /> How SalesIntel inferred this</summary>
        <p className="mt-1">Sensor “{a.sensor_name}” ({a.rule_version}). Repeated notices about one project, and republished copies, count as one source. No probability is shown, because none has been validated.</p>
        {!!a.disconfirming.length && <p className="mt-1">It would be disproved by: {a.disconfirming.join("; ")}.</p>}
        {!!detail?.revisions.length && <p className="mt-1">Assessment history: {detail.revisions.map((r) => `${fmt(r.as_of)} ${r.state}`).join(" → ")}.</p>}
      </details>
    </article>
  );
}

type Finding = { question_id: string; section: string; text: string; effect: "supports" | "weakens" | "neutral"; source_url: string; source_date: string; quote: string };
type DossierT = { id: number; version: number; verdict: "strengthened" | "weakened" | "unresolved"; created_at: string; plan: { id: string; question: string; purpose: string }[];
  challenge: { answers: Record<string, { question: string; purpose: string; outcome: string; findings: number }>; weakened: number; supported: number };
  sections: { key: string; label: string; items: Finding[] }[]; rejected: { text: string; reason: string }[]; sources: number; cost_cents: number };
const VERDICT = { strengthened: { label: "Evidence supports it", tone: "green" as const }, weakened: { label: "Evidence against it", tone: "red" as const }, unresolved: { label: "Not settled", tone: "amber" as const } };
const OUTCOME_TONE: Record<string, "green" | "red" | "neutral"> = { supports: "green", weakens: "red", unanswered: "neutral" };

export function DossierPanel({ accountId, notify, onChanged }: { accountId: number; notify: (m: string, e?: boolean) => void; onChanged: () => void }) {
  const [data, setData] = useState<{ latest: DossierT | null; versions: { version: number; verdict: string }[]; job: JobT | null } | null>(null);
  const first = useRef(true);
  const changed = useRef(onChanged);
  useEffect(() => { changed.current = onChanged; }, [onChanged]);
  const load = useCallback(async () => {
    try {
      const next = await si<{ latest: DossierT | null; versions: { version: number; verdict: string }[]; job: JobT | null }>(`/radar/accounts/${accountId}/dossier`);
      setData(next);
      // The investigation may have finished between the account loading and this panel loading. If so the
      // account was read before the job saved its contacts, so refresh it once rather than wait for a poll that never comes.
      if (first.current && next.job && !["queued", "running"].includes(next.job.status)) changed.current();
      first.current = false;
    } catch { /* not every account has one */ }
  }, [accountId]);
  const done = useCallback(() => { void load(); onChanged(); }, [load, onChanged]);
  const [job] = useJob(data?.job || null, done);
  useEffect(() => { void load(); }, [load]);
  if (!data || (!data.latest && !data.job)) return null;
  const d = data.latest;
  return (
    <section className="ds-card p-4" aria-label="Investigation">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-[15px] font-semibold text-ds-ink"><FileSearch size={16} className="text-ds-brand" /> Investigation{d ? ` (version ${d.version})` : ""}</h2>
        {d && <Pill tone={VERDICT[d.verdict].tone}>{VERDICT[d.verdict].label}</Pill>}
      </div>
      {job && ["queued", "running"].includes(job.status) && <div className="mt-2"><JobStatus job={job} /></div>}
      {job?.result?.message && !["queued", "running"].includes(job.status) && <p className="mt-2 text-[13px] text-ds-ink-2">{job.result.message}</p>}
      {d && <>
        <ul className="mt-3 space-y-1.5" aria-label="Questions tested">{Object.entries(d.challenge.answers).map(([qid, x]) => (
          <li key={qid} className="flex items-start justify-between gap-2 text-[13px]"><span><span className={`mr-1 text-[11px] font-semibold uppercase ${x.purpose === "challenge" ? "text-ds-red" : "text-ds-muted"}`}>{x.purpose === "challenge" ? "Test" : "Find"}</span>{x.question}</span>
            <Pill tone={OUTCOME_TONE[x.outcome]}>{x.outcome === "unanswered" ? "Open" : x.outcome === "supports" ? "Supports" : "Against"}</Pill></li>))}</ul>
        {d.sections.map((s) => <div key={s.key} className="mt-3"><p className="ds-label">{s.label}</p>
          <ul className="mt-1 space-y-1.5">{s.items.map((f, i) => { const href = safeUrl(f.source_url); return <li key={i} className="text-[13px]"><span className="text-ds-ink">{f.text}</span>
            {f.effect !== "neutral" && <span className={`ml-1 text-[11px] font-semibold uppercase ${f.effect === "weakens" ? "text-ds-red" : "text-ds-green"}`}>{f.effect === "weakens" ? "against" : "supports"}</span>}
            <blockquote className="mt-0.5 border-l-2 border-ds-border pl-2 text-[12px] italic text-ds-ink-2">“{f.quote}”</blockquote>
            {href && <a className="inline-flex items-center gap-0.5 text-[12px] font-medium text-ds-brand hover:underline" href={href} target="_blank" rel="noreferrer">Source{f.source_date ? `, ${f.source_date}` : ""} <ArrowUpRight size={11} /></a>}</li>; })}</ul></div>)}
        {!!d.rejected.length && <details className="mt-3 text-[12px] text-ds-muted"><summary className="cursor-pointer font-semibold">{d.rejected.length} finding(s) rejected</summary>
          <ul className="mt-1 space-y-0.5">{d.rejected.map((x, i) => <li key={i}>{x.reason}</li>)}</ul></details>}
        <p className="mt-2 text-[12px] text-ds-muted">{d.sources} source page(s) read · {d.cost_cents ? `$${(d.cost_cents / 100).toFixed(2)}` : "no AI cost"} · kept on this account and carried into any deal.</p>
      </>}
    </section>
  );
}
