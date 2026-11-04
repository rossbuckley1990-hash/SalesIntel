"use client";
import { useEffect, useState, type FormEvent } from "react";
import { ArrowRight, ArrowUpRight, ChevronDown, Database, Search } from "lucide-react";
import type { ReactNode } from "react";
import { mutate } from "./api";
import { Badge, Button, Empty, Heading, Loading, SectionHeading } from "./ui";
import { OpportunityTable } from "./opportunities";
import type { SharedProps, View } from "./types";
import { EarlyOpportunitiesPanel } from "../classic/early-opportunities";
import { EvidenceInbox } from "./evidence-inbox";
import { FalseAlarmSensor } from "./false-alarm-sensor";
import { PublicResearch } from "./public-research";
import { SourceExplorer } from "./source-explorer";
import { MarketNetwork } from "./market-network";

type Result = {
  matches: number[];
  created: boolean;
  explanation: string;
  intent: View;
};
const examples = [
  "Find fire and security maintenance opportunities at universities in Yorkshire",
  "Which opportunities are missing delivery capability evidence?",
  "Show the five biggest opportunities at risk",
  "What self-delivery opportunities are leaking margin to subcontractors?",
];

function ResearchTool({ title, description, children, defaultOpen = false }: {
  title: string;
  description: string;
  children: ReactNode;
  defaultOpen?: boolean;
}) {
  return (
    <details open={defaultOpen || undefined} className="group border-b border-[var(--misi-border)] last:border-b-0">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-4 py-4 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[var(--misi-accent)] [&::-webkit-details-marker]:hidden">
        <span className="min-w-0"><span className="block text-sm font-semibold text-[var(--misi-ink)]">{title}</span><span className="mt-1 block text-sm leading-6 text-[var(--misi-muted)]">{description}</span></span>
        <ChevronDown aria-hidden="true" size={18} className="shrink-0 text-[var(--misi-muted)] transition-transform motion-reduce:transition-none group-open:rotate-180" />
      </summary>
      <div className="pb-6">{children}</div>
    </details>
  );
}
export function Discover(props: SharedProps & { initialQuery?: string }) {
  const [query, setQuery] = useState(props.initialQuery || "");
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [draft, setDraft] = useState(false);
  const [owner, setOwner] = useState("");
  const [buyer, setBuyer] = useState("");
  useEffect(() => {
    if (props.initialQuery) void search(props.initialQuery);
  }, []); // A command executes once on entry.
  async function search(value = query) {
    if (value.trim().length < 4) return;
    setQuery(value);
    setBusy(true);
    setError("");
    try {
      setResult(await mutate<Result>("/discover", { query: value }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function saveDraft(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const r = await mutate<Result>("/discover", {
        query,
        create_draft: true,
        owner,
        buyer: buyer || "Unconfirmed buyer",
      });
      await props.refresh();
      props.notify(
        "Unverified draft saved. Values remain unknown until evidenced.",
      );
      props.navigate("field", r.matches[0]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const matches = props.data.opportunities
    .filter((o) => result?.matches.includes(o.id))
    .sort(
      (a, b) =>
        (result?.matches.indexOf(a.id) ?? 0) -
        (result?.matches.indexOf(b.id) ?? 0),
    );
  return (
    <>
      <Heading
        eyebrow="Discover / Opportunity intelligence"
        title="Discover opportunities"
        description="Explore public signals, investigate the evidence and find a useful next conversation."
      />
      <PublicResearch />
      <section aria-labelledby="additional-research-title" className="mt-8 border-t border-[var(--misi-border)] pt-6">
        <p className="m-eyebrow">Explore further</p>
        <h2 id="additional-research-title" className="mt-2 text-[17px] font-semibold text-[var(--misi-ink)]">More ways to investigate</h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--misi-muted)]">Use these focused tools when you need more context. Each has its own sources and limits.</p>
      <MarketNetwork />
      <SourceExplorer />
      <ResearchTool title="Search internal records" description="Find opportunities already saved in your workspace." defaultOpen={Boolean(props.initialQuery)}>
      <section className="m-discovery mt-8">
        <div className="m-between">
          <p className="m-eyebrow">
            <Database size={14} /> Internal intelligence
          </p>
          <Badge tone="green">
            {props.data.opportunities.length} searchable records
          </Badge>
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void search();
          }}
        >
          <label className="m-sr-only" htmlFor="discovery-query">
            Commercial question
          </label>
          <textarea
            id="discovery-query"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Find opportunities to provide fire and security maintenance to universities in Yorkshire…"
            minLength={4}
            maxLength={600}
            required
          />
          <div className="m-between">
            <p className="m-small m-muted">
              Local record search · no external model call
            </p>
            <Button
              type="submit"
              kind="primary"
              disabled={busy || query.trim().length < 4}
            >
              <Search size={16} /> Explore intelligence <ArrowRight size={16} />
            </Button>
          </div>
        </form>
      </section>
      <div className="m-example-grid">
        {examples.map((example, i) => (
          <button
            key={example}
            onClick={() => void search(example)}
            disabled={busy}
          >
            <span>0{i + 1}</span>
            {example}
            <ArrowUpRight size={16} />
          </button>
        ))}
      </div>
      {busy && <Loading label="Searching permitted records" />}
      {error && (
        <p className="m-error" role="alert">
          {error}
        </p>
      )}
      {result && !busy && (
        <section className="m-results">
          <SectionHeading
            title={`${matches.length} connected ${matches.length === 1 ? "opportunity" : "opportunities"}`}
            detail={result.explanation}
          >
            {matches[0] && (
              <Button onClick={() => props.navigate("field", matches[0].id)}>
                Assemble in the field <ArrowUpRight size={16} />
              </Button>
            )}
          </SectionHeading>
          {matches.length ? (
            <OpportunityTable opportunities={matches} inspect={props.inspect} />
          ) : (
            <Empty title="No substantiated matches yet">
              No opportunity or financial value has been invented. Save your
              question as an unverified draft to start investigation.
            </Empty>
          )}
          {["finance", "assets", "selfDelivery"].includes(result.intent) && (
            <div className="m-notice">
              <span>
                Continue this question in{" "}
                {result.intent === "assets"
                  ? "Asset Studio"
                  : result.intent === "finance"
                    ? "Finance"
                    : "Self-Delivery"}
                .
              </span>
              <Button onClick={() => props.navigate(result.intent)}>
                Continue <ArrowRight size={15} />
              </Button>
            </div>
          )}
          <Button kind="quiet" onClick={() => setDraft(!draft)}>
            Save this question as a new unverified opportunity
          </Button>
          {draft && (
            <form className="m-form m-surface" onSubmit={saveDraft}>
              <h3>Create an investigation record</h3>
              <p className="m-muted">
                Source: your question. Revenue, margin, probability and delivery
                fit stay unknown.
              </p>
              <div className="m-form-grid">
                <label>
                  Owner
                  <input
                    value={owner}
                    onChange={(e) => setOwner(e.target.value)}
                    required
                    minLength={2}
                    maxLength={120}
                  />
                </label>
                <label>
                  Buyer, if known
                  <input
                    value={buyer}
                    onChange={(e) => setBuyer(e.target.value)}
                    placeholder="Unconfirmed buyer"
                    maxLength={255}
                  />
                </label>
              </div>
              <Button type="submit" kind="primary" disabled={busy}>
                Save draft and assemble <ArrowRight size={16} />
              </Button>
            </form>
          )}
        </section>
      )}
      </ResearchTool>
      <ResearchTool title="Explore London fire-alarm attendances" description="Review patterns in the imported London Fire Brigade snapshot.">
      <FalseAlarmSensor />
      </ResearchTool>
      <ResearchTool title="Review your evidence inbox" description="Investigate observations you have added or imported.">
      <EvidenceInbox />
      </ResearchTool>
      <ResearchTool title="Search early maintenance opportunities" description="Run the separate maintenance-focused public research workflow.">
      <div className="mt-8">
        <EarlyOpportunitiesPanel showDemoNote />
      </div>
      </ResearchTool>
      </section>
      <div className="m-source-boundary">
        <Database size={19} />
        <div>
          <strong>Know what was searched.</strong>
          <p>
            {props.data.connector_status} More OpenAI research and
            manual-assist workflows remain in{" "}
            <a href="/classic">Classic workspace</a>.
          </p>
        </div>
      </div>
    </>
  );
}
