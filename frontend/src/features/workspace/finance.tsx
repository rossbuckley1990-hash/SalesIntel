"use client";
import { useEffect, useRef, useState } from "react";
import { ArrowRight, ArrowUpRight, RotateCcw, Save } from "lucide-react";
import dynamic from "next/dynamic";
import { dateLabel, fieldLabel, money, mutate, request } from "./api";
import { Badge, Button, Heading, Loading, Metric, SectionHeading } from "./ui";
import type {
  Asset,
  Scenario,
  ScenarioInputs,
  ScenarioResult,
  SharedProps,
  Snapshot,
} from "./types";

const FinancialScene = dynamic(
  () => import("../field/financial-scene").then((m) => m.FinancialScene),
  {
    ssr: false,
    loading: () => <Loading label="Preparing financial geometry" />,
  },
);

function defaults(props: SharedProps, id: number): ScenarioInputs {
  const opportunity = props.data.opportunities.find((o) => o.id === id);
  return {
    annual_revenue:
      opportunity?.financials.estimated_annual_revenue?.toString() || "",
    baseline_share: "0.40",
    proposed_share: "0.70",
    inhouse_cost_ratio: "0.62",
    subcontract_cost_ratio: "0.84",
    probability: opportunity?.financials.probability?.toString() ?? "",
    bid_cost: "12000",
    mobilisation_cost: "18000",
    payment_delay_days: 30,
    start_month:
      opportunity?.forecast_start_month || props.data.as_of.slice(0, 7),
    financial_year_start: props.data.finance.financial_year_start,
    assumption_note:
      "Hypothetical 40% to 70% self-delivery model. Cost ratios, bid spend and mobilisation require Operations and Finance validation.",
    source_references: opportunity ? [`opportunity:${opportunity.id}`] : [],
  };
}

export function Finance(props: SharedProps & { selfDelivery?: boolean }) {
  const [tab, setTab] = useState("scenario");
  return (
    <>
      <Heading
        eyebrow={
          props.selfDelivery
            ? "Self-Delivery / Find the missing margin"
            : `Finance / FY ${props.data.finance.financial_year}`
        }
        title={
          props.selfDelivery
            ? "Bring the value closer to home."
            : "Understand the financial move."
        }
        description="Explore a defensible scenario. Keep assumptions visible. Save only when you decide."
      />
      <div className="m-pulse">
        <Metric
          label="Secured revenue"
          value={money(props.data.finance.secured_revenue, true)}
          detail="Recorded won work · FY basis"
        />
        <Metric
          label="Weighted open revenue"
          value={money(props.data.finance.open_weighted_revenue, true)}
          detail="FY value × probability"
        />
        <Metric
          label="Risk adjusted open"
          value={money(props.data.finance.risk_adjusted_revenue, true)}
          detail="Recorded risk adjustment applied"
        />
        <Metric
          label="LE1 revenue"
          value={money(props.data.finance.forecast_to_financial_year_end, true)}
          detail="Secured + risk adjusted open"
          tone="accent"
        />
      </div>
      <div className="m-tabs" role="tablist" aria-label="Finance views">
        {[
          ["scenario", "Scenario Lab"],
          ["forecast", "LE1 forecast"],
          ["changes", "Change ledger"],
        ].map(([value, label]) => (
          <button
            role="tab"
            aria-selected={tab === value}
            key={value}
            className={tab === value ? "active" : ""}
            onClick={() => setTab(value)}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === "scenario" && <ScenarioLab {...props} />}
      {tab === "forecast" && <Forecast {...props} />}
      {tab === "changes" && <Changes {...props} />}
    </>
  );
}

function ScenarioLab(props: SharedProps) {
  const initialId = props.selectedId || props.data.opportunities[0]?.id || 0;
  const [id, setId] = useState(initialId);
  const [inputs, setInputs] = useState<ScenarioInputs>(() =>
    defaults(props, initialId),
  );
  const [result, setResult] = useState<ScenarioResult | null>(null);
  const [calculating, setCalculating] = useState(false);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState<Scenario[]>([]);
  const [savedId, setSavedId] = useState<number | null>(null);
  const [name, setName] = useState("Self-delivery capture scenario");
  const [owner, setOwner] = useState(
    props.data.opportunities.find((o) => o.id === initialId)?.owner ||
      "Local reviewer",
  );
  const [spatial, setSpatial] = useState(false);
  const requestKey = JSON.stringify(inputs);
  const computedKey = useRef("");
  useEffect(() => {
    const abort = new AbortController();
    request<Scenario[]>("/scenarios", { signal: abort.signal })
      .then(setSaved)
      .catch((e) => {
        if (!abort.signal.aborted) setError(e.message);
      });
    return () => abort.abort();
  }, []);
  useEffect(() => {
    const abort = new AbortController();
    setCalculating(true);
    setError("");
    const timer = setTimeout(() => {
      if (!inputs.annual_revenue || !inputs.probability) {
        setResult(null);
        setCalculating(false);
        setError(
          "Enter annual revenue and probability explicitly; unknown values are not zero.",
        );
        return;
      }
      request<ScenarioResult>("/scenarios/calculate", {
        method: "POST",
        body: requestKey,
        signal: abort.signal,
      })
        .then((r) => {
          computedKey.current = requestKey;
          setResult(r);
          setCalculating(false);
        })
        .catch((e) => {
          if (!abort.signal.aborted) {
            setError(e.message);
            setResult(null);
            setCalculating(false);
          }
        });
    }, 180);
    return () => {
      clearTimeout(timer);
      abort.abort();
    };
  }, [requestKey, inputs.annual_revenue, inputs.probability]);
  function update<K extends keyof ScenarioInputs>(
    key: K,
    value: ScenarioInputs[K],
  ) {
    setSavedId(null);
    setInputs((v) => ({ ...v, [key]: value }));
  }
  function select(value: number) {
    setId(value);
    setInputs(defaults(props, value));
    setSavedId(null);
    setOwner(
      props.data.opportunities.find((o) => o.id === value)?.owner ||
        "Local reviewer",
    );
  }
  async function save() {
    if (computedKey.current !== requestKey) return;
    setSaving(true);
    try {
      const s = await mutate<Scenario>("/scenarios", {
        opportunity_id: id,
        name,
        owner,
        inputs,
      });
      setSaved((v) => [s, ...v]);
      setSavedId(s.id);
      await props.refresh();
      props.notify(
        "Scenario saved with its inputs, source references and calculation version.",
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }
  async function businessCase() {
    if (!savedId) return;
    setSaving(true);
    try {
      await mutate<Asset>("/assets", {
        kind: "self_delivery",
        opportunity_id: id,
        scenario_id: savedId,
      });
      await props.refresh();
      props.notify(
        "Self-delivery business case created from the saved scenario.",
      );
      props.navigate("assets", id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }
  const percentControl = (
    key:
      | "baseline_share"
      | "proposed_share"
      | "inhouse_cost_ratio"
      | "subcontract_cost_ratio"
      | "probability",
    label: string,
  ) => (
    <label className="m-slider">
      <span>
        {label}
        <output>
          {inputs[key] === ""
            ? "Unknown"
            : `${Math.round(Number(inputs[key]) * 100)}%`}
        </output>
      </span>
      <input
        aria-label={label}
        type="range"
        min="0"
        max="100"
        step="1"
        value={Number(inputs[key]) * 100}
        onChange={(e) => update(key, (Number(e.target.value) / 100).toFixed(2))}
      />
    </label>
  );
  const moneyControl = (
    key: "annual_revenue" | "bid_cost" | "mobilisation_cost",
    label: string,
  ) => (
    <label>
      {label}
      <div className="m-input-prefix">
        <span>£</span>
        <input
          aria-label={label}
          type="number"
          min="0"
          max="1000000000000"
          step="0.01"
          value={inputs[key]}
          onChange={(e) => update(key, e.target.value)}
        />
      </div>
    </label>
  );
  return (
    <div className="m-lab">
      <aside className="m-lab-controls m-form">
        <label>
          Opportunity
          <select value={id} onChange={(e) => select(Number(e.target.value))}>
            {props.data.opportunities.map((o) => (
              <option key={o.id} value={o.id}>
                {o.buyer_name}
              </option>
            ))}
          </select>
        </label>
        <div className="m-divider" />
        <div className="m-between">
          <h3>Delivery mix</h3>
          <Badge tone="amber">Hypothesis</Badge>
        </div>
        {percentControl("baseline_share", "Baseline self-delivery")}
        {percentControl("proposed_share", "Proposed self-delivery")}
        <div className="m-divider" />
        <h3>Commercial assumptions</h3>
        {moneyControl("annual_revenue", "Annual revenue")}
        {percentControl("inhouse_cost_ratio", "In-house cost / revenue")}
        {percentControl("subcontract_cost_ratio", "Subcontract cost / revenue")}
        {percentControl("probability", "Probability of award")}
        <div className="m-form-grid">
          {moneyControl("bid_cost", "Bid spend")}
          {moneyControl("mobilisation_cost", "Mobilisation")}
        </div>
        <div className="m-form-grid">
          <label>
            Service starts
            <input
              type="month"
              value={inputs.start_month}
              onChange={(e) => update("start_month", e.target.value)}
            />
          </label>
          <label>
            Payment delay days
            <input
              type="number"
              min="0"
              max="365"
              value={inputs.payment_delay_days}
              onChange={(e) =>
                update("payment_delay_days", Number(e.target.value))
              }
            />
          </label>
        </div>
        <Button
          kind="quiet"
          onClick={() => {
            setInputs(defaults(props, id));
            setSavedId(null);
          }}
        >
          <RotateCcw size={15} /> Reset assumptions
        </Button>
      </aside>
      <div className="m-lab-main">
        <div className="m-between">
          <div>
            <p className="m-eyebrow">
              Financial scenario / Reversible exploration
            </p>
            <h2>
              A different delivery mix.
              <br />A measurable difference.
            </h2>
          </div>
          <Badge tone={savedId ? "green" : "amber"}>
            {savedId ? "Saved scenario" : "Unsaved exploration"}
          </Badge>
        </div>
        {error && (
          <p className="m-error" role="alert">
            {error}
          </p>
        )}
        {result && (
          <>
            <div
              className="m-scenario-hero"
              aria-live="polite"
              aria-busy={calculating}
            >
              <span>Change in annual gross margin</span>
              <strong>
                {Number(result.delta_gross_margin) > 0 ? "+" : ""}
                {money(result.delta_gross_margin)}
              </strong>
              <p>
                {calculating
                  ? "Recalculating from changed inputs…"
                  : "Modelled potential · not realised savings"}
              </p>
            </div>
            <div className="m-between">
              <p className="m-eyebrow">Cost and margin structure</p>
              <Button kind="quiet" onClick={() => setSpatial((v) => !v)}>
                {spatial ? "Show 2D structure" : "Explore in 3D"}
              </Button>
            </div>
            {spatial ? (
              <FinancialScene result={result} />
            ) : (
              <div className="m-financial-structure">
                {[
                  ["Baseline", result.baseline],
                  ["Proposed", result.proposed],
                ].map(([label, c]) => {
                  const value = c as ScenarioResult["baseline"];
                  const revenue = Math.max(Number(value.annual_revenue), 1);
                  return (
                    <div className="m-financial-row" key={label as string}>
                      <div className="m-between">
                        <strong>{label as string}</strong>
                        <span>{money(value.gross_margin)} gross margin</span>
                      </div>
                      <div
                        className="m-value-stack"
                        role="img"
                        aria-label={`${label}: in-house cost ${money(value.inhouse_cost)}, subcontract cost ${money(value.subcontract_cost)}, gross margin ${money(value.gross_margin)}`}
                      >
                        <span
                          className="internal"
                          style={{
                            width: `${(Number(value.inhouse_cost) / revenue) * 100}%`,
                          }}
                        />
                        <span
                          className="external"
                          style={{
                            width: `${(Number(value.subcontract_cost) / revenue) * 100}%`,
                          }}
                        />
                        <span
                          className="margin"
                          style={{
                            width: `${(Number(value.gross_margin) / revenue) * 100}%`,
                          }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
            <div className="m-legend">
              <span>
                <i className="internal" />
                In-house cost
              </span>
              <span>
                <i className="external" />
                Subcontract cost
              </span>
              <span>
                <i className="margin" />
                Gross margin
              </span>
            </div>
            <div className="m-scenario-comparison">
              <Metric
                label="Baseline expected contribution"
                value={money(result.baseline.expected_contribution)}
                detail="Probability × GM − bid spend"
              />
              <Metric
                label="Proposed expected contribution"
                value={money(result.proposed.expected_contribution)}
                detail="Probability × (GM − mobilisation) − bid"
                tone="accent"
              />
              <Metric
                label="Working capital proxy"
                value={money(result.proposed.working_capital_proxy)}
                detail="Annual delivery cost × delay / 365"
              />
            </div>
            <details className="m-calculation">
              <summary>
                Calculation, sensitivity and financial-year phasing
              </summary>
              <p>{result.formula}</p>
              <table className="m-table">
                <thead>
                  <tr>
                    <th>In-house cost ratio</th>
                    <th>Annual GM</th>
                    <th>Expected contribution</th>
                  </tr>
                </thead>
                <tbody>
                  {result.sensitivity.map((s, i) => (
                    <tr key={i}>
                      <td>
                        {(Number(s.inhouse_cost_ratio) * 100).toFixed(0)}%
                      </td>
                      <td>{money(s.gross_margin)}</td>
                      <td>{money(s.expected_contribution)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p>
                FY revenue from this twelve-month service period:{" "}
                {money(result.financial_year_revenue)}.
              </p>
              <table className="m-table">
                <thead>
                  <tr>
                    <th>Month</th>
                    <th>Unweighted revenue</th>
                    <th>Unweighted margin</th>
                  </tr>
                </thead>
                <tbody>
                  {result.monthly.map((m) => (
                    <tr key={m.month}>
                      <td>{m.month}</td>
                      <td>{money(m.revenue)}</td>
                      <td>{money(m.gross_margin)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>
            <div className="m-assumptions">
              <h3>What must be true</h3>
              <ul className="m-list">
                {result.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            </div>
          </>
        )}
        {!result && calculating && <Loading label="Calculating the scenario" />}
        <div className="m-form m-save-scenario">
          <SectionHeading
            title="Keep this scenario"
            detail="Save the exact inputs and calculation. Source opportunity values stay unchanged."
          />
          <div className="m-form-grid">
            <label>
              Scenario name
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={160}
              />
            </label>
            <label>
              Accountable owner
              <input
                value={owner}
                onChange={(e) => setOwner(e.target.value)}
                maxLength={120}
              />
            </label>
          </div>
          <label>
            Assumptions and evidence
            <textarea
              value={inputs.assumption_note}
              onChange={(e) => update("assumption_note", e.target.value)}
              minLength={10}
              maxLength={4000}
            />
          </label>
          <div className="m-wrap">
            <Button
              kind="primary"
              onClick={() => void save()}
              disabled={
                saving ||
                calculating ||
                !result ||
                name.length < 3 ||
                owner.length < 2
              }
            >
              <Save size={16} /> Save scenario
            </Button>
            <Button
              onClick={() => void businessCase()}
              disabled={!savedId || saving}
            >
              Build business case <ArrowUpRight size={16} />
            </Button>
          </div>
          {saved.filter((s) => s.opportunity_id === id).length > 0 && (
            <label>
              Reopen a saved scenario
              <select
                value={savedId || ""}
                onChange={(e) => {
                  const s = saved.find((v) => v.id === Number(e.target.value));
                  if (s) {
                    setInputs(s.assumptions);
                    setName(s.name);
                    setOwner(s.owner);
                    setSavedId(s.id);
                  }
                }}
              >
                <option value="">Choose a saved scenario</option>
                {saved
                  .filter((s) => s.opportunity_id === id)
                  .map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} · {dateLabel(s.created_at)}
                    </option>
                  ))}
              </select>
            </label>
          )}
        </div>
      </div>
    </div>
  );
}

function Forecast(props: SharedProps) {
  const [busy, setBusy] = useState(false);
  async function build() {
    setBusy(true);
    try {
      await mutate("/assets", { kind: "forecast" });
      await props.refresh();
      props.navigate("assets");
      props.notify(
        "LE1 pack created with sources, movement and a financial workbook export.",
      );
    } catch (e) {
      props.notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="m-surface">
      <SectionHeading
        title="The recorded LE1 position"
        detail="Existing backend calculations. Definitions await Finance approval for operational use."
      >
        <Button onClick={() => void build()} disabled={busy}>
          Build forecast pack <ArrowUpRight size={15} />
        </Button>
      </SectionHeading>
      <table className="m-table">
        <thead>
          <tr>
            <th>Month</th>
            <th>Forecast revenue</th>
            <th>Forecast margin</th>
          </tr>
        </thead>
        <tbody>
          {props.data.finance.monthly_revenue.map((r, i) => (
            <tr key={r.month}>
              <td>{r.month}</td>
              <td>{money(r.value)}</td>
              <td>{money(props.data.finance.monthly_margin[i].value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="m-notice">
        <span>
          Secured work, weighted pipeline, risk adjustments and source finance
          records are also available in the{" "}
          <a href="/classic">classic LE1 module</a>. Exports preserve these
          separate bases.
        </span>
      </div>
    </section>
  );
}

function Changes(props: SharedProps) {
  const [label, setLabel] = useState("");
  const [reviewer, setReviewer] = useState("Local reviewer");
  const [busy, setBusy] = useState(false);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [index, setIndex] = useState(0);
  useEffect(() => {
    request<Snapshot[]>("/snapshots")
      .then((s) => {
        setSnapshots(s.reverse());
        setIndex(Math.max(0, s.length - 1));
      })
      .catch((e) => props.notify(e.message, true));
  }, [props.data.changes.current?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  async function snapshot() {
    setBusy(true);
    try {
      await mutate("/snapshots", { label, reviewer });
      await props.refresh();
      setLabel("");
      props.notify("Current portfolio accepted as a timestamped snapshot.");
    } catch (e) {
      props.notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="m-surface">
      <SectionHeading
        title="A traceable change in position"
        detail={props.data.changes.message}
      />
      <div className="m-snapshot-pair">
        <span>
          {props.data.changes.previous?.label || "Previous snapshot missing"}
        </span>
        <ArrowRight size={19} />
        <span>
          {props.data.changes.current?.label || "Current snapshot missing"}
        </span>
      </div>
      <table className="m-table">
        <thead>
          <tr>
            <th>Opportunity</th>
            <th>Changed field</th>
            <th>Previous</th>
            <th>Current</th>
          </tr>
        </thead>
        <tbody>
          {props.data.changes.changes.map((m, i) => (
            <tr key={i}>
              <td>
                <button
                  className="m-table-title"
                  onClick={() => props.inspect(m.opportunity_id)}
                >
                  {m.name}
                </button>
              </td>
              <td>{fieldLabel(m.field)}</td>
              <td>{m.before ?? "Unknown"}</td>
              <td>{m.after ?? "Unknown"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {snapshots.length > 0 && (
        <section className="m-snapshot-playback">
          <h3>Inspect the saved position</h3>
          <label className="m-slider">
            <span>
              {snapshots[index]?.label}
              <output>
                {index + 1} / {snapshots.length}
              </output>
            </span>
            <input
              aria-label="Snapshot playback"
              type="range"
              min={0}
              max={snapshots.length - 1}
              value={index}
              onChange={(e) => setIndex(Number(e.target.value))}
            />
          </label>
          <p className="m-muted">
            Captured {snapshots[index]?.captured_at} ·{" "}
            {snapshots[index]?.reviewer}
          </p>
          <div className="m-mini-pulse">
            <Metric
              label="Saved LE1 revenue"
              value={money(
                snapshots[index]?.payload?.finance
                  .forecast_to_financial_year_end,
              )}
              detail="Snapshot value"
            />
            <Metric
              label="Saved records"
              value={String(
                snapshots[index]?.payload?.opportunities.length ?? 0,
              )}
              detail="Underlying opportunity records"
            />
          </div>
        </section>
      )}
      <div className="m-form">
        <h3>Accept a new snapshot</h3>
        <p className="m-muted m-small">
          This records the current position for future comparison; it is not a
          claim that the source data is verified.
        </p>
        <div className="m-form-grid">
          <label>
            Snapshot label
            <input
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="Pipeline review 24 October"
              maxLength={160}
            />
          </label>
          <label>
            Reviewer
            <input
              value={reviewer}
              onChange={(e) => setReviewer(e.target.value)}
            />
          </label>
        </div>
        <Button
          onClick={() => void snapshot()}
          disabled={busy || label.trim().length < 3 || reviewer.length < 2}
        >
          Accept current snapshot
        </Button>
      </div>
    </section>
  );
}
