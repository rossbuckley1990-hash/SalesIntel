"use client";
/**
 * SalesIntel for signed-in teams. It reuses the five SalesIntel workspaces unchanged and talks
 * only to the tenant-scoped API. Single-user tools are not offered here: the API does not serve
 * them to hosted workspaces.
 */
import { useCallback, useEffect, useState, type FormEvent } from "react";
import dynamic from "next/dynamic";
import { Briefcase, Building2, CalendarCheck, Compass, LogOut, Mail, Menu, Settings, Users } from "lucide-react";

import { ApiError, api, authMode, getWorkspace, setToken, setWorkspace, signOut } from "@/lib/session";
import { SERVICES, si } from "@/features/workspace/si-api";
import type { SharedProps, Workspace } from "@/features/workspace/types";

const SiToday = dynamic(() => import("@/features/workspace/si-today").then((m) => m.SiToday));
const SiDiscover = dynamic(() => import("@/features/workspace/si-discover").then((m) => m.SiDiscover));
const SiAccounts = dynamic(() => import("@/features/workspace/si-accounts").then((m) => m.SiAccounts));
const SiEngage = dynamic(() => import("@/features/workspace/si-engage").then((m) => m.SiEngage));
const SiDeals = dynamic(() => import("@/features/workspace/si-deals").then((m) => m.SiDeals));

type Me = { mode: string; user: { id: number; name: string; email: string }; workspaces: { id: number; name: string; role: string; role_label: string }[] };
type Target = { amount: string | null; basis: string | null; basis_label: string | null; period: string | null };
type Current = { id: number; name: string; role: string; role_label: string; permissions: string[]; me: { territory: string[]; services: string[]; target: Target }; target_bases: Record<string, string> };
type Member = { user_id: number; name: string; email: string; role: string; role_label: string; target: Target };
type View = "today" | "find" | "clients" | "engage" | "deals" | "team" | "settings";

const NAV: { id: View; label: string; icon: typeof CalendarCheck }[] = [
  { id: "today", label: "Today", icon: CalendarCheck }, { id: "find", label: "Discover", icon: Compass }, { id: "clients", label: "Accounts", icon: Building2 },
  { id: "engage", label: "Engage", icon: Mail }, { id: "deals", label: "Deals", icon: Briefcase },
];
const PERIODS: [string, string][] = [["annual", "a year"], ["quarterly", "a quarter"], ["monthly", "a month"]];

function viewFromUrl(): View {
  const v = new URL(window.location.href).searchParams.get("view") as View | null;
  return v && ["today", "find", "clients", "engage", "deals", "team", "settings"].includes(v) ? v : "today";
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
  return <div className="ds-root flex min-h-screen items-center justify-center bg-ds-canvas p-4">{children}</div>;
}

function Brand() {
  return <div className="mb-5 flex items-center gap-2"><span className="m-brand-mark" aria-hidden="true">S<span>i</span></span><span className="text-[18px] font-semibold text-ds-ink">SalesIntel</span></div>;
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
      <div className="ds-card w-full max-w-sm p-6">
        <Brand />
        <h1 className="text-[20px] font-semibold text-ds-ink">Sign in</h1>
        {authMode === "dev" ? <>
          <p className="mt-1 rounded-lg border border-ds-amber-line bg-ds-amber-soft px-3 py-2 text-[12px] text-ds-amber">Development sign-in for testing. A hosted SalesIntel signs you in through your company&apos;s identity provider.</p>
          <form className="mt-4 space-y-3" onSubmit={submit}>
            <label className="block"><span className="ds-label">Work email</span><input className="ds-input mt-1 h-10 w-full" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></label>
            <label className="block"><span className="ds-label">Your name</span><input className="ds-input mt-1 h-10 w-full" value={name} onChange={(e) => setName(e.target.value)} required /></label>
            {error && <p role="alert" className="text-[13px] text-ds-red">{error}</p>}
            <button className="ds-btn primary w-full" disabled={busy}>Continue</button>
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
      <form className="ds-card w-full max-w-md p-6" onSubmit={submit} aria-label="Create your workspace">
        <Brand />
        {notice && <p role="alert" className="mb-3 rounded-lg border border-ds-amber-line bg-ds-amber-soft px-3 py-2 text-[13px] text-ds-amber">{notice}</p>}
        <h1 className="text-[20px] font-semibold text-ds-ink">Create your company workspace</h1>
        <p className="mt-1 text-[13px] text-ds-muted">Your accounts, contacts, deals and research stay inside it. You can invite your team next.</p>
        <label className="mt-4 block"><span className="ds-label">Company name</span><input className="ds-input mt-1 h-10 w-full" value={name} onChange={(e) => setName(e.target.value)} required minLength={2} /></label>
        {error && <p role="alert" className="mt-2 text-[13px] text-ds-red">{error}</p>}
        <button className="ds-btn primary mt-4 w-full">Create workspace</button>
        <p className="mt-3 text-[12px] text-ds-muted">Joining a colleague&apos;s workspace? Open the invitation link they sent you.</p>
      </form>
    </Centre>
  );
}

function Shell({ me, reload }: { me: Me; reload: () => void }) {
  const [view, setView] = useState<View>("today");
  const [mobile, setMobile] = useState(false);
  const [current, setCurrent] = useState<Current | null>(null);
  const [toast, setToast] = useState<{ message: string; error: boolean } | null>(null);
  const notify = useCallback((message: string, isError = false) => setToast({ message, error: isError }), []);
  const loadCurrent = useCallback(async () => setCurrent(await api<Current>("/api/workspace")), []);
  useEffect(() => { setView(viewFromUrl()); void loadCurrent(); const sync = () => setView(viewFromUrl()); window.addEventListener("popstate", sync); return () => window.removeEventListener("popstate", sync); }, [loadCurrent]);
  useEffect(() => { if (!toast) return; const t = setTimeout(() => setToast(null), toast.error ? 15000 : 7000); return () => clearTimeout(t); }, [toast]);
  const go = (next: View) => { const url = new URL(window.location.href); url.search = ""; url.searchParams.set("view", next); window.history.pushState({}, "", url); setView(next); setMobile(false); };
  if (!current) return <Centre><div className="ds-skeleton h-24 w-80 rounded-xl" aria-label="Loading" /></Centre>;
  const needsSetup = !current.me.services.length || !current.me.target.amount;
  const shared = { data: { changes: [] } as unknown as Workspace, notify, inspect: () => {}, navigate: () => {}, refresh: async () => {}, selectedId: null, selectOpportunity: () => {} } as SharedProps;
  const ws = me.workspaces.find((w) => w.id === current.id);
  return (
    <div className="m-workspace">
      <a className="m-skip" href="#m-main">Skip to workspace</a>
      {mobile && <button className="m-mobile-backdrop" aria-label="Close navigation" onClick={() => setMobile(false)} />}
      <aside id="m-navigation" className={`m-sidebar ${mobile ? "open" : ""}`}>
        <a className="m-brand" href="/?view=today" aria-label="SalesIntel home"><span className="m-brand-mark" aria-hidden="true">S<span>i</span></span><span className="m-brand-wordmark">SalesIntel<small>Find · Research · Win</small></span></a>
        <div className="m-workspace-name"><div><small>YOUR WORKSPACE</small>
          {me.workspaces.length > 1 ? <select aria-label="Workspace" className="ds-select mt-1 w-full" value={current.id} onChange={(e) => { setWorkspace(Number(e.target.value)); window.location.assign("/?view=today"); }}>
            {me.workspaces.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}</select> : <strong>{current.name}</strong>}
        </div></div>
        <nav aria-label="Main navigation">
          {NAV.map((item) => <button key={item.id} aria-current={view === item.id ? "page" : undefined} onClick={() => go(item.id)} className={`m-nav-item ${view === item.id ? "active" : ""}`}><item.icon size={18} strokeWidth={1.75} /><span>{item.label}</span></button>)}
        </nav>
        <div className="m-sidebar-bottom">
          <button className={`m-nav-item ${view === "team" ? "active" : ""}`} onClick={() => go("team")} aria-current={view === "team" ? "page" : undefined}><Users size={18} strokeWidth={1.75} /><span>Team</span></button>
          <button className={`m-nav-item ${view === "settings" ? "active" : ""}`} onClick={() => go("settings")} aria-current={view === "settings" ? "page" : undefined}><Settings size={18} strokeWidth={1.75} /><span>My settings</span></button>
        </div>
      </aside>
      <div className="m-shell-main">
        <header className="m-topbar">
          <div className="m-breadcrumb">
            <button className="m-icon-button m-menu" onClick={() => setMobile((v) => !v)} aria-label="Toggle navigation" aria-expanded={mobile} aria-controls="m-navigation"><Menu size={20} /></button>
            <span>{current.name}</span></div>
          <div className="m-topbar-right">
            <span className="text-[13px] text-ds-ink-2">{me.user.name} · <span className="font-semibold">{ws?.role_label || current.role_label}</span></span>
            <button className="m-icon-button" aria-label="Sign out" title="Sign out" onClick={() => signOut()}><LogOut size={17} /></button>
          </div>
        </header>
        <main id="m-main" className={`m-main m-view-${view} m-modern-view`} tabIndex={-1}>
          {needsSetup && view !== "settings" && <div className="ds-root mb-4"><div className="ds-card flex flex-wrap items-center justify-between gap-3 border-ds-brand-line bg-ds-brand-soft p-4">
            <p className="text-[14px] text-ds-ink"><strong>Tell SalesIntel what you sell, where, and your target.</strong> It uses this to judge fit and to show your progress.</p>
            <button className="ds-btn primary" onClick={() => go("settings")}>Set up</button></div></div>}
          {view === "today" && <SiToday {...shared} />}
          {view === "find" && <SiDiscover {...shared} />}
          {view === "clients" && <SiAccounts {...shared} />}
          {view === "engage" && <SiEngage {...shared} />}
          {view === "deals" && <SiDeals {...shared} />}
          {view === "team" && <Team current={current} notify={notify} />}
          {view === "settings" && <MySettings current={current} notify={notify} saved={() => { void loadCurrent(); reload(); }} />}
        </main>
      </div>
      {toast && <div className={`m-toast ${toast.error ? "error" : ""}`} role={toast.error ? "alert" : "status"}>{toast.message}</div>}
    </div>
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
    si<{ sectors: string[]; deal_size_min: string | null; deal_size_max: string | null; capabilities: string[] }>("/preferences").then((p) => {
      setSectors(p.sectors.join(", ")); setDealMin(p.deal_size_min || ""); setDealMax(p.deal_size_max || ""); setCapabilities(p.capabilities.join(", "));
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
    <form className="ds-root max-w-2xl space-y-5" onSubmit={submit} aria-label="My settings">
      <h1 className="text-[22px] font-semibold text-ds-ink">My settings</h1>
      <fieldset className="ds-card p-4"><legend className="ds-label px-1">What you sell</legend>
        <div className="flex flex-wrap gap-1.5">{SERVICES.map(([v, l]) => <button type="button" key={v} aria-pressed={services.includes(v)} onClick={() => setServices(services.includes(v) ? services.filter((s) => s !== v) : [...services, v])}
          className={`rounded-full border px-3 py-1 text-[13px] font-medium ${services.includes(v) ? "border-ds-brand bg-ds-brand-soft text-ds-brand" : "border-ds-border bg-white text-ds-ink-2"}`}>{l}</button>)}</div></fieldset>
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
    <div className="ds-root max-w-3xl space-y-5">
      <h1 className="text-[22px] font-semibold text-ds-ink">Team</h1>
      <div className="ds-card divide-y divide-ds-border">{(members?.items || []).map((m) => <div key={m.user_id} className="flex flex-wrap items-center justify-between gap-2 p-3">
        <div><p className="text-[14px] font-semibold text-ds-ink">{m.name || m.email}</p><p className="text-[12px] text-ds-muted">{m.email}{m.target.amount ? ` · target £${Number(m.target.amount).toLocaleString("en-GB")} ${m.target.basis_label?.toLowerCase()}` : ""}</p></div>
        {manage ? <select aria-label={`Role for ${m.name || m.email}`} className="ds-select" value={m.role} onChange={(e) => void change(m.user_id, e.target.value)}>{members?.roles.map((r) => <option key={r.role} value={r.role}>{r.label}</option>)}</select>
          : <span className="text-[13px] text-ds-ink-2">{m.role_label}</span>}
      </div>)}</div>
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
