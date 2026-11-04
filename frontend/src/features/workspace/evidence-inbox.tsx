"use client";
import "./research-tool-accessibility.css";

import { useEffect, useState, type FormEvent } from "react";
import { getApiBaseUrl } from "@/lib/api";
import { safeSource } from "./api";
import { Button, Empty, SectionHeading } from "./ui";

type Observation = {
  id: number;
  organisation_id: string;
  organisation_name: string;
  site: string;
  category: string;
  observed_statement: string;
  source_url: string | null;
  source_title: string;
  source_reference: string;
  published_at: string | null;
  observed_at: string | null;
  retrieved_at: string;
};
type Account = { organisation_id: string; organisation_name: string; observation_count: number };
type AccountsPage = { items: Account[]; total: number };
type Dossier = { organisation_id: string; organisation_name: string; observations: Observation[]; total: number };
type ImportResult = { imported: number; duplicates: number };
type FeedResult = { imported: number; duplicates: number; scanned: number; matched: number; pages: number; updated_from: string; updated_to: string; next_cursor: string | null; warnings: string[] };
type RuleHypothesis = { title: string; explanation: string; observation_ids: number[]; question: string };
type RuleHypotheses = {
  organisation_id: string;
  total_observations: number;
  analysed_observations: number;
  observations: Observation[];
  sites: { site: string; hypotheses: RuleHypothesis[] }[];
  limitations: string[];
};
type AiHypothesis = { title: string; explanation: string; supporting_observation_ids: number[]; counter_observation_ids: number[]; unknowns: string[]; question: string };
type AiHypotheses = { organisation_id: string; site: string; observations: Observation[]; hypotheses: AiHypothesis[]; limitations: string[] };

const PAGE_SIZE = 25;
const categories = [
  ["service_issue", "Reported service issue"],
  ["customer_feedback", "Customer feedback"],
  ["compliance", "Compliance"],
  ["maintenance", "Maintenance"],
  ["supplier", "Supplier"],
  ["estate_change", "Estate change"],
  ["other", "Other"],
] as const;
const categoryLabel = (category: string) => categories.find(([value]) => value === category)?.[1] ?? category;

async function evidenceRequest<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}/api/evidence-observations${path}`, {
    cache: "no-store",
    ...(body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    const detail = data?.detail;
    throw new Error(typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map((item: { msg: string }) => item.msg).join(" · ") : `Evidence request failed (${response.status}).`);
  }
  return response.json() as Promise<T>;
}

export function EvidenceInbox() {
  const [accounts, setAccounts] = useState<AccountsPage | null>(null);
  const [accountOffset, setAccountOffset] = useState(0);
  const [dossier, setDossier] = useState<Dossier | null>(null);
  const [observationOffset, setObservationOffset] = useState(0);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [showBatch, setShowBatch] = useState(false);
  const [feedResult, setFeedResult] = useState<FeedResult | null>(null);
  const [batch, setBatch] = useState("");
  const [organisationId, setOrganisationId] = useState("");
  const [organisationName, setOrganisationName] = useState("");
  const [site, setSite] = useState("");
  const [category, setCategory] = useState("maintenance");
  const [statement, setStatement] = useState("");
  const [sourceTitle, setSourceTitle] = useState("");
  const [sourceReference, setSourceReference] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [publishedAt, setPublishedAt] = useState("");
  const [observedAt, setObservedAt] = useState("");

  async function loadAccounts(offset: number) {
    try {
      const result = await evidenceRequest<AccountsPage>(`/accounts?limit=${PAGE_SIZE}&offset=${offset}`);
      setAccounts(result);
      setAccountOffset(offset);
      setError("");
    } catch (e) { setError((e as Error).message); }
  }
  async function loadDossier(id: string, offset = 0) {
    try {
      setError("");
      const result = await evidenceRequest<Dossier>(`/accounts/${encodeURIComponent(id)}?limit=${PAGE_SIZE}&offset=${offset}`);
      setDossier(result);
      setObservationOffset(offset);
    } catch (e) { setError((e as Error).message); }
  }
  useEffect(() => { void loadAccounts(0); }, []);

  async function save(observations: unknown[]) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await evidenceRequest<ImportResult>("/import", { observations });
      setMessage(`${result.imported} observation${result.imported === 1 ? "" : "s"} saved; ${result.duplicates} duplicate${result.duplicates === 1 ? "" : "s"} skipped.`);
      await loadAccounts(0);
      if (dossier) await loadDossier(dossier.organisation_id);
      return true;
    } catch (e) { setError((e as Error).message); return false; }
    finally { setBusy(false); }
  }
  async function refreshFeed(continuePrevious = false) {
    setBusy(true); setError(""); setMessage("");
    try {
      const previous = feedResult;
      const body = continuePrevious && previous?.next_cursor ? { updated_from: previous.updated_from, updated_to: previous.updated_to, cursor: previous.next_cursor } : {};
      const response = await fetch(`${getApiBaseUrl()}/api/public-sources/find-a-tender/refresh`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      if (!response.ok) { const data = await response.json().catch(() => null); throw new Error(typeof data?.detail === "string" ? data.detail : `Public source refresh failed (${response.status}).`); }
      const result: FeedResult = await response.json();
      setFeedResult(result);
      await loadAccounts(0);
      if (dossier) await loadDossier(dossier.organisation_id);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!safeSource(sourceUrl)) { setError("Enter a valid HTTP or HTTPS source URL."); return; }
    const ok = await save([{
      organisation_id: organisationId.trim(), organisation_name: organisationName.trim(), site: site.trim() || "Unspecified", category,
      observed_statement: statement.trim(), source_url: sourceUrl.trim(), source_title: sourceTitle.trim(), source_reference: sourceReference.trim(),
      published_at: publishedAt || null, observed_at: observedAt || null, retrieved_at: new Date().toISOString(),
    }]);
    if (ok) { setStatement(""); setSourceUrl(""); setSourceTitle(""); setSourceReference(""); setPublishedAt(""); setObservedAt(""); }
  }
  async function submitBatch(event: FormEvent) {
    event.preventDefault();
    try {
      const observations: unknown = JSON.parse(batch);
      if (!Array.isArray(observations) || observations.length < 1 || observations.length > 1000) throw new Error("Enter a JSON array containing 1 to 1,000 observations.");
      if (await save(observations)) setBatch("");
    } catch (e) { setError((e as Error).message); }
  }
  return (
    <section className="m-results mt-8" aria-label="Evidence inbox">
      <SectionHeading title="Evidence to investigate" detail="Public-source and manually supplied observations, grouped by organisation. Review the original sources and confirm the organisation identity before using them." />
      <p className="m-small m-muted">This is a local evidence inbox, not live UK-wide monitoring. A signal or missing record does not establish a supplier failure, a lack of maintenance or a compliance breach. No opportunities are created automatically.</p>
      <div className="flex flex-wrap gap-2 mt-4">
        <Button onClick={() => setShowForm(!showForm)}>{showForm ? "Close observation form" : "Add an observation"}</Button>
        <Button onClick={() => setShowBatch(!showBatch)}>{showBatch ? "Close batch import" : "Import a batch"}</Button>
        <Button disabled={busy} onClick={() => void refreshFeed()}>Refresh historical public-sector context</Button>
      </div>
      <p className="m-small m-muted mt-2">Find a Tender refresh checks a bounded selection of recent historical awards and contracts for context. It does not indicate current demand or cover the whole market.</p>
      {feedResult && <div className="m-notice mt-3" role="status"><p>{feedResult.imported} observations added · {feedResult.duplicates} duplicates · {feedResult.scanned} records checked across {feedResult.pages} pages. Review them in the organisation groups below.</p>{feedResult.warnings.map((warning, index) => <p key={index} className="mt-2">{warning}</p>)}{feedResult.next_cursor && <Button className="mt-3" disabled={busy} onClick={() => void refreshFeed(true)}>Check next pages</Button>}</div>}
      {showForm && <form className="m-form m-surface mt-4" onSubmit={submit}>
        <h3>Add a source observation</h3>
        <p className="m-muted">Use the same trusted identifier for the same organisation. Enter what the source says, not an unverified conclusion.</p>
        <div className="m-form-grid">
          <label>Organisation ID <input value={organisationId} onChange={e => setOrganisationId(e.target.value)} placeholder="GB-COH:12345678" required maxLength={120} /></label>
          <label>Organisation name <input value={organisationName} onChange={e => setOrganisationName(e.target.value)} required maxLength={255} /></label>
          <label>Site, if known <input value={site} onChange={e => setSite(e.target.value)} placeholder="Unspecified" maxLength={255} /></label>
          <label>Signal type <select value={category} onChange={e => setCategory(e.target.value)}>{categories.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          <label>Source title <input value={sourceTitle} onChange={e => setSourceTitle(e.target.value)} required maxLength={255} /></label>
          <label>Stable source reference <input value={sourceReference} onChange={e => setSourceReference(e.target.value)} placeholder="Document or record ID" required maxLength={255} /></label>
          <label>Source URL <input type="url" value={sourceUrl} onChange={e => setSourceUrl(e.target.value)} required maxLength={2048} /></label>
          <label>Published date, if known <input type="date" value={publishedAt} onChange={e => setPublishedAt(e.target.value)} /></label>
          <label>Observed date, if known <input type="date" value={observedAt} onChange={e => setObservedAt(e.target.value)} /></label>
        </div>
        <label>Observed statement <textarea value={statement} onChange={e => setStatement(e.target.value)} required maxLength={4000} rows={3} /></label>
        <Button type="submit" kind="primary" disabled={busy}>Save observation</Button>
      </form>}
      {showBatch && <form className="m-form m-surface mt-4" onSubmit={submitBatch}>
        <h3>Import source observations</h3>
        <p className="m-muted">Paste a JSON array of up to 1,000 records. Each needs organisation_id, organisation_name, site, category, observed_statement, source_title, source_reference and retrieved_at (ISO timestamp with time zone). Optional fields: source_url, published_at and observed_at (dates in YYYY-MM-DD). Categories: {categories.map(([value]) => value).join(", ")}.</p>
        <label>Observation JSON <textarea value={batch} onChange={e => setBatch(e.target.value)} required rows={8} placeholder={'[{"organisation_id":"GB-COH:12345678","organisation_name":"Example Ltd","site":"Unspecified","category":"maintenance","observed_statement":"A source statement","source_title":"Example source","source_reference":"record-1","source_url":"https://example.com/record-1","published_at":null,"retrieved_at":"2026-10-28T12:00:00Z"}]'} /></label>
        <Button type="submit" kind="primary" disabled={busy}>Import batch</Button>
      </form>}
      {error && <p className="m-error mt-3" role="alert">{error}</p>}
      {message && <p className="m-notice mt-3" role="status">{message}</p>}
      <div className="m-surface mt-4 p-4">
        <h3>Organisation groups</h3>
        {!accounts ? <p className="m-small m-muted">{error ? "Organisation groups could not be loaded." : "Loading organisation groups…"}</p> : accounts.items.length === 0 ? <Empty title="No saved observations">Add observations or import a batch to start an evidence review.</Empty> : <div className="grid gap-2 mt-3">{accounts.items.map(account => <button key={account.organisation_id} type="button" onClick={() => void loadDossier(account.organisation_id)} className="text-left rounded border border-[var(--misi-border)] p-3 hover:border-[var(--misi-border)]"><strong>{account.organisation_name}</strong><span className="m-small m-muted"> · {account.organisation_id} · {account.observation_count} observations</span></button>)}</div>}
        <div className="flex gap-2 mt-3"><Button disabled={!accounts || accountOffset === 0} onClick={() => void loadAccounts(Math.max(0, accountOffset - PAGE_SIZE))}>Previous groups</Button><Button disabled={!accounts || accountOffset + PAGE_SIZE >= accounts.total} onClick={() => void loadAccounts(accountOffset + PAGE_SIZE)}>Next groups</Button>{!accounts && error && <Button onClick={() => void loadAccounts(0)}>Retry</Button>}</div>
      </div>
      {dossier && <div className="m-surface mt-4 p-4">
        <h3>{dossier.organisation_name}</h3><p className="m-small m-muted">Supplied ID: {dossier.organisation_id} · {dossier.total} observations. Check identity, relevance and source reliability.</p>
        <HypothesisPanel key={`${dossier.organisation_id}:${dossier.total}`} organisationId={dossier.organisation_id} />
        <div className="grid gap-3 mt-3">{dossier.observations.map(item => <article key={item.id} className="rounded border border-[var(--misi-border)] p-4">
          <p className="m-small m-muted">{categoryLabel(item.category)} · {item.site} · Published: {item.published_at || "unknown"} · Observed: {item.observed_at || "unknown"} · Retrieved: {item.retrieved_at}</p>
          <p className="mt-2">{item.observed_statement}</p>
          <p className="m-small m-muted mt-2">{item.source_title} · {item.source_reference}</p>
          {item.source_url && safeSource(item.source_url) ? <a className="text-[var(--misi-accent)] break-all" href={safeSource(item.source_url) || "#"} target="_blank" rel="noreferrer">View source</a> : <p className="m-small m-muted">Source URL unavailable</p>}
        </article>)}</div>
        <div className="flex gap-2 mt-3"><Button disabled={observationOffset === 0} onClick={() => void loadDossier(dossier.organisation_id, Math.max(0, observationOffset - PAGE_SIZE))}>Previous observations</Button><Button disabled={observationOffset + PAGE_SIZE >= dossier.total} onClick={() => void loadDossier(dossier.organisation_id, observationOffset + PAGE_SIZE)}>Next observations</Button></div>
      </div>}
    </section>
  );
}

function ObservationReferences({ ids, observations, label }: { ids: number[]; observations: Observation[]; label: string }) {
  if (!ids.length) return <p className="m-small m-muted">{label}: none identified.</p>;
  const byId = new Map(observations.map(item => [item.id, item]));
  return <div className="mt-2"><p className="m-small"><strong>{label}</strong></p><ul className="grid gap-2 mt-2">{ids.map(id => {
    const item = byId.get(id);
    return <li key={id} className="rounded border border-[var(--misi-border)] p-3 text-sm">{item ? <>
      <p>{item.observed_statement}</p>
      <p className="m-small m-muted mt-1">{item.source_title} · {item.source_reference} · Published {item.published_at || "unknown"} · Observed {item.observed_at || "unknown"}</p>
      {item.source_url && safeSource(item.source_url) ? <a href={safeSource(item.source_url) || "#"} target="_blank" rel="noreferrer" className="text-[var(--misi-accent)] break-all">Open source</a> : <span className="m-small m-muted">Source URL unavailable</span>}
    </> : <span className="m-muted">Observation {id} is unavailable; check the original evidence.</span>}</li>;
  })}</ul></div>;
}

function HypothesisPanel({ organisationId }: { organisationId: string }) {
  const [rules, setRules] = useState<RuleHypotheses | null>(null);
  const [rulesError, setRulesError] = useState("");
  const [ai, setAi] = useState<AiHypotheses | null>(null);
  const [aiError, setAiError] = useState("");
  const [busySite, setBusySite] = useState<string | null>(null);
  const [selectionSite, setSelectionSite] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);

  useEffect(() => {
    let active = true;
    setRules(null);
    setRulesError("");
    setAi(null);
    void evidenceRequest<RuleHypotheses>(`/accounts/${encodeURIComponent(organisationId)}/hypotheses`)
      .then(result => { if (active) setRules(result); })
      .catch(error => { if (active) setRulesError((error as Error).message); });
    return () => { active = false; };
  }, [organisationId]);

  async function runAi(site: string) {
    setBusySite(site);
    setAi(null);
    setAiError("");
    try {
      const result = await evidenceRequest<AiHypotheses>(`/accounts/${encodeURIComponent(organisationId)}/ai-hypotheses`, { site, observation_ids: selectedIds });
      setAi(result);
    } catch (error) { setAiError((error as Error).message); }
    finally { setBusySite(null); }
  }

  return <section className="mt-4 rounded border border-[var(--misi-border)] p-4" aria-label="Patterns to investigate">
    <h4 className="font-semibold">Patterns to investigate</h4>
    <p className="m-small m-muted mt-1">Rules look for combinations of supplied observations at the same named site. These are prompts for investigation, not verified findings or predictions of buying intent. Rule patterns do not use AI.</p>
    {rulesError && <p className="m-error mt-2" role="alert">Could not assess patterns: {rulesError}</p>}
    {!rules && !rulesError && <p className="m-small m-muted mt-2">Checking observation patterns…</p>}
    {rules && <>
      <p className="m-small m-muted mt-2">{rules.analysed_observations} of {rules.total_observations} observations assessed. Check source independence and identity before relying on a pattern.</p>
      {rules.sites.length === 0 && <p className="m-small m-muted mt-2">No named sites are available for a site-level investigation.</p>}
      {rules.sites.map(group => <div key={group.site} className="mt-4 rounded border border-[var(--misi-border)] p-3">
        <h5 className="font-semibold">{group.site}</h5>
        {group.hypotheses.length === 0 && <p className="m-small m-muted mt-2">No rule pattern identified for this site.</p>}
        {group.hypotheses.map((hypothesis, index) => <article key={`${hypothesis.title}-${index}`} className="mt-3 rounded border border-[var(--misi-border)] p-3">
          <p className="font-semibold">{hypothesis.title}</p><p className="mt-1 text-sm">{hypothesis.explanation}</p>
          <ObservationReferences ids={hypothesis.observation_ids} observations={rules.observations} label="Observations to review" />
          <p className="mt-2 text-sm text-[var(--misi-accent)]"><strong>Investigate:</strong> {hypothesis.question}</p>
        </article>)}
        <p className="m-small m-muted mt-3">Select 2–100 observations for this organisation and site. Only select publicly available observations; MiSi cannot verify source accessibility. The organisation ID, site, selected text, categories, dates, source titles, references and URL origins and paths are sent to the configured AI model. URL query strings are omitted.</p>
        <div className="grid gap-2 mt-2">{rules.observations.filter(item => item.site === group.site && item.source_url && safeSource(item.source_url)).map(item => <label key={item.id} className="flex items-start gap-2 rounded border border-[var(--misi-border)] p-2 text-sm">
          <input type="checkbox" checked={selectionSite === group.site && selectedIds.includes(item.id)} disabled={busySite !== null || (selectionSite === group.site && selectedIds.length >= 100 && !selectedIds.includes(item.id))} onChange={event => {
            setAi(null);
            setAiError("");
            if (selectionSite !== group.site) {
              setSelectionSite(group.site);
              setSelectedIds(event.target.checked ? [item.id] : []);
            } else setSelectedIds(current => event.target.checked ? [...current, item.id] : current.filter(id => id !== item.id));
          }} />
          <span>{item.observed_statement}<span className="block m-small m-muted">{item.source_title} · {item.source_reference}</span></span>
        </label>)}</div>
        <Button disabled={busySite !== null || selectionSite !== group.site || selectedIds.length < 2} onClick={() => void runAi(group.site)}>{busySite === group.site ? "Analysing evidence…" : "Analyse selected observations with AI"}</Button>
      </div>)}
      {rules.limitations.length > 0 && <ul className="mt-3 list-disc pl-5 m-small m-muted">{rules.limitations.map((limitation, index) => <li key={index}>{limitation}</li>)}</ul>}
    </>}
    {aiError && <p className="m-error mt-3" role="alert">AI analysis was not completed: {aiError}</p>}
    {ai && <div className="mt-4 rounded border border-[var(--misi-border)] p-3">
      <h5 className="font-semibold">AI hypotheses · {ai.site}</h5>
      <p className="m-small m-muted mt-1">Interpretations to check, not confirmed buyer needs or supplier failures.</p>
      {ai.hypotheses.length === 0 && <p className="m-small m-muted mt-2">The model returned no sufficiently supported hypotheses.</p>}
      {ai.hypotheses.map((hypothesis, index) => <article key={`${hypothesis.title}-${index}`} className="mt-3 rounded border border-[var(--misi-border)] p-3">
        <p className="font-semibold">{hypothesis.title}</p><p className="mt-1 text-sm">{hypothesis.explanation}</p>
        <ObservationReferences ids={hypothesis.supporting_observation_ids} observations={ai.observations} label="Supporting observations" />
        <ObservationReferences ids={hypothesis.counter_observation_ids} observations={ai.observations} label="Counter-evidence to review" />
        {hypothesis.unknowns.length > 0 && <div className="mt-2 text-sm text-[#825929]"><strong>Unknowns</strong><ul className="list-disc pl-5">{hypothesis.unknowns.map((unknown, i) => <li key={i}>{unknown}</li>)}</ul></div>}
        <p className="mt-2 text-sm text-[var(--misi-accent)]"><strong>Investigate:</strong> {hypothesis.question}</p>
      </article>)}
      {ai.limitations.length > 0 && <ul className="mt-3 list-disc pl-5 m-small m-muted">{ai.limitations.map((limitation, index) => <li key={index}>{limitation}</li>)}</ul>}
    </div>}
  </section>;
}
