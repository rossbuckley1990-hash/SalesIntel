"use client";
import {
  ArrowRight,
  ArrowUpRight,
  CircleDot,
  FileText,
  Layers3,
  MoveUpRight,
} from "lucide-react";
import { dateLabel, fieldLabel, money } from "./api";
import { DailyResearchBrief } from "./daily-research-brief";
import {
  Badge,
  Button,
  Metric,
  OpenLink,
  SectionHeading,
  Sparkline,
} from "./ui";
import type { SharedProps } from "./types";

export function Today({ data, navigate, inspect }: SharedProps) {
  const moves = [...data.actions]
    .filter((a) => a.status !== "completed")
    .sort(
      (a, b) =>
        (a.due_date || "9999").localeCompare(b.due_date || "9999") ||
        (a.priority === "high" ? -1 : 1),
    )
    .slice(0, 3);
  const atRisk = data.opportunities.filter(
    (o) =>
      o.risk_rating.toLowerCase() === "red" &&
      !["Won", "Lost"].includes(o.stage),
  );
  const date = new Intl.DateTimeFormat("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
    timeZone: "Europe/London",
  }).format(new Date(data.as_of));
  const focus = [...data.opportunities]
    .filter((o) => !["Won", "Lost"].includes(o.stage))
    .sort(
      (a, b) =>
        (b.financials.weighted_contract_value ?? -1) -
        (a.financials.weighted_contract_value ?? -1),
    )[0];
  return (
    <>
      <header className="p-today-header">
        <div><p className="p-today-date">{date} <span> / </span> YOUR WORKSPACE</p><h1>Your priorities<span>.</span></h1><p>Recent intelligence and the follow-ups you have chosen.</p></div>
        <button onClick={() => navigate("discover")} className="p-today-discover">Explore opportunities <ArrowUpRight size={16} /></button>
      </header>
      <DailyResearchBrief navigate={navigate} />
      <div className="m-today-legacy">
      <section className="m-pulse" aria-label="Commercial pulse">
        <Metric
          label="Weighted open pipeline"
          value={money(data.pulse.weighted_contract_value.value, true)}
          detail={`Whole contract basis · ${data.pulse.weighted_contract_value.unknown} unknown`}
        />
        <Metric
          label={`LE1 revenue · FY ${data.finance.financial_year}`}
          value={money(data.finance.forecast_to_financial_year_end, true)}
          detail="Secured + risk adjusted open"
        />
        <Metric
          label="Open annual gross margin"
          value={money(data.pulse.estimated_gross_margin.value, true)}
          detail="Unweighted estimates · not realised"
          tone="accent"
        />
        <Metric
          label="Opportunities needing attention"
          value={String(atRisk.length).padStart(2, "0")}
          detail="Recorded red risk · active pipeline"
        />
      </section>
      <div className="m-today-top">
        <section className="m-focus-panel">
          <div className="m-focus-copy">
            <p className="m-eyebrow">
              <span className="m-live-dot" /> The intelligence field
            </p>
            <h2>
              See how the
              <br />
              opportunity fits together.
            </h2>
            <p>
              Follow the evidence. Surface the gaps.
              <br />
              Turn a commercial question into a pursuit.
            </p>
            <Button onClick={() => navigate("field", focus?.id)}>
              Enter the field <ArrowRight size={17} />
            </Button>
            <small>
              Connected to {data.opportunities.length} saved opportunities
            </small>
          </div>
          <div className="m-focus-composition" aria-hidden="true">
            <div className="m-orbital-ring ring-one" />
            <div className="m-orbital-ring ring-two" />
            <div className="m-orbital-ring ring-three" />
            <div className="m-focus-core">
              <Layers3 size={34} strokeWidth={1} />
              <span>INTELLIGENCE</span>
              <strong>
                {data.opportunities.length.toString().padStart(2, "0")}
              </strong>
            </div>
            <span className="m-float-label label-a">
              <CircleDot size={12} /> Evidence
            </span>
            <span className="m-float-label label-b">
              <CircleDot size={12} /> Delivery
            </span>
            <span className="m-float-label label-c">
              <CircleDot size={12} /> Value
            </span>
          </div>
        </section>
        <section className="m-forecast-preview">
          <div className="m-between">
            <p className="m-eyebrow">The forward view</p>
            <Badge tone="green">FY {data.finance.financial_year}</Badge>
          </div>
          <h2>{money(data.finance.secured_revenue, true)}</h2>
          <p>Secured revenue in the recorded forecast</p>
          <Sparkline
            values={data.finance.monthly_revenue.map((v) => v.value)}
            label="Monthly LE1 revenue profile from April to March"
          />
          <div className="m-between m-muted">
            <small>APR</small>
            <small>MAR</small>
          </div>
          <div className="m-divider" />
          <div className="m-between">
            <span className="m-small">
              {data.finance.margin_warnings.length} margin items to review
            </span>
            <OpenLink onClick={() => navigate("finance")}>
              Open Finance
            </OpenLink>
          </div>
        </section>
      </div>
      <section className="m-moves">
        <SectionHeading
          title="The three moves"
          detail="Open actions, ordered by due date. Start where time matters."
        >
          <OpenLink onClick={() => navigate("actions")}>All actions</OpenLink>
        </SectionHeading>
        {moves.length > 0 && <div className="m-move-grid">
          {moves.map((action, index) => {
            const opportunity = data.opportunities.find(
              (o) => o.id === action.related_opportunity_id,
            );
            return (
              <article className="m-move" key={action.id}>
                <div className="m-between">
                  <span className="m-step">0{index + 1}</span>
                  <Badge
                    tone={action.priority === "high" ? "amber" : "neutral"}
                  >
                    Due {dateLabel(action.due_date)}
                  </Badge>
                </div>
                <p className="m-kicker">
                  {opportunity?.buyer_name || action.category}
                </p>
                <h3>{action.recommended_action}</h3>
                <p>{action.reason}</p>
                <div className="m-move-value">
                  <strong>
                    {money(
                      opportunity?.financials.estimated_gross_margin,
                      true,
                    )}
                  </strong>
                  <span>potential annual margin</span>
                </div>
                <footer>
                  <span className="m-owner">
                    <span>
                      {action.owner
                        .split(" ")
                        .map((s) => s[0])
                        .slice(0, 2)
                        .join("")}
                    </span>
                    {action.owner}
                  </span>
                  <button
                    className="m-icon-button"
                    aria-label={`Review ${opportunity?.buyer_name || action.category}`}
                    onClick={() =>
                      action.related_opportunity_id
                        ? inspect(action.related_opportunity_id)
                        : navigate("actions")
                    }
                  >
                    <ArrowUpRight size={19} />
                  </button>
                </footer>
              </article>
            );
          })}
        </div>}
        {moves.length === 0 && (
          <p className="p-compact-empty">No open pursuit actions. Create a pursuit decision to assign the next move.</p>
        )}
      </section>
      <div className="m-bottom-grid">
        <section>
          <SectionHeading
            title="What changed"
            detail={
              data.changes.current
                ? `Accepted snapshots · ${data.changes.previous?.label || "Awaiting baseline"}`
                : "An honest record of movement"
            }
          >
            <OpenLink onClick={() => navigate("finance")}>Compare</OpenLink>
          </SectionHeading>
          <div className="m-ledger">
            {data.changes.changes.slice(0, 4).map((change, i) => (
              <button
                key={i}
                className="m-ledger-row"
                onClick={() => inspect(change.opportunity_id)}
              >
                <span className="m-ledger-icon">
                  <MoveUpRight size={17} />
                </span>
                <span>
                  <strong>{change.name}</strong>
                  <small>
                    {fieldLabel(change.field)}{" "}
                    <span className="m-strike">
                      {change.before ?? "Unknown"}
                    </span>{" "}
                    → {change.after ?? "Unknown"}
                  </small>
                </span>
                <ArrowUpRight size={15} />
              </button>
            ))}
            {!data.changes.changes.length && (
              <p className="m-muted m-pad">{data.changes.message}</p>
            )}
          </div>
          <p className="m-footnote">
            Compared saved states. No overnight or live-market claim.
          </p>
        </section>
        <section>
          <SectionHeading
            title="Recently created"
            detail="Your intelligence, made useful."
          >
            <OpenLink onClick={() => navigate("assets")}>Asset Studio</OpenLink>
          </SectionHeading>
          {data.assets.length ? (
            <div className="m-ledger">
              {data.assets.slice(0, 4).map((asset) => (
                <button
                  key={asset.id}
                  className="m-ledger-row"
                  onClick={() =>
                    navigate("assets", asset.opportunity_id ?? undefined)
                  }
                >
                  <span className="m-ledger-icon">
                    <FileText size={18} />
                  </span>
                  <span>
                    <strong>{asset.title}</strong>
                    <small>
                      Version {asset.version} · {asset.review_status} ·{" "}
                      {dateLabel(asset.created_at)}
                    </small>
                  </span>
                  <ArrowUpRight size={15} />
                </button>
              ))}
            </div>
          ) : (
            <div className="p-asset-empty">
              <h3>Your next decision deserves a better brief.</h3>
              <p>Build a dossier from saved evidence, risks and actions.</p>
              <button className="p-link" onClick={() => navigate("assets", focus?.id)}>Create your first asset <ArrowUpRight size={15} /></button>
            </div>
          )}
        </section>
      </div>
      </div>
    </>
  );
}
