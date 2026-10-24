"use client";
import { useState } from "react";
import { ArrowUpRight, Building2 } from "lucide-react";
import { Badge, Button, Heading, SectionHeading } from "./ui";
import type { SharedProps } from "./types";

export function Accounts(props: SharedProps) {
  const [view, setView] = useState("accounts");
  return (
    <>
      <Heading
        eyebrow="Accounts / Relationships with context"
        title="Know who is on the other side."
        description="Buyer priorities and competitor profiles, with the limits of the evidence in view."
      />
      <div className="m-tabs" role="tablist" aria-label="Account views">
        <button
          role="tab"
          aria-selected={view === "accounts"}
          className={view === "accounts" ? "active" : ""}
          onClick={() => setView("accounts")}
        >
          Buyer accounts
        </button>
        <button
          role="tab"
          aria-selected={view === "competitors"}
          className={view === "competitors" ? "active" : ""}
          onClick={() => setView("competitors")}
        >
          Competitor profiles
        </button>
      </div>
      <div className="m-account-grid">
        {view === "accounts"
          ? props.data.buyers.map((buyer) => (
              <article className="m-account" key={buyer.id}>
                <div className="m-between">
                  <Building2 size={22} strokeWidth={1.3} />
                  <Badge>{buyer.sector}</Badge>
                </div>
                <h2>{buyer.buyer_name}</h2>
                <p>
                  {buyer.region} · {buyer.estate_size || "Estate size unknown"}
                </p>
                <SectionHeading title="Procurement drivers" />
                <ul className="m-list">
                  {buyer.procurement_drivers.map((v) => (
                    <li key={v}>{v}</li>
                  ))}
                </ul>
                <h3>Next relationship action</h3>
                <p>{buyer.next_best_action}</p>
                <footer>
                  {props.data.opportunities
                    .filter((o) => o.buyer_name === buyer.buyer_name)
                    .map((o) => (
                      <Button
                        key={o.id}
                        kind="quiet"
                        onClick={() => props.inspect(o.id)}
                      >
                        {o.name}
                        <ArrowUpRight size={15} />
                      </Button>
                    ))}
                </footer>
              </article>
            ))
          : props.data.competitors.map((competitor) => (
              <article className="m-account" key={competitor.id}>
                <Badge>Recorded profile · participation unconfirmed</Badge>
                <h2>{competitor.name}</h2>
                <p>{competitor.sectors.join(" · ")}</p>
                <h3>Recorded strengths</h3>
                <ul className="m-list">
                  {competitor.strengths.map((v) => (
                    <li key={v}>{v}</li>
                  ))}
                </ul>
                <h3>Limitations and pricing</h3>
                <p>{competitor.weaknesses.join("; ")}</p>
                <p>{competitor.pricing_behaviour}</p>
                <h3>Response hypothesis</h3>
                <p>{competitor.counter_strategy}</p>
              </article>
            ))}
      </div>
    </>
  );
}
