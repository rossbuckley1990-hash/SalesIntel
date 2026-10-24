"use client";
import { useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import {
  ArrowUpRight,
  Box,
  FileText,
  Layers3,
  RotateCcw,
  ShieldAlert,
  Undo2,
} from "lucide-react";
import { fieldLabel, mutate, request } from "../workspace/api";
import { Badge, Button, Empty, Heading, Loading } from "../workspace/ui";
import type { Asset, Detail, SharedProps } from "../workspace/types";
import { commercialGraph, type FieldNode, type Metric } from "./graph";
import type { FieldCommand } from "./field-canvas";

const FieldCanvas = dynamic(
  () => import("./field-canvas").then((m) => m.FieldCanvas),
  { ssr: false, loading: () => <Loading label="Loading the spatial engine" /> },
);

export function IntelligenceField(props: SharedProps) {
  const [id, setId] = useState<number | null>(props.selectedId);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [metric, setMetric] = useState<Metric>("estimated_gross_margin");
  const [mode, setMode] = useState<"spatial" | "data">("spatial");
  const [fallback, setFallback] = useState(false);
  const [reduced, setReduced] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [command, setCommand] = useState<FieldCommand>();
  const [busy, setBusy] = useState(false);
  const [asset, setAsset] = useState<Asset | null>(null);
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => {
      setReduced(media.matches);
      if (media.matches) setMode("data");
    };
    update();
    if (window.innerWidth < 850) setMode("data");
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  useEffect(() => {
    setError("");
    setAsset(null);
    setSelected(id ? `opportunity:${id}` : null);
    if (!id) {
      setDetail(null);
      return;
    }
    setLoading(true);
    const abort = new AbortController();
    request<Detail>(`/opportunities/${id}`, { signal: abort.signal })
      .then(setDetail)
      .catch((e) => {
        if (!abort.signal.aborted) setError(e.message);
      })
      .finally(() => {
        if (!abort.signal.aborted) setLoading(false);
      });
    return () => abort.abort();
  }, [id]);
  const graph = useMemo(
    () => commercialGraph(props.data.opportunities, id ? detail : null, metric),
    [props.data.opportunities, detail, id, metric],
  );
  const selectedNode =
    graph.nodes.find((node) => node.id === selected) || graph.nodes[0];
  function pick(nodeId: string) {
    setSelected(nodeId);
    const node = graph.nodes.find((v) => v.id === nodeId);
    if (!id && node?.kind === "opportunity") setId(node.recordId);
  }
  function act(value: FieldCommand["mode"]) {
    setCommand({ mode: value, key: Date.now() });
  }
  async function build() {
    if (!id) return;
    setBusy(true);
    act("pack");
    try {
      const next = await mutate<Asset>("/assets", {
        kind: "dossier",
        opportunity_id: id,
      });
      setAsset(next);
      await props.refresh();
      props.notify(
        "Pursuit pack created from the selected opportunity and its evidence.",
      );
    } catch (e) {
      setError((e as Error).message);
      act("assemble");
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Heading
        eyebrow="The Living Intelligence Field / Connected commercial records"
        title="Intelligence you can get hold of."
        description="Select an opportunity. Follow its evidence. Make the move."
      >
        <div className="m-segmented" aria-label="Field view">
          <button
            aria-pressed={mode === "spatial"}
            onClick={() => {
              setFallback(false);
              setMode("spatial");
            }}
          >
            <Box size={15} /> Spatial
          </button>
          <button
            aria-pressed={mode === "data"}
            onClick={() => setMode("data")}
          >
            Accessible data view
          </button>
        </div>
      </Heading>
      <div className="m-field-toolbar">
        <label>
          Focus
          <select
            aria-label="Field focus"
            value={id || ""}
            onChange={(e) => {
              setDetail(null);
              setId(e.target.value ? Number(e.target.value) : null);
            }}
          >
            <option value="">Whole opportunity field</option>
            {props.data.opportunities.map((o) => (
              <option key={o.id} value={o.id}>
                {o.buyer_name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Scale metric
          <select
            aria-label="Scale metric"
            value={metric}
            onChange={(e) => setMetric(e.target.value as Metric)}
          >
            <option value="estimated_gross_margin">Annual gross margin</option>
            <option value="estimated_annual_revenue">Annual revenue</option>
            <option value="weighted_contract_value">
              Weighted contract value
            </option>
          </select>
        </label>
        <div className="m-field-tools">
          <Button kind="quiet" onClick={() => act("risk")}>
            <ShieldAlert size={16} /> Reveal risk
          </Button>
          <Button kind="quiet" onClick={() => act("group")}>
            <Layers3 size={16} /> Group
          </Button>
          <Button kind="quiet" onClick={() => act("assemble")}>
            <RotateCcw size={15} /> Reset
          </Button>
          <button
            className="m-icon-button"
            onClick={() => act("undo")}
            aria-label="Undo spatial move"
          >
            <Undo2 size={17} />
          </button>
        </div>
      </div>
      {error && (
        <p className="m-error" role="alert">
          {error}
        </p>
      )}
      {fallback && (
        <p className="m-notice" role="status">
          WebGL is unavailable or the context was lost. Every record and action
          is available in this data view.
        </p>
      )}
      {reduced && (
        <p className="m-footnote">
          Reduced motion enabled. The data view is the default; spatial
          exploration uses static positions.
        </p>
      )}
      <div className="m-field-layout">
        <section className="m-field-stage">
          {loading ? (
            <Loading label="Reading the opportunity relationships" />
          ) : !graph.nodes.length ? (
            <Empty title="No records in the field">
              Discover an opportunity to begin.
            </Empty>
          ) : mode === "spatial" && !fallback ? (
            <FieldCanvas
              graph={graph}
              onSelect={pick}
              onFallback={() => {
                setFallback(true);
                setMode("data");
              }}
              command={command}
              reduced={reduced}
            />
          ) : (
            <div className="m-field-data">
              <div className="m-between">
                <h2>{id ? "Connected records" : "Opportunity field"}</h2>
                <Badge>{graph.nodes.length} records</Badge>
              </div>
              {graph.nodes.map((node) => (
                <button
                  key={node.id}
                  className={`m-data-node ${node.id === selectedNode?.id ? "selected" : ""}`}
                  onClick={() => pick(node.id)}
                >
                  <span
                    className={`m-node-indicator ${node.unknown ? "unknown" : node.kind}`}
                  />
                  <span>
                    <strong>{node.title}</strong>
                    <small>
                      {node.subtitle} · {node.id}
                    </small>
                  </span>
                  <span>{node.value}</span>
                  <ArrowUpRight size={16} />
                </button>
              ))}
            </div>
          )}
        </section>
        <aside className="m-field-inspection">
          {selectedNode && (
            <NodeInspector
              node={selectedNode}
              detail={detail}
              onInspect={() => props.inspect(id || selectedNode.recordId)}
            />
          )}
          {id && (
            <div className="m-field-produce">
              <p className="m-eyebrow">From intelligence to action</p>
              <h3>Make this opportunity useful.</h3>
              <p>
                Build a dossier with the evidence, risks, unknowns and next
                actions in this record.
              </p>
              <Button
                kind="primary"
                onClick={() => void build()}
                disabled={busy || loading}
              >
                <FileText size={16} />
                {busy ? "Building pack…" : "Build pursuit pack"}
              </Button>
              {asset && (
                <div className="m-asset-ready" role="status">
                  <Badge tone="green">Version {asset.version} saved</Badge>
                  <p>{asset.title}</p>
                  <Button onClick={() => props.navigate("assets", id)}>
                    Review and export <ArrowUpRight size={15} />
                  </Button>
                </div>
              )}
            </div>
          )}
        </aside>
      </div>
      <div className="m-field-legend">
        <div className="m-legend">
          <span>
            <i className="margin" />
            Green · recorded lower risk
          </span>
          <span>
            <i className="external" />
            Amber · uncertainty / missing evidence
          </span>
          <span>
            <i className="risk" />
            Red · recorded higher risk
          </span>
          <span>
            <i className="internal" />
            Cyan · evidence / account
          </span>
        </div>
        <p>
          Opportunity width = 0.85–1.45×, using √(value / maximum). Unknown
          values use a fixed outlined marker, excluded from the scale. Evidence
          nodes use equal sizes. Solid or incomplete borders show known versus
          missing values. Lines are recorded relationships. Dragging never
          changes business data.
        </p>
      </div>
      {mode === "spatial" && !fallback && (
        <details className="m-field-record-list">
          <summary>
            Keyboard-accessible record list · {graph.nodes.length} items
          </summary>
          <div className="m-field-data">
            {graph.nodes.map((node) => (
              <button
                key={node.id}
                className="m-data-node"
                onClick={() => pick(node.id)}
              >
                <strong>{node.title}</strong>
                <span>{node.value}</span>
                <small>{node.id}</small>
              </button>
            ))}
          </div>
        </details>
      )}
    </>
  );
}

function NodeInspector({
  node,
  detail,
  onInspect,
}: {
  node: FieldNode;
  detail: Detail | null;
  onInspect: () => void;
}) {
  const field =
    node.kind === "evidence"
      ? detail?.evidence.find((f) => f.id === node.recordId)
      : null;
  return (
    <div className="m-node-inspector">
      <p className="m-eyebrow">Evidence inspector</p>
      <Badge
        tone={
          node.unknown
            ? "amber"
            : node.kind === "opportunity"
              ? node.risk
              : "cyan"
        }
      >
        {fieldLabel(node.kind)}
      </Badge>
      <h2>{node.title}</h2>
      <strong className="m-node-value">{node.value}</strong>
      <p>{node.rationale}</p>
      <dl className="m-definition">
        <div>
          <dt>Record</dt>
          <dd>{node.id}</dd>
        </div>
        {node.confidence != null && (
          <div>
            <dt>Confidence</dt>
            <dd>{Math.round(node.confidence * 100)}%</dd>
          </div>
        )}
        <div>
          <dt>Status</dt>
          <dd>{node.subtitle}</dd>
        </div>
        {field && (
          <>
            <div>
              <dt>Source</dt>
              <dd>{field.source_titles.join("; ") || "Not recorded"}</dd>
            </div>
            <div>
              <dt>Updated</dt>
              <dd>{field.updated_at}</dd>
            </div>
          </>
        )}
      </dl>
      {field?.stale && <Badge tone="amber">Source older than 30 days</Badge>}
      <Button onClick={onInspect}>
        Open full workspace <ArrowUpRight size={15} />
      </Button>
    </div>
  );
}
