import { getApiBaseUrl } from "@/lib/api";

export function livingUrl(path: string) {
  return `${getApiBaseUrl()}/api/living${path}`;
}
export async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const timeout = AbortSignal.timeout(60_000);
  const response = await fetch(livingUrl(path), {
    ...options,
    signal: options.signal
      ? AbortSignal.any([options.signal, timeout])
      : timeout,
    cache: "no-store",
    headers:
      options.body instanceof FormData
        ? options.headers
        : { "Content-Type": "application/json", ...options.headers },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = payload?.detail;
    throw new Error(
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: { msg: string }) => d.msg).join(" · ")
          : `Request failed (${response.status}). Check the local API connection.`,
    );
  }
  return response.json() as Promise<T>;
}
export function mutate<T>(path: string, body: unknown, method = "POST") {
  return request<T>(path, { method, body: JSON.stringify(body) });
}
export const money = (
  value: number | string | null | undefined,
  compact = false,
) =>
  value == null
    ? "Unknown"
    : new Intl.NumberFormat("en-GB", {
        style: "currency",
        currency: "GBP",
        minimumFractionDigits: 0,
        maximumFractionDigits: 2,
        notation: compact ? "compact" : "standard",
      }).format(Number(value));
export const dateLabel = (value: string | null | undefined) =>
  value
    ? new Intl.DateTimeFormat("en-GB", {
        day: "numeric",
        month: "short",
        timeZone: "Europe/London",
      }).format(new Date(value.length === 10 ? `${value}T12:00:00Z` : value))
    : "Not set";
export const fieldLabel = (value: string) =>
  value.replaceAll("_", " ").replace(/^./, (s) => s.toUpperCase());
export function safeSource(url: string) {
  try {
    const parsed = new URL(url);
    return ["https:", "http:"].includes(parsed.protocol) ? parsed.href : null;
  } catch {
    return null;
  }
}
