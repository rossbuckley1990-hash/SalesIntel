"use client";
/** Who to call about one lead: the line to act on, how the route was found, and the roles that usually decide.
 * Every route is one a public source states, the organisation's own website shows, or the team saved. Never a guessed address.
 * A small firm's directors can also come from Companies House: named, never given a route. */
import { useState } from "react";
import { Globe, Landmark, Loader2 } from "lucide-react";
import { Pill } from "./ds";
import { hostOf, safeUrl } from "./radar-model";
import { si, type Call, type CompanyMatch, type Lead } from "./si-api";

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

/** For a saved lead: find the company on Companies House, by the number on record or one the rep chooses, for the
 * directors of a small firm. A name search only lists companies; the rep says which one it is. */
function FindCompany({ prospectId, organisation, number, ask, onRead }:
  { prospectId: number; organisation: string; number: string; ask: boolean; onRead: (lead: Lead) => void }) {
  const [query, setQuery] = useState(number && !ask ? "" : organisation);
  const [matches, setMatches] = useState<CompanyMatch[]>([]);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const send = async (json: { query?: string; company_number?: string }, which: string) => {
    setBusy(which); setError("");
    try {
      const got = await si<{ lead: Lead | null; candidates: CompanyMatch[] }>(`/prospects/${prospectId}/read-register`, { method: "POST", json });
      setMatches(got.candidates);
      if (got.lead) onRead(got.lead);
    } catch (e) { setError(e instanceof Error ? e.message : "Companies House could not be read."); }
    finally { setBusy(""); }
  };
  const typing = !number || ask;
  return (
    <div className="si-call-ch">
      <form className="si-call-read" onSubmit={(e) => { e.preventDefault(); void send(typing ? { query: query.trim() } : {}, "find"); }}>
        {typing && <label className="si-call-site"><span className="sr-only">Company name or number</span>
          <input className="ds-input sm" type="text" placeholder="Company name or Companies House number" value={query} onChange={(e) => setQuery(e.target.value)} /></label>}
        <button className="ds-btn ghost sm" type="submit" disabled={!!busy || (typing && !query.trim())}>
          {busy === "find" ? <Loader2 size={13} className="animate-spin" aria-hidden="true" /> : <Landmark size={13} aria-hidden="true" />}
          {typing ? " Find their directors on Companies House" : " Read their directors on Companies House"}</button>
      </form>
      {!!matches.length && <fieldset className="si-call-matches"><legend>Which company is it? Only you can confirm this.</legend>
        <ul>{matches.map((m) => <li key={m.company_number}>
          <span className="min-w-0"><span className="name">{m.name}</span> <span className="text-ds-muted">· {m.company_number}{m.town && ` · ${m.town}`}
            {m.status && m.status !== "active" && ` · ${m.status.replace(/-/g, " ")}`}{m.created && ` · since ${m.created.slice(0, 4)}`}</span></span>
          <button type="button" className="ds-btn ghost sm" disabled={!!busy} aria-label={`This one: ${m.name}, ${m.company_number}`}
            onClick={() => void send({ company_number: m.company_number }, m.company_number)}>
            {busy === m.company_number && <Loader2 size={13} className="animate-spin" aria-hidden="true" />} This one</button></li>)}</ul></fieldset>}
      {error && <p className="si-call-error" role="alert">{error}</p>}
    </div>
  );
}

/** `onChanged`: called after a reading is kept, so the page holding the lead loads it again and a redraw (another
 * layout, say) shows what was read. */
export function WhoToCall({ call: given, prospectId, website = "", organisation = "", companyNumber = "", onChanged }:
  { call: Call; prospectId?: number; website?: string; organisation?: string; companyNumber?: string; onChanged?: () => void }) {
  const [call, setCall] = useState(given);
  const [site, setSite] = useState(website);
  const [number, setNumber] = useState(companyNumber);
  // When the page loads the lead again, follow it: a copy drawn elsewhere (the phone layout) must not keep an old reading.
  const [held, setHeld] = useState({ given, website, companyNumber });
  if (held.given !== given || held.website !== website || held.companyNumber !== companyNumber) {
    setHeld({ given, website, companyNumber });
    setCall(given); setSite(website); setNumber(companyNumber);
  }
  const p = call.person;
  const reg = call.register;
  return (
    <section aria-label="Who to call" className="si-call">
      <p className="si-call-line">{call.line}</p>
      <p className="si-call-meta"><Pill tone={TONE[call.grade] || "neutral"}>{call.grade_label}</Pill>
        <span>{call.route ? <>{call.route.how}<Source url={call.route.source_url} label="source" /></> : call.grade_detail}</span></p>
      {p && <p className="si-call-meta">{p.fits ? "Named" : "Most senior person named"}: {p.name}{p.role && `, ${p.role}`}
        <Source url={p.source_url} label={p.from === "register" ? "Companies House" : undefined} /></p>}
      <p className="si-call-roles">Usually decides: {call.roles.join(" · ")}</p>
      {!!call.also.length && <p className="si-call-roles">Also named: {call.also.map((a) => `${a.name}${a.role ? `, ${a.role}` : ""}`).join("; ")}</p>}
      {!!call.more.length && <details className="si-call-more"><summary>Other ways in ({call.more.length})</summary>
        <ul>{call.more.map((m, i) => <li key={i}>{m.value} <span className="text-ds-muted">· {m.grade} · {m.how}</span><Source url={m.source_url} label="source" /></li>)}</ul></details>}
      {call.site && <p className="si-call-roles">{siteLine(call.site)}</p>}
      {reg && <p className="si-call-roles">{reg.note}</p>}
      {call.cautions.map((c) => <p key={c} className="si-call-caution">{c}</p>)}
      {prospectId !== undefined && call.grade !== "notice" && <>
        <ReadSite prospectId={prospectId} website={site}
          onRead={(lead) => { if (lead.brief.who.call) setCall(lead.brief.who.call); setSite(lead.website || site); onChanged?.(); }} />
        <FindCompany key={`${number}-${reg?.read_on || ""}-${reg?.mismatch || false}`} prospectId={prospectId} organisation={organisation} number={number}
          ask={!!reg?.mismatch} onRead={(lead) => { if (lead.brief.who.call) setCall(lead.brief.who.call); setNumber(lead.company_number || number); onChanged?.(); }} />
      </>}
    </section>
  );
}
