"use client";
/** Who to call about one lead: the line to act on, how the route was found, and the roles that usually decide.
 * Every route is one a public source states, the organisation's own website shows, or the team saved. Never a guessed address. */
import { useState } from "react";
import { Globe, Loader2 } from "lucide-react";
import { Pill } from "./ds";
import { hostOf, safeUrl } from "./radar-model";
import { si, type Call, type Lead } from "./si-api";

const TONE: Record<string, "green" | "amber" | "neutral"> = {
  direct: "green", department: "green", main_line: "amber", general: "amber", form: "amber", unattributed: "amber", none: "neutral", notice: "neutral",
};

function day(iso: string) {
  const d = new Date(`${iso.slice(0, 10)}T12:00:00Z`);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
}

function Source({ url, label }: { url: string; label?: string }) {
  const href = safeUrl(url);
  return href ? <> · <a href={href} target="_blank" rel="noreferrer">{label || hostOf(url)}</a></> : null;
}

function siteLine(site: NonNullable<Call["site"]>) {
  if (site.stopped) return site.stopped;
  const where = hostOf(safeUrl(site.website) || `https://${site.website}`) || site.website;
  return `SalesIntel read ${site.pages} page${site.pages === 1 ? "" : "s"} of ${where} on ${day(site.read_on)}: ` +
    (site.found ? `${site.found} published contact detail${site.found === 1 ? "" : "s"}.` : "no published email address or phone number.");
}

/** For a saved lead: read the organisation's own website, from the address on record or one given here. */
function ReadSite({ prospectId, website, onRead }: { prospectId: number; website: string; onRead: (lead: Lead) => void }) {
  const [address, setAddress] = useState(website);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const read = async () => {
    setBusy(true); setError("");
    try { onRead(await si<Lead>(`/prospects/${prospectId}/read-site`, { method: "POST", json: { website: address.trim() || null } })); }
    catch (e) { setError(e instanceof Error ? e.message : "The website could not be read."); }
    finally { setBusy(false); }
  };
  return (
    <form className="si-call-read" onSubmit={(e) => { e.preventDefault(); void read(); }}>
      {!website && <label className="si-call-site"><span className="sr-only">Their website</span>
        <input className="ds-input sm" type="text" inputMode="url" placeholder="Their website, e.g. www.example.co.uk" value={address} onChange={(e) => setAddress(e.target.value)} /></label>}
      <button className="ds-btn ghost sm" type="submit" disabled={busy || !address.trim()}>
        {busy ? <Loader2 size={13} className="animate-spin" aria-hidden="true" /> : <Globe size={13} aria-hidden="true" />} Read their website for contact details</button>
      {error && <p className="si-call-error" role="alert">{error}</p>}
    </form>
  );
}

export function WhoToCall({ call: given, prospectId, website = "" }: { call: Call; prospectId?: number; website?: string }) {
  const [call, setCall] = useState(given);
  const [site, setSite] = useState(website);
  const p = call.person;
  return (
    <section aria-label="Who to call" className="si-call">
      <p className="si-call-line">{call.line}</p>
      <p className="si-call-meta"><Pill tone={TONE[call.grade] || "neutral"}>{call.grade_label}</Pill>
        <span>{call.route ? <>{call.route.how}<Source url={call.route.source_url} label="source" /></> : call.grade_detail}</span></p>
      {p && <p className="si-call-meta">{p.fits ? "Named" : "Most senior person named"}: {p.name}{p.role && `, ${p.role}`}<Source url={p.source_url} /></p>}
      <p className="si-call-roles">Usually decides: {call.roles.join(" · ")}</p>
      {!!call.also.length && <p className="si-call-roles">Also named: {call.also.map((a) => `${a.name}${a.role ? `, ${a.role}` : ""}`).join("; ")}</p>}
      {!!call.more.length && <details className="si-call-more"><summary>Other ways in ({call.more.length})</summary>
        <ul>{call.more.map((m, i) => <li key={i}>{m.value} <span className="text-ds-muted">· {m.grade} · {m.how}</span><Source url={m.source_url} label="source" /></li>)}</ul></details>}
      {call.site && <p className="si-call-roles">{siteLine(call.site)}</p>}
      {call.cautions.map((c) => <p key={c} className="si-call-caution">{c}</p>)}
      {prospectId !== undefined && call.grade !== "notice" && <ReadSite prospectId={prospectId} website={site}
        onRead={(lead) => { if (lead.brief.who.call) setCall(lead.brief.who.call); setSite(lead.website || site); }} />}
    </section>
  );
}
