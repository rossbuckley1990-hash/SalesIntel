"use client";

import { type Opportunity } from "@/lib/api";
import { compactCurrency, percentage } from "@/lib/format";
import {
  buildSelfDeliverySummary,
  type SelfDeliveryAggregate,
  type SelfDeliveryOpportunityInsight,
  type SelfDeliverySummary,
} from "@/lib/self-delivery";
import { ShieldAlert, Target } from "lucide-react";
import { useMemo } from "react";
import { Tone } from "./shared";
import {
  DetailField,
  EmptyState,
  MiniMetric,
  Panel,
  ProgressRow,
  RiskPill,
  StatusPill,
} from "./ui";

export function SelfDeliveryView({
  opportunities,
}: {
  opportunities: Opportunity[];
}) {
  const summary = useMemo(
    () => buildSelfDeliverySummary(opportunities),
    [opportunities],
  );
  const maxDisciplineValue = Math.max(
    ...summary.disciplineOpportunity.map((discipline) => discipline.value),
    1,
  );

  return (
    <div className="grid gap-5">
      <Panel
        title="Self-Delivery Intelligence"
        action={
          <StatusPill
            tone="green"
            label={`${summary.routeOpportunities.length} routed`}
          />
        }
      >
        <div className="grid gap-4 md:grid-cols-3 2xl:grid-cols-6">
          <MiniMetric
            label="Opportunity value"
            value={compactCurrency(summary.opportunityValue)}
          />
          <MiniMetric
            label="Value captured"
            value={compactCurrency(summary.valueCaptured)}
          />
          <MiniMetric
            label="Value at risk"
            value={compactCurrency(summary.valueAtRisk)}
            danger={summary.valueAtRisk > 0}
          />
          <MiniMetric
            label="Accepted opportunities"
            value={String(summary.acceptedCount)}
          />
          <MiniMetric
            label="Declined opportunities"
            value={String(summary.declinedCount)}
            danger={summary.declinedCount > 0}
          />
          <MiniMetric
            label="Conversion rate"
            value={percentage(summary.conversionRate)}
          />
        </div>

        <div className="mt-5 rounded-md border border-mitie-lime/20 bg-mitie-lime/10 p-4">
          <p className="text-sm font-semibold text-mitie-lime">
            Commercial readout
          </p>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            Route high-fit fire and security scopes into Mitie Fire & Security
            early, protect captured value through mobilisation governance, and
            challenge moderate-fit packages before third-party leakage becomes
            embedded in the bid.
          </p>
        </div>
      </Panel>

      <SelfDeliveryGovernancePanel summary={summary} />

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_390px]">
        <Panel
          title="Disciplines With Highest Opportunity"
          action={
            <StatusPill
              tone="cyan"
              label={`${summary.disciplineOpportunity.length} disciplines`}
            />
          }
        >
          {summary.disciplineOpportunity.length > 0 ? (
            <div className="grid gap-4">
              {summary.disciplineOpportunity.map((discipline) => (
                <ProgressRow
                  key={discipline.label}
                  label={`${discipline.label} (${discipline.count})`}
                  value={compactCurrency(discipline.value)}
                  width={(discipline.value / maxDisciplineValue) * 100}
                />
              ))}
            </div>
          ) : (
            <EmptyState
              title="No discipline opportunity"
              message="MiSi has not found enough discipline evidence yet. Research or upload opportunities and it will infer Fire & Security scope, fit and leakage risk."
            />
          )}
        </Panel>

        <div className="grid content-start gap-5">
          <SelfDeliverySupplierPanel
            suppliers={summary.topDisplacedSuppliers}
          />
          <SelfDeliveryDecisionPanel
            accepted={summary.acceptedOpportunities}
            declined={summary.declinedOpportunities}
          />
        </div>
      </div>

      <Panel
        title="Route To Mitie Fire & Security"
        action={
          <Target aria-hidden="true" className="h-5 w-5 text-mitie-lime" />
        }
      >
        <SelfDeliveryOpportunityList
          opportunities={summary.routeOpportunities}
          emptyTitle="No routed opportunities"
          emptyMessage="No opportunities currently meet the self-delivery routing threshold. MiSi will flag capture opportunities when fit, value and discipline evidence strengthen."
        />
      </Panel>

      <Panel
        title="Third-Party Leakage Risk"
        action={
          <StatusPill
            tone={summary.leakageOpportunities.length > 0 ? "red" : "green"}
            label={`${summary.leakageOpportunities.length} risks`}
          />
        }
      >
        <SelfDeliveryOpportunityList
          opportunities={summary.leakageOpportunities}
          emptyTitle="No leakage risks"
          emptyMessage="No third-party leakage risks are currently flagged. MiSi will warn when high-fit Fire & Security work appears likely to leave Mitie delivery."
        />
      </Panel>
    </div>
  );
}

export function SelfDeliveryGovernancePanel({
  summary,
}: {
  summary: SelfDeliverySummary;
}) {
  const decisionCount = summary.acceptedCount + summary.declinedCount;
  const topRoute = summary.routeOpportunities[0];
  const topLeakage = summary.leakageOpportunities[0];

  const controls = [
    {
      label: "Route now",
      value: topRoute ? compactCurrency(topRoute.estimatedValue) : "No route",
      action: topRoute
        ? `${topRoute.buyerName}: route ${topRoute.discipline} scope through Mitie Fire & Security.`
        : "No strong-fit route candidates are visible in the current view.",
      tone: topRoute ? "green" : "cyan",
    },
    {
      label: "Protect value",
      value: compactCurrency(summary.valueCaptured),
      action:
        "Keep accepted scopes under Mitie Fire & Security ownership through mobilisation and handover.",
      tone: "cyan",
    },
    {
      label: "Challenge leakage",
      value: compactCurrency(summary.valueAtRisk),
      action: topLeakage
        ? `${topLeakage.buyerName}: challenge third-party dependency before commercial close.`
        : "No third-party leakage risks are flagged in the current view.",
      tone: summary.valueAtRisk > 0 ? "red" : "green",
    },
    {
      label: "Decision discipline",
      value: `${decisionCount} decisions`,
      action:
        "Accepted and declined positions should be explicit before bid sign-off.",
      tone: summary.declinedCount > 0 ? "amber" : "green",
    },
  ] satisfies Array<{
    label: string;
    value: string;
    action: string;
    tone: Tone;
  }>;

  return (
    <Panel
      title="Self-Delivery Capture Governance"
      action={<StatusPill tone="green" label="Commercial controls" />}
    >
      <div className="grid gap-3 lg:grid-cols-4">
        {controls.map((control) => (
          <article
            key={control.label}
            className="rounded-md border border-white/10 bg-[#111a20] p-4"
          >
            <div className="flex items-center justify-between gap-3">
              <p className="text-xs font-black uppercase text-slate-500">
                {control.label}
              </p>
              <StatusPill tone={control.tone} label={control.value} />
            </div>
            <p className="mt-4 text-sm leading-6 text-slate-300">
              {control.action}
            </p>
          </article>
        ))}
      </div>
    </Panel>
  );
}

export function SelfDeliverySupplierPanel({
  suppliers,
}: {
  suppliers: SelfDeliveryAggregate[];
}) {
  const maxSupplierValue = Math.max(
    ...suppliers.map((supplier) => supplier.value),
    1,
  );

  return (
    <Panel
      title="Top Displaced Suppliers"
      action={
        <ShieldAlert aria-hidden="true" className="h-5 w-5 text-amber-200" />
      }
    >
      {suppliers.length > 0 ? (
        <div className="grid gap-4">
          {suppliers.map((supplier) => (
            <ProgressRow
              key={supplier.label}
              label={`${supplier.label} (${supplier.count})`}
              value={compactCurrency(supplier.value)}
              width={(supplier.value / maxSupplierValue) * 100}
            />
          ))}
        </div>
      ) : (
        <EmptyState
          title="No supplier displacement"
          message="No self-delivery supplier displacement has been calculated from the backend opportunities."
        />
      )}
    </Panel>
  );
}

export function SelfDeliveryDecisionPanel({
  accepted,
  declined,
}: {
  accepted: SelfDeliveryOpportunityInsight[];
  declined: SelfDeliveryOpportunityInsight[];
}) {
  return (
    <Panel
      title="Capture Decision Position"
      action={<StatusPill tone="cyan" label="Accepted / declined" />}
    >
      <div className="grid gap-5">
        <SelfDeliveryDecisionList
          title="Accepted self-delivery opportunities"
          items={accepted.slice(0, 4)}
          emptyMessage="No accepted self-delivery opportunities were found in the backend dataset."
        />
        <SelfDeliveryDecisionList
          title="Declined opportunities"
          items={declined.slice(0, 4)}
          emptyMessage="No declined or qualified-out self-delivery opportunities were found."
        />
      </div>
    </Panel>
  );
}

export function SelfDeliveryDecisionList({
  title,
  items,
  emptyMessage,
}: {
  title: string;
  items: SelfDeliveryOpportunityInsight[];
  emptyMessage: string;
}) {
  return (
    <div>
      <h3 className="text-sm font-semibold text-white">{title}</h3>
      {items.length > 0 ? (
        <div className="mt-3 grid gap-3">
          {items.map((item) => (
            <div
              key={item.opportunityId}
              className="border-b border-white/10 pb-3 last:border-0 last:pb-0"
            >
              <p className="text-sm font-semibold leading-5 text-slate-200">
                {item.buyerName}
              </p>
              <p className="mt-1 text-sm leading-5 text-slate-500">
                {item.discipline} | {compactCurrency(item.estimatedValue)}
              </p>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-3 text-sm leading-6 text-slate-500">{emptyMessage}</p>
      )}
    </div>
  );
}

export function SelfDeliveryOpportunityList({
  opportunities,
  emptyTitle,
  emptyMessage,
}: {
  opportunities: SelfDeliveryOpportunityInsight[];
  emptyTitle: string;
  emptyMessage: string;
}) {
  if (opportunities.length === 0) {
    return <EmptyState title={emptyTitle} message={emptyMessage} />;
  }

  return (
    <div className="grid gap-3 xl:grid-cols-2">
      {opportunities.map((opportunity) => (
        <article
          key={opportunity.opportunityId}
          className="rounded-md border border-white/10 bg-[#111a20] p-4"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-sm font-semibold text-mitie-lime">
                {opportunity.buyerName}
              </p>
              <h3 className="mt-1 text-base font-semibold leading-6 text-white">
                {opportunity.name}
              </h3>
            </div>
            <RiskPill risk={opportunity.riskRating} />
          </div>
          <div className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
            <DetailField label="Discipline" value={opportunity.discipline} />
            <DetailField
              label="Value"
              value={compactCurrency(opportunity.estimatedValue)}
            />
            <DetailField label="Stage" value={opportunity.stage} />
          </div>
          <div className="mt-4 rounded-md border border-white/10 bg-white/[0.03] p-3">
            <p className="text-xs font-semibold text-slate-500">
              Displaced supplier
            </p>
            <p className="mt-1 text-sm font-semibold leading-5 text-slate-200">
              {opportunity.displacedSupplier}
            </p>
          </div>
          <p className="mt-4 text-sm leading-6 text-slate-300">
            {opportunity.reason}
          </p>
          <p className="mt-3 text-sm leading-6 text-slate-500">
            {opportunity.recommendedAction}
          </p>
        </article>
      ))}
    </div>
  );
}
