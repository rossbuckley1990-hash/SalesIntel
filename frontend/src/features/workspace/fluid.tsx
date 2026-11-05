"use client";
/**
 * Small pieces that make the interface feel continuous: a thumb that glides between tabs, counts that
 * roll up, the signed-in person for greetings, and avatar initials. All are progressive enhancements:
 * without them the controls keep their ordinary selected styles.
 */
import { createContext, useEffect, useLayoutEffect, useRef, useState, type RefObject } from "react";

export type Viewer = { name: string; email: string; target: { amount: string | null; basis_label: string | null; period: string | null } | null };
export const ViewerContext = createContext<Viewer | null>(null);

const reduced = () => typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
const useIsoLayoutEffect = typeof window === "undefined" ? useEffect : useLayoutEffect;

/** Every .ds-tabs and .ds-underline-tabs under root gets a thumb that slides to its chosen option. */
export function useFluidTabs(el: HTMLElement | null) {
  useEffect(() => {
    if (!el || typeof MutationObserver === "undefined") return;
    let frame = 0;
    const place = () => {
      frame = 0;
      el.querySelectorAll<HTMLElement>(".ds-tabs, .ds-underline-tabs").forEach((tabs) => {
        const active = tabs.querySelector<HTMLElement>(':scope > button[aria-pressed="true"], :scope > button[aria-selected="true"]');
        tabs.classList.add("fluid");
        if (!active) { tabs.style.setProperty("--ti-o", "0"); return; }
        tabs.style.setProperty("--ti-x", `${active.offsetLeft}px`);
        tabs.style.setProperty("--ti-y", `${active.offsetTop}px`);
        tabs.style.setProperty("--ti-w", `${active.offsetWidth}px`);
        tabs.style.setProperty("--ti-h", `${active.offsetHeight}px`);
        tabs.style.setProperty("--ti-o", "1");
        // Glide only after the first placement, so a thumb never flies in from the left on arrival.
        if (!tabs.classList.contains("ready")) requestAnimationFrame(() => tabs.classList.add("ready"));
      });
    };
    const schedule = () => { if (!frame) frame = requestAnimationFrame(place); };
    const observer = new MutationObserver(schedule);
    observer.observe(el, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ["aria-pressed", "aria-selected"] });
    window.addEventListener("resize", schedule);
    document.fonts?.ready.then(schedule).catch(() => {});
    schedule();
    return () => { observer.disconnect(); window.removeEventListener("resize", schedule); if (frame) cancelAnimationFrame(frame); };
  }, [el]);
}

/** Position a highlight behind the [aria-current="page"] item of a vertical list. */
export function useNavIndicator(nav: RefObject<HTMLElement | null>, key: string) {
  const [style, setStyle] = useState<Record<string, string>>({ "--o": "0" });
  const [ready, setReady] = useState(false);
  useIsoLayoutEffect(() => {
    const el = nav.current;
    if (!el) return;
    const place = () => {
      const active = el.querySelector<HTMLElement>('[aria-current="page"]');
      setStyle(active ? { "--y": `${active.offsetTop}px`, "--h": `${active.offsetHeight}px`, "--o": "1" } : { "--o": "0" });
    };
    place();
    window.addEventListener("resize", place);
    return () => window.removeEventListener("resize", place);
  }, [nav, key]);
  useEffect(() => { const t = requestAnimationFrame(() => setReady(true)); return () => cancelAnimationFrame(t); }, []);
  return { style: style as React.CSSProperties, ready };
}

/** Roll a number up from where it was to where it is now. */
export function useCountUp(target: number, duration = 650) {
  const [value, setValue] = useState(target);
  const from = useRef(0);
  useEffect(() => {
    if (reduced()) { setValue(target); from.current = target; return; }
    const start = performance.now();
    const origin = from.current;
    let frame = requestAnimationFrame(function tick(now) {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setValue(Math.round(origin + (target - origin) * eased));
      if (t < 1) frame = requestAnimationFrame(tick);
      else from.current = target;
    });
    return () => cancelAnimationFrame(frame);
  }, [target, duration]);
  return value;
}

export function initials(name: string) {
  const parts = name.replace(/[^\p{L}\p{N}\s'-]/gu, " ").trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  return ((parts[0][0] || "") + (parts.length > 1 ? parts[parts.length - 1][0] : parts[0][1] || "")).toUpperCase();
}

// Quiet, deep tones: white initials stay well above 4.5:1 on every one.
const PALETTE = ["#3b3940", "#2f4f4a", "#4a3f5b", "#5b3f3f", "#3f4a5b", "#6b4a2a", "#2f3f52"];
/** A stable, muted colour for a person or workspace. */
export function avatarStyle(seed: string): React.CSSProperties {
  let h = 0;
  for (const ch of seed) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return { background: PALETTE[h % PALETTE.length] };
}

export function Avatar({ name, seed, round, small, large }: { name: string; seed?: string; round?: boolean; small?: boolean; large?: boolean }) {
  return <span aria-hidden="true" className={`si-avatar ${round ? "round" : ""} ${small ? "sm" : ""} ${large ? "lg" : ""}`} style={avatarStyle(seed || name)}>{initials(name)}</span>;
}

export const isMac = () => typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
