"use client";
import type { ReactNode } from "react";
import { ArrowUpRight } from "lucide-react";
import type { Tone } from "./radar-model";
import { hostOf, safeUrl } from "./radar-model";

export function Pill({ tone = "neutral", dot, children, title }: { tone?: Tone; dot?: boolean; children: ReactNode; title?: string }) {
  return <span className={`ds-pill ${tone}`} title={title}>{dot && <i aria-hidden="true" />}{children}</span>;
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`ds-card ${className}`}>{children}</div>;
}

export function SectionTitle({ icon, title, detail, action }: { icon?: ReactNode; title: string; detail?: ReactNode; action?: ReactNode }) {
  return (
    <div className="mb-3 flex items-end justify-between gap-4">
      <div className="min-w-0">
        <h2 className="flex items-center gap-2 text-[15px] font-semibold tracking-[-0.01em] text-ds-ink">{icon}{title}</h2>
        {detail && <p className="mt-0.5 text-[13px] text-ds-muted">{detail}</p>}
      </div>
      {action}
    </div>
  );
}

export function SourceLink({ url, title, meta }: { url: string; title?: string; meta?: string }) {
  const href = safeUrl(url);
  if (!href) return <span className="text-[13px] text-ds-muted">{title || url}</span>;
  return (
    <a href={href} target="_blank" rel="noreferrer" className="group flex items-start gap-3 rounded-lg border border-ds-border bg-white px-3 py-2.5 transition hover:border-ds-brand-line hover:bg-ds-brand-soft">
      <span className="mt-0.5 grid h-7 w-7 flex-none place-items-center rounded-md bg-ds-subtle text-[11px] font-bold uppercase text-ds-muted group-hover:bg-white">{hostOf(href).slice(0, 2)}</span>
      <span className="min-w-0 flex-1">
        <span className="line-clamp-2 block text-[13px] font-medium leading-5 text-ds-ink">{title || hostOf(href)}</span>
        <span className="block truncate text-[12px] text-ds-muted">{meta ? `${meta} · ` : ""}{hostOf(href)}</span>
      </span>
      <ArrowUpRight size={15} className="mt-1 flex-none text-ds-faint group-hover:text-ds-brand" />
    </a>
  );
}

export function Fact({ label, children, hint }: { label: string; children: ReactNode; hint?: ReactNode }) {
  return (
    <div className="min-w-0 rounded-lg bg-ds-canvas px-3.5 py-3">
      <dt className="text-[12px] font-medium text-ds-muted">{label}</dt>
      <dd className="mt-1 text-[14px] font-semibold leading-5 text-ds-ink">{children}</dd>
      {hint && <dd className="mt-1 text-[12px] leading-[18px] text-ds-muted">{hint}</dd>}
    </div>
  );
}

export function EmptyState({ icon, title, children, action }: { icon: ReactNode; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center px-6 py-14 text-center">
      <span className="grid h-12 w-12 place-items-center rounded-xl border border-ds-border bg-white text-ds-muted shadow-ds-xs">{icon}</span>
      <h3 className="mt-4 text-[15px] font-semibold text-ds-ink">{title}</h3>
      {children && <div className="mt-1 max-w-sm text-[13px] leading-5 text-ds-muted">{children}</div>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
