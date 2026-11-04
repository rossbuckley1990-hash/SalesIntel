"use client";
import { useState } from "react";
import { ArrowRight, ArrowUpRight, Building2, Search, UsersRound } from "lucide-react";
import { Heading } from "./ui";
import type { SharedProps } from "./types";
import "./supporting-workspace.css";

export function Accounts(props: SharedProps) {
  const [view, setView] = useState<"accounts" | "competitors">("accounts");
  const [query, setQuery] = useState("");
  const search = query.trim().toLocaleLowerCase();
  const buyers = props.data.buyers.filter((buyer) => !search || `${buyer.buyer_name} ${buyer.sector} ${buyer.region}`.toLocaleLowerCase().includes(search));
  const competitors = props.data.competitors.filter((competitor) => !search || `${competitor.name} ${competitor.sectors.join(" ")}`.toLocaleLowerCase().includes(search));
  return (
    <div className="m-support-light m-support-accounts">
      <Heading eyebrow="Commercial / Relationships" title="Customers" description="The organisations and competitive context already recorded in your workspace." />
      <div className="m-support-controls"><div className="m-support-tabs" role="tablist" aria-label="Account views">
        <button role="tab" aria-selected={view === "accounts"} className={view === "accounts" ? "active" : ""} onClick={() => setView("accounts")}>Buyer accounts <span>{props.data.buyers.length}</span></button>
        <button role="tab" aria-selected={view === "competitors"} className={view === "competitors" ? "active" : ""} onClick={() => setView("competitors")}>Competitor profiles <span>{props.data.competitors.length}</span></button>
      </div><label className="m-support-record-search"><Search size={16} aria-hidden="true" /><span className="m-sr-only">Search customer and competitor records</span><input value={query} onChange={(event) => setQuery(event.target.value)} maxLength={120} placeholder="Search records" /></label></div>
      {view === "accounts" ? <section className="m-support-records" aria-label="Buyer accounts">
        {props.data.buyers.length === 0 ? <div className="m-support-blank" aria-label="No buyer accounts"><span className="m-support-empty-icon"><Building2 size={18} /></span><h2>No buyer accounts yet</h2><p>Explore public research to build an evidence-led view of an organisation. Buyer accounts appear here once they have been recorded in your workspace.</p><button onClick={() => props.navigate("discover")}>Explore research <ArrowRight size={15} /></button></div> : !buyers.length ? <div className="m-support-blank"><h2>No matching customers</h2><p>Try a different name, sector or region.</p></div> : buyers.map((buyer) => {
          const linked = props.data.opportunities.filter((o) => o.buyer_name === buyer.buyer_name);
          return <article className="m-support-record" key={buyer.id}>
            <div className="m-support-record-main"><div className="m-support-record-title"><span className="m-support-avatar"><Building2 size={18}/></span><div><h2>{buyer.buyer_name}</h2><p>{buyer.sector} · {buyer.region} · {buyer.estate_size || "Estate size unknown"}</p></div></div>
              <div className="m-support-record-context"><div><h3>Procurement drivers</h3>{buyer.procurement_drivers.length ? <ul>{buyer.procurement_drivers.map((v) => <li key={v}>{v}</li>)}</ul> : <p>Not recorded</p>}</div><div><h3>Next relationship action</h3><p>{buyer.next_best_action || "No action recorded"}</p></div></div>
            </div><div className="m-support-record-side"><h3>Related opportunities</h3>{linked.length ? linked.map((o) => <button key={o.id} onClick={() => props.inspect(o.id)}>{o.name}<ArrowUpRight size={15}/></button>) : <p>None recorded</p>}</div>
          </article>;
        })}
      </section> : <section className="m-support-records" aria-label="Competitor profiles">
        {props.data.competitors.length === 0 ? <div className="m-support-blank" aria-label="No competitor profiles"><span className="m-support-empty-icon"><UsersRound size={18} /></span><h2>No competitor profiles yet</h2><p>Profiles appear here when competitor information has been added to your workspace.</p></div> : !competitors.length ? <div className="m-support-blank"><h2>No matching competitors</h2><p>Try a different name or sector.</p></div> : competitors.map((competitor) => <article className="m-support-record" key={competitor.id}><div className="m-support-record-main"><div className="m-support-record-title"><span className="m-support-avatar"><UsersRound size={18}/></span><div><h2>{competitor.name}</h2><p>{competitor.sectors.join(" · ") || "Sectors not recorded"} · Participation unconfirmed</p></div></div><div className="m-support-record-context"><div><h3>Recorded strengths</h3>{competitor.strengths.length ? <ul>{competitor.strengths.map((v) => <li key={v}>{v}</li>)}</ul> : <p>Not recorded</p>}</div><div><h3>Limitations and pricing</h3><p>{competitor.weaknesses.join("; ") || "Not recorded"}</p><p>{competitor.pricing_behaviour}</p></div></div></div><div className="m-support-record-side"><h3>Response hypothesis</h3><p>{competitor.counter_strategy || "Not recorded"}</p></div></article>)}
      </section>}
    </div>
  );
}
