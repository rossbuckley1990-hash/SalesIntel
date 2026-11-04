"use client";
import { useMemo, useState } from "react";
import { ArrowRight, ArrowUpRight, Search, SlidersHorizontal } from "lucide-react";
import { dateLabel, money } from "./api";
import { Badge, Button, Heading } from "./ui";
import type { LivingOpportunity, SharedProps } from "./types";
import "./supporting-workspace.css";

export function OpportunityTable({
  opportunities,
  inspect,
}: {
  opportunities: LivingOpportunity[];
  inspect: (id: number) => void;
}) {
  return (
    <div className="m-table-scroll">
      <table className="m-table">
        <caption className="m-sr-only">
          Opportunity records with owner, annual revenue, weighted contract
          value, evidence gaps and risk
        </caption>
        <thead>
          <tr>
            <th>Opportunity / account</th>
            <th>Stage</th>
            <th>Annual revenue</th>
            <th>Weighted contract</th>
            <th>Evidence</th>
            <th>Risk</th>
            <th>Due</th>
            <th>
              <span className="m-sr-only">Inspect</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {opportunities.map((o) => (
            <tr key={o.id}>
              <td>
                <button className="m-table-title" onClick={() => inspect(o.id)}>
                  {o.name}
                </button>
                <small>
                  {o.buyer_name} · {o.owner}
                </small>
              </td>
              <td>{o.stage}</td>
              <td className="m-number">
                {money(o.financials.estimated_annual_revenue)}
              </td>
              <td className="m-number">
                {money(o.financials.weighted_contract_value)}
              </td>
              <td>
                <span className={o.unknown_count ? "m-amber" : "m-muted"}>
                  {o.unknown_count} gaps
                </span>
                <small>{o.evidence_count} fields</small>
              </td>
              <td>
                <Badge tone={o.risk_rating}>{o.risk_rating}</Badge>
              </td>
              <td>{dateLabel(o.submission_deadline)}</td>
              <td>
                <button
                  className="m-icon-button"
                  onClick={() => inspect(o.id)}
                  aria-label={`Inspect ${o.buyer_name}`}
                >
                  <ArrowUpRight size={17} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Opportunities(props: SharedProps & { pursuits?: boolean }) {
  const [search, setSearch] = useState("");
  const [risk, setRisk] = useState("");
  const [sector, setSector] = useState("");
  const rows = useMemo(
    () =>
      props.data.opportunities.filter(
        (o) =>
          (!search ||
            `${o.name} ${o.buyer_name} ${o.owner} ${o.region}`
              .toLowerCase()
              .includes(search.toLowerCase())) &&
          (!risk || o.risk_rating === risk) &&
          (!sector || o.sector === sector) &&
          (!props.pursuits ||
            props.data.outcomes.some(
              (v) =>
                v.opportunity_id === o.id &&
                ["approved", "investigating", "won"].includes(v.stage),
            )),
      ),
    [props.data, search, risk, sector, props.pursuits],
  );
  return (
    <div className="m-support-light m-support-opportunities">
      <Heading
        eyebrow={props.pursuits ? "Commercial / Pursuits" : "Commercial / Opportunities"}
        title={props.pursuits ? "Pursuits" : "Opportunities"}
        description={props.pursuits ? "Follow the opportunities with a recorded pursuit decision." : "Review your saved opportunities, their evidence and next steps."}
      >
        <Button kind="primary" onClick={() => props.navigate("discover")}>
          Discover opportunities <ArrowUpRight size={16} />
        </Button>
      </Heading>
      <div className="m-support-list-heading"><div><h2>{props.pursuits ? "Your pursuits" : "Opportunity workspace"}</h2><p>Filter the records already in your workspace.</p></div></div>
      <div className="m-toolbar">
        <label className="m-search">
          <Search size={17} />
          <input
            aria-label="Filter opportunities"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search account, owner or opportunity"
          />
        </label>
        <label className="m-inline-field">
          <SlidersHorizontal size={15} />
          <select
            aria-label="Filter by risk"
            value={risk}
            onChange={(e) => setRisk(e.target.value)}
          >
            <option value="">All risks</option>
            {[
              ...new Set(props.data.opportunities.map((o) => o.risk_rating)),
            ].map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </label>
        <select
          aria-label="Filter by sector"
          value={sector}
          onChange={(e) => setSector(e.target.value)}
        >
          <option value="">All sectors</option>
          {[...new Set(props.data.opportunities.map((o) => o.sector))].map(
            (v) => (
              <option key={v}>{v}</option>
            ),
          )}
        </select>
        <span className="m-muted m-small">{rows.length} records</span>
      </div>
      {rows.length ? (
        <OpportunityTable opportunities={rows} inspect={props.inspect} />
      ) : (
        <div className="m-support-zero" role="status">
          <div><h3>No matching opportunities</h3><p>Adjust your filters or explore public research to find a useful conversation.</p></div>
          <button onClick={() => props.navigate("discover")}>Explore research <ArrowRight size={15} /></button>
        </div>
      )}
      <p className="m-footnote">
        Annual revenue and whole-contract value are separate measures. Unknown
        values remain unknown.
      </p>
    </div>
  );
}
