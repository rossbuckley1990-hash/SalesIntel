"use client";

import {
  getApiBaseUrl,
  type BuyerProfile,
  type CompetitorProfile,
  type ExecutiveAction,
} from "@/lib/api";
import { LockKeyhole } from "lucide-react";
import { ExecutiveActionsList } from "./charts";
import { relationshipTone, threatTone } from "./finance";
import { DetailList, EmptyState, Panel, SourceRow, StatusPill } from "./ui";

export function BuyersView({ buyers }: { buyers: BuyerProfile[] }) {
  return (
    <Panel
      title="Buyer Intelligence"
      action={
        <StatusPill tone="cyan" label={`${buyers.length} API profiles`} />
      }
    >
      {buyers.length > 0 ? (
        <div className="grid gap-4 lg:grid-cols-3">
          {buyers.map((buyer) => (
            <article
              key={buyer.id}
              className="rounded-md border border-white/10 bg-[#111a20] p-4"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-base font-semibold text-white">
                    {buyer.buyer_name}
                  </h3>
                  <p className="mt-1 text-sm text-slate-500">
                    {buyer.sector} | {buyer.region}
                  </p>
                </div>
                <StatusPill
                  tone={relationshipTone(buyer.relationship_status)}
                  label={buyer.relationship_status || "Unknown"}
                />
              </div>
              <DetailList
                title="Procurement drivers"
                items={buyer.procurement_drivers.slice(0, 3)}
              />
              <DetailList
                title="Pain points"
                items={buyer.pain_points.slice(0, 2)}
              />
              <p className="mt-4 border-t border-white/10 pt-3 text-sm font-semibold leading-6 text-mitie-lime">
                {buyer.next_best_action ||
                  "Confirm relationship owner and next best action."}
              </p>
            </article>
          ))}
        </div>
      ) : (
        <EmptyState
          title="No confirmed buyer intelligence yet"
          message="SalesIntel has not researched these buyers yet. Start with a buyer, sector or tender phrase and SalesIntel will infer drivers, pain points and next best action with confidence labels."
        />
      )}
    </Panel>
  );
}

export function CompetitorsView({
  competitors,
}: {
  competitors: CompetitorProfile[];
}) {
  return (
    <Panel
      title="Competitor Intelligence"
      action={
        <StatusPill tone="amber" label={`${competitors.length} API profiles`} />
      }
    >
      {competitors.length > 0 ? (
        <div className="grid gap-4 lg:grid-cols-3">
          {competitors.map((competitor) => (
            <article
              key={competitor.id}
              className="rounded-md border border-white/10 bg-[#111a20] p-4"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-base font-semibold text-white">
                    {competitor.name}
                  </h3>
                  <p className="mt-1 text-sm text-slate-500">
                    {competitor.sectors.join(", ") || "Sectors TBC"}
                  </p>
                </div>
                <StatusPill
                  tone={threatTone(competitor.threat_level)}
                  label={competitor.threat_level || "Unknown"}
                />
              </div>
              <DetailList
                title="Strengths"
                items={competitor.strengths.slice(0, 2)}
              />
              <DetailList
                title="Weaknesses"
                items={competitor.weaknesses.slice(0, 2)}
              />
              <p className="mt-4 text-sm leading-6 text-slate-400">
                {competitor.pricing_behaviour ||
                  "Pricing behaviour not yet captured."}
              </p>
              <p className="mt-4 border-t border-white/10 pt-3 text-sm font-semibold leading-6 text-mitie-lime">
                {competitor.counter_strategy ||
                  "Confirm counter-strategy before bid gate."}
              </p>
            </article>
          ))}
        </div>
      ) : (
        <EmptyState
          title="No confirmed competitor evidence yet"
          message="SalesIntel can infer likely competitor threat from sector, scope and incumbent patterns, then separate inferred threat from confirmed competitor evidence."
        />
      )}
    </Panel>
  );
}

export function ExecutiveActionsView({
  actions,
}: {
  actions: ExecutiveAction[];
}) {
  return (
    <ExecutiveActionsList
      actions={actions}
      title="Executive Action Centre"
      expanded
    />
  );
}

export function SettingsView() {
  return (
    <div className="grid gap-5 xl:grid-cols-2">
      <Panel
        title="API Connection"
        action={
          <LockKeyhole aria-hidden="true" className="h-5 w-5 text-mitie-lime" />
        }
      >
        <div className="grid gap-3 text-sm leading-6 text-slate-300">
          <p>
            Frontend API base URL:{" "}
            <span className="font-semibold text-white">{getApiBaseUrl()}</span>
          </p>
          <p>
            The browser only receives `NEXT_PUBLIC_API_BASE_URL`; OpenAI keys,
            prompts and connector credentials remain backend-only.
          </p>
          <p>
            For real-data mode, start from an empty database and upload only
            data you are allowed to process in this local environment.
          </p>
        </div>
      </Panel>
      <Panel
        title="Workspace Status"
        action={<StatusPill tone="cyan" label="Real-data ready" />}
      >
        <div className="grid gap-4">
          <SourceRow
            label="SQLite local database"
            value="Can run empty or seeded for demos"
            tone="green"
          />
          <SourceRow
            label="PostgreSQL migration path"
            value="Documented"
            tone="cyan"
          />
          <SourceRow
            label="OpenAI analysis"
            value="Backend endpoint only"
            tone="amber"
          />
          <SourceRow
            label="Authentication"
            value="Planned for Entra ID"
            tone="amber"
          />
        </div>
      </Panel>
    </div>
  );
}
