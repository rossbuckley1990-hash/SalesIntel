"use client";
/**
 * SalesIntel for signed-in teams. It reuses the five SalesIntel workspaces unchanged and talks
 * only to the tenant-scoped API. Single-user tools are not offered here: the API does not serve
 * them to hosted workspaces.
 */
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import dynamic from "next/dynamic";
import { AlertCircle, ArrowRight, Bookmark, Briefcase, Building2, CalendarCheck, Check, CheckCircle2, Circle, Compass, LogOut, Mail, Menu, Search, Settings, Users, X } from "lucide-react";

import { ApiError, api, authMode, getWorkspace, setToken, setWorkspace, signOut } from "@/lib/session";
import { SERVICES, si, type AccountRow, type TodayT } from "@/features/workspace/si-api";
import type { SharedProps, Workspace } from "@/features/workspace/types";
import { Avatar, ViewerContext, initials, isMac, useFluidTabs, useNavIndicator } from "@/features/workspace/fluid";
import { CommandPalette, VIEW_KEYS } from "./command-palette";
import { ResearchBudget } from "@/features/workspace/research-budget";

const SiToday = dynamic(() => import("@/features/workspace/si-today").then((m) => m.SiToday));
const SiDiscover = dynamic(() => import("@/features/workspace/si-discover").then((m) => m.SiDiscover));
const SiAccounts = dynamic(() => import("@/features/workspace/si-accounts").then((m) => m.SiAccounts));
const SiEngage = dynamic(() => import("@/features/workspace/si-engage").then((m) => m.SiEngage));
const SiDeals = dynamic(() => import("@/features/workspace/si-deals").then((m) => m.SiDeals));
const SiReview = dynamic(() => import("@/features/workspace/si-review").then((m) => m.SiReview));

type Me = { mode: string; user: { id: number; name: string; email: string }; workspaces: { id: number; name: string; role: string; role_label: string }[] };
type Target = { amount: string | null; basis: string | null; basis_label: string | null; period: string | null };
type Current = { id: number; name: string; role: string; role_label: string; permissions: string[]; me: { territory: string[]; services: string[]; target: Target }; target_bases: Record<string, string> };
type Member = { user_id: number; name: string; email: string; role: string; role_label: string; target: Target };
type View = "today" | "find" | "clients" | "engage" | "deals" | "team" | "settings" | "review";

const NAV: { id: View; label: string; icon: typeof CalendarCheck }[] = [
  { id: "today", label: "Today", icon: CalendarCheck }, { id: "find", label: "Discover", icon: Compass }, { id: "clients", label: "Accounts", icon: Building2 },
  { id: "engage", label: "Engage", icon: Mail }, { id: "deals", label: "Deals", icon: Briefcase },
];
const LOWER: { id: View; label: string; icon: typeof CalendarCheck }[] = [{ id: "team", label: "Team", icon: Users }, { id: "settings", label: "My settings", icon: Settings }];
const TITLE: Record<View, string> = { today: "Today", find: "Discover", clients: "Accounts", engage: "Engage", deals: "Deals", team: "Team", settings: "My settings", review: "Blind review" };
const PERIODS: [string, string][] = [["annual", "a year"], ["quarterly", "a quarter"], ["monthly", "a month"]];

function viewFromUrl(): View {
  const v = new URL(window.location.href).searchParams.get("view") as View | null;
  return v && ["today", "find", "clients", "engage", "deals", "team", "settings", "review"].includes(v) ? v : "today";
}

export function HostedApp() {
  const [me, setMe] = useState<Me | null>(null);
  const [state, setState] = useState<"loading" | "signed-out" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const load = useCallback(async () => {
    try {
      const who = await api<Me>("/api/me");
      const invite = new URL(window.location.href).searchParams.get("invite");
      if (invite) {
        const url = new URL(window.location.href); url.searchParams.delete("invite"); window.history.replaceState({}, "", url);
        try { setWorkspace((await api<{ id: number }>("/api/invitations/accept", { method: "POST", json: { token: invite } })).id); }
        catch (e) { setNotice((e as Error).message); }
        return void load();
      }
      const chosen = who.workspaces.find((w) => String(w.id) === getWorkspace()) || who.workspaces[0];
      setWorkspace(chosen ? chosen.id : null);
      setMe(who); setState("ready");
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) setState("signed-out");
      else { setError((e as Error).message); setState("error"); }
    }
  }, []);
  useEffect(() => {
    void load();
    const out = () => { setMe(null); setState("signed-out"); };
    window.addEventListener("salesintel:signed-out", out);
    return () => window.removeEventListener("salesintel:signed-out", out);
  }, [load]);

  if (state === "loading") return <Centre><div className="ds-skeleton h-24 w-80 rounded-xl" aria-label="Loading" /></Centre>;
  if (state === "signed-out") return <SignIn onSignedIn={() => void load()} />;
  if (state === "error") return <Centre><div className="ds-card p-6" role="alert"><p className="font-semibold text-ds-ink">SalesIntel is unavailable</p><p className="mt-1 text-[13px] text-ds-muted">{error}</p><button className="ds-btn mt-3" onClick={() => void load()}>Try again</button></div></Centre>;
  if (!me?.workspaces.length) return <CreateWorkspace notice={notice} onCreated={(id) => { setWorkspace(id); void load(); }} />;
  return <Shell me={me} reload={() => void load()} />;
}

function Centre({ children }: { children: React.ReactNode }) {
  return <div className="ds-root si-auth flex min-h-screen items-center justify-center p-4"><div className="si-view w-full max-w-md">{children}</div></div>;
}

function Brand() {
  return <div className="mb-8 flex items-center gap-2.5"><span className="si-logo" aria-hidden="true" /><span className="si-wordmark">SalesIntel</span></div>;
}

function SignIn({ onSignedIn }: { onSignedIn: () => void }) {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError("");
    try {
      const { token } = await api<{ token: string }>("/api/dev/session", { method: "POST", json: { email, name } });
      setToken(token); onSignedIn();
    } catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  }
  return (
    <Centre>
      <div className="ds-card si-auth-card w-full p-7">
        <Brand />
        <h1 className="text-[22px] font-semibold tracking-[-0.02em] text-ds-ink">Sign in</h1>
        <p className="mt-1 text-[14px] text-ds-muted">Find the work others miss, and win it.</p>
        {authMode === "dev" ? <>
          <p className="mt-4 rounded-lg border border-ds-amber-line bg-ds-amber-soft px-3 py-2 text-[12px] text-ds-amber">Development sign-in for testing. A hosted SalesIntel signs you in through your company&apos;s identity provider.</p>
          <form className="mt-4 space-y-3" onSubmit={submit}>
            <label className="block"><span className="ds-label">Work email</span><input className="ds-input mt-1 h-10 w-full !pl-3" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></label>
            <label className="block"><span className="ds-label">Your name</span><input className="ds-input mt-1 h-10 w-full !pl-3" autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} required /></label>
            {error && <p role="alert" className="text-[13px] text-ds-red">{error}</p>}
            <button className="ds-btn primary !h-10 w-full" disabled={busy}>Continue <ArrowRight size={15} /></button>
          </form>
        </> : <p className="mt-2 text-[13px] text-ds-muted">Sign-in through your identity provider is not configured for this deployment yet.</p>}
      </div>
    </Centre>
  );
}

function CreateWorkspace({ onCreated, notice }: { onCreated: (id: number) => void; notice?: string }) {
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  async function submit(e: FormEvent) {
    e.preventDefault(); setError("");
    try { onCreated((await api<{ id: number }>("/api/workspaces", { method: "POST", json: { name } })).id); } catch (err) { setError((err as Error).message); }
  }
  return (
    <Centre>
      <form className="ds-card si-auth-card w-full p-7" onSubmit={submit} aria-label="Create your workspace">
        <Brand />
        {notice && <p role="alert" className="mb-3 rounded-lg border border-ds-amber-line bg-ds-amber-soft px-3 py-2 text-[13px] text-ds-amber">{notice}</p>}
        <h1 className="text-[22px] font-semibold tracking-[-0.02em] text-ds-ink">Create your company workspace</h1>
        <p className="mt-1 text-[13px] text-ds-muted">Your accounts, contacts, deals and research stay inside it. You can invite your team next.</p>
        <label className="mt-4 block"><span className="ds-label">Company name</span><input className="ds-input mt-1 h-10 w-full !pl-3" autoComplete="organization" value={name} onChange={(e) => setName(e.target.value)} required minLength={2} /></label>
        {error && <p role="alert" className="mt-2 text-[13px] text-ds-red">{error}</p>}
        <button className="ds-btn primary mt-5 !h-10 w-full">Create workspace <ArrowRight size={15} /></button>
        <p className="mt-3 text-[12px] text-ds-muted">Joining a colleague&apos;s workspace? Open the invitation link they sent you.</p>
      </form>
    </Centre>
  );
}

function Shell({ me, reload }: { me: Me; reload: () => void }) {
  const [current, setCurrent] = useState<Current | null>(null);
  const loadCurrent = useCallback(async () => setCurrent(await api<Current>("/api/workspace")), []);
  useEffect(() => { void loadCurrent(); }, [loadCurrent]);
  if (!current) return <Centre><div className="ds-skeleton h-24 w-full rounded-xl" aria-label="Loading" /></Centre>;
  return <Frame me={me} current={current} reload={reload} loadCurrent={loadCurrent} />;
}

function Frame({ me, current, reload, loadCurrent }: { me: Me; current: Current; reload: () => void; loadCurrent: () => Promise<void> }) {
  const [view, setView] = useState<View>(() => (typeof window === "undefined" ? "today" : viewFromUrl()));
  const [visit, setVisit] = useState(0);
  const [mobile, setMobile] = useState(false);
  const [palette, setPalette] = useState(0); // 0 is closed; each opening gets its own id, so it always starts fresh
  const [queue, setQueue] = useState<number | null>(null);
  const [recent, setRecent] = useState<AccountRow[]>([]);
  const [saved, setSaved] = useState<{ id: number; name: string }[]>([]);
  const [toast, setToast] = useState<{ id: number; message: string; error: boolean } | null>(null);
  const [main, setMain] = useState<HTMLElement | null>(null);
  const nav = useRef<HTMLElement>(null);
  const lower = useRef<HTMLDivElement>(null);
  const indicator = useNavIndicator(nav, view);
  const lowerIndicator = useNavIndicator(lower, view);
  useFluidTabs(main);
  const notify = useCallback((message: string, isError = false) => setToast({ id: Date.now(), message, error: isError }), []);
  useEffect(() => { const sync = () => setView(viewFromUrl()); window.addEventListener("popstate", sync); return () => window.removeEventListener("popstate", sync); }, []);
  useEffect(() => { if (!toast) return; const t = setTimeout(() => setToast(null), toast.error ? 15000 : 7000); return () => clearTimeout(t); }, [toast]);
  useEffect(() => {
    si<TodayT>("/today").then((t) => setQueue(t.queue.length)).catch(() => setQueue(null));
    // Recently active accounts and saved Discover views, for one-click return from anywhere.
    si<{ items: AccountRow[] }>("/accounts").then((d) => setRecent([...d.items].filter((a) => a.last_activity).sort((a, b) => (b.last_activity || "").localeCompare(a.last_activity || "")).slice(0, 4))).catch(() => setRecent([]));
    si<{ items: { id: number; name: string }[] }>("/saved-views").then((d) => setSaved(d.items.slice(0, 5))).catch(() => setSaved([]));
  }, [view]);
  const go = useCallback((next: View, params: Record<string, string | number> = {}) => {
    const url = new URL(window.location.href); url.search = ""; url.searchParams.set("view", next);
    for (const [k, v] of Object.entries(params)) url.searchParams.set(k, String(v));
    window.history.pushState({}, "", url); setView(next); setMobile(false);
    if (Object.keys(params).length) setVisit((n) => n + 1); // a jump with a target reopens the view on it
    window.scrollTo({ top: 0 });
  }, []);
  // ⌘K or Ctrl+K opens the command menu; G then a letter jumps between workspaces.
  useEffect(() => {
    let armed = 0;
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setPalette((v) => (v ? 0 : Date.now())); return; }
      const t = e.target as HTMLElement;
      if (["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName) || t.isContentEditable || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === "g") { armed = Date.now(); return; }
      if (armed && Date.now() - armed < 1200 && VIEW_KEYS[e.key]) { e.preventDefault(); go(VIEW_KEYS[e.key]); }
      armed = 0;
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go]);

  const done = { services: current.me.services.length > 0, territory: current.me.territory.length > 0, target: !!current.me.target.amount };
  const needsSetup = !done.services || !done.target;
  const shared = { data: { changes: [] } as unknown as Workspace, notify, inspect: () => {}, navigate: () => {}, refresh: async () => {}, selectedId: null, selectOpportunity: () => {} } as SharedProps;
  const ws = me.workspaces.find((w) => w.id === current.id);
  const viewer = { name: me.user.name || me.user.email, email: me.user.email, target: current.me.target.amount ? current.me.target : null };
  const item = (x: { id: View; label: string; icon: typeof CalendarCheck }) => (
    <button key={x.id} aria-current={view === x.id ? "page" : undefined} onClick={() => go(x.id)} className={`m-nav-item ${view === x.id ? "active" : ""}`}>
      <x.icon size={16} strokeWidth={1.6} /><span>{x.label}</span>
      {x.id === "today" && !!queue && <span className="si-nav-count hot" aria-hidden="true">{queue}</span>}
    </button>
  );
  return (
    <ViewerContext.Provider value={viewer}>
    <div className="m-workspace si-shell">
      <a className="m-skip" href="#m-main">Skip to workspace</a>
      {mobile && <button className="m-mobile-backdrop" aria-label="Close navigation" onClick={() => setMobile(false)} />}
      <aside id="m-navigation" className={`m-sidebar ${mobile ? "open" : ""}`}>
        <a className="m-brand" href="/?view=today" aria-label="SalesIntel home"><span className="si-logo" aria-hidden="true" /><span className="m-brand-wordmark">SalesIntel</span></a>
        <div className="si-switcher">
          <Avatar name={current.name} seed={`ws-${current.id}`} />
          <div className="min-w-0 flex-1"><small>Workspace</small>
            {me.workspaces.length > 1 ? <select aria-label="Workspace" className="ds-select w-full" value={current.id} onChange={(e) => { setWorkspace(Number(e.target.value)); window.location.assign("/?view=today"); }}>
              {me.workspaces.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}</select> : <strong>{current.name}</strong>}
          </div>
        </div>
        <nav aria-label="Main navigation" ref={nav} className={`si-nav ${indicator.ready ? "ready" : ""}`}>
          <span className="si-nav-indicator" style={indicator.style} aria-hidden="true" />
          {NAV.map(item)}
        </nav>
        {!!saved.length && <><p className="si-side-label">Saved views</p>
          {saved.map((v) => <a key={v.id} className="si-recent" href={`/?view=find&saved=${v.id}`} onClick={(e) => { e.preventDefault(); go("find", { saved: v.id }); }}>
            <Bookmark size={13} className="flex-none text-ds-muted" aria-hidden="true" /><span>{v.name}</span></a>)}</>}
        {!!recent.length && <><p className="si-side-label">Recently active</p>
          {recent.map((a) => <a key={a.id} className="si-recent" href={`/?view=clients&account=${a.id}`} onClick={(e) => { e.preventDefault(); go("clients", { account: a.id }); }}>
            <span className="si-mono-mark" aria-hidden="true">{initials(a.name)}</span><span>{a.name}</span></a>)}</>}
        <div className="m-sidebar-bottom">
          <div ref={lower} className={`si-nav ${lowerIndicator.ready ? "ready" : ""}`}>
            <span className="si-nav-indicator" style={lowerIndicator.style} aria-hidden="true" />
            {LOWER.map(item)}
          </div>
          <div className="si-profile">
            <Avatar name={viewer.name} seed={me.user.email} round small />
            <p><strong>{viewer.name}</strong><span>{ws?.role_label || current.role_label}</span></p>
            <button className="m-icon-button" aria-label="Sign out" title="Sign out" onClick={() => signOut()}><LogOut size={16} /></button>
          </div>
        </div>
      </aside>
      <div className="m-shell-main">
        <header className="m-topbar">
          <div className="si-crumb">
            <button className="m-icon-button m-menu" onClick={() => setMobile((v) => !v)} aria-label="Toggle navigation" aria-expanded={mobile} aria-controls="m-navigation"><Menu size={18} /></button>
            <span className="ws">{current.name}</span><span className="sep" aria-hidden="true">/</span><b>{TITLE[view]}</b>
          </div>
          <div className="m-topbar-right">
            <button className="si-cmdk" onClick={() => setPalette(Date.now())} aria-label="Open command menu" aria-keyshortcuts="Meta+K Control+K">
              <Search size={14} aria-hidden="true" /><span>Search or jump to…</span><span className="si-kbd" aria-hidden="true">{isMac() ? "⌘" : "Ctrl"} K</span>
            </button>
          </div>
        </header>
        <main id="m-main" ref={setMain} className={`m-main m-view-${view} m-modern-view`} tabIndex={-1}>
          {needsSetup && view !== "settings" && <div className="ds-root si-view mb-7"><section className="si-setup" aria-label="Getting started">
            <div className="flex min-w-0 items-center gap-3"><span className="si-setup-dot" aria-hidden="true" />
              <p className="text-[13px] text-ds-ink-2"><strong className="font-semibold text-ds-ink">Tell SalesIntel what you sell, where, and your target.</strong>{" "}
                <span className="text-ds-muted">Discovery ranks what fits you first.</span></p></div>
            <div className="flex flex-wrap items-center gap-4">
              {([["services", "What you sell"], ["territory", "Where"], ["target", "Target"]] as const).map(([k, l]) => <span key={k} className={`si-check ${done[k] ? "done" : ""}`}>
                {done[k] ? <Check strokeWidth={2.5} aria-hidden="true" /> : <Circle aria-hidden="true" />}{l}<span className="sr-only">{done[k] ? " (done)" : " (to do)"}</span></span>)}
              <button className="ds-btn primary sm" onClick={() => go("settings")}>Set up <ArrowRight size={14} /></button>
            </div></section></div>}
          <div key={`${view}-${visit}`} className="si-view">
            {view === "today" && <SiToday {...shared} />}
            {view === "find" && <SiDiscover {...shared} />}
            {view === "clients" && <SiAccounts {...shared} />}
            {view === "engage" && <SiEngage {...shared} />}
            {view === "deals" && <SiDeals {...shared} />}
            {view === "team" && <Team current={current} notify={notify} />}
            {view === "settings" && <MySettings current={current} notify={notify} saved={() => { void loadCurrent(); reload(); }} />}
            {view === "review" && <SiReview notify={notify} admin={current.permissions.includes("members.manage")} />}
          </div>
        </main>
      </div>
      <CommandPalette key={palette} open={palette > 0} close={() => setPalette(0)} go={go} signOut={() => signOut()} canInvite={current.permissions.includes("members.manage")} />
      {toast && <div key={toast.id} className={`m-toast ${toast.error ? "error" : ""}`} role={toast.error ? "alert" : "status"}>
        <span className="si-toast-icon" aria-hidden="true">{toast.error ? <AlertCircle size={15} /> : <CheckCircle2 size={15} />}</span>
        <span className="si-toast-text">{toast.message}</span>
        <button aria-label="Close notification" onClick={() => setToast(null)}><X size={15} /></button>
        <i className="si-toast-timer" style={{ animationDuration: `${toast.error ? 15000 : 7000}ms` }} aria-hidden="true" />
      </div>}
    </div>
    </ViewerContext.Provider>
  );
}

function MySettings({ current, notify, saved }: { current: Current; notify: (m: string, e?: boolean) => void; saved: () => void }) {
  const [services, setServices] = useState<string[]>(current.me.services);
  const [territory, setTerritory] = useState(current.me.territory.join(", "));
  const [amount, setAmount] = useState(current.me.target.amount || "");
  const [basis, setBasis] = useState(current.me.target.basis || "");
  const [period, setPeriod] = useState(current.me.target.period || "annual");
  const [sectors, setSectors] = useState("");
  const [dealMin, setDealMin] = useState("");
  const [dealMax, setDealMax] = useState("");
  const [capabilities, setCapabilities] = useState("");
  const writer = current.permissions.includes("crm.write");
  useEffect(() => {
    // Fill only what is still blank: a late response must never overwrite something already typed.
    si<{ sectors: string[]; deal_size_min: string | null; deal_size_max: string | null; capabilities: string[] }>("/preferences").then((p) => {
      setSectors((v) => v || p.sectors.join(", ")); setDealMin((v) => v || p.deal_size_min || ""); setDealMax((v) => v || p.deal_size_max || ""); setCapabilities((v) => v || p.capabilities.join(", "));
    }).catch(() => {});
  }, []);
  const list = (text: string) => text.split(",").map((t) => t.trim()).filter(Boolean);
  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      const places = territory.split(",").map((t) => t.trim()).filter(Boolean);
      await api("/api/workspace/me", { method: "PATCH", json: { services, territory: places, ...(amount ? { target_amount: amount.replace(/[£,\s]/g, ""), target_basis: basis || null, target_period: period } : {}) } });
      // These also describe what the company sells and where, which discovery and commercial fit use.
      if (writer) await si("/preferences", { method: "PUT", json: { services, territory: places, company_name: current.name, sectors: list(sectors),
        deal_size_min: dealMin.replace(/[£,\s]/g, "") || null, deal_size_max: dealMax.replace(/[£,\s]/g, "") || null, capabilities: list(capabilities) } });
      notify("Saved."); saved();
    } catch (err) { notify((err as Error).message, true); }
  }
  return (
    <form className="ds-root si-stagger max-w-2xl space-y-5" onSubmit={submit} aria-label="My settings">
      <header><h1 className="text-[26px] font-semibold leading-tight tracking-[-0.025em] text-ds-ink">My settings</h1>
        <p className="mt-1 text-[14px] text-ds-muted">What you sell, where, and your target. Discovery and fit use these straight away.</p></header>
      <fieldset className="ds-card p-4"><legend className="ds-label px-1">What you sell</legend>
        <div className="flex flex-wrap gap-1.5">{SERVICES.map(([v, l]) => <button type="button" key={v} aria-pressed={services.includes(v)} onClick={() => setServices(services.includes(v) ? services.filter((s) => s !== v) : [...services, v])}
          className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[13px] font-medium transition duration-150 active:scale-[.97] ${services.includes(v) ? "border-ds-brand bg-ds-brand-soft text-ds-brand shadow-ds-xs" : "border-ds-border bg-white text-ds-ink-2 hover:border-ds-border-strong"}`}>
          {services.includes(v) && <Check size={13} strokeWidth={2.5} aria-hidden="true" />}{l}</button>)}</div></fieldset>
      <label className="ds-card block p-4"><span className="ds-label">Territory</span><input className="ds-input mt-1 h-10 w-full" aria-label="Territory" placeholder="e.g. England, Yorkshire" value={territory} onChange={(e) => setTerritory(e.target.value)} /></label>
      <fieldset className="ds-card grid gap-3 p-4 sm:grid-cols-2"><legend className="ds-label px-1">Customers you want</legend>
        <label className="block sm:col-span-2"><span className="ds-label">Customer sectors</span><input className="ds-input mt-1 h-10 w-full" aria-label="Customer sectors" placeholder="e.g. Logistics, Housing, Healthcare" value={sectors} onChange={(e) => setSectors(e.target.value)} /></label>
        <label className="block"><span className="ds-label">Smallest contract (£)</span><input className="ds-input mt-1 h-10 w-full" inputMode="decimal" aria-label="Smallest contract" value={dealMin} onChange={(e) => setDealMin(e.target.value)} /></label>
        <label className="block"><span className="ds-label">Largest contract (£)</span><input className="ds-input mt-1 h-10 w-full" inputMode="decimal" aria-label="Largest contract" value={dealMax} onChange={(e) => setDealMax(e.target.value)} /></label>
        <label className="block sm:col-span-2"><span className="ds-label">Capabilities and accreditations</span><input className="ds-input mt-1 h-10 w-full" aria-label="Capabilities" placeholder="e.g. BAFE SP203-1, NSI Gold, 24/7 call-out" value={capabilities} onChange={(e) => setCapabilities(e.target.value)} /></label>
        <p className="text-[12px] text-ds-muted sm:col-span-2">Discovery ranks what fits these first and shows why. Capabilities are recorded as you state them; SalesIntel does not assume compliance.</p>
      </fieldset>
      <fieldset className="ds-card p-4"><legend className="ds-label px-1">Your new-business target</legend>
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="block"><span className="ds-label">Amount (£)</span><input className="ds-input mt-1 h-10 w-full" inputMode="decimal" aria-label="Target amount" value={amount} onChange={(e) => setAmount(e.target.value)} /></label>
          <label className="block"><span className="ds-label">Measured as</span><select className="ds-select mt-1 w-full" aria-label="Target measured as" value={basis} onChange={(e) => setBasis(e.target.value)} required={!!amount}>
            <option value="">Choose…</option>{Object.entries(current.target_bases).map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
          <label className="block"><span className="ds-label">Per</span><select className="ds-select mt-1 w-full" aria-label="Target period" value={period} onChange={(e) => setPeriod(e.target.value)}>{PERIODS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
        </div>
        <p className="mt-2 text-[12px] text-ds-muted">Contract value, total contract value and margin are different numbers. SalesIntel never adds one to another.</p></fieldset>
      <button className="ds-btn primary">Save</button>
    </form>
  );
}

function Team({ current, notify }: { current: Current; notify: (m: string, e?: boolean) => void }) {
  const [members, setMembers] = useState<{ items: Member[]; roles: { role: string; label: string }[]; invitations: { id: number; email: string; role: string }[] } | null>(null);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("salesperson");
  const [link, setLink] = useState("");
  const manage = current.permissions.includes("members.manage");
  const load = useCallback(async () => setMembers(await api("/api/workspace/members")), []);
  useEffect(() => { void load(); }, [load]);
  async function invite(e: FormEvent) {
    e.preventDefault();
    try {
      const made = await api<{ token: string }>("/api/workspace/invitations", { method: "POST", json: { email, role } });
      setLink(`${window.location.origin}/?invite=${made.token}`); setEmail(""); void load();
    } catch (err) { notify((err as Error).message, true); }
  }
  async function change(userId: number, next: string) {
    try { await api(`/api/workspace/members/${userId}`, { method: "PATCH", json: { role: next } }); notify("Role changed."); void load(); } catch (err) { notify((err as Error).message, true); }
  }
  return (
    <div className="ds-root si-stagger max-w-3xl space-y-5">
      <header><h1 className="text-[26px] font-semibold leading-tight tracking-[-0.025em] text-ds-ink">Team</h1>
        <p className="mt-1 text-[14px] text-ds-muted">Everyone in this workspace and what their role allows.</p></header>
      <div className="ds-card divide-y divide-ds-border">{(members?.items || []).map((m) => <div key={m.user_id} className="flex flex-wrap items-center justify-between gap-2 p-3">
        <div className="flex min-w-0 items-center gap-3"><Avatar name={m.name || m.email} seed={m.email} round small /><div className="min-w-0"><p className="text-[14px] font-semibold text-ds-ink">{m.name || m.email}</p><p className="text-[12px] text-ds-muted">{m.email}{m.target.amount ? ` · target £${Number(m.target.amount).toLocaleString("en-GB")} ${m.target.basis_label?.toLowerCase()}` : ""}</p></div></div>
        {manage ? <select aria-label={`Role for ${m.name || m.email}`} className="ds-select" value={m.role} onChange={(e) => void change(m.user_id, e.target.value)}>{members?.roles.map((r) => <option key={r.role} value={r.role}>{r.label}</option>)}</select>
          : <span className="text-[13px] text-ds-ink-2">{m.role_label}</span>}
      </div>)}</div>
      <section className="ds-card flex flex-wrap items-center justify-between gap-3 p-4" aria-label="Opportunity review">
        <div><p className="text-[14px] font-semibold text-ds-ink">Blind opportunity review</p>
          <p className="text-[12.5px] text-ds-muted">Judge a frozen sample of discovered opportunities without being told where each came from. Your answers measure whether SalesIntel finds better leads.</p></div>
        <a className="ds-btn" href="/?view=review">Open the review</a></section>
      <ResearchBudget manage={manage} notify={notify} />
      {manage && <form className="ds-card space-y-3 p-4" onSubmit={invite} aria-label="Invite a colleague">
        <p className="text-[14px] font-semibold text-ds-ink">Invite a colleague</p>
        <div className="flex flex-wrap gap-2"><input className="ds-input h-10 min-w-[220px] flex-1" type="email" aria-label="Colleague's email" placeholder="name@company.co.uk" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <select className="ds-select" aria-label="Their role" value={role} onChange={(e) => setRole(e.target.value)}>{members?.roles.map((r) => <option key={r.role} value={r.role}>{r.label}</option>)}</select>
          <button className="ds-btn primary">Create invitation</button></div>
        {link && <div className="rounded-lg border border-ds-border bg-ds-canvas p-3 text-[13px]"><p className="font-semibold text-ds-ink">Send this link to them yourself. It works once, for that email address, for 7 days.</p>
          <input readOnly aria-label="Invitation link" className="ds-input mt-2 h-9 w-full font-mono text-[12px]" value={link} onFocus={(e) => e.target.select()} /></div>}
      </form>}
    </div>
  );
}

