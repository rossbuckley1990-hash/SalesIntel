"use client";
import { useCallback, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import {
  ArrowUpRight,
  BriefcaseBusiness,
  Building2,
  CheckCheck,
  ChevronRight,
  CircleDollarSign,
  FileText,
  Flag,
  House,
  Layers3,
  MessagesSquare,
  Compass,
  Users,
  ListChecks,
  Menu,
  Orbit,
  Radar,
  Search,
  ShieldCheck,
  Sparkles,
  Target,
  Telescope,
  Undo2,
  Upload,
  X,
} from "lucide-react";
import { getApiBaseUrl } from "@/lib/api";
import { request, mutate } from "./api";
import { Button, Empty, Loading, Modal } from "./ui";
import type { Navigate, SharedProps, View, Workspace } from "./types";
import { SiToday } from "./si-today";
import { SiDiscover } from "./si-discover";
import { Opportunities } from "./opportunities";
import { Discover } from "./discover";
import { Inspector } from "./inspector";
const IntelligenceField = dynamic(
  () => import("../field/field-view").then((m) => m.IntelligenceField),
  { loading: () => <Loading /> },
);
const Finance = dynamic(() => import("./finance").then((m) => m.Finance), {
  loading: () => <Loading />,
});
const AssetStudio = dynamic(
  () => import("./assets").then((m) => m.AssetStudio),
  { loading: () => <Loading /> },
);
const Actions = dynamic(() => import("./actions").then((m) => m.Actions), {
  loading: () => <Loading />,
});
const Outcomes = dynamic(() => import("./actions").then((m) => m.Outcomes), {
  loading: () => <Loading />,
});
const Accounts = dynamic(() => import("./accounts").then((m) => m.Accounts), {
  loading: () => <Loading />,
});
const RenewalRadar = dynamic(() => import("./renewal-radar").then((m) => m.RenewalRadar), {
  loading: () => <Loading />,
});
const SiAccounts = dynamic(() => import("./si-accounts").then((m) => m.SiAccounts), { loading: () => <Loading /> });
const SiEngage = dynamic(() => import("./si-engage").then((m) => m.SiEngage), { loading: () => <Loading /> });
const SiDeals = dynamic(() => import("./si-deals").then((m) => m.SiDeals), { loading: () => <Loading /> });
const Prospects = dynamic(() => import("./prospects").then((m) => m.Prospects), {
  loading: () => <Loading />,
});
const Imports = dynamic(() => import("./imports").then((m) => m.Imports), {
  loading: () => <Loading />,
});

const navigation = [
  { id: "today", label: "Today", icon: House },
  { id: "find", label: "Discover", icon: Compass },
  { id: "clients", label: "Accounts", icon: Building2 },
  { id: "engage", label: "Engage", icon: MessagesSquare },
  { id: "deals", label: "Deals", icon: BriefcaseBusiness },
  { id: "radar", label: "Opportunity Finder", icon: Radar },
  { id: "prospects", label: "Prospects", icon: Telescope },
  { id: "discover", label: "AI Research", icon: Sparkles },
  { id: "opportunities", label: "Pipeline records", icon: Target },
  { id: "pursuits", label: "Pursuits", icon: Flag },
  { id: "accounts", label: "Buyer profiles", icon: Users },
  { id: "actions", label: "My Work", icon: ListChecks },
  { id: "assets", label: "Asset Studio", icon: FileText },
  { id: "finance", label: "Finance", icon: CircleDollarSign },
  { id: "selfDelivery", label: "Self-Delivery", icon: Layers3 },
  { id: "field", label: "Intelligence Field", icon: Orbit },
  { id: "outcomes", label: "Outcomes", icon: CheckCheck },
] as const;
const primaryViews: View[] = ["today", "find", "clients", "engage", "deals"];

export function LivingWorkspace() {
  const [data, setData] = useState<Workspace | null>(null);
  const [error, setError] = useState("");
  const [view, setView] = useState<View>("today");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [inspectId, setInspectId] = useState<number | null>(null);
  const [command, setCommand] = useState(false);
  const [query, setQuery] = useState("");
  const [toast, setToast] = useState<{
    message: string;
    error: boolean;
  } | null>(null);
  const [mobile, setMobile] = useState(false);
  const [toolsOpen, setToolsOpen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [readyCount, setReadyCount] = useState(0);
  useEffect(() => {
    fetch(`${getApiBaseUrl()}/api/market-network/opportunities/summary`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((s) => s && setReadyCount(Number(s.by_tier?.["1"] || 0)))
      .catch(() => {});
  }, []);
  const openPipeline = data ? data.opportunities.filter((o) => !["Won", "Lost"].includes(o.stage)).length : 0;
  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      setData(await request<Workspace>("/workspace"));
      setError("");
    } catch (e) {
      setError((e as Error).message);
      throw e;
    } finally {
      setRefreshing(false);
    }
  }, []);
  const notify = useCallback(
    (message: string, isError = false) => setToast({ message, error: isError }),
    [],
  );
  const navigate: Navigate = useCallback((next, id) => {
    setView(next);
    if (id !== undefined) setSelectedId(id);
    setMobile(false);
    const url = new URL(window.location.href);
    url.search = "";
    url.searchParams.set("view", next);
    if (id !== undefined) url.searchParams.set("opportunity", String(id));
    window.history.pushState({}, "", url);
    window.scrollTo({ top: 0, behavior: "instant" });
  }, []);
  useEffect(() => {
    const url = new URL(window.location.href);
    const next = url.searchParams.get("view");
    if (
      next &&
      [...navigation.map((n) => n.id), "imports"].includes(next as View)
    )
      setView(next as View);
    const id = Number(url.searchParams.get("opportunity"));
    if (id > 0) setSelectedId(id);
    const abort = new AbortController();
    request<Workspace>("/workspace", { signal: abort.signal })
      .then(setData)
      .catch((e) => {
        if (!abort.signal.aborted) setError(e.message);
      });
    return () => abort.abort();
  }, []);
  useEffect(() => {
    // Workspaces link to each other through the URL; keep the shell in step.
    const sync = () => {
      const next = new URL(window.location.href).searchParams.get("view");
      setView(next && [...navigation.map((n) => n.id), "imports"].includes(next as View) ? (next as View) : "today");
    };
    window.addEventListener("popstate", sync);
    return () => window.removeEventListener("popstate", sync);
  }, []);
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCommand((v) => !v);
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);
  useEffect(() => {
    if (!primaryViews.includes(view) && view !== "imports") setToolsOpen(true);
  }, [view]);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), toast.error ? 15000 : 7000);
    return () => clearTimeout(timer);
  }, [toast]);
  async function undo() {
    if (!data?.last_event) return;
    try {
      await mutate(`/audit/${data.last_event.id}/undo`, {});
      await refresh();
      notify(
        "The latest workspace change has been undone. The audit record is retained.",
      );
    } catch (e) {
      notify((e as Error).message, true);
    }
  }
  const shared: SharedProps | null = data
    ? {
        data,
        navigate,
        inspect: (id) => {
          setSelectedId(id);
          setInspectId(id);
        },
        refresh,
        notify,
        selectedId,
        ask: (q: string) => {
          setQuery(q);
          navigate("discover");
        },
        selectOpportunity: (id: number | null) => {
          setSelectedId(id);
          const url = new URL(window.location.href);
          if (id) url.searchParams.set("opportunity", String(id));
          else url.searchParams.delete("opportunity");
          window.history.replaceState({}, "", url);
        },
      }
    : null;
  const content = () => {
    if (!shared) return null;
    switch (view) {
      case "today":
        return <SiToday {...shared} />;
      case "find":
        return <SiDiscover {...shared} />;
      case "clients":
        return <SiAccounts {...shared} />;
      case "engage":
        return <SiEngage {...shared} />;
      case "deals":
        return <SiDeals {...shared} />;
      case "field":
        return <IntelligenceField {...shared} />;
      case "discover":
        return <Discover key={query} {...shared} initialQuery={query} />;
      case "radar":
        return <RenewalRadar {...shared} />;
      case "prospects":
        return <Prospects {...shared} />;
      case "opportunities":
        return <Opportunities {...shared} />;
      case "pursuits":
        return <Opportunities {...shared} pursuits />;
      case "accounts":
        return <Accounts {...shared} />;
      case "selfDelivery":
        return (
          <Finance key={`delivery-${selectedId}`} {...shared} selfDelivery />
        );
      case "finance":
        return <Finance key={`finance-${selectedId}`} {...shared} />;
      case "actions":
        return <Actions {...shared} />;
      case "assets":
        return <AssetStudio {...shared} />;
      case "imports":
        return <Imports {...shared} />;
      case "outcomes":
        return <Outcomes {...shared} />;
    }
  };
  return (
    <div className="m-workspace">
      <a className="m-skip" href="#m-main">
        Skip to workspace
      </a>
      <aside id="m-navigation" className={`m-sidebar ${mobile ? "open" : ""}`}>
        <a className="m-brand" href="/?view=today" aria-label="SalesIntel home">
          <span className="m-brand-mark" aria-hidden="true">S<span>i</span></span>
          <span className="m-brand-wordmark">SalesIntel<small>Find · Research · Win</small></span>
        </a>
        <div className="m-workspace-name">
          <div>
            <small>YOUR WORKSPACE</small>
            <strong>Mitie Fire & Security</strong>
          </div>
        </div>
        <nav aria-label="Main navigation">
          {navigation.filter((item) => primaryViews.includes(item.id)).map((item) => (
            <button
              key={item.id}
              aria-current={view === item.id ? "page" : undefined}
              onClick={() => navigate(item.id)}
              className={`m-nav-item ${view === item.id ? "active" : ""}`}
            >
              <item.icon size={18} strokeWidth={1.75} />
              <span>{item.label}</span>
              {item.id === "find" && readyCount > 0 && <span className="ds-nav-hint" aria-label={`${readyCount} high-priority leads`}>{readyCount}</span>}
            </button>
          ))}
          <div className="m-nav-tools">
            <button className="m-nav-group-toggle" aria-expanded={toolsOpen} aria-controls="m-tools-navigation" onClick={() => setToolsOpen((open) => !open)}>
              <span>Tools</span><ChevronRight size={14} className={toolsOpen ? "expanded" : ""} />
            </button>
            <div id="m-tools-navigation" hidden={!toolsOpen}>{navigation.filter((item) => !primaryViews.includes(item.id)).map((item) => <button
              key={item.id}
              aria-current={view === item.id ? "page" : undefined}
              onClick={() => navigate(item.id)}
              className={`m-nav-item ${view === item.id ? "active" : ""}`}
            >
              <item.icon size={18} strokeWidth={1.5} /><span>{item.label}</span>
              {item.id === "actions" && data && data.actions.some((a) => a.status !== "completed") && <span className="m-nav-count">{data.actions.filter((a) => a.status !== "completed").length}</span>}
            </button>)}</div>
          </div>
        </nav>
        <div className="m-sidebar-bottom">
          <button
            className={`m-nav-item ${view === "imports" ? "active" : ""}`}
            onClick={() => navigate("imports")}
          >
            <Upload size={17} />
            <span>Import data</span>
          </button>
          <a href="/classic" className="m-nav-item">
            <Layers3 size={17} />
            <span>Classic workspace</span>
            <ArrowUpRight size={14} />
          </a>
          <div className="m-local-state">
            <ShieldCheck size={17} />
            <span>
              Local workspace
              <small>
                {data?.mode === "synthetic"
                  ? "Synthetic data only"
                  : "Review access before real data"}
              </small>
            </span>
          </div>
        </div>
      </aside>
      {mobile && (
        <button
          className="m-mobile-backdrop"
          aria-label="Close navigation"
          onClick={() => setMobile(false)}
        />
      )}
      <div className="m-shell-main">
        <header className="m-topbar">
          <div className="m-breadcrumb">
            <button
              className="m-icon-button m-menu"
              onClick={() => setMobile((v) => !v)}
              aria-label="Toggle navigation"
              aria-expanded={mobile}
              aria-controls="m-navigation"
            >
              <Menu size={20} />
            </button>
            <span>SalesIntel</span>
            <ChevronRight size={13} />
            <strong>
              {navigation.find((n) => n.id === view)?.label || "Import data"}
            </strong>
          </div>
          <button
            className="m-command-trigger"
            aria-label="Search or ask SalesIntel"
            onClick={() => setCommand(true)}
          >
            <Search size={15} />
            <span>Search, or ask SalesIntel to find opportunities…</span>
            <kbd>⌘ K</kbd>
          </button>
          <div className="m-topbar-right">
            {data?.last_event && (
              <button
                className="m-icon-button"
                onClick={() => void undo()}
                aria-label={`Undo latest change: ${data.last_event.action}`}
                title={`Undo: ${data.last_event.action}`}
              >
                <Undo2 size={17} />
              </button>
            )}
            <span className="m-topbar-mode"><i aria-hidden="true" />{data?.mode === "synthetic" ? "DEMO WORKSPACE" : "LOCAL WORKSPACE"}</span>
          </div>
        </header>
        <main
          id="m-main"
          className={`m-main m-view-${view} m-modern-view ${view === "field" ? "field" : ""}`}
          tabIndex={-1}
        >
          {!data && !error && <Loading />}
          {error && (
            <div className="m-error" role="alert">
              <strong>Workspace connection unavailable</strong>
              <p>{error}</p>
              <Button
                onClick={() => void refresh().catch(() => {})}
                disabled={refreshing}
              >
                Retry connection
              </Button>
              <p className="m-small">
                Start the local API with scripts/living-dev.sh. Existing records
                remain on disk.
              </p>
            </div>
          )}
          {data && content()}
        </main>
        <footer className="m-shell-footer">
          <span>{data?.notice || "SalesIntel / Local commercial intelligence"}</span>
          <span>Public sources only · every lead links to its evidence</span>
        </footer>
      </div>
      {inspectId && (
        <Inspector
          id={inspectId}
          close={() => setInspectId(null)}
          refresh={refresh}
          notify={notify}
          navigate={navigate}
        />
      )}
      {command && (
        <CommandMenu
          data={data}
          close={() => setCommand(false)}
          navigate={navigate}
          inspect={(id) => {
            setSelectedId(id);
            setInspectId(id);
          }}
          ask={(q) => {
            setQuery(q);
            navigate("discover");
          }}
        />
      )}
      {toast && (
        <div
          className={`m-toast ${toast.error ? "error" : ""}`}
          role={toast.error ? "alert" : "status"}
        >
          <span>{toast.message}</span>
          <button
            aria-label="Dismiss notification"
            onClick={() => setToast(null)}
          >
            <X size={16} />
          </button>
        </div>
      )}
    </div>
  );
}

function CommandMenu({
  data,
  close,
  navigate,
  inspect,
  ask,
}: {
  data: Workspace | null;
  close: () => void;
  navigate: Navigate;
  inspect: (id: number) => void;
  ask: (query: string) => void;
}) {
  const [search, setSearch] = useState("");
  const matches =
    data?.opportunities
      .filter((o) =>
        `${o.name} ${o.buyer_name} ${o.owner}`
          .toLowerCase()
          .includes(search.toLowerCase()),
      )
      .slice(0, 5) || [];
  function run(fn: () => void) {
    close();
    fn();
  }
  return (
    <Modal title="Search and command" close={close} className="m-command-dialog">
      <div className="m-command-menu">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (search.trim().length >= 4) run(() => ask(search));
          }}
        >
          <Search size={20} />
          <input
            aria-label="Search or ask SalesIntel"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search records, open a workspace or ask a question…"
            autoFocus
            data-dialog-autofocus
          />
          <kbd>ESC</kbd>
        </form>
        {search.trim().length >= 4 && (
          <button
            className="m-command-result"
            onClick={() => run(() => ask(search))}
          >
            <Sparkles size={18} />
            <span>
              Explore “{search}”
              <small>Search permitted records with transparent matching</small>
            </span>
            <ArrowUpRight size={16} />
          </button>
        )}
        <p className="m-eyebrow">Workspaces</p>
        {navigation
          .filter((n) => n.label.toLowerCase().includes(search.toLowerCase()))
          .map((n) => (
            <button
              className="m-command-result"
              key={n.id}
              onClick={() => run(() => navigate(n.id))}
            >
              <n.icon size={17} />
              <span>{n.label}</span>
              <ChevronRight size={15} />
            </button>
          ))}
        <p className="m-eyebrow">Opportunity records</p>
        {matches.map((o) => (
          <button
            className="m-command-result"
            key={o.id}
            onClick={() => run(() => inspect(o.id))}
          >
            <Target size={17} />
            <span>
              {o.buyer_name}
              <small>{o.name}</small>
            </span>
            <ArrowUpRight size={15} />
          </button>
        ))}
        {!matches.length && (
          <p className="m-muted m-small">
            No matching saved opportunity. Ask a commercial question to
            continue.
          </p>
        )}
      </div>
    </Modal>
  );
}
