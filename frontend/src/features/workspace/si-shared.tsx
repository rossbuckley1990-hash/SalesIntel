"use client";
import { useEffect, useState, type ReactNode, useRef } from "react";
import { Calendar, CheckCircle2, FileText, Mail, MapPin, MessageSquare, Phone, StickyNote, Users } from "lucide-react";
import { Pill } from "./ds";
import { safeUrl } from "./radar-model";
import { OUTCOMES, dayLabel, inDays, si, when, type ActivityT, type ContactT, type TaskT } from "./si-api";
import { newKey } from "./si-people";

/** Re-render when the URL changes, so workspaces can link to each other. */
export function useUrl() {
  const [, setTick] = useState(0);
  useEffect(() => {
    const update = () => setTick((x) => x + 1);
    window.addEventListener("popstate", update);
    return () => window.removeEventListener("popstate", update);
  }, []);
}

export function PageHeader({ eyebrow, title, children, actions }: { eyebrow?: string; title: string; children?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {eyebrow && <p className="si-eyebrow mb-1.5">{eyebrow}</p>}
        <h1 className="mt-0.5 text-[26px] font-semibold leading-tight tracking-[-0.025em] text-ds-ink">{title}</h1>
        {children && <p className="mt-1 max-w-3xl text-[14px] leading-6 text-ds-muted">{children}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </header>
  );
}

export function Panel({ title, action, children, className = "" }: { title?: ReactNode; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`ds-card ${className}`}>
      {title && <div className="flex items-center justify-between gap-3 border-b border-ds-border px-4 py-3"><h2 className="text-[14px] font-semibold text-ds-ink">{title}</h2>{action}</div>}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function Basis({ basis }: { basis: string }) {
  const map: Record<string, [string, "green" | "amber" | "neutral" | "brand"]> = {
    published: ["Published", "green"], stated: ["Stated in source", "green"], inferred: ["Inferred", "amber"], user_entered: ["Entered by you", "brand"],
    verified: ["Verified", "green"], unverified: ["Not yet verified", "neutral"], unknown: ["Unknown", "neutral"], user_estimate: ["Your estimate", "brand"],
    published_derived: ["From published value", "green"], surveyed: ["Surveyed", "green"], customer_stated: ["Customer stated", "brand"], estimate: ["Estimate", "amber"],
  };
  const [label, tone] = map[basis] || [basis, "neutral"];
  return <Pill tone={tone}>{label}</Pill>;
}

const KIND_ICON: Record<string, typeof Phone> = { call: Phone, email: Mail, meeting: Users, site_visit: MapPin, note: StickyNote };

export function Timeline({ items, contacts = [] }: { items: ActivityT[]; contacts?: ContactT[] }) {
  if (!items.length) return <p className="text-[13px] text-ds-muted">Nothing recorded yet. Log your first call, email or meeting.</p>;
  const who = (id: number | null) => contacts.find((c) => c.id === id);
  return (
    <ol className="relative space-y-4 border-l border-ds-border pl-5">
      {items.map((a) => {
        const Icon = KIND_ICON[a.kind] || MessageSquare;
        const person = who(a.contact_id);
        return (
          <li key={a.id} className="relative">
            <span className="absolute -left-[31px] grid h-5 w-5 place-items-center rounded-full border border-ds-border bg-white text-ds-muted"><Icon size={11} /></span>
            <p className="text-[12px] text-ds-muted">{when(a.occurred_at)} · {a.kind.replace("_", " ")}{person ? ` · ${person.name || person.role || person.label}` : ""}{a.outcome ? ` · ${OUTCOMES.find((o) => o[0] === a.outcome)?.[1] || a.outcome}` : ""}</p>
            <p className="mt-0.5 text-[14px] leading-5 text-ds-ink">{a.summary}</p>
            {a.requirements && <p className="mt-1 text-[13px] leading-5 text-ds-ink-2"><strong className="font-semibold">Requirement:</strong> {a.requirements}</p>}
            {a.objections && <p className="mt-0.5 text-[13px] leading-5 text-ds-ink-2"><strong className="font-semibold">Objection:</strong> {a.objections}</p>}
            {a.commitments && <p className="mt-0.5 text-[13px] leading-5 text-ds-ink-2"><strong className="font-semibold">We committed:</strong> {a.commitments}</p>}
          </li>
        );
      })}
    </ol>
  );
}

export function TaskRow({ t, onDone, account }: { t: TaskT; onDone?: () => void; account?: boolean }) {
  const overdue = t.status === "open" && t.due_on < inDays(0);
  return (
    <li className="flex items-center gap-3 py-2">
      {t.status === "open" && onDone ? <button aria-label={`Mark done: ${t.title}`} onClick={onDone} className="grid h-5 w-5 flex-none place-items-center rounded-full border border-ds-border-strong text-transparent hover:border-ds-green hover:text-ds-green"><CheckCircle2 size={14} /></button>
        : <CheckCircle2 size={18} className={t.status === "done" ? "text-ds-green" : "text-ds-faint"} />}
      <span className={`min-w-0 flex-1 text-[14px] ${t.status === "done" ? "text-ds-muted line-through" : "text-ds-ink"}`}>{t.title}{account && t.account ? <span className="text-ds-muted"> · {t.account}</span> : null}</span>
      <span className={`flex-none text-[12px] font-semibold ${overdue ? "text-ds-red" : "text-ds-muted"}`}><Calendar size={12} className="mr-1 inline" />{dayLabel(t.due_on)}</span>
    </li>
  );
}

export function ContactCard({ c, onStatus }: { c: ContactT; onStatus?: (status: ContactT["status"]) => void }) {
  const href = safeUrl(c.source_url);
  return (
    <li className="rounded-xl border border-ds-border bg-white p-3.5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[14px] font-semibold text-ds-ink">{c.name || c.role || c.label || "Contact route"}</p>
          {c.name && c.role && <p className="text-[13px] text-ds-ink-2">{c.role}</p>}
          <p className="mt-1 flex flex-wrap gap-x-3 text-[13px]">
            {c.email && <a className="font-medium text-ds-brand hover:underline" href={`mailto:${c.email}`}>{c.email}</a>}
            {c.phone && <a className="font-medium text-ds-brand hover:underline" href={`tel:${c.phone.replace(/[^\d+]/g, "")}`}>{c.phone}</a>}
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5"><Basis basis={c.basis} />{c.status === "do_not_contact" ? <Pill tone="red">Do not contact</Pill> : <Basis basis={c.status} />}</div>
      </div>
      {c.source_quote && <p className="mt-2 text-[12px] italic leading-[18px] text-ds-muted">“{c.source_quote}” {href && <a className="not-italic font-medium text-ds-brand hover:underline" href={href} target="_blank" rel="noreferrer">source</a>}</p>}
      {onStatus && <div className="mt-2 flex gap-2">
        {c.status !== "verified" && c.status !== "do_not_contact" && <button className="ds-btn sm" onClick={() => onStatus("verified")}>Mark verified</button>}
        {c.status !== "do_not_contact" ? <button className="ds-btn ghost sm" onClick={() => onStatus("do_not_contact")}>Do not contact</button>
          : <button className="ds-btn ghost sm" onClick={() => onStatus("unverified")}>Allow contact</button>}
      </div>}
    </li>
  );
}

/** Log what happened and, in the same step, when to follow up. */
export function ActivityForm({ accountId, dealId, contacts = [], onSaved, notify, compact }: {
  accountId: number; dealId?: number | null; contacts?: ContactT[]; onSaved: () => void; notify: (m: string, e?: boolean) => void; compact?: boolean;
}) {
  const [kind, setKind] = useState("call");
  const [summary, setSummary] = useState("");
  const [outcome, setOutcome] = useState("");
  const [contactId, setContactId] = useState("");
  const [requirements, setRequirements] = useState("");
  const [objections, setObjections] = useState("");
  const [commitments, setCommitments] = useState("");
  const [follow, setFollow] = useState(inDays(3));
  const [followTitle, setFollowTitle] = useState("");
  const [more, setMore] = useState(!compact);
  const [busy, setBusy] = useState(false);
  const submission = useRef(newKey());
  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!summary.trim()) return;
    setBusy(true);
    try {
      await si(`/accounts/${accountId}/activities`, { method: "POST", headers: { "Idempotency-Key": submission.current }, json: {
        kind, summary, outcome, requirements, objections, commitments, deal_id: dealId || null, contact_id: contactId ? Number(contactId) : null,
        follow_up: follow ? { due_on: follow, title: followTitle || null } : null } });
      submission.current = newKey();
      setSummary(""); setRequirements(""); setObjections(""); setCommitments(""); setOutcome(""); setFollowTitle("");
      notify(follow ? `Logged. Follow-up set for ${dayLabel(follow).toLowerCase()}.` : "Logged.");
      onSaved();
    } catch (err) { notify((err as Error).message, true); } finally { setBusy(false); }
  }
  const usable = contacts.filter((c) => c.status !== "do_not_contact");
  return (
    <form onSubmit={save} className="space-y-3" aria-label="Log an interaction">
      <div className="ds-tabs w-fit" role="group" aria-label="Interaction type">
        {[["call", "Call"], ["email", "Email"], ["meeting", "Meeting"], ["site_visit", "Site visit"], ["note", "Note"]].map(([k, l]) => <button type="button" key={k} aria-pressed={kind === k} onClick={() => setKind(k)}>{l}</button>)}
      </div>
      <label className="block"><span className="ds-label">What happened</span>
        <textarea aria-label="What happened" className="mt-1 w-full rounded-lg border border-ds-border-strong p-2.5 text-[14px]" rows={compact ? 2 : 3} value={summary} onChange={(e) => setSummary(e.target.value)} placeholder="e.g. Spoke to the facilities manager about the annual service" required /></label>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block"><span className="ds-label">Outcome</span>
          <select className="ds-select mt-1 w-full" value={outcome} onChange={(e) => setOutcome(e.target.value)}>{OUTCOMES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
        <label className="block"><span className="ds-label">With</span>
          <select className="ds-select mt-1 w-full" value={contactId} onChange={(e) => setContactId(e.target.value)}><option value="">Not recorded</option>{usable.map((c) => <option key={c.id} value={c.id}>{c.name || c.role || c.label || c.email || c.phone}</option>)}</select></label>
      </div>
      {!more ? <button type="button" className="text-[12px] font-semibold text-ds-brand hover:underline" onClick={() => setMore(true)}>+ Requirements, objections, commitments</button> : <div className="grid gap-3 sm:grid-cols-3">
        <label className="block"><span className="ds-label">Requirement heard</span><textarea className="mt-1 w-full rounded-lg border border-ds-border-strong p-2 text-[13px]" rows={2} aria-label="Requirement heard" value={requirements} onChange={(e) => setRequirements(e.target.value)} /></label>
        <label className="block"><span className="ds-label">Objection</span><textarea className="mt-1 w-full rounded-lg border border-ds-border-strong p-2 text-[13px]" rows={2} aria-label="Objection" value={objections} onChange={(e) => setObjections(e.target.value)} /></label>
        <label className="block"><span className="ds-label">We committed to</span><textarea className="mt-1 w-full rounded-lg border border-ds-border-strong p-2 text-[13px]" rows={2} aria-label="We committed to" value={commitments} onChange={(e) => setCommitments(e.target.value)} /></label>
      </div>}
      <div className="flex flex-wrap items-end gap-3 rounded-lg bg-ds-canvas p-3">
        <label className="block"><span className="ds-label">Follow up on</span><input type="date" className="ds-select mt-1 block" value={follow} onChange={(e) => setFollow(e.target.value)} /></label>
        <div className="flex gap-1.5 pb-1">{[["Tomorrow", 1], ["3 days", 3], ["1 week", 7], ["2 weeks", 14]].map(([l, n]) => <button type="button" key={l} className={`rounded-full border px-2.5 py-1 text-[12px] font-medium ${follow === inDays(n as number) ? "border-ds-brand bg-ds-brand-soft text-ds-brand" : "border-ds-border bg-white text-ds-ink-2"}`} onClick={() => setFollow(inDays(n as number))}>{l}</button>)}
          <button type="button" className={`rounded-full border px-2.5 py-1 text-[12px] font-medium ${!follow ? "border-ds-brand bg-ds-brand-soft text-ds-brand" : "border-ds-border bg-white text-ds-ink-2"}`} onClick={() => setFollow("")}>None</button></div>
        {follow && <label className="block min-w-[180px] flex-1"><span className="ds-label">Follow-up</span><input className="mt-1 block h-10 w-full rounded-lg border border-ds-border-strong px-2.5 text-[14px]" value={followTitle} onChange={(e) => setFollowTitle(e.target.value)} placeholder="Follow up" /></label>}
      </div>
      <button className="ds-btn primary" disabled={busy || !summary.trim()}><FileText size={15} /> Save to timeline</button>
    </form>
  );
}
