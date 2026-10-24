"use client";
import { useEffect, useState, type FormEvent } from "react";
import { ArrowUpRight, Check, FileText, ShieldCheck } from "lucide-react";
import {
  dateLabel,
  fieldLabel,
  money,
  mutate,
  request,
  safeSource,
} from "./api";
import {
  Badge,
  Button,
  Empty,
  Loading,
  Metric,
  Modal,
  SectionHeading,
} from "./ui";
import type { Asset, Detail, Navigate, Notice } from "./types";

export function Inspector({
  id,
  close,
  refresh,
  notify,
  navigate,
}: {
  id: number;
  close: () => void;
  refresh: () => Promise<void>;
  notify: Notice;
  navigate: Navigate;
}) {
  const [detail, setDetail] = useState<Detail | null>(null);
  const [tab, setTab] = useState("overview");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function reload() {
    const next = await request<Detail>(`/opportunities/${id}`);
    setDetail(next);
  }
  useEffect(() => {
    const abort = new AbortController();
    request<Detail>(`/opportunities/${id}`, { signal: abort.signal })
      .then(setDetail)
      .catch((e) => {
        if (!abort.signal.aborted) setError(e.message);
      });
    return () => abort.abort();
  }, [id]);
  async function build() {
    setBusy(true);
    try {
      const asset = await mutate<Asset>("/assets", {
        kind: "dossier",
        opportunity_id: id,
      });
      await refresh();
      notify(
        `Dossier version ${asset.version} saved. Ready for review and export.`,
      );
      close();
      navigate("assets", id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title="Opportunity workspace" close={close} wide>
      {error && (
        <p className="m-error" role="alert">
          {error}
        </p>
      )}
      {!detail ? (
        <Loading label="Opening the evidence record" />
      ) : (
        <div className="m-inspector">
          <header className="m-inspector-title">
            <p className="m-eyebrow">
              {detail.opportunity.sector} / {detail.opportunity.region}
            </p>
            <h2>{detail.opportunity.buyer_name}</h2>
            <p>{detail.opportunity.name}</p>
            <div className="m-wrap">
              <Badge tone={detail.opportunity.risk_rating}>
                {detail.opportunity.risk_rating} risk
              </Badge>
              <Badge>{detail.opportunity.stage}</Badge>
              <span className="m-muted m-small">
                {detail.opportunity.owner} · due{" "}
                {dateLabel(detail.opportunity.submission_deadline)}
              </span>
            </div>
          </header>
          <div
            className="m-tabs"
            role="tablist"
            aria-label="Opportunity sections"
          >
            {["overview", "evidence", "decision", "tender"].map((v) => (
              <button
                role="tab"
                aria-selected={tab === v}
                key={v}
                onClick={() => setTab(v)}
                className={tab === v ? "active" : ""}
              >
                {v === "evidence"
                  ? `Evidence · ${detail.evidence.length}`
                  : fieldLabel(v)}
              </button>
            ))}
          </div>
          <div className="m-inspector-content" role="tabpanel">
            {tab === "overview" && (
              <>
                <div className="m-mini-pulse">
                  <Metric
                    label="Annual revenue"
                    value={money(detail.financials.estimated_annual_revenue)}
                    detail="Recorded estimate"
                  />
                  <Metric
                    label="Annual gross margin"
                    value={money(detail.financials.estimated_gross_margin)}
                    detail="Potential · not realised"
                    tone="accent"
                  />
                  <Metric
                    label="Contract total"
                    value={money(
                      detail.financials.estimated_total_contract_value,
                    )}
                    detail="Whole contract basis"
                  />
                </div>
                <SectionHeading title="The opportunity" />
                <p>
                  {detail.enrichment?.opportunity_summary ||
                    "This record has not yet been enriched. Begin with the evidence and capture the missing information."}
                </p>
                <div className="m-two-columns">
                  <section>
                    <h3>Delivery and mobilisation</h3>
                    <p className="m-muted">
                      {detail.enrichment?.self_delivery_assessment ||
                        "Delivery fit requires review."}
                    </p>
                    <p className="m-muted">
                      {detail.enrichment?.mobilisation_assessment ||
                        "Mobilisation assumptions are not recorded."}
                    </p>
                  </section>
                  <section>
                    <h3>Risk components</h3>
                    <ul className="m-list">
                      {detail.qualification.risks.map((r) => (
                        <li key={r}>{r}</li>
                      ))}
                    </ul>
                  </section>
                </div>
                <SectionHeading title="The next actions" />
                {detail.actions.map((a) => (
                  <div className="m-action-line" key={a.id}>
                    <span>
                      <strong>{a.recommended_action}</strong>
                      <small>
                        {a.owner} · {dateLabel(a.due_date)}
                      </small>
                    </span>
                    <Badge>{a.status.replaceAll("_", " ")}</Badge>
                  </div>
                ))}
                <div className="m-wrap">
                  <Button
                    onClick={() => {
                      close();
                      navigate("field", id);
                    }}
                  >
                    Explore in the field <ArrowUpRight size={15} />
                  </Button>
                  <Button
                    onClick={() => {
                      close();
                      navigate("finance", id);
                    }}
                  >
                    Model a scenario <ArrowUpRight size={15} />
                  </Button>
                </div>
              </>
            )}
            {tab === "evidence" && (
              <EvidencePanel
                detail={detail}
                updated={async () => {
                  await reload();
                  await refresh();
                }}
                notify={notify}
              />
            )}
            {tab === "decision" && (
              <DecisionPanel
                detail={detail}
                updated={async () => {
                  await reload();
                  await refresh();
                }}
                notify={notify}
              />
            )}
            {tab === "tender" && (
              <TenderPanel
                detail={detail}
                updated={async () => {
                  await reload();
                  await refresh();
                }}
                notify={notify}
              />
            )}
          </div>
          <footer className="m-inspector-footer">
            <span>
              <ShieldCheck size={16} /> Source-bound · human review required
            </span>
            <Button kind="primary" disabled={busy} onClick={() => void build()}>
              <FileText size={16} />
              {busy ? "Building dossier…" : "Build pursuit pack"}
            </Button>
          </footer>
        </div>
      )}
    </Modal>
  );
}

function EvidencePanel({
  detail,
  updated,
  notify,
}: {
  detail: Detail;
  updated: () => Promise<void>;
  notify: Notice;
}) {
  const [fieldId, setFieldId] = useState<number | null>(null);
  const [note, setNote] = useState("");
  const [reviewer, setReviewer] = useState("Local reviewer");
  const [disposition, setDisposition] = useState("acknowledged");
  const [busy, setBusy] = useState(false);
  async function review(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await mutate(`/evidence/${fieldId}/reviews`, {
        disposition,
        reviewer,
        note,
      });
      await updated();
      setFieldId(null);
      setNote("");
      notify("Review saved. The original provenance is preserved.");
    } catch (err) {
      notify((err as Error).message, true);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="m-notice">
        <span>
          Known, inferred, estimated and missing information remain distinct.
          Acknowledging a field does not verify its source.
        </span>
      </div>
      {detail.evidence.length ? (
        detail.evidence.map((field) => (
          <details className="m-evidence" key={field.id}>
            <summary>
              <span>
                <strong>{fieldLabel(field.field_name)}</strong>
                <small>
                  {field.field_value == null
                    ? "Missing information"
                    : String(field.field_value)}
                </small>
              </span>
              <span className="m-wrap">
                <Badge
                  tone={
                    field.value_type === "unknown"
                      ? "amber"
                      : field.value_type === "known"
                        ? "green"
                        : "cyan"
                  }
                >
                  {fieldLabel(field.value_type)}
                </Badge>
                {field.stale && <Badge tone="amber">Stale</Badge>}
              </span>
            </summary>
            <div className="m-evidence-body">
              <p>{field.rationale}</p>
              <dl className="m-definition">
                <div>
                  <dt>Confidence</dt>
                  <dd>{Math.round(field.confidence_score * 100)}%</dd>
                </div>
                <div>
                  <dt>Updated</dt>
                  <dd>{dateLabel(field.updated_at)}</dd>
                </div>
                <div>
                  <dt>Source</dt>
                  <dd>
                    {field.source_titles.join("; ") ||
                      "No source title recorded"}
                  </dd>
                </div>
                <div>
                  <dt>Record</dt>
                  <dd>
                    field:{field.id} → opportunity:{detail.opportunity.id}
                  </dd>
                </div>
              </dl>
              {field.source_urls.map((source, i) =>
                safeSource(source) ? (
                  <a
                    className="m-source-link"
                    key={i}
                    href={safeSource(source)!}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {source} <ArrowUpRight size={13} />
                  </a>
                ) : (
                  <p key={i} className="m-small">
                    Source reference: {source}
                  </p>
                ),
              )}
              <p className="m-small">
                <strong>Next step:</strong> {field.recommended_next_step}
              </p>
              {field.review && (
                <div className="m-notice">
                  <span>
                    {field.review.disposition} by {field.review.reviewer}:{" "}
                    {field.review.note}
                  </span>
                </div>
              )}
              <Button kind="quiet" onClick={() => setFieldId(field.id)}>
                Review this evidence
              </Button>
            </div>
          </details>
        ))
      ) : (
        <Empty title="No evidence captured">
          The opportunity exists, but its claims need source records.
        </Empty>
      )}
      {fieldId && (
        <form className="m-form m-surface" onSubmit={review}>
          <h3>
            Review{" "}
            {fieldLabel(
              detail.evidence.find((f) => f.id === fieldId)?.field_name ||
                "evidence",
            )}
          </h3>
          <div className="m-form-grid">
            <label>
              Reviewer
              <input
                value={reviewer}
                onChange={(e) => setReviewer(e.target.value)}
                minLength={2}
                maxLength={120}
                required
              />
            </label>
            <label>
              Disposition
              <select
                value={disposition}
                onChange={(e) => setDisposition(e.target.value)}
              >
                <option value="acknowledged">Acknowledge limitations</option>
                <option value="challenged">Challenge this claim</option>
              </select>
            </label>
          </div>
          <label>
            Review note
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              minLength={10}
              maxLength={3000}
              required
            />
          </label>
          <Button kind="primary" type="submit" disabled={busy}>
            Save evidence review
          </Button>
        </form>
      )}
    </>
  );
}

function DecisionPanel({
  detail,
  updated,
  notify,
}: {
  detail: Detail;
  updated: () => Promise<void>;
  notify: Notice;
}) {
  const [choice, setChoice] = useState("investigate");
  const [reviewer, setReviewer] = useState("Local reviewer");
  const [owner, setOwner] = useState(detail.opportunity.owner);
  const [due, setDue] = useState(
    detail.opportunity.submission_deadline ||
      new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 10),
  );
  const [rationale, setRationale] = useState("");
  const [action, setAction] = useState(detail.opportunity.recommended_action);
  const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await mutate(`/opportunities/${detail.opportunity.id}/decisions`, {
        choice,
        reviewer,
        owner,
        due_date: due,
        rationale,
        action,
      });
      await updated();
      notify("Decision, action and outcome link saved together.");
      setRationale("");
    } catch (err) {
      notify((err as Error).message, true);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="m-score">
        <strong>
          {detail.qualification.score}
          <span>/100</span>
        </strong>
        <div>
          <h3>{detail.qualification.recommendation}</h3>
          <p>{detail.qualification.method}</p>
        </div>
      </div>
      <div className="m-check-grid">
        {detail.qualification.criteria.map((c) => (
          <div key={c.label}>
            <span className={c.passed ? "m-check passed" : "m-check"}>
              {c.passed ? <Check size={13} /> : "?"}
            </span>
            <span>
              <strong>{c.label}</strong>
              <small>{c.basis}</small>
            </span>
          </div>
        ))}
      </div>
      <form className="m-form" onSubmit={submit}>
        <h3>Record the next move</h3>
        <p className="m-muted m-small">
          Local review record. Formal enterprise approval requires authenticated
          roles.
        </p>
        <div className="m-form-grid">
          <label>
            Decision
            <select value={choice} onChange={(e) => setChoice(e.target.value)}>
              <option value="investigate">Investigate evidence gaps</option>
              <option value="pursue">Approve for local pursuit</option>
              <option value="hold">Hold</option>
              <option value="no_bid">No bid</option>
            </select>
          </label>
          <label>
            Reviewer
            <input
              value={reviewer}
              onChange={(e) => setReviewer(e.target.value)}
              minLength={2}
              required
            />
          </label>
        </div>
        <label>
          Decision rationale
          <textarea
            value={rationale}
            onChange={(e) => setRationale(e.target.value)}
            minLength={10}
            maxLength={3000}
            placeholder="Explain the evidence, assumptions and conditions behind this decision…"
            required
          />
        </label>
        <label>
          Next action
          <textarea
            value={action}
            onChange={(e) => setAction(e.target.value)}
            minLength={5}
            maxLength={2000}
            required
          />
        </label>
        <div className="m-form-grid">
          <label>
            Responsible owner
            <input
              value={owner}
              onChange={(e) => setOwner(e.target.value)}
              required
              minLength={2}
              maxLength={120}
            />
          </label>
          <label>
            Due date
            <input
              type="date"
              value={due}
              onChange={(e) => setDue(e.target.value)}
              required
            />
          </label>
        </div>
        <Button type="submit" kind="primary" disabled={busy}>
          {busy ? "Saving…" : "Record decision and action"}
          <ArrowUpRight size={15} />
        </Button>
      </form>
      {detail.decisions.length > 0 && (
        <section className="m-decision-history">
          <SectionHeading title="Decision history" />
          {detail.decisions.map((d) => (
            <div className="m-history-item" key={d.id}>
              <Badge>{fieldLabel(d.choice)}</Badge>
              <p>{d.rationale}</p>
              <small>
                {d.reviewer} · {dateLabel(d.created_at)}
              </small>
            </div>
          ))}
        </section>
      )}
    </>
  );
}

function TenderPanel({
  detail,
  updated,
  notify,
}: {
  detail: Detail;
  updated: () => Promise<void>;
  notify: Notice;
}) {
  const [text, setText] = useState("");
  const [source, setSource] = useState("");
  const [extracts, setExtracts] = useState<
    { requirement: string; source_reference: string; compliance: string }[]
  >([]);
  async function extract() {
    setBusy(true);
    try {
      const result = await mutate<{ requirements: typeof extracts }>(
        "/requirements/extract",
        { text, source_reference: source },
      );
      setExtracts(result.requirements);
      notify(
        `${result.requirements.length} exact source lines found. Review before saving.`,
      );
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }
  async function capture() {
    setBusy(true);
    try {
      await mutate(
        `/opportunities/${detail.opportunity.id}/requirements/capture`,
        {
          requirements: extracts.map((r) => ({
            ...r,
            owner: detail.opportunity.owner,
          })),
        },
      );
      setExtracts([]);
      setText("");
      await updated();
      notify("Reviewed source extracts saved.");
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }

  const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await mutate(`/opportunities/${detail.opportunity.id}/requirements`, {
        requirement: text,
        source_reference: source,
        owner: detail.opportunity.owner,
      });
      await updated();
      setText("");
      setSource("");
      notify("Source-referenced requirement captured.");
    } catch (err) {
      notify((err as Error).message, true);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <SectionHeading
        title="Tender requirements"
        detail="Capture the exact requirement and the document, page or clause it came from."
      />
      {detail.requirements.map((r) => (
        <div className="m-requirement" key={r.id}>
          <div className="m-between">
            <strong>{r.requirement}</strong>
            <Badge tone="amber">{r.compliance}</Badge>
          </div>
          <p>{r.source_reference}</p>
          <small>
            {r.owner} · {r.evidence || "No compliance evidence recorded"}
          </small>
        </div>
      ))}
      <form className="m-form" onSubmit={submit}>
        <label>
          Requirement extract
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            required
            minLength={10}
            maxLength={4000}
          />
        </label>
        <label>
          Source reference
          <input
            value={source}
            onChange={(e) => setSource(e.target.value)}
            placeholder="Document title, page and clause or approved source URL"
            required
            minLength={5}
            maxLength={1500}
          />
        </label>
        <Button type="submit" disabled={busy}>
          Capture requirement
        </Button>
        <Button
          type="button"
          onClick={() => void extract()}
          disabled={busy || text.length < 10 || source.length < 5}
        >
          Extract requirements from pasted source
        </Button>
        <p className="m-muted m-small">
          For a multi-line source extract, identify exact lines containing must,
          shall, required or mandatory. Review against the original document for
          completeness.
        </p>
        {extracts.length > 0 && (
          <section>
            <h3>Review extracted requirements</h3>
            {extracts.map((r, i) => (
              <div className="m-requirement" key={i}>
                <p>{r.requirement}</p>
                <small>{r.source_reference}</small>
                <Button
                  kind="quiet"
                  type="button"
                  onClick={() =>
                    setExtracts((v) => v.filter((_, j) => i !== j))
                  }
                >
                  Exclude line {i + 1}
                </Button>
              </div>
            ))}
            <Button
              type="button"
              onClick={() => void capture()}
              disabled={busy}
            >
              Save reviewed extracts
            </Button>
          </section>
        )}
      </form>
    </>
  );
}
