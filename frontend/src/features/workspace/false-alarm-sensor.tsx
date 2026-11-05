"use client";
import "./research-tool-accessibility.css";

import { useEffect, useState, type FormEvent } from "react";
import { getApiBaseUrl } from "@/lib/api";
import { Button, Empty, SectionHeading } from "./ui";
import { safeSource } from "./api";

type Comparison = {
  cohort_sites: number;
  mean_attendances: number | null;
};
type SensorSite = {
  uprn: string;
  property_type: string;
  postcode_district: string | null;
  attendances: number;
  first_seen: string;
  last_seen: string;
  comparison: Comparison;
  research_brief: string;
};
type SensorPage = {
  total: number;
  items: SensorSite[];
  period_start: string | null;
  period_end: string | null;
  limitations: string[];
  source_url: string;
  policy_url: string;
  snapshot: { source_file: string; sha256: string; imported_at: string; acquisition_method: string; retrieved_at: string | null; records_imported: number } | null;
};
type SensorIncident = { incident_number: string; incident_date: string; stop_code_description: string; address_qualifier: string };
type SensorDetail = { site: SensorSite; incidents: SensorIncident[]; period_start: string; period_end: string; source_url: string; limitations: string[] };
type InspectionContext = { snapshot_available: boolean; matches: { organisation_name: string; site_name: string; site_reference_url: string; site_reference_period: string; inspection_address: string; postcode: string; completed_on: string; reason_or_outcome: string; source_file: string }[]; source_url: string; limitations: string[] };
type SiteReference = { uprn: string; organisation_id: string; organisation_name: string; site_name: string; postcode: string | null; source_url: string; source_period: string };
type SiteResearch = {
  site_references: SiteReference[];
  research: {
    identity_status: "candidate" | "unknown";
    organisation: string;
    site_name: string;
    identity_explanation: string;
    identity_sources: string[];
    inferred_maintenance_need: string;
    contact_name: string;
    contact_role: string;
    contact_sources: string[];
    engagement: string;
    limitations: string[];
  };
};

const PAGE_SIZE = 25;
const formatNumber = (value: number) => new Intl.NumberFormat("en-GB", { maximumFractionDigits: 1 }).format(value);

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}/api/virtual-sensors${path}`, { cache: "no-store", ...options });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(typeof payload?.detail === "string" ? payload.detail : `Request failed (${response.status}).`);
  }
  return response.json() as Promise<T>;
}

export function FalseAlarmSensor() {
  const [page, setPage] = useState<SensorPage | null>(null);
  const [offset, setOffset] = useState(0);
  const [filter, setFilter] = useState("");
  const [appliedFilter, setAppliedFilter] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<SensorDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [uprn, setUprn] = useState("");
  const [research, setResearch] = useState<SiteResearch | null>(null);
  const [researchLoading, setResearchLoading] = useState(false);
  const [researchError, setResearchError] = useState("");
  const [inspections, setInspections] = useState<InspectionContext | null>(null);
  const [inspectionLoading, setInspectionLoading] = useState(false);
  const [inspectionError, setInspectionError] = useState("");

  async function load(nextOffset: number, propertyType = appliedFilter) {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(nextOffset) });
      if (propertyType.trim()) params.set("property_type", propertyType.trim());
      const result = await request<SensorPage>(`/false-alarms?${params}`);
      setPage(result);
      setOffset(nextOffset);
      setSelected(null);
    } catch (e) {
      setError((e as Error).message);
      setPage(null);
    } finally { setLoading(false); }
  }
  useEffect(() => { void load(0, ""); }, []);

  function applyFilter(event: FormEvent) {
    event.preventDefault();
    setAppliedFilter(filter.trim());
    void load(0, filter.trim());
  }

  async function loadDetail(id: string, propertyType?: string) {
    setDetailLoading(true);
    setDetailError("");
    setSelected(null);
    setResearch(null);
    setResearchError("");
    setInspections(null);
    setInspectionError("");
    try {
      const params = new URLSearchParams();
      if (propertyType) params.set("property_type", propertyType);
      setSelected(await request<SensorDetail>(`/false-alarms/${encodeURIComponent(id)}${params.size ? `?${params}` : ""}`));
    } catch (e) { setDetailError((e as Error).message); }
    finally { setDetailLoading(false); }
  }

  async function checkInspections(id: string) {
    setInspectionLoading(true); setInspectionError(""); setInspections(null);
    try { setInspections(await request<InspectionContext>(`/false-alarms/${encodeURIComponent(id)}/inspection-context`)); }
    catch (e) { setInspectionError((e as Error).message); }
    finally { setInspectionLoading(false); }
  }

  async function researchSite(site: SensorSite) {
    setResearchLoading(true);
    setResearchError("");
    setResearch(null);
    try {
      setResearch(await request<SiteResearch>(`/false-alarms/${encodeURIComponent(site.uprn)}/research`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ property_type: site.property_type }),
      }));
    } catch (e) { setResearchError((e as Error).message); }
    finally { setResearchLoading(false); }
  }

  return (
    <section className="m-results mt-8" aria-label="False alarm sensor">
      <SectionHeading title="Repeated fire-alarm attendances" detail="Explore public London Fire Brigade attendances at non-residential properties and investigate whether a maintenance conversation may be relevant." />
      <p className="m-small m-muted">A UPRN identifies a property, not its occupier, service provider or buying intent. An attendance does not establish a fault, missing maintenance or supplier performance. These are leads for investigation, not predictions.</p>
      <form onSubmit={applyFilter} className="m-form m-surface mt-4">
        <div className="m-form-grid"><label>Exact property type, if known <input value={filter} onChange={event => setFilter(event.target.value)} placeholder="Filter by the dataset's property type" /></label></div>
        <div className="flex flex-wrap gap-2"><Button type="submit" disabled={loading || researchLoading}>Apply filter</Button><Button onClick={() => { setFilter(""); setAppliedFilter(""); void load(0, ""); }} disabled={loading || researchLoading}>Clear</Button></div>
      </form>
      <form className="m-form m-surface mt-4" onSubmit={event => { event.preventDefault(); void loadDetail(uprn.trim()); }}>
        <label>Look up an exact UPRN <input value={uprn} onChange={event => setUprn(event.target.value)} inputMode="numeric" pattern="[0-9]+" placeholder="Enter a property identifier" required /></label>
        <Button type="submit" disabled={detailLoading || researchLoading}>Look up property</Button>
      </form>
      {detailLoading && <p className="m-small m-muted mt-3" role="status">Loading site observations…</p>}
      {detailError && <p className="m-error mt-3" role="alert">Could not load the property: {detailError}</p>}
      {loading && <p className="m-small m-muted mt-3" role="status">Loading public attendance patterns…</p>}
      {error && <p className="m-error mt-3" role="alert">Could not load the sensor: {error}</p>}
      {page && !loading && <>
        <p className="m-small m-muted mt-4">{page.period_start && page.period_end ? `Analysis period ${page.period_start} to ${page.period_end}` : "No dataset period is available"} · {formatNumber(page.total)} property groups. Ordered by recorded attendance count, not commercial value or buying probability. The comparison is with properties in this dataset that had recorded attendances, not all properties.</p>
        {page.snapshot && <p className="m-small m-muted mt-2">Imported snapshot: {page.snapshot.source_file} · {formatNumber(page.snapshot.records_imported)} records · acquisition: {page.snapshot.acquisition_method || "unknown"} · retrieved: {page.snapshot.retrieved_at || "unknown"} · imported: {page.snapshot.imported_at} · SHA-256 {page.snapshot.sha256}. The fingerprint identifies the file; it does not verify its authenticity or completeness. The dataset is not refreshed automatically.</p>}
        {page.items.length === 0 ? <Empty title="No matching attendance patterns">Import the public LFB dataset using <code>backend/scripts/import_lfb_incidents.py</code> or try another property type. An empty result does not establish that a property has no alarms.</Empty> : <div className="grid gap-2 mt-4">{page.items.map(item => <button key={`${item.uprn}:${item.property_type}`} type="button" disabled={detailLoading || researchLoading} onClick={() => void loadDetail(item.uprn, item.property_type)} className="m-surface rounded border border-[var(--misi-border)] p-4 text-left hover:border-[var(--misi-border)] disabled:opacity-60">
          <strong>Property UPRN {item.uprn}</strong><span className="m-small m-muted"> · {item.property_type}{item.postcode_district ? ` · ${item.postcode_district}` : " · postcode district unavailable"}</span>
          <p className="mt-1 text-sm">{item.attendances} recorded attendances · Last {item.last_seen}</p>
          <p className="m-small m-muted">Peer mean: {item.comparison.mean_attendances == null ? "unavailable" : formatNumber(item.comparison.mean_attendances)} across {formatNumber(item.comparison.cohort_sites)} recorded properties</p>
        </button>)}</div>}
        <div className="flex gap-2 mt-3"><Button disabled={researchLoading || offset === 0} onClick={() => void load(Math.max(0, offset - PAGE_SIZE))}>Previous properties</Button><Button disabled={researchLoading || offset + PAGE_SIZE >= page.total} onClick={() => void load(offset + PAGE_SIZE)}>Next properties</Button></div>
        {page.limitations.length > 0 && <ul className="list-disc pl-5 m-small m-muted mt-4">{page.limitations.map((item, i) => <li key={`${item}-${i}`}>{item}</li>)}</ul>}
        {safeSource(page.source_url) && <a className="text-[var(--misi-accent)] text-sm break-all" href={safeSource(page.source_url) || "#"} target="_blank" rel="noreferrer">London Fire Brigade incident data</a>}
        {page.policy_url && safeSource(page.policy_url) && <a className="ml-4 text-[var(--misi-accent)] text-sm break-all" href={safeSource(page.policy_url) || "#"} target="_blank" rel="noreferrer">London Fire Brigade attendance policy</a>}
      </>}
      {selected && <div className="m-surface mt-4 p-4"><h3>Property UPRN {selected.site.uprn}</h3><p className="m-small m-muted mt-2">{selected.site.property_type}{selected.site.postcode_district ? ` · ${selected.site.postcode_district}` : ""} · recorded {selected.site.first_seen} to {selected.site.last_seen}</p><p className="mt-2">{selected.site.research_brief}</p><p className="m-small m-muted mt-2">Confirm the premises and current occupier independently before associating this pattern with any organisation or contacting anyone.</p><h4 className="font-semibold mt-4">Recorded attendances</h4><p className="m-small m-muted">Showing up to 200 of {formatNumber(selected.site.attendances)} attendances.</p><ul className="mt-2 grid gap-2">{selected.incidents.map(incident => <li key={incident.incident_number} className="rounded border border-[var(--misi-border)] p-3 text-sm">{incident.incident_date} · {incident.stop_code_description} · {incident.address_qualifier}<span className="m-small m-muted"> · Incident {incident.incident_number}</span></li>)}</ul>{selected.limitations.length > 0 && <ul className="list-disc pl-5 m-small m-muted mt-3">{selected.limitations.map((item, i) => <li key={`${item}-${i}`}>{item}</li>)}</ul>}
        <div className="mt-4 border-t border-[var(--misi-border)] pt-4"><h4 className="font-semibold">Connect inspection context</h4><p className="m-small m-muted mt-1">Look for an exact hospital-name and full-postcode match between historical NHS site references and the London inspection snapshot. This is a candidate association and may refer to a different building or block.</p><Button disabled={inspectionLoading} onClick={() => void checkInspections(selected.site.uprn)}>{inspectionLoading ? "Checking public records…" : "Check related inspections"}</Button>
          {inspectionError && <p className="m-error mt-3" role="alert">Inspection context unavailable: {inspectionError}</p>}
          {inspections && <div className="mt-3"><p className="m-small m-muted">{inspections.matches.length ? `${inspections.matches.length} candidate inspection records` : inspections.snapshot_available ? "No candidate matches in this snapshot; this does not establish that no inspection took place." : "No inspection matches are loaded. Import a compatible snapshot before using this check."}</p><ul className="mt-2 grid gap-2">{inspections.matches.map((item, index) => <li key={index} className="rounded border border-[var(--misi-border)] p-3 text-sm"><strong>{item.completed_on} · {item.reason_or_outcome}</strong><p>{item.inspection_address} · {item.postcode}</p><p className="m-small m-muted">Historical reference: {item.organisation_name} · {item.site_name} · {item.site_reference_period} · {item.source_file}</p>{safeSource(item.site_reference_url) && <a className="text-[var(--misi-accent)] text-sm" href={safeSource(item.site_reference_url) || "#"} target="_blank" rel="noreferrer">NHS site reference</a>}</li>)}</ul><ul className="list-disc pl-5 m-small m-muted mt-3">{inspections.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul>{safeSource(inspections.source_url) && <a className="text-[var(--misi-accent)] text-sm" href={safeSource(inspections.source_url) || "#"} target="_blank" rel="noreferrer">Inspection dataset</a>}</div>}
        </div>
        <div className="mt-4 border-t border-[var(--misi-border)] pt-4"><h4 className="font-semibold">Research this property</h4><p className="m-small m-muted mt-1">Search public sources for possible site identity, maintenance context and who to approach. The property identifier, attendance summary, historical NHS references and up to ten candidate inspection records are sent to the configured AI provider; results need independent review.</p><Button disabled={researchLoading} onClick={() => void researchSite(selected.site)}>{researchLoading ? "Researching public sources…" : "Research this property with AI"}</Button>
          {researchError && <p className="m-error mt-3" role="alert">Research could not be completed: {researchError}</p>}
          {research && <div className="mt-4 rounded border border-[var(--misi-border)] p-3"><h5 className="font-semibold">Research for UPRN {selected.site.uprn}</h5><p className="m-small m-muted mt-1">These are research candidates, not verified account identities or a confirmed service requirement.</p>
            {research.site_references.length > 0 && <div className="mt-3"><strong>Historical site references to check</strong><ul className="grid gap-2 mt-2">{research.site_references.map((item, i) => <li className="rounded border border-[var(--misi-border)] p-2 text-sm" key={`${item.organisation_id}-${i}`}>{item.organisation_name} · {item.site_name} · {item.organisation_id}{item.postcode ? ` · ${item.postcode}` : ""} · {item.source_period}{safeSource(item.source_url) && <> · <a className="text-[var(--misi-accent)]" href={safeSource(item.source_url) || "#"} target="_blank" rel="noreferrer">Source</a></>}</li>)}</ul></div>}
            <p className="mt-3"><strong>Possible identity:</strong> {research.research.identity_status === "unknown" ? "Unknown" : [research.research.organisation, research.research.site_name].filter(Boolean).join(" · ") || "Candidate not established"}</p><p className="m-small mt-1">{research.research.identity_explanation}</p>
            {research.research.identity_sources.map((url, i) => safeSource(url) && <a className="block text-[var(--misi-accent)] text-sm break-all" key={`${url}-${i}`} href={safeSource(url) || "#"} target="_blank" rel="noreferrer">Identity source: {url}</a>)}
            <p className="mt-3"><strong>Possible maintenance need:</strong> {research.research.inferred_maintenance_need}</p><p className="mt-3"><strong>Suggested contact:</strong> {[research.research.contact_name, research.research.contact_role].filter(Boolean).join(" · ") || "Unknown"}</p>
            {research.research.contact_sources.map((url, i) => safeSource(url) && <a className="block text-[var(--misi-accent)] text-sm break-all" key={`${url}-${i}`} href={safeSource(url) || "#"} target="_blank" rel="noreferrer">Contact source: {url}</a>)}
            <p className="mt-3"><strong>Approach:</strong> {research.research.engagement}</p>{research.research.limitations.length > 0 && <ul className="list-disc pl-5 m-small m-muted mt-3">{research.research.limitations.map((item, i) => <li key={`${item}-${i}`}>{item}</li>)}</ul>}
          </div>}
        </div>
      </div>}
    </section>
  );
}
