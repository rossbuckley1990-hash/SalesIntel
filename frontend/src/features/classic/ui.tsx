"use client";

import { getApiBaseUrl, type FieldIntelligence } from "@/lib/api";
import { percentage } from "@/lib/format";
import {
  AlertTriangle,
  CheckCircle2,
  Landmark,
  Loader2,
  Map as MapIcon,
  RefreshCw,
  Target,
  TrendingUp,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import {
  fieldConfidenceBorder,
  fieldConfidenceClass,
  normaliseRiskLabel,
  riskTone,
  valueTypeDescription,
  valueTypeDotClass,
  valueTypeLabel,
} from "./evidence";
import { SkeletonLine } from "./research";
import { IntelligenceFieldView, Tone, toneClasses } from "./shared";

export function KpiTile({
  label,
  display,
  detail,
  tone,
}: {
  label: string;
  display: string;
  detail: string;
  tone: Tone;
}) {
  const Icon =
    tone === "green"
      ? Target
      : tone === "cyan"
        ? TrendingUp
        : tone === "amber"
          ? Landmark
          : AlertTriangle;

  return (
    <article
      className={`rounded-lg border p-4 shadow-[0_18px_60px_rgba(0,0,0,0.24)] ${toneClasses[tone]}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-300">{label}</p>
          <p className="mt-3 text-3xl font-semibold text-white">{display}</p>
        </div>
        <div className="flex h-10 w-10 items-center justify-center rounded-md bg-white/10">
          <Icon aria-hidden="true" className="h-5 w-5" />
        </div>
      </div>
      <p className="mt-4 text-sm leading-5 text-slate-300">{detail}</p>
    </article>
  );
}

export function Panel({
  title,
  action,
  children,
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="min-w-0 rounded-lg border border-white/10 bg-[#0d151a] shadow-[0_20px_70px_rgba(0,0,0,0.28)]">
      <div className="flex min-h-16 items-center justify-between gap-4 border-b border-white/10 px-4 py-4 sm:px-5">
        <h2 className="text-base font-semibold text-white sm:text-lg">
          {title}
        </h2>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
      <div className="p-4 sm:p-5">{children}</div>
    </section>
  );
}

export function StatusPill({ tone, label }: { tone: Tone; label: string }) {
  return (
    <span
      className={`inline-flex rounded-md border px-2.5 py-1 text-xs font-semibold ${toneClasses[tone]}`}
    >
      {label}
    </span>
  );
}

export function ConfidenceOrbit({
  score,
  label,
}: {
  score: number;
  label: string;
}) {
  const percent = Math.round(Math.min(Math.max(score, 0), 1) * 100);

  return (
    <div
      className="misi-confidence-glow rounded-full p-[3px]"
      style={{
        background: `conic-gradient(#3b4fd8 ${percent}%, #e4e7ec 0)`,
      }}
      aria-label={`${label} confidence progress`}
    >
      <div className="flex h-16 w-16 items-center justify-center rounded-full border border-white/10 bg-[#0d151a]">
        <span className="text-sm font-black text-white">{label}</span>
      </div>
    </div>
  );
}

export function RiskPill({ risk }: { risk: string }) {
  return <StatusPill tone={riskTone(risk)} label={normaliseRiskLabel(risk)} />;
}

export function MetricLine({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="border-b border-white/10 pb-3 last:border-0 last:pb-0">
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-sm font-semibold text-slate-300">{label}</p>
        <p className="text-lg font-semibold text-white">{value}</p>
      </div>
      <p className="mt-1 text-sm leading-5 text-slate-500">{detail}</p>
    </div>
  );
}

export function MiniMetric({
  label,
  value,
  danger = false,
}: {
  label: string;
  value: string;
  danger?: boolean;
}) {
  return (
    <div className="rounded-md border border-white/10 bg-[#111a20] p-4">
      <p className="text-sm font-semibold text-slate-400">{label}</p>
      <p
        className={`mt-2 text-2xl font-semibold ${danger ? "text-red-200" : "text-white"}`}
      >
        {value}
      </p>
    </div>
  );
}

export function AutofillSummaryMetric({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="rounded-md border border-white/10 bg-[#111a20] p-4">
      <p className="text-xs font-black uppercase text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
      <p className="mt-2 text-xs leading-5 text-slate-500">{detail}</p>
    </div>
  );
}

export function IntelligenceMetric({
  field,
  fallbackLabel,
  danger = false,
}: {
  field: IntelligenceFieldView | undefined;
  fallbackLabel: string;
  danger?: boolean;
}) {
  if (!field) {
    return (
      <div className="rounded-md border border-slate-400/20 bg-slate-400/5 p-4">
        <div className="flex items-start justify-between gap-3">
          <p className="text-sm font-semibold text-slate-400">
            {fallbackLabel}
          </p>
          <StatusPill tone="amber" label="Unknown" />
        </div>
        <p className="mt-2 text-2xl font-semibold text-amber-100">
          Needs evidence
        </p>
        <p className="mt-2 text-xs leading-5 text-slate-500">
          SalesIntel has not confirmed this field yet. Attach source evidence or run
          AI research to estimate it with confidence.
        </p>
      </div>
    );
  }

  return (
    <div
      className={`rounded-md border p-4 transition hover:border-white/20 ${fieldConfidenceBorder(field.valueType)}`}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-semibold text-slate-400">{field.label}</p>
        <ConfidenceBadge field={field} />
      </div>
      <p
        className={`mt-2 text-2xl font-semibold ${danger || field.valueType === "unknown" ? "text-amber-100" : "text-white"}`}
      >
        {field.displayValue}
      </p>
      <p className="mt-2 text-xs leading-5 text-slate-500">{field.rationale}</p>
    </div>
  );
}

export function ConfidenceFieldCompact({
  field,
  label,
}: {
  field: IntelligenceFieldView | undefined;
  label: string;
}) {
  if (!field) {
    return <DetailField label={label} value="Unknown · evidence required" />;
  }

  return (
    <div>
      <div className="flex items-center gap-2">
        <p className="text-xs font-semibold text-slate-500">{label}</p>
        <ValueTypeDot valueType={field.valueType} />
      </div>
      <p className="mt-1 text-sm font-semibold leading-6 text-slate-200">
        {field.displayValue}
      </p>
      <p className="text-xs leading-5 text-slate-500">
        {valueTypeLabel(field.valueType)} · {percentage(field.confidenceScore)}{" "}
        confidence
      </p>
    </div>
  );
}

export function ConfidenceFieldCard({
  field,
  accepted,
  editing,
  onAccept,
  onEdit,
  onCancelEdit,
  onSaveEdit,
}: {
  field: IntelligenceFieldView;
  accepted: boolean;
  editing: boolean;
  onAccept: () => void;
  onEdit: () => void;
  onCancelEdit: () => void;
  onSaveEdit: (value: string) => void;
}) {
  const [draftValue, setDraftValue] = useState(field.displayValue);

  useEffect(() => {
    setDraftValue(field.displayValue);
  }, [field.displayValue, editing]);

  return (
    <article
      className={`rounded-md border p-4 transition hover:border-white/20 ${fieldConfidenceBorder(field.valueType)}`}
    >
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-sm font-semibold text-white">{field.label}</h4>
            <ConfidenceBadge field={field} />
            {field.needsUserConfirmation ? (
              <StatusPill tone="amber" label="Needs confirmation" />
            ) : null}
            {accepted ? (
              <StatusPill tone="green" label="Accepted in review" />
            ) : null}
          </div>
          {editing ? (
            <label className="mt-3 block">
              <span className="sr-only">Edit {field.label}</span>
              <textarea
                value={draftValue}
                onChange={(event) => setDraftValue(event.target.value)}
                rows={2}
                className="w-full rounded-md border border-white/10 bg-[#0b1115] px-3 py-2 text-sm leading-6 text-white"
              />
            </label>
          ) : (
            <p className="mt-3 text-base font-semibold leading-7 text-slate-100">
              {field.displayValue}
            </p>
          )}
          <p className="mt-2 text-sm leading-6 text-slate-400">
            {field.rationale}
          </p>
          <div className="mt-3 rounded-md border border-mitie-lime/20 bg-mitie-lime/10 p-3">
            <p className="text-xs font-black uppercase text-mitie-lime">
              Next action
            </p>
            <p className="mt-1 text-sm font-semibold leading-6 text-white">
              {field.recommendedNextStep}
            </p>
          </div>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <button
            type="button"
            onClick={onAccept}
            disabled={accepted || field.valueType === "unknown"}
            className="inline-flex min-h-9 items-center justify-center gap-2 rounded-md border border-emerald-300/20 bg-emerald-400/10 px-3 text-xs font-bold text-emerald-100 transition hover:bg-emerald-400/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <CheckCircle2 aria-hidden="true" className="h-3.5 w-3.5" />
            {field.valueType === "unknown"
              ? "Evidence needed"
              : accepted
                ? "Accepted"
                : "Accept AI value"}
          </button>
          {editing ? (
            <>
              <button
                type="button"
                onClick={() => onSaveEdit(draftValue)}
                className="inline-flex min-h-9 items-center justify-center rounded-md border border-cyan-300/20 bg-cyan-400/10 px-3 text-xs font-bold text-cyan-100 transition hover:bg-cyan-400/20"
              >
                Save draft
              </button>
              <button
                type="button"
                onClick={onCancelEdit}
                className="inline-flex min-h-9 items-center justify-center rounded-md border border-white/10 bg-white/[0.04] px-3 text-xs font-bold text-slate-300 transition hover:bg-white/[0.08]"
              >
                Cancel
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={onEdit}
              className="inline-flex min-h-9 items-center justify-center rounded-md border border-white/10 bg-white/[0.04] px-3 text-xs font-bold text-slate-300 transition hover:bg-white/[0.08]"
            >
              Edit
            </button>
          )}
        </div>
      </div>

      <details className="mt-3 rounded-md border border-white/10 bg-[#0b1115] px-3 py-2">
        <summary className="cursor-pointer text-xs font-semibold text-slate-300">
          Evidence, confidence and rationale
        </summary>
        <div className="mt-3 grid gap-2 text-xs leading-5 text-slate-400">
          <p>{valueTypeDescription(field)}</p>
          {field.sourceUrls.length > 0 ? (
            <div className="grid gap-1">
              {field.sourceUrls.slice(0, 4).map((url, index) => (
                <a
                  key={url}
                  href={url}
                  target="_blank"
                  rel="noreferrer"
                  className="truncate font-semibold text-cyan-200 hover:text-white"
                >
                  {field.sourceTitles[index]
                    ? `${field.sourceTitles[index]} · `
                    : ""}
                  {url}
                </a>
              ))}
            </div>
          ) : (
            <p>
              No source URL is attached; validate this against an approved
              source before using it commercially.
            </p>
          )}
        </div>
      </details>
    </article>
  );
}

export function ConfidenceBadge({ field }: { field: IntelligenceFieldView }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-bold ${fieldConfidenceClass(field.valueType)}`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${valueTypeDotClass(field.valueType)} ${field.valueType === "unknown" ? "" : "misi-confidence-glow"}`}
        aria-hidden="true"
      />
      {valueTypeLabel(field.valueType)} · {percentage(field.confidenceScore)}
    </span>
  );
}

export function ValueTypeDot({
  valueType,
}: {
  valueType: FieldIntelligence["value_type"];
}) {
  return (
    <span
      className={`h-2 w-2 rounded-full ${valueTypeDotClass(valueType)}`}
      aria-hidden="true"
    />
  );
}

export function DetailField({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div>
      <p className="text-xs font-semibold text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-semibold leading-6 text-slate-200">
        {value}
      </p>
    </div>
  );
}

export function DetailList({
  title,
  items,
}: {
  title: string;
  items: string[];
}) {
  if (items.length === 0) {
    return null;
  }

  return (
    <div className="mt-4">
      <h4 className="text-xs font-semibold text-slate-500">{title}</h4>
      <ul className="mt-2 grid gap-2">
        {items.map((item) => (
          <li
            key={item}
            className="flex gap-2 text-sm leading-6 text-slate-300"
          >
            <CheckCircle2
              aria-hidden="true"
              className="mt-1 h-4 w-4 shrink-0 text-mitie-lime"
            />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function DashboardLoading() {
  return (
    <div className="grid gap-5">
      <section
        className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-4"
        aria-label="Loading KPIs"
      >
        {["Pipeline", "Weighted", "Margin", "Risk"].map((label) => (
          <div
            key={label}
            className="rounded-lg border border-white/10 bg-white/[0.04] p-4"
          >
            <SkeletonLine className="h-4 w-24 rounded-full" />
            <SkeletonLine className="mt-5 h-9 w-32 rounded-full" />
            <SkeletonLine className="mt-5 h-3 w-40 rounded-full" />
          </div>
        ))}
      </section>
      <Panel
        title="Preparing The Command Centre"
        action={
          <Loader2
            aria-hidden="true"
            className="h-5 w-5 animate-spin text-cyan-200"
          />
        }
      >
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
          <div className="grid gap-3">
            <p className="text-sm font-semibold text-white">
              SalesIntel is loading pipeline, market signals, finance forecast and
              executive actions.
            </p>
            <SkeletonLine className="h-3 rounded-full" />
            <SkeletonLine className="h-3 w-5/6 rounded-full" />
            <SkeletonLine className="h-3 w-2/3 rounded-full" />
          </div>
          <div className="rounded-md border border-cyan-300/20 bg-cyan-400/10 p-4">
            <p className="text-xs font-black uppercase text-cyan-100">
              While loading
            </p>
            <p className="mt-2 text-sm leading-6 text-cyan-100/75">
              Empty fields will appear as unknown with a next step, not as
              silent blanks.
            </p>
          </div>
        </div>
      </Panel>
    </div>
  );
}

export function DashboardError({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <Panel
      title="Backend Connection Error"
      action={<StatusPill tone="red" label="API unavailable" />}
    >
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div className="flex gap-3">
          <AlertTriangle
            aria-hidden="true"
            className="mt-1 h-5 w-5 shrink-0 text-red-200"
          />
          <div>
            <p className="text-sm font-semibold text-white">
              Could not load dashboard data from {getApiBaseUrl()}.
            </p>
            <p className="mt-2 text-sm leading-6 text-slate-400">{message}</p>
          </div>
        </div>
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-white/10 bg-white px-3 text-sm font-semibold text-[#10171b] transition hover:bg-slate-200"
        >
          <RefreshCw aria-hidden="true" className="h-4 w-4" />
          Retry
        </button>
      </div>
    </Panel>
  );
}

export function EmptyState({
  title,
  message,
}: {
  title: string;
  message: string;
}) {
  return (
    <div className="rounded-md border border-cyan-300/15 bg-[#111a20] p-6 text-center shadow-[0_18px_50px_rgba(0,0,0,0.18)]">
      <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-md border border-cyan-300/20 bg-cyan-400/10 text-cyan-100">
        <MapIcon aria-hidden="true" className="h-5 w-5" />
      </div>
      <p className="mt-4 text-sm font-semibold text-white">{title}</p>
      <p className="mx-auto mt-2 max-w-2xl text-sm leading-6 text-slate-400">
        {message}
      </p>
    </div>
  );
}

export function SourceRow({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: Tone;
}) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-white/10 pb-3 last:border-0 last:pb-0">
      <div>
        <p className="text-sm font-semibold text-white">{label}</p>
        <p className="mt-1 text-sm text-slate-500">{value}</p>
      </div>
      <StatusPill
        tone={tone}
        label={
          tone === "green" ? "Ready" : tone === "cyan" ? "Available" : "Planned"
        }
      />
    </div>
  );
}

export function ProgressRow({
  label,
  value,
  width,
}: {
  label: string;
  value: string;
  width: number;
}) {
  return (
    <div>
      <div className="flex items-center justify-between gap-3 text-sm">
        <span className="font-semibold text-slate-300">{label}</span>
        <span className="font-semibold text-white">{value}</span>
      </div>
      <div className="mt-2 h-2 rounded-full bg-white/10">
        <div
          className="h-2 rounded-full bg-mitie-lime"
          style={{ width: `${Math.min(Math.max(width, 0), 100)}%` }}
        />
      </div>
    </div>
  );
}
