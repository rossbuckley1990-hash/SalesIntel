"use client";
import { useCallback, useEffect, useState } from "react";
import { ArrowDown, ArrowLeft, ArrowUp, ArrowUpRight, Briefcase, Building2, CheckCircle2, CircleHelp, Eye, EyeOff, Globe, Link2, MapPin, Plus, Search, UserPlus } from "lucide-react";
import { EmptyState, Pill } from "./ds";
import { safeUrl } from "./radar-model";
import { BASIS_LABEL, STAGE_LABEL, dayLabel, goto, param, si, type AccountRow, type AccountT } from "./si-api";
import { ActivityForm, Basis, ContactCard, PageHeader, Panel, TaskRow, Timeline, useUrl } from "./si-shared";
import { PeopleFinder } from "./si-people";
import { AccountSuppliers } from "./si-atlas";
import { DossierPanel } from "./si-shadow";
import { CommitteePanel, GapsPanel, usePlay } from "./si-intel";
import { ActionDock, OpportunityBrief, useOpportunity, useWide } from "./si-living";
import type { SharedProps } from "./types";
import { initials } from "./fluid";

type SortKey = "name" | "status" | "sources" | "contacts" | "open_deals" | "next_due" | "last_activity";
const FILTERS: [string, string, (r: AccountRow) => boolean][] = [
  ["all", "All", () => true], ["customer", "Customers", (r) => r.status === "customer"], ["opportunity", "Opportunities", (r) => r.status === "opportunity"],
  ["deals", "With open deals", (r) => r.open_deals > 0], ["due", "Follow-up overdue", (r) => r.overdue], ["watched", "Watched", (r) => r.watched]];
const since = (iso: string | null) => { if (!iso) return null; const d = Math.floor((Date.now() - Date.parse(iso)) / 86400000); return d <= 0 ? "Today" : d === 1 ? "Yesterday" : d < 30 ? `${d} days ago` : d < 365 ? `${Math.floor(d / 30)} mo ago` : `${Math.floor(d / 365)} yr ago`; };

export function SiAccounts(props: SharedProps) {
  useUrl();
  const id = Number(param("account"));
  return id > 0 ? <AccountRecord key={id} id={id} {...props} /> : <AccountList {...props} />;
}

function AccountList({ notify }: SharedProps) {
  const [rows, setRows] = useState<AccountRow[] | null>(null);
  const [q, setQ] = useState("");
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [filter, setFilter] = useState("all");
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "last_activity", dir: -1 });
  useEffect(() => { si<{ items: AccountRow[] }>(`/accounts?q=${encodeURIComponent(q)}`).then((d) => setRows(d.items)).catch((e) => notify(e.message, true)); }, [q, notify]);
  async function create(e: React.FormEvent) {
    e.preventDefault();
    try {
      const r = await si<{ account_id: number; created: boolean }>("/accounts", { method: "POST", json: { name } });
      notify(r.created ? "Account created." : "An account with that name already exists. Opening it.");
      goto("clients", { account: r.account_id });
    } catch (err) { notify((err as Error).message, true); }
  }
  return (
    <div className="ds-root space-y-5">
      <PageHeader eyebrow="Relationships" title="Accounts" actions={<button className="ds-btn primary" onClick={() => setAdding((v) => !v)}><Plus size={15} /> New account</button>}>
        Every organisation you are working, with its evidence, people, history and next step in one place.
      </PageHeader>
      {adding && <form onSubmit={create} className="ds-card flex flex-wrap items-end gap-3 p-4">
        <label className="min-w-[260px] flex-1"><span className="ds-label">Organisation name</span><input className="mt-1 block h-10 w-full rounded-lg border border-ds-border-strong px-3 text-[14px]" value={name} onChange={(e) => setName(e.target.value)} required minLength={2} autoFocus /></label>
        <button className="ds-btn primary">Create</button>
      </form>}
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative w-full max-w-xs"><Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ds-muted" />
          <input className="ds-input !pl-9" aria-label="Search accounts" placeholder="Search accounts" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        {rows && !!rows.length && <div className="ds-tabs" role="group" aria-label="Show">
          {FILTERS.map(([id, label, test]) => <button key={id} aria-pressed={filter === id} onClick={() => setFilter(id)}>{label}<span>{rows.filter(test).length}</span></button>)}
        </div>}
      </div>
      {!rows && <div className="ds-skeleton h-40 rounded-xl" />}
      {rows && !rows.length && <div className="ds-card"><EmptyState icon={<Building2 size={20} />} title="No accounts yet" action={<button className="ds-btn primary" onClick={() => goto("find")}>Go to Discover</button>}>Accounts are created when you investigate an opportunity in Discover, or add one yourself.</EmptyState></div>}
      {rows && !!rows.length && <AccountTable rows={rows.filter(FILTERS.find((f) => f[0] === filter)![2])} sort={sort} setSort={setSort} />}
    </div>
  );
}

function AccountTable({ rows, sort, setSort }: { rows: AccountRow[]; sort: { key: SortKey; dir: 1 | -1 }; setSort: (s: { key: SortKey; dir: 1 | -1 }) => void }) {
  const value = (r: AccountRow, k: SortKey): string | number => k === "next_due" ? (r.next_due || "9999") : k === "last_activity" ? (r.last_activity || "") : k === "name" || k === "status" ? String(r[k]).toLowerCase() : Number(r[k]);
  const sorted = [...rows].sort((a, b) => { const x = value(a, sort.key), y = value(b, sort.key); return (x < y ? -1 : x > y ? 1 : 0) * sort.dir; });
  const Head = ({ k, label, className = "" }: { k: SortKey; label: string; className?: string }) => {
    const on = sort.key === k;
    return <th className={`px-3 py-2.5 font-medium ${className}`} aria-sort={on ? (sort.dir === 1 ? "ascending" : "descending") : "none"}>
      <button className={`inline-flex items-center gap-1 ${on ? "text-ds-ink" : "hover:text-ds-ink"}`} onClick={() => setSort({ key: k, dir: on ? (sort.dir === 1 ? -1 : 1) : k === "name" || k === "next_due" ? 1 : -1 })}>
        {label}{on && (sort.dir === 1 ? <ArrowUp size={12} aria-hidden="true" /> : <ArrowDown size={12} aria-hidden="true" />)}</button></th>;
  };
  if (!rows.length) return <div className="ds-card px-4 py-10 text-center text-[13px] text-ds-muted">No accounts match this filter.</div>;
  return (
    <div className="ds-card overflow-x-auto">
      <table className="w-full min-w-[820px] text-left text-[13px]">
        <thead><tr className="border-b border-ds-border text-[12px] text-ds-muted">
          <Head k="name" label="Account" className="pl-4" /><Head k="status" label="Status" /><Head k="sources" label="Evidence" /><Head k="contacts" label="Contacts" />
          <Head k="open_deals" label="Open deals" /><Head k="last_activity" label="Last activity" /><Head k="next_due" label="Next follow-up" /></tr></thead>
        <tbody>{sorted.map((r) => (
          <tr key={r.id} className="si-row cursor-pointer border-b border-ds-border last:border-0" onClick={() => goto("clients", { account: r.id })}>
            <td className="py-2.5 pl-4 pr-3"><span className="flex items-center gap-2.5"><span className="si-mono-mark !h-7 !w-7 !text-[10px]" aria-hidden="true">{initials(r.name)}</span>
              <span className="min-w-0"><button className="block text-left font-semibold text-ds-ink hover:underline" onClick={(e) => { e.stopPropagation(); goto("clients", { account: r.id }); }}>{r.name}</button>
              <span className="block text-[12px] text-ds-muted">{[r.kind === "public_body" ? "Public body" : r.kind === "private" ? "Private" : "", r.sector, r.region].filter(Boolean).join(" · ") || "Organisation"}</span></span></span></td>
            <td className="px-3"><span className="inline-flex items-center gap-1.5 text-ds-ink-2"><i aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${r.status === "customer" ? "bg-ds-green" : r.status === "opportunity" ? "bg-[#c2410c]" : "bg-ds-border-strong"}`} />
              {r.status[0].toUpperCase() + r.status.slice(1)}</span>{r.watched && <Eye size={13} className="ml-1.5 inline text-ds-muted" aria-label="Watched" />}</td>
            <td className="si-mono px-3 text-ds-ink-2">{r.sources}</td><td className="si-mono px-3 text-ds-ink-2">{r.contacts}</td><td className="si-mono px-3 text-ds-ink-2">{r.open_deals}</td>
            <td className="px-3 text-ds-muted">{since(r.last_activity) || "None yet"}</td>
            <td className={`px-3 font-medium ${r.overdue ? "text-ds-red" : "text-ds-muted"}`}>{r.next_due ? dayLabel(r.next_due) : "None"}</td>
          </tr>))}</tbody>
      </table>
    </div>
  );
}

function AccountRecord({ id, notify }: SharedProps & { id: number }) {
  const [a, setA] = useState<AccountT | null>(null);
  const [error, setError] = useState("");
  const [panel, setPanel] = useState<"" | "contact" | "site">("");
  const [suggest, setSuggest] = useState<{ source: string; name: string; why: string }[]>([]);
  const [investigations, setInvestigations] = useState(0);
  const [play, reloadPlay] = usePlay(id);
  const load = useCallback(async () => {
    try { setA(await si<AccountT>(`/accounts/${id}`)); setError(""); } catch (e) { setError((e as Error).message); }
  }, [id]);
  // The Living Opportunity for this account: its brief and the one next move, shared with every other screen.
  const op = useOpportunity(`acct:${id}`, notify, { onChanged: () => { void load(); setInvestigations((n) => n + 1); } });
  const changed = () => { void load(); void op.reload(); };
  const [frame, wide] = useWide(1000);
  useEffect(() => { if (a) void reloadPlay(); }, [a, reloadPlay]); // every recorded change can move the play on
  useEffect(() => { void load(); si<{ items: typeof suggest }>(`/accounts/${id}/suggestions`).then((d) => setSuggest(d.items)).catch(() => {}); }, [id, load]);
  if (error) return <div className="ds-root"><button className="ds-btn ghost sm" onClick={() => goto("clients")}><ArrowLeft size={14} /> Accounts</button><p role="alert" className="mt-4 text-ds-red">{error}</p></div>;
  if (!a) return <div className="ds-root space-y-3"><div className="ds-skeleton h-24 rounded-xl" /><div className="ds-skeleton h-64 rounded-xl" /></div>;
  const site = safeUrl(a.website);

  async function call(path: string, method: string, json?: unknown, done?: string) {
    try { await si(path, { method, json }); if (done) notify(done); changed(); return true; } catch (e) { notify((e as Error).message, true); return false; }
  }
  return (
    <div className="ds-root space-y-5">
      <button className="ds-btn ghost sm -ml-2" onClick={() => goto("clients")}><ArrowLeft size={14} /> Accounts</button>
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-1.5"><Pill tone={a.status === "customer" ? "green" : a.status === "opportunity" ? "brand" : "neutral"}>{a.status}</Pill><Pill>{a.kind === "public_body" ? "Public body" : a.kind === "private" ? "Private company" : "Organisation"}</Pill></div>
          <h1 className="mt-2 text-[26px] font-semibold leading-tight tracking-[-0.025em] text-ds-ink">{a.name}</h1>
          <p className="mt-1 flex flex-wrap gap-x-3 text-[13px] text-ds-muted">{a.sector && <span>{a.sector}</span>}{a.region && <span className="line-clamp-1">{a.region}</span>}
            {site && <a className="inline-flex items-center gap-1 font-medium text-ds-brand hover:underline" href={site} target="_blank" rel="noreferrer"><Globe size={13} />{new URL(site).hostname.replace(/^www\./, "")}</a>}
            {a.company_number && <a className="hover:underline" href={`https://find-and-update.company-information.service.gov.uk/company/${a.company_number}`} target="_blank" rel="noreferrer">Company {a.company_number}</a>}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {/* Qualifying is always possible here; it is offered as the next move only once the customer has stated a requirement. */}
          {op.brief && op.brief.next.action !== "qualify" && !a.deals.length && <button className="ds-btn ghost" onClick={() => { op.setForm("qualify"); document.querySelector('[aria-label="Next move"]')?.scrollIntoView({ behavior: "smooth", block: "start" }); }}>
            <Briefcase size={15} /> Qualify into a deal</button>}
          <button className="ds-btn ghost" onClick={() => void call(`/accounts/${a.id}`, "PATCH", { watched: !a.watched }, a.watched ? "No longer watching." : "Watching. New intelligence will appear on Today.")}>{a.watched ? <><EyeOff size={15} /> Unwatch</> : <><Eye size={15} /> Watch</>}</button>
        </div>
      </header>
      <div ref={frame} className={`lo-account ${wide ? "wide" : ""}`}>
        <OpportunityBrief op={op} afterReveal={wide ? null : <ActionDock op={op} onAccountPage />} />
        {wide && <div className="lo-dock-col"><ActionDock op={op} onAccountPage /></div>}
      </div>

      <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="min-w-0 space-y-5">
          <Panel title="Why this customer?">
            {!a.sources.length ? <p className="text-[13px] text-ds-muted">No linked evidence yet. Find them in Discover or add your own notes.</p> : <ul className="space-y-4">
              {a.sources.map((s) => <li key={s.key}>
                <div className="flex flex-wrap items-center gap-1.5"><Pill tone={s.type === "public" ? "blue" : "violet"}>{s.type === "public" ? "Public procurement" : "Private research"}</Pill><Basis basis={s.basis} /><span className="text-[12px] text-ds-muted">{BASIS_LABEL[s.link_basis]}</span></div>
                <p className="mt-1.5 text-[15px] font-medium leading-6 text-ds-ink">{s.why_now}</p>
                <p className="text-[13px] text-ds-ink-2">{s.title}</p>
                {!!s.evidence.length && <ul className="mt-2 space-y-1">{s.evidence.map((e, i) => { const href = safeUrl(e.url); return <li key={i} className="text-[13px]">
                  {href ? <a className="inline-flex items-center gap-1 font-medium text-ds-brand hover:underline" href={href} target="_blank" rel="noreferrer">{e.label}<ArrowUpRight size={12} /></a> : e.label}{e.date && <span className="text-ds-muted"> · {e.date}</span>}</li>; })}</ul>}
              </li>)}
            </ul>}
          </Panel>
          <div className="grid gap-5 lg:grid-cols-2">
            <Panel title={<span className="flex items-center gap-2"><CheckCircle2 size={15} className="text-ds-green" /> What we know</span>}>
              {!a.known.length ? <p className="text-[13px] text-ds-muted">Nothing sourced yet.</p> : <ul className="space-y-2">{a.known.map((k, i) => <li key={i} className="text-[13px] leading-5 text-ds-ink-2">{k.text} <Basis basis={k.basis} /></li>)}</ul>}
            </Panel>
            <Panel title={<span className="flex items-center gap-2"><CircleHelp size={15} className="text-ds-amber" /> What still needs confirming</span>}>
              <ul className="space-y-1.5">{a.to_confirm.map((k) => <li key={k} className="flex gap-2 text-[13px] leading-5 text-ds-ink-2"><span className="mt-[7px] h-1.5 w-1.5 flex-none rounded-full bg-ds-amber" />{k}</li>)}</ul>
            </Panel>
          </div>
          <AccountSuppliers accountId={a.id} />
          <DossierPanel key={`dossier-${investigations}`} accountId={a.id} notify={notify} onChanged={changed} />
          {play && <GapsPanel play={play} notify={notify} onChanged={() => { changed(); void reloadPlay(); }} />}
          {play && <CommitteePanel play={play} notify={notify} onChanged={() => { changed(); void reloadPlay(); }} />}
          <PeopleFinder key={`${a.id}-${a.contacts.map((c) => `${c.id}:${c.status}`).join(",")}`} accountId={a.id} notify={notify} onChanged={changed} />
          <Panel title="Log an interaction"><ActivityForm accountId={a.id} contacts={a.contacts} notify={notify} onSaved={changed} /></Panel>
          <Panel title={`History (${a.activities.length})`}><Timeline items={a.activities} contacts={a.contacts} /></Panel>
        </div>

        <div className="space-y-5">
          <Panel title={`Follow-ups (${a.tasks.filter((t) => t.status === "open").length})`}>
            {!a.tasks.length ? <p className="text-[13px] text-ds-muted">None scheduled.</p> : <ul className="divide-y divide-ds-border">{a.tasks.map((t) => <TaskRow key={t.id} t={t} onDone={() => void call(`/tasks/${t.id}/complete`, "POST", undefined, "Done.")} />)}</ul>}
          </Panel>
          <Panel title="Add or review contacts" action={<button className="ds-btn ghost sm" onClick={() => setPanel(panel === "contact" ? "" : "contact")}><UserPlus size={14} /> Add</button>}>
            {panel === "contact" && <ContactForm onSave={async (c) => { if (await call(`/accounts/${a.id}/contacts`, "POST", c, "Contact added.")) setPanel(""); }} />}
            {panel !== "contact" && <p className="text-[13px] text-ds-muted">Everyone you can contact is ranked under Find the right people. Add someone you know here.</p>}
            {a.contacts.some((c) => c.status === "do_not_contact") && <div className="mt-3"><p className="ds-label">Asked not to be contacted</p>
              <ul className="mt-1 space-y-2">{a.contacts.filter((c) => c.status === "do_not_contact").map((c) => <ContactCard key={c.id} c={c} onStatus={(status) => void call(`/contacts/${c.id}`, "PATCH", { status }, "Updated.")} />)}</ul></div>}
          </Panel>
          <Panel title={`Sites (${a.sites.length})`} action={<button className="ds-btn ghost sm" onClick={() => setPanel(panel === "site" ? "" : "site")}><MapPin size={14} /> Add</button>}>
            {panel === "site" && <SiteForm onSave={async (s) => { if (await call(`/accounts/${a.id}/sites`, "POST", s, "Site added.")) setPanel(""); }} />}
            {!a.sites.length && panel !== "site" && <p className="text-[13px] text-ds-muted">No sites confirmed. Sites are never assumed from a matching name.</p>}
            <ul className="space-y-2">{a.sites.map((s) => <li key={s.id} className="text-[13px]"><span className="font-semibold text-ds-ink">{s.name}</span> <Basis basis={s.basis} /><span className="block text-ds-muted">{[s.address, s.postcode, s.uprn && `UPRN ${s.uprn}`].filter(Boolean).join(", ")}</span></li>)}</ul>
          </Panel>
          {!!a.deals.length && <Panel title="Deals"><ul className="space-y-2">{a.deals.map((d) => <li key={d.id}><button className="flex w-full items-center justify-between gap-2 text-left" onClick={() => goto("deals", { deal: d.id })}><span className="text-[13px] font-semibold text-ds-ink">{d.title}</span><Pill>{STAGE_LABEL[d.stage]}</Pill></button></li>)}</ul></Panel>}
          <Panel title="Identity">
            <ul className="space-y-1.5">{a.identities.map((i) => <li key={`${i.entity_type}${i.entity_id}`} className="flex flex-wrap items-center gap-1.5 text-[12px] text-ds-ink-2"><Link2 size={12} className="text-ds-muted" />{i.name_seen}<Pill tone={i.confirmed ? "green" : "amber"}>{BASIS_LABEL[i.basis] || i.basis}</Pill></li>)}</ul>
            {!!suggest.length && <div className="mt-3 border-t border-ds-border pt-3"><p className="text-[12px] font-semibold text-ds-muted">Possibly the same organisation</p>
              <ul className="mt-1.5 space-y-1.5">{suggest.map((s) => <li key={s.source} className="flex items-center justify-between gap-2 text-[12px]"><span className="text-ds-ink-2">{s.name}</span>
                <button className="ds-btn sm" onClick={async () => { if (await call(`/accounts/${a.id}/links`, "POST", { source_key: s.source }, "Linked. Confirmed by you.")) setSuggest((x) => x.filter((y) => y.source !== s.source)); }}>Same organisation</button></li>)}</ul></div>}
          </Panel>
        </div>
      </div>
    </div>
  );
}

function ContactForm({ onSave }: { onSave: (c: Record<string, unknown>) => void }) {
  const [c, setC] = useState({ name: "", role: "", email: "", phone: "", source_url: "", influence: "", verified: false });
  const field = (k: keyof typeof c, label: string, type = "text") => <label className="block"><span className="ds-label">{label}</span><input type={type} className="mt-1 block h-9 w-full rounded-lg border border-ds-border-strong px-2.5 text-[13px]" value={String(c[k])} onChange={(e) => setC({ ...c, [k]: e.target.value })} /></label>;
  return (
    <form className="mb-3 space-y-2 rounded-lg bg-ds-canvas p-3" onSubmit={(e) => { e.preventDefault(); onSave(Object.fromEntries(Object.entries(c).filter(([, v]) => v !== ""))); }}>
      <div className="grid gap-2 sm:grid-cols-2">{field("name", "Name")}{field("role", "Role")}{field("email", "Business email", "email")}{field("phone", "Phone", "tel")}</div>
      {field("source_url", "Where you found it (optional)", "url")}
      <label className="flex items-center gap-2 text-[13px] text-ds-ink-2"><input type="checkbox" checked={c.verified} onChange={(e) => setC({ ...c, verified: e.target.checked })} /> I have confirmed these details</label>
      <p className="text-[12px] text-ds-muted">Business contact details only. Record a do-not-contact request as soon as you receive one.</p>
      <button className="ds-btn primary sm">Save contact</button>
    </form>
  );
}

function SiteForm({ onSave }: { onSave: (s: Record<string, unknown>) => void }) {
  const [s, setS] = useState({ name: "", address: "", postcode: "", uprn: "", source_url: "" });
  return (
    <form className="mb-3 space-y-2 rounded-lg bg-ds-canvas p-3" onSubmit={(e) => { e.preventDefault(); onSave(Object.fromEntries(Object.entries(s).filter(([, v]) => v !== ""))); }}>
      {(["name", "address", "postcode", "uprn", "source_url"] as const).map((k) => <label key={k} className="block"><span className="ds-label">{{ name: "Site name", address: "Address", postcode: "Postcode", uprn: "UPRN (only if confirmed)", source_url: "Source (optional)" }[k]}</span>
        <input className="mt-1 block h-9 w-full rounded-lg border border-ds-border-strong px-2.5 text-[13px]" value={s[k]} required={k === "name"} pattern={k === "uprn" ? "\\d{1,12}" : undefined} onChange={(e) => setS({ ...s, [k]: e.target.value })} /></label>)}
      <button className="ds-btn primary sm">Save site</button>
    </form>
  );
}
