"use client";
import { useMemo, useState } from "react";
import { FieldCanvas } from "./field-canvas";
import { financialGraph } from "./graph";
import type { ScenarioResult } from "../workspace/types";
import { money } from "../workspace/api";

export function FinancialScene({ result }: { result: ScenarioResult }) {
  const graph = useMemo(() => financialGraph(result), [result]);
  const [fallback, setFallback] = useState(false);
  const [selected, setSelected] = useState("");
  if (fallback)
    return (
      <p className="m-notice">
        WebGL unavailable. In-house cost {money(result.proposed.inhouse_cost)},
        subcontract cost {money(result.proposed.subcontract_cost)}, gross margin{" "}
        {money(result.proposed.gross_margin)}. The calculation and comparison
        remain available below.
      </p>
    );
  return (
    <div className="m-financial-scene">
      <FieldCanvas
        graph={graph}
        onSelect={setSelected}
        onFallback={() => setFallback(true)}
        reduced={
          typeof window !== "undefined" &&
          window.matchMedia("(prefers-reduced-motion: reduce)").matches
        }
      />
      <p className="m-footnote">
        {graph.nodes.find((n) => n.id === selected)?.title ||
          "Proposed annual cost and margin"}{" "}
        · Width uses a bounded square-root mapping; precise values are
        authoritative.
      </p>
    </div>
  );
}
