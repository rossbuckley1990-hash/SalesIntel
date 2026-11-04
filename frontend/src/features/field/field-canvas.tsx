"use client";
import { useEffect, useRef, useState } from "react";
import type { FieldGraph } from "./graph";
import { FieldStage } from "./engine/stage";
import { Loading } from "../workspace/ui";

export type FieldCommand = {
  mode: "assemble" | "risk" | "group" | "pack" | "undo";
  key: number;
};
export function FieldCanvas({
  graph,
  onSelect,
  onFallback,
  command,
  reduced = false,
}: {
  graph: FieldGraph;
  onSelect: (id: string) => void;
  onFallback: () => void;
  command?: FieldCommand;
  reduced?: boolean;
}) {
  const surface = useRef<HTMLDivElement>(null);
  const overlay = useRef<HTMLDivElement>(null);
  const stage = useRef<FieldStage | null>(null);
  const callbacks = useRef({ onSelect, onFallback });
  callbacks.current = { onSelect, onFallback };
  const [ready, setReady] = useState(false);
  const topology =
    graph.nodes.map((n) => n.id).join("|") +
    graph.edges.map((e) => e.source + e.target).join("|");
  useEffect(() => {
    let renderer: FieldStage | null = null;
    setReady(false);
    const canvas = document.createElement("canvas");
    canvas.tabIndex = 0;
    canvas.setAttribute(
      "aria-label",
      "Interactive intelligence field. Arrow keys select records. Escape resets the scene. Command or Control Z undoes a spatial move.",
    );
    surface.current?.append(canvas);
    try {
      if (
        !surface.current ||
        !overlay.current ||
        !canvas.getContext("webgl2") ||
        new URLSearchParams(window.location.search).get("webgl") === "off"
      ) {
        canvas.remove();
        callbacks.current.onFallback();
        return;
      }
      renderer = new FieldStage(
        canvas,
        overlay.current,
        graph,
        (id) => callbacks.current.onSelect(id),
        () => callbacks.current.onFallback(),
        reduced,
      );
      stage.current = renderer;
      setReady(true);
    } catch {
      renderer?.dispose();
      callbacks.current.onFallback();
    }
    return () => {
      renderer?.dispose();
      canvas.remove();
      stage.current = null;
    };
  }, [topology, reduced]);
  useEffect(() => {
    stage.current?.updateGraph(graph);
  }, [graph]);
  useEffect(() => {
    if (command?.mode === "undo") stage.current?.undoMove();
    else if (command) stage.current?.setMode(command.mode);
  }, [command]);
  return (
    <div className="m-field-canvas">
      <div ref={surface} className="m-field-surface" />
      <div ref={overlay} className="m-field-labels" aria-hidden="true" />
      {!ready && (
        <div className="m-field-loading">
          <Loading label="Assembling the recorded intelligence" />
        </div>
      )}
      <span className="m-field-watermark" aria-hidden="true">
        SalesIntel / LIVING INTELLIGENCE
      </span>
    </div>
  );
}
