"use client";
/**
 * ⌘K: one box to jump anywhere, find an account or deal by name, or search for new opportunities.
 * Results come only from this workspace's own API; nothing is sent anywhere else.
 */
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { ArrowRight, Briefcase, ClipboardCheck, Building2, CalendarCheck, Compass, CornerDownLeft, LogOut, Mail, Radar, Search, Settings, UserPlus, Users } from "lucide-react";
import { si, STAGE_LABEL, type DealCard } from "@/features/workspace/si-api";

export type PaletteView = "today" | "find" | "clients" | "engage" | "deals" | "team" | "settings" | "review";
type Item = { id: string; group: string; label: string; detail?: string; icon: ReactNode; keys?: string[]; run: () => void };
type AccountRow = { id: number; name: string; sector?: string | null; region?: string | null };

export const VIEW_KEYS: Record<string, PaletteView> = { t: "today", d: "find", a: "clients", e: "engage", l: "deals" };

type Props = { close: () => void; go: (v: PaletteView, params?: Record<string, string | number>) => void; signOut: () => void; canInvite: boolean };

/** Mounted afresh each time it opens, so a new search never starts from the last one. */
export function CommandPalette({ open, ...props }: Props & { open: boolean }) {
  return open ? <Palette {...props} /> : null;
}

function Palette({ close, go, signOut, canInvite }: Props) {
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const [accounts, setAccounts] = useState<AccountRow[]>([]);
  const [deals, setDeals] = useState<DealCard[]>([]);
  const input = useRef<HTMLInputElement>(null);
  const list = useRef<HTMLDivElement>(null);
  const returnFocus = useRef<HTMLElement | null>(null);

  useEffect(() => {
    returnFocus.current = document.activeElement as HTMLElement | null;
    input.current?.focus();
    si<{ items: DealCard[] }>("/deals").then((d) => setDeals(d.items)).catch(() => setDeals([]));
    return () => returnFocus.current?.focus?.();
  }, []);
  useEffect(() => {
    const text = q.trim();
    const t = setTimeout(() => {
      si<{ items: AccountRow[] }>(`/accounts?q=${encodeURIComponent(text)}`).then((d) => setAccounts(d.items.slice(0, text ? 6 : 4))).catch(() => setAccounts([]));
    }, text ? 140 : 0);
    return () => clearTimeout(t);
  }, [q]);

  const items = useMemo<Item[]>(() => {
    const text = q.trim();
    const match = (s: string) => !text || s.toLowerCase().includes(text.toLowerCase());
    const done = (fn: () => void) => () => { close(); fn(); };
    const nav: Item[] = ([
      ["today", "Today", "Your queue, follow-ups and new leads", <CalendarCheck key="i" size={16} />, ["G", "T"]],
      ["find", "Discover", "Tenders, renewals, private research and Shadow Radar", <Compass key="i" size={16} />, ["G", "D"]],
      ["clients", "Accounts", "Organisations you are working", <Building2 key="i" size={16} />, ["G", "A"]],
      ["engage", "Engage", "Introductions and outreach drafts", <Mail key="i" size={16} />, ["G", "E"]],
      ["deals", "Deals", "Qualified opportunities and quotes", <Briefcase key="i" size={16} />, ["G", "L"]],
      ["team", "Team", "Colleagues and roles", <Users key="i" size={16} />, undefined],
      ["settings", "My settings", "What you sell, territory and target", <Settings key="i" size={16} />, undefined],
      ["review", "Blind review", "Judge discovered opportunities without knowing their source", <ClipboardCheck key="i" size={16} />, undefined],
    ] as [PaletteView, string, string, ReactNode, string[] | undefined][]).filter(([, label]) => match(label)) // places match on their names, so "shadow" leads to Shadow Radar, not to Discover
      .map(([v, label, detail, icon, keys]) => ({ id: `go-${v}`, group: "Go to", label, detail, icon, keys, run: done(() => go(v)) }));
    const search: Item[] = text ? [{ id: "search", group: "Opportunities", label: `Search opportunities for “${text}”`, detail: "Discover, across every source", icon: <Search size={16} />, run: done(() => go("find", { q: text })) }] : [];
    const radar: Item[] = match("shadow radar unadvertised hidden") ? [{ id: "radar", group: "Opportunities", label: "Shadow Radar", detail: "Unadvertised needs inferred from public evidence", icon: <Radar size={16} />, run: done(() => go("find", { source: "shadow" })) }] : [];
    const acc: Item[] = accounts.map((a) => ({ id: `acc-${a.id}`, group: "Accounts", label: a.name, detail: [a.sector, a.region].filter(Boolean).join(" · ") || "Account", icon: <Building2 size={16} />, run: done(() => go("clients", { account: a.id })) }));
    const dl: Item[] = deals.filter((d) => match(d.title) || match(d.account || "")).slice(0, text ? 5 : 3)
      .map((d) => ({ id: `deal-${d.id}`, group: "Deals", label: d.title, detail: `${d.account || "No account"} · ${STAGE_LABEL[d.stage] || d.stage}`, icon: <Briefcase size={16} />, run: done(() => go("deals", { deal: d.id })) }));
    const actions: Item[] = ([
      canInvite ? { id: "invite", group: "Actions", label: "Invite a colleague", detail: "Create a single-use invitation link", icon: <UserPlus size={16} />, run: done(() => go("team")) } : null,
      { id: "signout", group: "Actions", label: "Sign out", detail: "End this session on this device", icon: <LogOut size={16} />, run: done(signOut) },
    ].filter(Boolean) as Item[]).filter((x) => match(x.label));
    // Places first, then things in the workspace, then a search across Discover for whatever was typed.
    return [...nav, ...radar, ...acc, ...dl, ...search, ...actions];
  }, [q, accounts, deals, close, go, signOut, canInvite]);

  useEffect(() => { setActive(0); }, [q]);
  useEffect(() => { list.current?.querySelector<HTMLElement>(`[data-index="${active}"]`)?.scrollIntoView({ block: "nearest" }); }, [active]);

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((i) => Math.min(i + 1, items.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((i) => Math.max(i - 1, 0)); }
    else if (e.key === "Enter") { e.preventDefault(); items[active]?.run(); }
    else if (e.key === "Escape") { e.preventDefault(); close(); }
    else if (e.key === "Tab") e.preventDefault(); // focus stays in the search box; arrows move through results
  };
  let last = "";
  return (
    <div className="si-palette" role="dialog" aria-modal="true" aria-label="Command menu" onKeyDown={onKey}>
      <button className="si-palette-backdrop" aria-label="Close command menu" tabIndex={-1} onClick={close} />
      <div className="si-palette-panel">
        <div className="si-palette-search">
          <Search size={18} aria-hidden="true" />
          <input ref={input} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Jump to, find an account or deal, or search opportunities…"
            role="combobox" aria-expanded="true" aria-controls="si-palette-list" aria-activedescendant={items[active] ? `si-pal-${items[active].id}` : undefined} aria-label="Search SalesIntel" autoComplete="off" spellCheck={false} autoFocus />
          <span className="si-kbd" aria-hidden="true">esc</span>
        </div>
        <div className="si-palette-list" id="si-palette-list" role="listbox" aria-label="Results" ref={list}>
          {!items.length && <p className="si-palette-empty">Nothing matches “{q}”. Press Enter on a search to look across Discover.</p>}
          {items.map((item, i) => {
            const header = item.group !== last ? item.group : null;
            last = item.group;
            return (
              <div key={item.id} role="presentation">
                {header && <p className="si-palette-group" role="presentation">{header}</p>}
                <button id={`si-pal-${item.id}`} data-index={i} role="option" aria-selected={i === active} tabIndex={-1} className="si-palette-item"
                  onMouseMove={() => setActive(i)} onClick={item.run}>
                  <span className="icon" aria-hidden="true">{item.icon}</span>
                  <span className="text"><b>{item.label}</b>{item.detail && <small>{item.detail}</small>}</span>
                  {item.keys ? <span className="hint" aria-hidden="true">{item.keys.map((k) => <span key={k} className="si-kbd">{k}</span>)}</span>
                    : i === active ? <ArrowRight size={15} className="text-ds-brand" aria-hidden="true" /> : null}
                </button>
              </div>
            );
          })}
        </div>
        <div className="si-palette-foot" aria-hidden="true">
          <span><span className="si-kbd">↑</span><span className="si-kbd">↓</span> move</span>
          <span><span className="si-kbd"><CornerDownLeft size={11} /></span> open</span>
          <span className="ml-auto">G then T, D, A, E or L to jump</span>
        </div>
      </div>
    </div>
  );
}
