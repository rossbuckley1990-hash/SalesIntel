/**
 * Who is signed in, and which of their workspaces they are using.
 *
 * local: a single-user install; nothing is sent. dev: tokens from the development sign-in
 * (demo and test only). oidc: the managed identity provider's SDK supplies the token through
 * setTokenSource; SalesIntel never sees a password.
 *
 * The workspace id sent with each request is only a choice among the user's own workspaces:
 * the API checks the membership and refuses any other.
 */
import { getApiBaseUrl } from "@/lib/api";

export type AuthMode = "local" | "dev" | "oidc";
export const authMode = (process.env.NEXT_PUBLIC_AUTH_MODE || "local") as AuthMode;
const TOKEN = "salesintel.session";
const WORKSPACE = "salesintel.workspace";

let tokenSource: (() => string | null) | null = null;
export function setTokenSource(source: () => string | null) { tokenSource = source; }

function store(): Storage | null {
  try { return typeof window === "undefined" ? null : window.sessionStorage; } catch { return null; }
}
export function getToken(): string | null { return tokenSource ? tokenSource() : store()?.getItem(TOKEN) ?? null; }
export function setToken(token: string | null) { if (token) store()?.setItem(TOKEN, token); else store()?.removeItem(TOKEN); }
export function getWorkspace(): string | null { return store()?.getItem(WORKSPACE) ?? null; }
export function setWorkspace(id: number | null) { if (id) store()?.setItem(WORKSPACE, String(id)); else store()?.removeItem(WORKSPACE); }
export function signOut() { setToken(null); setWorkspace(null); window.dispatchEvent(new Event("salesintel:signed-out")); }

export function authHeaders(): Record<string, string> {
  if (authMode === "local") return {};
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const workspace = getWorkspace();
  if (workspace) headers["X-SalesIntel-Workspace"] = workspace;
  return headers;
}

export class ApiError extends Error { constructor(message: string, readonly status: number) { super(message); } }

export async function api<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, ...rest } = init;
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    cache: "no-store", ...rest,
    headers: { ...(json !== undefined ? { "content-type": "application/json" } : {}), ...authHeaders(), ...((rest.headers as Record<string, string>) || {}) },
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  });
  const payload = await response.json().catch(() => null);
  if (response.status === 401 && authMode !== "local") window.dispatchEvent(new Event("salesintel:signed-out"));
  if (!response.ok) {
    const detail = payload?.detail;
    throw new ApiError(typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map((d: { msg: string }) => d.msg).join(" · ") : `Request failed (${response.status})`, response.status);
  }
  return payload as T;
}
