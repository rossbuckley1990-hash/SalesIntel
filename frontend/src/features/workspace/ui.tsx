"use client";
import { useEffect, useRef, type ReactNode } from "react";
import { ArrowUpRight, Loader2, X } from "lucide-react";
import { money } from "./api";

export function Button({
  children,
  onClick,
  kind = "secondary",
  disabled,
  type = "button",
  className = "",
  ...rest
}: {
  children: ReactNode;
  onClick?: () => void;
  kind?: "primary" | "secondary" | "quiet";
  disabled?: boolean;
  type?: "button" | "submit";
  className?: string;
  "aria-label"?: string;
}) {
  return (
    <button
      {...rest}
      type={type}
      className={`m-button ${kind} ${className}`}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
}
export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return <span className={`m-badge ${tone.toLowerCase()}`}>{children}</span>;
}
export function Heading({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow: string;
  title: string;
  description?: string;
  children?: ReactNode;
}) {
  return (
    <header className="m-heading">
      <div>
        <p className="m-eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        {description && <p className="m-description">{description}</p>}
      </div>
      {children && <div className="m-heading-actions">{children}</div>}
    </header>
  );
}
export function SectionHeading({
  title,
  detail,
  children,
}: {
  title: string;
  detail?: string;
  children?: ReactNode;
}) {
  return (
    <div className="m-section-heading">
      <div>
        <h2>{title}</h2>
        {detail && <p>{detail}</p>}
      </div>
      {children}
    </div>
  );
}
export function Metric({
  label,
  value,
  detail,
  tone,
}: {
  label: string;
  value: string;
  detail: string;
  tone?: string;
}) {
  return (
    <div className={`m-metric ${tone || ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  );
}
export function Empty({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="m-empty">
      <span className="m-empty-mark">∅</span>
      <h3>{title}</h3>
      <div>{children}</div>
    </div>
  );
}
export function Loading({
  label = "Reading your workspace",
}: {
  label?: string;
}) {
  return (
    <div className="m-loading" role="status">
      <Loader2 className="m-spin" size={20} />
      <span>{label}</span>
    </div>
  );
}
export function Modal({
  title,
  children,
  close,
  wide = false,
}: {
  title: string;
  children: ReactNode;
  close: () => void;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const closeRef = useRef(close);
  closeRef.current = close;
  useEffect(() => {
    const dialog = ref.current;
    dialog?.showModal();
    const cancel = (e: Event) => {
      e.preventDefault();
      closeRef.current();
    };
    dialog?.addEventListener("cancel", cancel);
    return () => {
      dialog?.removeEventListener("cancel", cancel);
      dialog?.close();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className={`m-dialog ${wide ? "wide" : ""}`}
      aria-label={title}
      onClick={(e) => {
        if (e.target === ref.current) {
          const r = ref.current.getBoundingClientRect();
          if (
            e.clientX < r.left ||
            e.clientX > r.right ||
            e.clientY < r.top ||
            e.clientY > r.bottom
          )
            close();
        }
      }}
    >
      <header className="m-dialog-header">
        <span>{title}</span>
        <button
          onClick={close}
          className="m-icon-button"
          aria-label="Close dialog"
        >
          <X size={20} />
        </button>
      </header>
      {children}
    </dialog>
  );
}
export function Sparkline({
  values,
  label,
}: {
  values: number[];
  label: string;
}) {
  const max = Math.max(...values, 1);
  const points = values
    .map(
      (v, i) =>
        `${(i * 240) / Math.max(values.length - 1, 1)},${56 - (v / max) * 46}`,
    )
    .join(" ");
  return (
    <svg
      viewBox="0 0 240 64"
      role="img"
      aria-label={label}
      className="m-sparkline"
    >
      <defs>
        <linearGradient id="spark-fill" x1="0" y1="0" x2="0" y2="1">
          <stop stopColor="#9cdd68" stopOpacity=".16" />
          <stop offset="1" stopColor="#9cdd68" stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={`0,64 ${points} 240,64`} fill="url(#spark-fill)" />
      <polyline
        points={points}
        fill="none"
        stroke="#9cdd68"
        strokeWidth="2"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
export function OpenLink({
  children,
  onClick,
}: {
  children: ReactNode;
  onClick: () => void;
}) {
  return (
    <button className="m-text-link" onClick={onClick}>
      {children}
      <ArrowUpRight size={15} />
    </button>
  );
}
export function Value({ value }: { value: number | string | null }) {
  return (
    <span className={value == null ? "m-muted" : "m-number"}>
      {money(value)}
    </span>
  );
}
