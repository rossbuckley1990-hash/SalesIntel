"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, ArrowUpRight, Building2, Check, CheckCircle2, Copy, FilePenLine, Mail, Send, ShieldCheck, Wand2 } from "lucide-react";
import { EmptyState, Pill } from "./ds";
import { safeUrl } from "./radar-model";
import { dayLabel, goto, inDays, param, si, type AccountT, type DraftT, type Evidence, type Prefs, type TodayT } from "./si-api";
import { ActivityForm, PageHeader, Panel, useUrl } from "./si-shared";
import type { SharedProps } from "./types";

export function SiEngage({ notify }: SharedProps) {
  useUrl();
  const accountId = Number(param("account"));
  const [drafts, setDrafts] = useState<DraftT[]>([]);
  const [today, setToday] = useState<TodayT | null>(null);
  const loadSide = useCallback(() => {
    si<{ items: DraftT[] }>("/drafts").then((d) => setDrafts(d.items)).catch(() => {});
    si<TodayT>("/today").then(setToday).catch(() => {});
  }, []);
  useEffect(() => { loadSide(); }, [loadSide, accountId]);
  const due = today?.queue.filter((x) => x.kind === "follow_up") || [];
  return (
    <div className="ds-root space-y-5">
      <PageHeader title="Engage">Prepare introductions from evidence, record what you did, and set the next follow-up in the same step. SalesIntel never sends anything for you.</PageHeader>
      <div className="grid items-start gap-5 xl:grid-cols-[300px_minmax(0,1fr)]">
        <aside className="space-y-4" aria-label="Engagement queue">
          <Panel title={`Drafts (${drafts.length})`}>
            {!drafts.length ? <p className="text-[13px] text-ds-muted">No drafts in progress.</p> : <ul className="space-y-2">{drafts.map((d) => <li key={d.id}>
              <button className={`w-full rounded-lg px-2 py-1.5 text-left hover:bg-ds-hover ${accountId === d.account_id ? "bg-ds-brand-soft" : ""}`} onClick={() => goto("engage", { account: d.account_id, draft: d.id })}>
                <span className="block truncate text-[13px] font-semibold text-ds-ink">{d.account}</span>
                <span className="flex items-center gap-1.5 text-[12px] text-ds-muted"><Pill tone={d.status === "approved" ? "green" : "neutral"}>{d.status === "approved" ? "Ready to send" : "Draft"}</Pill></span></button></li>)}</ul>}
          </Panel>
          <YourDetails notify={notify} />
          <Panel title={`Follow-ups due (${due.length})`}>
            {!due.length ? <p className="text-[13px] text-ds-muted">Nothing due.</p> : <ul className="space-y-2">{due.map((t) => <li key={t.task_id}>
              <button className={`w-full rounded-lg px-2 py-1.5 text-left hover:bg-ds-hover ${accountId === t.account_id ? "bg-ds-brand-soft" : ""}`} onClick={() => goto("engage", { account: t.account_id })}>
                <span className="block truncate text-[13px] font-semibold text-ds-ink">{t.title}</span><span className="text-[12px] text-ds-muted">{t.account} · {dayLabel(t.due_on)}</span></button></li>)}</ul>}
          </Panel>
        </aside>
        {accountId > 0 ? <Composer key={accountId} accountId={accountId} notify={notify} onChange={loadSide} />
          : <div className="ds-card"><EmptyState icon={<FilePenLine size={20} />} title="Choose who to engage" action={<button className="ds-btn primary" onClick={() => goto("clients")}>Open Accounts</button>}>Pick a draft or follow-up on the left, or open an account and choose Prepare introduction.</EmptyState></div>}
      </div>
    </div>
  );
}

function Composer({ accountId, notify, onChange }: { accountId: number; notify: SharedProps["notify"]; onChange: () => void }) {
  const [a, setA] = useState<AccountT | null>(null);
  const [contactId, setContactId] = useState<string>("");
  const [source, setSource] = useState<string>(param("source") || "");
  const [draftId, setDraftId] = useState<number | null>(Number(param("draft")) || null);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [gaps, setGaps] = useState<string[]>([]);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [status, setStatus] = useState<DraftT["status"] | "new">("new");
  const [confirmSent, setConfirmSent] = useState(false);
  const [follow, setFollow] = useState(inDays(5));
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const account = await si<AccountT>(`/accounts/${accountId}`);
    setA(account);
    // Reopen the draft asked for; otherwise only a draft that can still be used.
    const draft = account.drafts.find((d) => d.id === draftId) || (!draftId ? account.drafts.find((d) => d.status === "draft" || d.status === "approved") : undefined);
    if (draft) {
      setDraftId(draft.id); setSubject(draft.subject); setBody(draft.body); setGaps(draft.gaps); setEvidence(draft.evidence); setStatus(draft.status);
      setContactId(draft.contact_id ? String(draft.contact_id) : "");
    }
    return { account, draft };
  }, [accountId, draftId]);
  const started = useRef(false);
  useEffect(() => {
    load().then(({ account, draft }) => {
      // Arriving to engage someone: choose the best contact and draft straight away.
      if (started.current || draft) return;
      started.current = true;
      const first = account.contacts.find((c) => c.status !== "do_not_contact" && (c.name || c.email)) || account.contacts.find((c) => c.status !== "do_not_contact");
      if (first) setContactId(String(first.id));
      void prepare(first ? String(first.id) : "");
    }).catch((e) => notify(e.message, true));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load, notify]);

  async function prepare(chosen = contactId) {
    setBusy(true);
    try {
      const intro = await si<{ subject: string; body: string; gaps: string[]; evidence: Evidence[] }>(`/accounts/${accountId}/introduction`, { method: "POST", json: { contact_id: chosen ? Number(chosen) : null, source_key: source || null } });
      setSubject(intro.subject); setBody(intro.body); setGaps(intro.gaps); setEvidence(intro.evidence); setStatus(draftId ? "draft" : "new");
    } catch (e) { notify((e as Error).message, true); } finally { setBusy(false); }
  }
  async function save() {
    setBusy(true);
    try {
      const saved = draftId
        ? await si<DraftT>(`/drafts/${draftId}`, { method: "PATCH", json: { subject, body, contact_id: contactId ? Number(contactId) : null } })
        : await si<DraftT>(`/accounts/${accountId}/drafts`, { method: "POST", json: { subject, body, contact_id: contactId ? Number(contactId) : null, evidence, gaps } });
      setDraftId(saved.id); setStatus(saved.status); notify("Draft saved."); onChange();
      return saved.id;
    } catch (e) { notify((e as Error).message, true); return null; } finally { setBusy(false); }
  }
  async function approve() {
    const id = await save();
    if (!id) return;
    try { const d = await si<DraftT>(`/drafts/${id}/approve`, { method: "POST" }); setStatus(d.status); notify("Approved. Send it from your own email, then log it here."); onChange(); }
    catch (e) { notify((e as Error).message, true); }
  }
  async function logSent() {
    if (!draftId) return;
    try {
      await si(`/drafts/${draftId}/log`, { method: "POST", json: { sent_externally: confirmSent, follow_up: follow ? { due_on: follow, title: `Follow up on introduction to ${a?.name}` } : null } });
      notify(follow ? `Logged as sent. Follow-up set for ${dayLabel(follow).toLowerCase()}.` : "Logged as sent.");
      setStatus("logged"); setDraftId(null); setConfirmSent(false); onChange(); await load();
    } catch (e) { notify((e as Error).message, true); }
  }
  if (!a) return <div className="ds-skeleton h-96 rounded-xl" />;
  const contacts = a.contacts.filter((c) => c.status !== "do_not_contact");
  const contact = contacts.find((c) => String(c.id) === contactId);
  const placeholders = /\[(name|your name|your company)\]/.test(body);
  const mailto = contact?.email ? `mailto:${contact.email}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}` : null;

  return (
    <div className="min-w-0 space-y-5">
      <section className="ds-card p-5" aria-label="Introduction">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div><p className="text-[12px] font-semibold uppercase tracking-wide text-ds-muted">Introduction to</p>
            <button className="mt-0.5 flex items-center gap-1.5 text-[20px] font-semibold text-ds-ink hover:text-ds-brand" onClick={() => goto("clients", { account: a.id })}><Building2 size={18} />{a.name}</button></div>
          {status !== "new" && <Pill tone={status === "approved" ? "green" : status === "logged" ? "brand" : status === "suppressed" ? "red" : "neutral"}>{status === "approved" ? "Approved, ready to send" : status === "logged" ? "Logged as sent" : status === "suppressed" ? "Suspended: recipient opted out" : "Draft"}</Pill>}
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <label className="block"><span className="ds-label">To</span><select className="ds-select mt-1 w-full" value={contactId} onChange={(e) => setContactId(e.target.value)}>
            <option value="">No contact chosen</option>{contacts.map((c) => <option key={c.id} value={c.id}>{c.name || c.role || c.label || c.email || c.phone}{c.email ? ` · ${c.email}` : ""}</option>)}</select></label>
          <label className="block"><span className="ds-label">Reason for contact</span><select className="ds-select mt-1 w-full" value={source} onChange={(e) => setSource(e.target.value)}>
            <option value="">Strongest evidence</option>{a.sources.map((s) => <option key={s.key} value={s.key}>{s.why_now.slice(0, 80)}</option>)}</select></label>
        </div>
        {!contacts.length && <p className="mt-2 text-[12px] text-ds-muted">No contact on record. <button className="font-semibold text-ds-brand hover:underline" onClick={() => goto("clients", { account: a.id })}>Add one on the account</button> or address it to a role.</p>}
        <button className="ds-btn mt-3" onClick={() => void prepare()} disabled={busy}><Wand2 size={15} /> {body ? "Rebuild from evidence" : "Prepare introduction"}</button>

        {body && <div className="mt-4 space-y-3">
          <label className="block"><span className="ds-label">Subject</span><input aria-label="Subject" className="mt-1 block h-10 w-full rounded-lg border border-ds-border-strong px-3 text-[14px]" value={subject} onChange={(e) => setSubject(e.target.value)} disabled={status === "logged"} /></label>
          <label className="block"><span className="ds-label">Message</span><textarea aria-label="Message" className="mt-1 block w-full rounded-lg border border-ds-border-strong p-3 font-[inherit] text-[14px] leading-6" rows={12} value={body} onChange={(e) => { setBody(e.target.value); if (status === "approved") setStatus("draft"); }} disabled={status === "logged"} /></label>
          {!!gaps.length && <div className="rounded-lg border border-ds-amber-line bg-ds-amber-soft p-3"><p className="flex items-center gap-1.5 text-[13px] font-semibold text-ds-amber"><AlertTriangle size={14} /> Check before sending</p>
            <ul className="mt-1 list-disc space-y-0.5 pl-5 text-[13px] text-ds-ink-2">{gaps.map((g) => <li key={g}>{g}</li>)}</ul></div>}
          {!!evidence.length && <div><p className="ds-label">Based on</p><ul className="mt-1 space-y-1">{evidence.map((e, i) => { const href = safeUrl(e.url); return <li key={i} className="text-[13px]">{href ? <a className="inline-flex items-center gap-1 font-medium text-ds-brand hover:underline" href={href} target="_blank" rel="noreferrer">{e.label}<ArrowUpRight size={12} /></a> : e.label}</li>; })}</ul></div>}
          <div className="flex flex-wrap gap-2">
            <button className="ds-btn" onClick={() => void save()} disabled={busy || status === "logged"}>Save draft</button>
            <button className="ds-btn primary" onClick={() => void approve()} disabled={busy || placeholders || status === "logged" || status === "approved" || status === "suppressed"} title={placeholders ? "Replace the [placeholders] first" : ""}><Check size={15} /> Approve</button>
            <button className="ds-btn ghost" onClick={() => { void navigator.clipboard?.writeText(`${subject}\n\n${body}`); notify("Copied."); }}><Copy size={15} /> Copy</button>
            {mailto && status === "approved" && <a className="ds-btn ghost" href={mailto}><Mail size={15} /> Open in my email</a>}
          </div>
          {placeholders && <p className="text-[12px] text-ds-muted">Replace the text in [brackets] before approving.</p>}
          {status === "approved" && <div className="rounded-xl border border-ds-green-line bg-ds-green-soft p-4">
            <p className="flex items-center gap-1.5 text-[14px] font-semibold text-ds-green"><Send size={15} /> Sent it from your own email?</p>
            <label className="mt-2 flex items-center gap-2 text-[13px] text-ds-ink"><input type="checkbox" checked={confirmSent} onChange={(e) => setConfirmSent(e.target.checked)} /> I sent this message myself</label>
            <div className="mt-2 flex flex-wrap items-end gap-2"><label><span className="ds-label">Follow up on</span><input type="date" className="ds-select mt-1 block" value={follow} onChange={(e) => setFollow(e.target.value)} /></label>
              <button className="ds-btn primary" disabled={!confirmSent} onClick={() => void logSent()}><CheckCircle2 size={15} /> Log as sent</button></div>
          </div>}
        </div>}
        <p className="mt-4 flex items-start gap-1.5 text-[12px] text-ds-muted"><ShieldCheck size={13} className="mt-0.5 flex-none" /> Drafts use only recorded evidence. Business contacts only; respect opt-outs (UK GDPR, PECR).</p>
      </section>
      <Panel title="Log a call, meeting or note"><ActivityForm accountId={a.id} contacts={a.contacts} notify={notify} onSaved={() => { onChange(); void load(); }} /></Panel>
    </div>
  );
}

function YourDetails({ notify }: { notify: SharedProps["notify"] }) {
  const [p, setP] = useState<Prefs | null>(null);
  useEffect(() => { si<Prefs>("/preferences").then(setP).catch(() => {}); }, []);
  if (!p) return null;
  return (
    <Panel title="Your details">
      <form className="space-y-2" onSubmit={async (e) => { e.preventDefault(); try { setP(await si<Prefs>("/preferences", { method: "PUT", json: { sender_name: p.sender_name, company_name: p.company_name } })); notify("Saved. New introductions will use these."); } catch (err) { notify((err as Error).message, true); } }}>
        <label className="block"><span className="ds-label">Your name</span><input className="mt-1 block h-9 w-full rounded-lg border border-ds-border-strong px-2.5 text-[13px]" value={p.sender_name} onChange={(e) => setP({ ...p, sender_name: e.target.value })} /></label>
        <label className="block"><span className="ds-label">Your company</span><input className="mt-1 block h-9 w-full rounded-lg border border-ds-border-strong px-2.5 text-[13px]" value={p.company_name} onChange={(e) => setP({ ...p, company_name: e.target.value })} /></label>
        <button className="ds-btn sm">Save</button>
      </form>
    </Panel>
  );
}
