"use client";
import { useCallback, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import {
  Activity,
  ArrowUpRight,
  BriefcaseBusiness,
  Building2,
  CheckCheck,
  ChevronRight,
  CircleDollarSign,
  Command,
  Compass,
  FileText,
  Layers3,
  ListChecks,
  Menu,
  Orbit,
  Search,
  ShieldCheck,
  Sparkles,
  Target,
  Undo2,
  Upload,
  X,
} from "lucide-react";
import { request, mutate } from "./api";
import { Badge, Button, Empty, Loading, Modal } from "./ui";
import type { Navigate, SharedProps, View, Workspace } from "./types";
import { Today } from "./today";
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
const Imports = dynamic(() => import("./imports").then((m) => m.Imports), {
  loading: () => <Loading />,
});

const navigation = [
  { id: "today", label: "Today", icon: Activity, group: "WORKSPACE" },
  { id: "field", label: "Intelligence Field", icon: Orbit },
  { id: "discover", label: "Discover", icon: Compass },
  {
    id: "opportunities",
    label: "Opportunities",
    icon: Target,
    group: "COMMERCIAL",
  },
  { id: "pursuits", label: "Pursuits", icon: BriefcaseBusiness },
  { id: "accounts", label: "Accounts", icon: Building2 },
  { id: "selfDelivery", label: "Self-Delivery", icon: Layers3 },
  { id: "finance", label: "Finance", icon: CircleDollarSign },
  {
    id: "actions",
    label: "My Work",
    icon: ListChecks,
    group: "MAKE IT HAPPEN",
  },
  { id: "assets", label: "Asset Studio", icon: FileText },
  { id: "outcomes", label: "Outcomes", icon: CheckCheck },
] as const;

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
  const [refreshing, setRefreshing] = useState(false);
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
    url.searchParams.set("view", next);
    if (id !== undefined) url.searchParams.set("opportunity", String(id));
    window.history.replaceState({}, "", url);
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
      }
    : null;
  const content = () => {
    if (!shared) return null;
    switch (view) {
      case "today":
        return <Today {...shared} />;
      case "field":
        return <IntelligenceField key={selectedId || "all"} {...shared} />;
      case "discover":
        return <Discover key={query} {...shared} initialQuery={query} />;
      case "opportunities":
        return <Opportunities {...shared} />;
      case "pursuits":
        return <Opportunities {...shared} pursuits />;
      case "accounts":
        return <Accounts {...shared} />;
      case "selfDelivery":
        return <Finance {...shared} selfDelivery />;
      case "finance":
        return <Finance {...shared} />;
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
      <aside className={`m-sidebar ${mobile ? "open" : ""}`}>
        <a className="m-brand" href="/?view=today" aria-label="MiSi home">
          <span>
            MiS<span className="m-brand-i">i</span>
            <i />
          </span>
          <small>COMMERCIAL INTELLIGENCE</small>
        </a>
        <div className="m-workspace-name">
          <span className="m-team-icon">M</span>
          <div>
            <strong>Mitie Fire & Security</strong>
            <small>Commercial workspace</small>
          </div>
        </div>
        <nav aria-label="Main navigation">
          {navigation.map((item) => (
            <div key={item.id}>
              {"group" in item && item.group && (
                <p className="m-nav-group">{item.group}</p>
              )}
              <button
                aria-current={view === item.id ? "page" : undefined}
                onClick={() => navigate(item.id)}
                className={`m-nav-item ${view === item.id ? "active" : ""}`}
              >
                <item.icon size={18} strokeWidth={1.5} />
                <span>{item.label}</span>
                {item.id === "field" && <span className="m-nav-new">NEW</span>}
                {item.id === "actions" && data && (
                  <span className="m-nav-count">
                    {
                      data.actions.filter((a) => a.status !== "completed")
                        .length
                    }
                  </span>
                )}
              </button>
            </div>
          ))}
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
            >
              <Menu size={20} />
            </button>
            <span>Workspace</span>
            <ChevronRight size={13} />
            <strong>
              {navigation.find((n) => n.id === view)?.label || "Import data"}
            </strong>
          </div>
          <button
            className="m-command-trigger"
            onClick={() => setCommand(true)}
          >
            <Search size={15} />
            <span>Search or ask MiSi</span>
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
            <Badge tone="green">
              {data?.mode === "synthetic" ? "DEMO" : "LOCAL"}
            </Badge>
            <span className="m-profile">MFS</span>
          </div>
        </header>
        <main
          id="m-main"
          className={`m-main ${view === "field" ? "field" : ""}`}
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
          <span>{data?.notice || "MiSi / Local commercial intelligence"}</span>
          <span>See the opportunity. Make the move.</span>
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
    <Modal title="Search and command" close={close}>
      <div className="m-command-menu">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (search.trim().length >= 4) run(() => ask(search));
          }}
        >
          <Search size={20} />
          <input
            aria-label="Search or ask MiSi"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search records, open a workspace or ask a question…"
            autoFocus
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
