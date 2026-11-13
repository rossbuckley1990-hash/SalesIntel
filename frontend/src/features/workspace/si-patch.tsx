"use client";
import { useCallback, useEffect, useState } from "react";
import { ArrowRight, ArrowUpRight, ClipboardCopy, Printer, SlidersHorizontal, UserPlus } from "lucide-react";
import { Pill } from "./ds";
import { safeUrl } from "./radar-model";
import { SERVICES, VERDICTS, goto, setRepName, si, type VerdictSummary, type VerdictT, type VerdictValue } from "./si-api";

/** The patch brief: five leads for one rep's patch, from records already held. The first thing a rep sees, and the thing the
 * owner sends. Chosen by the rule shown at the foot, never by a score; each lead carries its dated evidence chain and takes a
 * one-tap verdict. Nothing here costs anything or sends anything. */
type ChainLink = { date: string; text: string; url: string; label: "Published" | "Inferred" };
type Card = {
  key: string; organisation: string; kind: string; kind_label: string; chosen: string; chosen_because: string; headline: string; why_now: string; chain: ChainLink[];
  against: number; next: { action: string; label: string; url: string }; region: string; place: string; worth: string; sources: number; account_id: number | null;
  verdict: VerdictT | null;
};
type Rep = { name: string; regions: string[]; services: string[]; sectors: string[]; targets: string[] };
export type PatchT = {
  rep: Rep; reps: Rep[]; active: string; leads: Card[]; counts: { in_patch: number; held: number; target: number; two_records: number; closing: number; ending: number };
  calls: { key: string; organisation: string; why_now: string; account_id: number | null }[];
  rule: string[]; said: VerdictSummary; as_of: string; text: string; options: { regions: { name: string; leads: number }[]; sectors: string[] };
};
type Notify = (m: string, e?: boolean) => void;

const day = (iso: string) => {
  if (/^\d{4}-\d\d-\d\d/.test(iso)) return new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }).format(new Date(`${iso.slice(0, 10)}T00:00:00Z`));
  if (/^\d{4}-\d\d$/.test(iso)) return new Intl.DateTimeFormat("en-GB", { month: "short", year: "numeric", timeZone: "UTC" }).format(new Date(`${iso}-01T00:00:00Z`));
  return iso;
};
const toggle = (list: string[], value: string) => (list.includes(value) ? list.filter((x) => x !== value) : [...list, value]);

function Chips({ label, options, chosen, onToggle }: { label: string; options: [string, string][]; chosen: string[]; onToggle: (value: string) => void }) {
  return (
    <fieldset className="lo-chips">
      <legend>{label}</legend>
      <div>{options.map(([value, text]) => <button key={value} type="button" aria-pressed={chosen.includes(value)} onClick={() => onToggle(value)}>{text}</button>)}</div>
    </fieldset>
  );
}

function RepForm({ patch, draft, setDraft, onSave, onCancel, onRemove, busy }: { patch: PatchT; draft: Rep; setDraft: (change: (r: Rep) => Rep) => void; onSave: () => void;
  onCancel: () => void; onRemove: (() => void) | null; busy: boolean }) {
  // Each tap is applied to the latest draft, so two quick taps never undo each other.
  const flip = (field: "regions" | "services" | "sectors") => (value: string) => setDraft((r) => ({ ...r, [field]: toggle(r[field], value) }));
  return (
    <form className="lo-repform" aria-label="Patch" onSubmit={(e) => { e.preventDefault(); onSave(); }}>
      <label className="lo-field"><span>Whose patch is this?</span>
        <input className="ds-input !pl-3" value={draft.name} maxLength={60} onChange={(e) => { const name = e.target.value; setDraft((r) => ({ ...r, name })); }} /></label>
      <Chips label="Patch: where they sell" options={patch.options.regions.map((r) => [r.name, `${r.name} · ${r.leads}`])} chosen={draft.regions} onToggle={flip("regions")} />
      <Chips label="Disciplines" options={SERVICES} chosen={draft.services} onToggle={flip("services")} />
      <Chips label="Sectors" options={patch.options.sectors.map((s) => [s, s])} chosen={draft.sectors} onToggle={flip("sectors")} />
      <label className="lo-field"><span>Target accounts, one per line (optional)</span>
        <textarea className="ds-input !pl-3" rows={2} value={draft.targets.join("\n")} onChange={(e) => { const targets = e.target.value.split("\n"); setDraft((r) => ({ ...r, targets })); }} /></label>
      <p className="lo-note">Nothing chosen means no limit. The number beside each region is how many leads are held there today.</p>
      <div className="lo-repform-actions">
        <button className="ds-btn primary sm" disabled={busy || !draft.name.trim()}>Save and show the five</button>
        <button type="button" className="ds-btn ghost sm" onClick={onCancel}>Cancel</button>
        {onRemove && <button type="button" className="ds-btn ghost sm" onClick={onRemove}>Remove this rep</button>}
      </div>
    </form>
  );
}

function LeadCard({ card, n, of, busy, onJudge }: { card: Card; n: number; of: number; busy: boolean; onJudge: (c: Card, v: VerdictValue) => void }) {
  const open = () => goto("find", { lead: card.key });
  const meta = [card.kind_label, card.place, card.worth].filter(Boolean).join(" · ");
  return (
    <li><article className="lo-pcard" aria-label={card.organisation}>
      <p className="lo-pcard-top"><span className="lo-ptag">{card.chosen_because}</span><span className="lo-pn">{n} of {of}</span></p>
      <h3><button onClick={open}>{card.organisation}</button></h3>
      <p className="lo-pmeta">{meta}</p>
      <p className="lo-pwhy"><strong>Why now: </strong>{card.why_now}</p>
      <ol className="lo-chain" aria-label={`Evidence for ${card.organisation}`}>
        {card.chain.map((l, i) => { const href = safeUrl(l.url); return (
          <li key={i}><span className="d">{l.date ? day(l.date) : "So"}</span>
            <span className="t">{href ? <a href={href} target="_blank" rel="noreferrer">{l.text}<ArrowUpRight size={12} aria-hidden="true" /><span className="sr-only"> (opens the source in a new tab)</span></a> : l.text}</span>
            <Pill tone={l.label === "Published" ? "green" : "amber"}>{l.label}</Pill></li>); })}
      </ol>
      {card.against > 0 && <p className="lo-note">{card.against} record{card.against === 1 ? " points" : "s point"} the other way. Read the brief before you call.</p>}
      <div className="lo-pcard-foot">
        <button className="ds-btn sm" onClick={open}>Next: {card.next.label} <ArrowRight size={13} aria-hidden="true" /></button>
        <div className="lo-verdict-row" role="group" aria-label={`Verdict on ${card.organisation}`}>
          {VERDICTS.map(([id, label]) => <button key={id} type="button" className={id === "wrong" ? "no" : ""} aria-pressed={card.verdict?.value === id} disabled={busy} onClick={() => onJudge(card, id)}>{label}</button>)}
        </div>
      </div>
    </article></li>
  );
}

export function PatchBrief({ notify, onChanged }: { notify: Notify; onChanged?: () => void }) {
  const [patch, setPatch] = useState<PatchT | null>(null);
  const [error, setError] = useState("");
  const [draft, setDraft] = useState<Rep | null>(null);
  const [fresh, setFresh] = useState(false); // the form is for a new rep, not the one on screen
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState("");

  const show = useCallback((p: PatchT) => { setRepName(p.rep.name); setPatch(p); setError(""); }, []);
  const load = useCallback(async () => { try { show(await si<PatchT>("/patch")); } catch (e) { setError((e as Error).message); } }, [show]);
  useEffect(() => { void load(); }, [load]);

  async function act(fn: () => Promise<PatchT>, done?: string) {
    setBusy(true);
    try { show(await fn()); if (done) notify(done); } catch (e) { notify((e as Error).message, true); } finally { setBusy(false); }
  }
  async function judge(card: Card, verdict: VerdictValue | "cleared", key = card.key) {
    setBusy(true);
    try {
      await si(`/brief/${key}/verdict`, { method: "POST", json: { verdict, rep: patch?.rep.name || "" } });
      notify(verdict === "cleared" ? "Verdict taken back." : verdict === "wrong" ? "Marked wrong. It is hidden from your lists." : "Verdict recorded. The next lead has moved up.");
      await load(); onChanged?.();
    } catch (e) { notify((e as Error).message, true); } finally { setBusy(false); }
  }
  async function copy() {
    if (!patch) return;
    try { await navigator.clipboard.writeText(patch.text); notify("Copied. Paste it into an email: SalesIntel sends nothing."); setCopied(""); }
    catch { setCopied(patch.text); } // no clipboard here: show the text to select by hand
  }

  if (error) return <p role="alert" className="rounded-lg border border-ds-red-line bg-ds-red-soft px-3 py-2 text-[13px] text-ds-red">{error}</p>;
  if (!patch) return <div className="ds-skeleton h-64" aria-label="Loading the patch brief" />;
  const rep = patch.rep;
  const where = rep.regions.length ? rep.regions.join(", ") : "all of the UK";
  const blank: Rep = { name: patch.reps.length ? "" : "My patch", regions: [], services: [], sectors: [], targets: [] };
  const asOf = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "long", timeZone: "UTC" }).format(new Date(`${patch.as_of}T00:00:00Z`));
  const judged = patch.said.recent.filter((r) => r.value);

  return (
    <section className="lo-patch" aria-label="Patch brief">
      <div className="lo-patch-head">
        <div className="min-w-0">
          <h2>{rep.name ? `Patch brief: ${rep.name}` : "This week from the public record"}</h2>
          <p>{patch.leads.length} lead{patch.leads.length === 1 ? "" : "s"} from records already held · {where} · as of {asOf}</p>
        </div>
        <div className="lo-patch-tools">
          {patch.reps.length > 1 && <select className="ds-select !h-9" aria-label="Rep" value={patch.active} disabled={busy}
            onChange={(e) => void act(() => si<PatchT>("/patch/active", { method: "POST", json: { name: e.target.value } }))}>{patch.reps.map((r) => <option key={r.name} value={r.name}>{r.name}</option>)}</select>}
          <button className="ds-btn sm" aria-expanded={!!draft && !fresh} onClick={() => { setFresh(false); setDraft(draft && !fresh ? null : rep.name ? { ...rep } : blank); }}>
            <SlidersHorizontal size={14} aria-hidden="true" /> {rep.name ? "Edit patch" : "Set up your patch"}</button>
          {!!patch.reps.length && <button className="ds-btn ghost sm" aria-expanded={!!draft && fresh} onClick={() => { setFresh(true); setDraft(draft && fresh ? null : { ...blank, name: "" }); }}><UserPlus size={14} aria-hidden="true" /> Add a rep</button>}
          <button className="ds-btn ghost sm" onClick={() => void copy()} disabled={!patch.leads.length}><ClipboardCopy size={14} aria-hidden="true" /> Copy to send</button>
          <button className="ds-btn ghost sm" onClick={() => window.print()} disabled={!patch.leads.length}><Printer size={14} aria-hidden="true" /> Print</button>
        </div>
      </div>

      {draft && <RepForm patch={patch} draft={draft} setDraft={(change) => setDraft((d) => (d ? change(d) : d))} busy={busy} onCancel={() => setDraft(null)}
        onRemove={!fresh && rep.name ? () => { if (window.confirm(`Remove ${rep.name}? Their verdicts stay on record.`)) { setDraft(null); void act(() => si<PatchT>(`/patch/reps/${encodeURIComponent(rep.name)}`, { method: "DELETE" }), "Rep removed."); } } : null}
        onSave={() => { const saved = { ...draft, name: draft.name.trim(), targets: draft.targets.map((t) => t.trim()).filter(Boolean) }; setDraft(null);
          void act(() => si<PatchT>("/patch/reps", { method: "PUT", json: saved }), "Patch saved."); }} />}

      {copied && <label className="lo-field"><span>Select this text and copy it. SalesIntel sends nothing.</span>
        <textarea className="ds-input si-mono" rows={10} readOnly value={copied} onFocus={(e) => e.currentTarget.select()} /></label>}

      {!!patch.calls.length && <div className="lo-calls" role="group" aria-label="Worth a call">
        <h3>Worth a call ({patch.calls.length})</h3>
        <ul>{patch.calls.map((c) => <li key={c.key}><button onClick={() => goto("find", { lead: c.key })}><strong>{c.organisation}</strong><span>{c.why_now}</span></button></li>)}</ul>
      </div>}

      {!patch.leads.length ? <p className="lo-patch-empty">{patch.counts.held ? "You have judged every lead held for this patch. New ones appear here as the public record changes."
        : "No lead held today states this patch, these disciplines and these sectors. Widen the patch, or look at everything in Discover."}{" "}
        <button className="lo-link inline" onClick={() => goto("find")}>Open Discover</button></p>
        : <ol className="lo-pcards">{patch.leads.map((c, i) => <LeadCard key={c.key} card={c} n={i + 1} of={patch.leads.length} busy={busy} onJudge={(card, v) => void judge(card, v)} />)}</ol>}

      <div className="lo-patch-foot">
        {patch.said.judged > 0 && <p className="lo-patch-said"><strong>{patch.said.headline}.</strong> {patch.said.knew_already} knew already · {patch.said.wrong} wrong.</p>}
        {!!judged.length && <details className="lo-patch-more"><summary>Judged so far ({patch.said.judged})</summary>
          <ul>{judged.map((r) => <li key={r.key}><button className="lo-link inline" onClick={() => goto("find", { lead: r.key })}>{r.organisation || r.key}</button><span>{r.label}</span>
            <button className="lo-link inline" disabled={busy} onClick={() => void judge(patch.leads[0], "cleared", r.key)}>Take back</button></li>)}</ul></details>}
        <details className="lo-patch-more"><summary>How these {patch.leads.length || "five"} were chosen</summary>
          <ol>{patch.rule.map((r) => <li key={r}>{r}</li>)}</ol>
          <p>No score or probability is used. {patch.counts.in_patch} lead{patch.counts.in_patch === 1 ? " is" : "s are"} in this patch and not yet judged: {patch.counts.two_records} on two or more sources,
            {" "}{patch.counts.closing} with a deadline ahead, {patch.counts.ending} ending within twelve months.</p></details>
        <button className="lo-clock-all" onClick={() => goto("find", rep.regions.length === 1 ? { region: rep.regions[0] } : {})}>
          {rep.regions.length === 1 ? `Everything held in ${rep.regions[0]}` : "Everything in Discover"} <ArrowRight size={13} aria-hidden="true" /></button>
      </div>
    </section>
  );
}
