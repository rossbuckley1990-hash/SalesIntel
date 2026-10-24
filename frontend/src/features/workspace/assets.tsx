"use client";
import { useEffect, useState, type FormEvent } from "react";
import {
  ArrowUpRight,
  BriefcaseBusiness,
  ClipboardCheck,
  FileSpreadsheet,
  FileText,
  Flag,
  Layers3,
  ShieldCheck,
  Swords,
} from "lucide-react";
import { dateLabel, livingUrl, mutate, request } from "./api";
import {
  Badge,
  Button,
  Empty,
  Heading,
  Loading,
  Modal,
  SectionHeading,
} from "./ui";
import type { Asset, AssetKind, Scenario, SharedProps } from "./types";

export const assetKinds: {
  kind: AssetKind;
  title: string;
  description: string;
  icon: typeof FileText;
}[] = [
  {
    kind: "dossier",
    title: "Opportunity dossier",
    description:
      "The opportunity, evidence and next move in one defensible pack.",
    icon: FileText,
  },
  {
    kind: "bid_decision",
    title: "Bid / no-bid pack",
    description:
      "Transparent qualification, risks and the recorded human decision.",
    icon: ClipboardCheck,
  },
  {
    kind: "pursuit_plan",
    title: "Sales pursuit plan",
    description: "Buyer questions, working win themes and accountable actions.",
    icon: Flag,
  },
  {
    kind: "battlecard",
    title: "Competitor battlecard",
    description: "Source-bound profiles. Facts and assumptions kept apart.",
    icon: Swords,
  },
  {
    kind: "self_delivery",
    title: "Self-delivery business case",
    description:
      "A saved delivery scenario, sensitivity and operational conditions.",
    icon: Layers3,
  },
  {
    kind: "forecast",
    title: "LE1 forecast pack",
    description:
      "Secured work, open pipeline, monthly movement and Excel export.",
    icon: FileSpreadsheet,
  },
  {
    kind: "leadership",
    title: "Leadership briefing",
    description:
      "Financial meaning, priorities and decisions for the review meeting.",
    icon: BriefcaseBusiness,
  },
  {
    kind: "tender",
    title: "Tender starter pack",
    description:
      "A source-referenced requirements matrix and the compliance gaps.",
    icon: ShieldCheck,
  },
];

export function AssetStudio(props: SharedProps) {
  const [kind, setKind] = useState<AssetKind>("dossier");
  const [id, setId] = useState(
    props.selectedId || props.data.opportunities[0]?.id || 0,
  );
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [scenarioId, setScenarioId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [active, setActive] = useState<Asset | null>(null);
  const [loadingAsset, setLoadingAsset] = useState(false);
  useEffect(() => {
    request<Scenario[]>("/scenarios")
      .then(setScenarios)
      .catch((e) => setError(e.message));
  }, []);
  async function build(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const asset = await mutate<Asset>("/assets", {
        kind,
        opportunity_id: ["leadership", "forecast"].includes(kind) ? null : id,
        scenario_id: scenarioId ? Number(scenarioId) : null,
      });
      setActive(asset);
      await props.refresh();
      props.notify(
        `${assetKinds.find((v) => v.kind === kind)?.title} created. Version ${asset.version} is saved.`,
      );
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function open(assetId: number) {
    setLoadingAsset(true);
    try {
      setActive(await request<Asset>(`/assets/${assetId}`));
    } catch (e) {
      props.notify((e as Error).message, true);
    } finally {
      setLoadingAsset(false);
    }
  }
  return (
    <>
      <Heading
        eyebrow="Asset Studio / Turn evidence into an advantage"
        title="Intelligence. Ready to use."
        description="Useful commercial assets, built from the records you can stand behind."
      />
      <div className="m-asset-kinds">
        {assetKinds.map((item) => (
          <button
            key={item.kind}
            className={kind === item.kind ? "selected" : ""}
            onClick={() => {
              setKind(item.kind);
              setError("");
            }}
            aria-pressed={kind === item.kind}
          >
            <item.icon size={22} strokeWidth={1.4} />
            <strong>{item.title}</strong>
            <span>{item.description}</span>
            <ArrowUpRight size={16} />
          </button>
        ))}
      </div>
      <form className="m-asset-builder m-form" onSubmit={build}>
        <div>
          <p className="m-eyebrow">Selected deliverable</p>
          <h2>{assetKinds.find((v) => v.kind === kind)?.title}</h2>
          <p>Versioned · source references · review status</p>
        </div>
        {!["leadership", "forecast"].includes(kind) && (
          <label>
            Source opportunity
            <select
              value={id}
              onChange={(e) => {
                setId(Number(e.target.value));
                setScenarioId("");
              }}
            >
              {props.data.opportunities.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.buyer_name}
                </option>
              ))}
            </select>
          </label>
        )}
        {["self_delivery", "forecast"].includes(kind) && (
          <label>
            Saved scenario{kind === "forecast" ? " (optional)" : ""}
            <select
              value={scenarioId}
              onChange={(e) => setScenarioId(e.target.value)}
              required={kind === "self_delivery"}
            >
              <option value="">Select a saved scenario</option>
              {scenarios
                .filter((s) => kind === "forecast" || s.opportunity_id === id)
                .map((s) => (
                  <option value={s.id} key={s.id}>
                    {s.name}
                  </option>
                ))}
            </select>
          </label>
        )}
        <Button
          type="submit"
          kind="primary"
          disabled={busy || (kind === "self_delivery" && !scenarioId)}
        >
          {busy ? "Building from records…" : "Build asset"}
          <ArrowUpRight size={16} />
        </Button>
      </form>
      {kind === "self_delivery" &&
        !scenarios.some((s) => s.opportunity_id === id) && (
          <div className="m-notice">
            <span>
              A business case needs a saved scenario with explicit cost
              assumptions.
            </span>
            <Button onClick={() => props.navigate("finance", id)}>
              Open Scenario Lab
            </Button>
          </div>
        )}
      {error && (
        <p className="m-error" role="alert">
          {error}
        </p>
      )}
      <section className="m-asset-library">
        <SectionHeading
          title="Your asset library"
          detail="Saved versions are snapshots of their sources at generation time."
        />
        {loadingAsset && <Loading label="Opening saved asset" />}
        {props.data.assets.length ? (
          <div className="m-table-scroll">
            <table className="m-table">
              <thead>
                <tr>
                  <th>Asset</th>
                  <th>Version</th>
                  <th>Review</th>
                  <th>Created</th>
                  <th>Open</th>
                </tr>
              </thead>
              <tbody>
                {props.data.assets.map((a) => (
                  <tr key={a.id}>
                    <td>
                      <button
                        className="m-table-title"
                        onClick={() => void open(a.id)}
                      >
                        {a.title}
                      </button>
                      <small>
                        {assetKinds.find((k) => k.kind === a.kind)?.title}
                      </small>
                    </td>
                    <td>v{a.version}</td>
                    <td>
                      <Badge
                        tone={
                          a.review_status === "reviewed" ? "green" : "amber"
                        }
                      >
                        {a.review_status}
                      </Badge>
                    </td>
                    <td>{dateLabel(a.created_at)}</td>
                    <td>
                      <button
                        className="m-icon-button"
                        onClick={() => void open(a.id)}
                        aria-label={`Open asset ${a.id}`}
                      >
                        <ArrowUpRight size={17} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty title="Your first useful asset starts here">
            Select a format and build it from the saved opportunity records.
          </Empty>
        )}
      </section>
      {active && (
        <AssetPreview
          asset={active}
          close={() => setActive(null)}
          update={setActive}
          {...props}
        />
      )}
    </>
  );
}

function AssetPreview({
  asset,
  close,
  update,
  refresh,
  notify,
}: SharedProps & {
  asset: Asset;
  close: () => void;
  update: (asset: Asset) => void;
}) {
  const [notes, setNotes] = useState(asset.content?.notes || "");
  const [reviewer, setReviewer] = useState(asset.reviewer || "Local reviewer");
  const [busy, setBusy] = useState(false);
  async function review() {
    setBusy(true);
    try {
      update(
        await mutate<Asset>(
          `/assets/${asset.id}/review`,
          { status: "reviewed", reviewer },
          "PATCH",
        ),
      );
      await refresh();
      notify("Local review recorded for this version.");
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }
  async function newVersion() {
    setBusy(true);
    try {
      const next = await mutate<Asset>("/assets", {
        kind: asset.kind,
        opportunity_id: asset.opportunity_id,
        scenario_id: asset.content?.scenario?.id || null,
        notes,
      });
      update(next);
      await refresh();
      notify(`Version ${next.version} created using current source records.`);
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title="Saved commercial asset" close={close} wide>
      <div className="m-asset-preview">
        <header>
          <p className="m-eyebrow">MiSi / Commercial intelligence</p>
          <h2>{asset.title}</h2>
          <div className="m-wrap">
            <Badge>Version {asset.version}</Badge>
            <Badge
              tone={asset.review_status === "reviewed" ? "green" : "amber"}
            >
              {asset.review_status}
            </Badge>
            <span className="m-muted m-small">{asset.created_at}</span>
          </div>
          <div className="m-export-links">
            <a href={livingUrl(`/assets/${asset.id}/export/pdf`)}>
              Download PDF <ArrowUpRight size={14} />
            </a>
            <a href={livingUrl(`/assets/${asset.id}/export/docx`)}>
              Editable Word <ArrowUpRight size={14} />
            </a>
            <a href={livingUrl(`/assets/${asset.id}/export/xlsx`)}>
              Excel workbook <ArrowUpRight size={14} />
            </a>
          </div>
        </header>
        <article>
          {asset.content?.sections.map((s, i) => (
            <section key={i}>
              <h3>{s.title}</h3>
              {s.paragraphs.map((p, j) => (
                <p key={j}>{p}</p>
              ))}
              {s.columns.length > 0 && (
                <div className="m-table-scroll">
                  <table className="m-table">
                    <thead>
                      <tr>
                        {s.columns.map((c, j) => (
                          <th key={j}>{c}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {s.rows.map((row, j) => (
                        <tr key={j}>
                          {row.map((value, k) => (
                            <td key={k}>{value}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          ))}
          <details className="m-calculation">
            <summary>
              Linked source register · {asset.content?.sources.length || 0}{" "}
              records
            </summary>
            {asset.content?.sources.map((s, i) => (
              <p key={i}>
                {s.reference} · {s.title} · {s.type} · {s.timestamp}
              </p>
            ))}
          </details>
        </article>
        <section className="m-form m-asset-edit">
          <h3>Review and refine</h3>
          <label>
            Reviewer
            <input
              value={reviewer}
              onChange={(e) => setReviewer(e.target.value)}
              required
              minLength={2}
              maxLength={120}
            />
          </label>
          <Button
            onClick={() => void review()}
            disabled={busy || reviewer.length < 2}
          >
            Mark this version reviewed
          </Button>
          <label>
            Working notes for the next version
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              maxLength={6000}
            />
          </label>
          <p className="m-small m-muted">
            A new version refreshes the source records and includes your
            editable working notes. Local review is not formal enterprise
            approval.
          </p>
          <Button onClick={() => void newVersion()} disabled={busy}>
            Create revised version
          </Button>
        </section>
      </div>
    </Modal>
  );
}
