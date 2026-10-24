"use client";
import { useState, type FormEvent } from "react";
import { ArrowUpRight, Plus } from "lucide-react";
import type { ExecutiveAction } from "./types";
import { dateLabel, fieldLabel, money, mutate } from "./api";
import { Badge, Button, Empty, Heading, Metric, Modal } from "./ui";
import type { Outcome, SharedProps } from "./types";

export function Actions(props: SharedProps) {
  const [status, setStatus] = useState("");
  const [active, setActive] = useState<ExecutiveAction | "new" | null>(null);
  const actions = props.data.actions.filter(
    (a) => !status || a.status === status,
  );
  return (
    <>
      <Heading
        eyebrow="My Work / Close the loop"
        title="A next step with a name on it."
        description="Move from a recommendation to a responsible owner and evidenced completion."
      >
        <Button kind="primary" onClick={() => setActive("new")}>
          <Plus size={16} /> Create action
        </Button>
      </Heading>
      <div className="m-toolbar">
        <label>
          Status{" "}
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All actions</option>
            {["open", "in_progress", "blocked", "completed"].map((v) => (
              <option key={v} value={v}>
                {fieldLabel(v)}
              </option>
            ))}
          </select>
        </label>
        <span className="m-muted m-small">{actions.length} actions</span>
      </div>
      <div className="m-work-queue">
        {actions.map((a) => (
          <article className="m-work-item" key={a.id}>
            <div className="m-work-priority">
              <Badge tone={a.priority === "high" ? "amber" : "neutral"}>
                {a.priority}
              </Badge>
              <span>{dateLabel(a.due_date)}</span>
            </div>
            <div>
              <h3>{a.recommended_action}</h3>
              <p>{a.reason}</p>
              <span className="m-muted m-small">
                {a.owner} ·{" "}
                {props.data.opportunities.find(
                  (o) => o.id === a.related_opportunity_id,
                )?.buyer_name || "Portfolio action"}
              </span>
            </div>
            <Badge
              tone={
                a.status === "completed"
                  ? "green"
                  : a.status === "blocked"
                    ? "red"
                    : "neutral"
              }
            >
              {fieldLabel(a.status)}
            </Badge>
            <Button onClick={() => setActive(a)}>
              Continue <ArrowUpRight size={15} />
            </Button>
          </article>
        ))}
      </div>
      {!actions.length && (
        <Empty title="No matching actions">
          Create an action or change the status filter.
        </Empty>
      )}
      {active && (
        <ActionEditor
          action={active}
          close={() => setActive(null)}
          {...props}
        />
      )}
    </>
  );
}

function ActionEditor({
  action,
  close,
  ...props
}: SharedProps & { action: ExecutiveAction | "new"; close: () => void }) {
  const existing = action === "new" ? null : action;
  const [owner, setOwner] = useState(existing?.owner || "");
  const [due, setDue] = useState(
    existing?.due_date ||
      new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 10),
  );
  const [text, setText] = useState(existing?.recommended_action || "");
  const [reason, setReason] = useState(existing?.reason || "");
  const [id, setId] = useState(
    existing?.related_opportunity_id ||
      props.selectedId ||
      props.data.opportunities[0]?.id,
  );
  const [status, setStatus] = useState(existing?.status || "open");
  const [evidence, setEvidence] = useState(existing?.completion_evidence || "");
  const [dependencies, setDependencies] = useState<number[]>(
    existing?.depends_on || [],
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      if (existing)
        await mutate(
          `/actions/${existing.id}`,
          {
            owner,
            due_date: due,
            action: text,
            status,
            completion_evidence: evidence,
            expected_status: existing.status,
            depends_on: dependencies,
          },
          "PATCH",
        );
      else
        await mutate("/actions", {
          opportunity_id: id,
          owner,
          due_date: due,
          action: text,
          reason,
          depends_on: dependencies,
        });
      await props.refresh();
      props.notify("Action saved with its owner and due date.");
      close();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title={existing ? "Continue action" : "Create pursuit action"}
      close={close}
    >
      <form className="m-form m-dialog-body" onSubmit={save}>
        {!existing && (
          <label>
            Linked opportunity
            <select
              value={id}
              onChange={(e) => {
                setId(Number(e.target.value));
                setDependencies([]);
              }}
            >
              {props.data.opportunities.map((o) => (
                <option value={o.id} key={o.id}>
                  {o.buyer_name}
                </option>
              ))}
            </select>
          </label>
        )}
        <label>
          Action
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            minLength={5}
            maxLength={2000}
            required
          />
        </label>
        {!existing && (
          <label>
            Why now and commercial consequence
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              minLength={5}
              maxLength={2000}
              required
            />
          </label>
        )}
        <div className="m-form-grid">
          <label>
            Owner
            <input
              value={owner}
              onChange={(e) => setOwner(e.target.value)}
              minLength={2}
              maxLength={120}
              required
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
        {existing && (
          <label>
            Status
            <select value={status} onChange={(e) => setStatus(e.target.value)}>
              {["open", "in_progress", "blocked", "completed"].map((v) => (
                <option key={v} value={v}>
                  {fieldLabel(v)}
                </option>
              ))}
            </select>
          </label>
        )}
        <fieldset className="m-dependencies">
          <legend>Prerequisites on this opportunity</legend>
          {props.data.actions
            .filter(
              (a) => a.related_opportunity_id === id && a.id !== existing?.id,
            )
            .map((a) => (
              <label key={a.id}>
                <input
                  type="checkbox"
                  checked={dependencies.includes(a.id)}
                  onChange={(e) =>
                    setDependencies((v) =>
                      e.target.checked
                        ? [...v, a.id]
                        : v.filter((x) => x !== a.id),
                    )
                  }
                />
                #{a.id} · {a.recommended_action} · {fieldLabel(a.status)}
              </label>
            ))}
          <small>
            All selected prerequisites must be completed before this action can
            close.
          </small>
        </fieldset>
        {status === "completed" && (
          <label>
            Completion evidence
            <textarea
              value={evidence}
              onChange={(e) => setEvidence(e.target.value)}
              required
              minLength={10}
              maxLength={3000}
              placeholder="Reference the completed work or supporting source."
            />
          </label>
        )}
        {error && (
          <p className="m-error" role="alert">
            {error}
          </p>
        )}
        <Button kind="primary" type="submit" disabled={busy}>
          Save action
        </Button>
      </form>
    </Modal>
  );
}

export function Outcomes(props: SharedProps) {
  const [active, setActive] = useState<Outcome | null>(null);
  const stages = ["identified", "investigating", "approved", "won", "realised"];
  return (
    <>
      <Heading
        eyebrow="Commercial outcome ledger / Value with evidence"
        title="What did the intelligence change?"
        description="Potential, pursuit, won work and realised value stay separate. Completion needs evidence."
      />
      <div className="m-outcome-stages">
        {stages.map((stage) => {
          const records = props.data.outcomes.filter((o) => o.stage === stage);
          const known = records.filter(
            (o) =>
              (stage === "realised" ? o.actual_value : o.expected_impact) !=
              null,
          );
          const value = known.reduce(
            (sum, o) =>
              sum +
              Number(stage === "realised" ? o.actual_value : o.expected_impact),
            0,
          );
          return (
            <Metric
              key={stage}
              label={fieldLabel(stage)}
              value={money(value, true)}
              detail={`${records.length} records · ${stage === "realised" ? "recorded actual" : "potential annual GM"} · ${records.length - known.length} unknown`}
              tone={stage === "realised" ? "accent" : undefined}
            />
          );
        })}
      </div>
      <div className="m-table-scroll">
        <table className="m-table">
          <thead>
            <tr>
              <th>Opportunity</th>
              <th>Lifecycle</th>
              <th>Potential annual GM</th>
              <th>Recorded actual</th>
              <th>Owner</th>
              <th>Evidence</th>
              <th>Review</th>
            </tr>
          </thead>
          <tbody>
            {props.data.outcomes.map((o) => (
              <tr key={o.id}>
                <td>
                  {
                    props.data.opportunities.find(
                      (p) => p.id === o.opportunity_id,
                    )?.buyer_name
                  }
                  <small>
                    Decision{" "}
                    {o.decision_id ? `#${o.decision_id}` : "not recorded"} ·
                    Action {o.action_id ? `#${o.action_id}` : "not assigned"}
                  </small>
                </td>
                <td>
                  <Badge tone={o.stage === "realised" ? "green" : "neutral"}>
                    {fieldLabel(o.stage)}
                  </Badge>
                </td>
                <td>{money(o.expected_impact)}</td>
                <td>{money(o.actual_value)}</td>
                <td>{o.owner}</td>
                <td>{o.completion_evidence || "Awaiting evidence"}</td>
                <td>
                  <Button kind="quiet" onClick={() => setActive(o)}>
                    Update <ArrowUpRight size={15} />
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="m-footnote">
        Potential annual gross margin is not revenue, a contracted saving or
        realised value. Realised amounts are manually evidenced local records;
        identity verification remains a deployment gate.
      </p>
      {active && (
        <OutcomeEditor
          outcome={active}
          close={() => setActive(null)}
          {...props}
        />
      )}
    </>
  );
}

function OutcomeEditor({
  outcome,
  close,
  ...props
}: SharedProps & { outcome: Outcome; close: () => void }) {
  const [stage, setStage] = useState(outcome.stage);
  const [owner, setOwner] = useState(outcome.owner);
  const [expected, setExpected] = useState(outcome.expected_impact || "");
  const [actual, setActual] = useState(outcome.actual_value || "");
  const [assumptions, setAssumptions] = useState(outcome.assumptions);
  const [evidence, setEvidence] = useState(outcome.completion_evidence);
  const [reviewer, setReviewer] = useState(outcome.verified_by);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await mutate(
        `/opportunities/${outcome.opportunity_id}/outcome`,
        {
          stage,
          owner,
          due_date: outcome.due_date,
          expected_impact: expected || null,
          actual_value: stage === "realised" ? actual || null : null,
          assumptions,
          completion_evidence: evidence,
          verified_by: reviewer,
        },
        "PUT",
      );
      await props.refresh();
      props.notify("Commercial outcome recorded with its evidence.");
      close();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title="Record a commercial outcome" close={close}>
      <form className="m-form m-dialog-body" onSubmit={save}>
        <label>
          Lifecycle stage
          <select value={stage} onChange={(e) => setStage(e.target.value)}>
            {["identified", "investigating", "approved", "won", "realised"].map(
              (v) => (
                <option key={v} value={v}>
                  {fieldLabel(v)}
                </option>
              ),
            )}
          </select>
        </label>
        <label>
          Accountable owner
          <input
            value={owner}
            onChange={(e) => setOwner(e.target.value)}
            minLength={2}
            required
          />
        </label>
        <label>
          Potential annual gross margin GBP
          <input
            type="number"
            step=".01"
            min="0"
            value={expected}
            onChange={(e) => setExpected(e.target.value)}
            placeholder="Unknown"
          />
        </label>
        {stage === "realised" && (
          <label>
            Actual evidenced value GBP
            <input
              type="number"
              step=".01"
              min="0"
              value={actual}
              onChange={(e) => setActual(e.target.value)}
              required
            />
          </label>
        )}
        <label>
          Assumptions and measurement basis
          <textarea
            value={assumptions}
            onChange={(e) => setAssumptions(e.target.value)}
            minLength={10}
            maxLength={4000}
            required
          />
        </label>
        <label>
          Completion or award evidence
          <textarea
            value={evidence}
            onChange={(e) => setEvidence(e.target.value)}
            minLength={["won", "realised"].includes(stage) ? 10 : undefined}
            required={["won", "realised"].includes(stage)}
          />
        </label>
        <label>
          Evidence reviewer
          <input
            value={reviewer}
            onChange={(e) => setReviewer(e.target.value)}
            minLength={2}
            required={["won", "realised"].includes(stage)}
          />
        </label>
        {error && (
          <p className="m-error" role="alert">
            {error}
          </p>
        )}
        <Button kind="primary" type="submit" disabled={busy}>
          Save evidenced outcome
        </Button>
      </form>
    </Modal>
  );
}
