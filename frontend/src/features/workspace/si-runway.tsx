"use client";
/**
 * Runway: when each opportunity opens, on one time axis.
 * Lanes keep identity separate from colour: tenders are pins at their published date, contract ends are
 * diamonds at the reported end, and Shadow Radar leads are bars across their inferred investigation window
 * (a rule of thumb, never a prediction). Every mark is a button with a full text label; the list view is
 * the table equivalent.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import type { Lead } from "./si-api";

type Lane = { id: string; label: string; shape: "pin" | "diamond" | "bar"; color: string; note: string };
// Validated categorical slots (light surface): blue, orange, aqua. Aqua is below 3:1, so every lane is labelled and shaped.
const LANES: Lane[] = [
  { id: "tender", label: "Tenders and notices", shape: "pin", color: "#2a78d6", note: "Published deadline or expected date" },
  { id: "ending", label: "Contracts ending", shape: "diamond", color: "#1baf7a", note: "Published contract end" },
  { id: "shadow", label: "Shadow Radar windows", shape: "bar", color: "#eb6834", note: "Inferred window, a rule of thumb" },
  { id: "other", label: "Other dated signals", shape: "pin", color: "#8e8b93", note: "Dated private or other signals" },
];
const DAY = 86400000;
const ROW = 22;
const PIN = 11;
// Calendar days as whole numbers (UTC-based), so a published date never shifts by an hour into the wrong day.
const day = (s: string) => Date.UTC(Number(s.slice(0, 4)), Number(s.slice(5, 7)) - 1, Number(s.slice(8, 10))) / DAY;
const fmt = (n: number, opts: Intl.DateTimeFormatOptions = { day: "numeric", month: "short", year: "numeric" }) => new Date(n * DAY).toLocaleDateString("en-GB", { ...opts, timeZone: "UTC" });
const todayIndex = () => { const n = new Date(); return Date.UTC(n.getFullYear(), n.getMonth(), n.getDate()) / DAY; };
const rel = (n: number, today: number) => { const d = n - today; return d === 0 ? "today" : d > 0 ? `in ${d} day${d === 1 ? "" : "s"}` : `${-d} day${d === -1 ? "" : "s"} ago`; };

type Mark = { lead: Lead; lane: string; start: number; end: number; label: string };

function marksOf(items: Lead[]): Mark[] {
  const out: Mark[] = [];
  for (const lead of items) {
    if (lead.type === "shadow" && lead.shadow?.window?.[0] && lead.shadow.window[1]) {
      out.push({ lead, lane: "shadow", start: day(lead.shadow.window[0]), end: day(lead.shadow.window[1]), label: "Inferred investigation window" });
    } else if (lead.timing) {
      const lane = lead.kind === "contract_ending" ? "ending" : lead.type === "public" ? "tender" : "other";
      const label = lead.timing_label ? lead.timing_label[0].toUpperCase() + lead.timing_label.slice(1) : "Dated signal";
      out.push({ lead, lane, start: day(lead.timing), end: day(lead.timing), label });
    }
  }
  return out;
}

export function Runway({ items, selected, onSelect, horizon = 456, compact = false }: {
  items: Lead[]; selected: string | null; onSelect: (key: string) => void; horizon?: number; compact?: boolean;
}) {
  const today = todayIndex();
  const from = today - (compact ? 3 : 21);
  const to = today + horizon;
  const [room, setRoom] = useState(0);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = box.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(([entry]) => setRoom(Math.floor(entry.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  // Fill the space available, but never squeeze a day below a readable width (the axis scrolls instead).
  const pxPerDay = Math.max(compact ? 9 : 2.8, room ? (room - 2) / (to - from) : 0);
  const width = Math.round((to - from) * pxPerDay);
  const x = (d: number) => Math.round((Math.min(Math.max(d, from), to) - from) * pxPerDay);
  const [tip, setTip] = useState<{ m: Mark; left: number; top: number } | null>(null);

  const { lanes, undated, outside } = useMemo(() => {
    const all = marksOf(items);
    // The compact runway answers "what opens soon", so only marks that start inside the period; the full one shows overlap.
    const inRange = all.filter((m) => (compact ? m.start >= today && m.start <= to : m.end >= from && m.start <= to));
    const lanes = LANES.map((lane) => {
      const marks = inRange.filter((m) => m.lane === lane.id).sort((a, b) => a.start - b.start || a.end - b.end);
      const rows: number[] = [];
      const placed = marks.map((m) => {
        const x0 = x(m.start) - (lane.shape === "bar" ? 0 : PIN / 2);
        const x1 = Math.max(x(m.end), x0 + PIN) + 3;
        let r = rows.findIndex((end) => end <= x0);
        if (r < 0) { rows.push(0); r = rows.length - 1; }
        rows[r] = x1;
        return { m, x0, w: x1 - 3 - x0, row: r };
      });
      return { lane, placed, rows: Math.max(rows.length, 1) };
    }).filter((l) => l.placed.length);
    return { lanes, undated: items.length - all.length, outside: all.length - inRange.length };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items, from, to, pxPerDay, compact, today]);

  // Gridlines: the first of each month, or each Monday on the compact runway.
  const months: { left: number; label: string }[] = [];
  for (let d = from + 1; d < to; d++) {
    const dt = new Date(d * DAY);
    if (compact ? dt.getUTCDay() === 1 : dt.getUTCDate() === 1)
      months.push({ left: x(d), label: compact ? fmt(d, { day: "numeric", month: "short" }) : fmt(d, dt.getUTCMonth() === 0 ? { month: "short", year: "numeric" } : { month: "short" }) });
  }

  function show(m: Mark, el: HTMLElement) {
    const host = box.current?.getBoundingClientRect();
    const r = el.getBoundingClientRect();
    if (!host) return;
    const left = Math.min(Math.max(r.left - host.left, 8), host.width - 290);
    setTip({ m, left, top: r.bottom - host.top + 6 });
  }

  if (!lanes.length) return <div ref={box} className="si-runway p-6 text-[13px] text-ds-muted">Nothing dated in this period. Switch to the list to see undated leads.</div>;
  return (
    <div className="space-y-2">
      <div ref={box} className="si-runway" onMouseLeave={() => setTip(null)}>
        <div className="si-runway-scroll" onScroll={() => setTip(null)}>
          <div style={{ width, position: "relative" }}>
            <div className="si-runway-axis" aria-hidden="true">{months.map((m) => <span key={m.left} className="si-runway-month" style={{ left: m.left }}>{m.label}</span>)}</div>
            <div className="si-runway-today" style={{ left: x(today) }} aria-hidden="true"><span>TODAY</span></div>
            {lanes.map(({ lane, placed, rows }) => (
              <div key={lane.id} className="si-runway-lane" role="group" aria-label={`${lane.label}: ${placed.length}`} style={{ height: (compact ? 28 : 36) + rows * ROW + 8 }}>
                {months.map((m) => <span key={m.left} className="si-runway-grid" style={{ left: m.left }} />)}
                <span className="si-runway-lane-label"><Shape lane={lane} />{lane.label}<span className="si-mono text-ds-muted">{placed.length}</span></span>
                {placed.map(({ m, x0, w, row }) => {
                  const name = `${m.lead.organisation}. ${m.label}: ${m.start === m.end ? fmt(m.start) : `${fmt(m.start)} to ${fmt(m.end)}`}`;
                  return (
                    <button key={m.lead.key} className="si-mark" aria-label={name} aria-current={m.lead.key === selected ? "true" : undefined}
                      style={{ left: x0, top: (compact ? 26 : 34) + row * ROW, width: Math.max(w, PIN), ["--c" as string]: lane.color }}
                      onClick={() => onSelect(m.lead.key)} onMouseEnter={(e) => show(m, e.currentTarget)} onFocus={(e) => show(m, e.currentTarget)} onBlur={() => setTip(null)}>
                      {lane.shape === "bar" && <span className="bar" />}
                      {lane.shape === "diamond" ? <span className="diamond" /> : <span className="pin" />}
                    </button>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
        {tip && <div className="si-runway-tip" style={{ left: tip.left, top: tip.top }} role="tooltip">
          <b>{tip.m.start === tip.m.end ? `${fmt(tip.m.start)} · ${rel(tip.m.start, today)}` : `${fmt(tip.m.start)} – ${fmt(tip.m.end)}`}</b>
          <span>{tip.m.lead.organisation}</span><br /><span>{tip.m.label}{tip.m.lead.type === "shadow" ? " (not a prediction)" : ""}</span>
        </div>}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="si-legend" aria-hidden="true">{LANES.filter((l) => lanes.some((x) => x.lane.id === l.id)).map((l) => <span key={l.id}><Shape lane={l} />{l.note}</span>)}</div>
        {(undated > 0 || outside > 0) && <p className="text-[12px] text-ds-muted">{[undated ? `${undated} without a date` : "", outside ? `${outside} outside this period` : ""].filter(Boolean).join(" · ")}. The list shows everything.</p>}
      </div>
    </div>
  );
}

function Shape({ lane }: { lane: Lane }) {
  const style = { background: lane.color };
  if (lane.shape === "bar") return <i aria-hidden="true" style={{ ...style, width: 14, height: 6, borderRadius: 3, opacity: .75, display: "inline-block" }} />;
  if (lane.shape === "diamond") return <i aria-hidden="true" style={{ ...style, width: 7, height: 7, borderRadius: 1.5, transform: "rotate(45deg)", display: "inline-block" }} />;
  return <i aria-hidden="true" style={{ ...style, width: 8, height: 8, borderRadius: "50%", display: "inline-block" }} />;
}
