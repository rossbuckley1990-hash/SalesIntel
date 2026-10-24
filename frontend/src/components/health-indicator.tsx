"use client";

import { useEffect, useState } from "react";
import { ShieldCheck, ShieldX } from "lucide-react";

type ApiStatus = "checking" | "online" | "offline";

export function HealthIndicator() {
  const [status, setStatus] = useState<ApiStatus>("checking");

  useEffect(() => {
    const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

    fetch(`${baseUrl}/health`, { cache: "no-store" })
      .then((response) => {
        setStatus(response.ok ? "online" : "offline");
      })
      .catch(() => {
        setStatus("offline");
      });
  }, []);

  const online = status === "online";
  const checking = status === "checking";
  const Icon = online || checking ? ShieldCheck : ShieldX;

  return (
    <div
      className="flex min-w-0 items-center gap-2 rounded-md border border-white/10 bg-white/[0.04] px-3 py-2 text-xs font-semibold uppercase text-slate-200"
      aria-live="polite"
    >
      <Icon
        aria-hidden="true"
        className={`h-4 w-4 ${online ? "text-mitie-lime" : checking ? "text-amber-300" : "text-red-300"}`}
      />
      <span className="whitespace-nowrap font-medium">
        API {checking ? "checking" : online ? "online" : "offline"}
      </span>
    </div>
  );
}
