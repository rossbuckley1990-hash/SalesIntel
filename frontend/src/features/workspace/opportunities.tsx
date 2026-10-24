"use client";
import { useMemo, useState } from "react";
import { ArrowUpRight, Search, SlidersHorizontal } from "lucide-react";
import { dateLabel, money } from "./api";
import { Badge, Button, Empty, Heading } from "./ui";
import type { LivingOpportunity, SharedProps } from "./types";

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
    <>
      <Heading
        eyebrow={
          props.pursuits
            ? "Pursuits / Accountable progress"
            : "Opportunities / The commercial picture"
        }
        title={
          props.pursuits
            ? "Make the pursuit move."
            : "A pipeline with perspective."
        }
        description="Inspect the evidence, qualify the risk and put a named next step in motion."
      >
        <Button kind="primary" onClick={() => props.navigate("discover")}>
          Discover opportunities <ArrowUpRight size={16} />
        </Button>
      </Heading>
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
        <Empty title="No matching opportunities">
          Adjust your filters or start a discovery.
        </Empty>
      )}
      <p className="m-footnote">
        Annual revenue and whole-contract value are separate measures. Unknown
        values remain unknown.
      </p>
    </>
  );
}
