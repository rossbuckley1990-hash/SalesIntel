import type { ExecutiveReport } from "./api";
import {
  compactCurrency,
  currency,
  monthLabel,
  percentage,
  percentageValue,
  shortDate,
} from "./format";

export type ExecutiveReportExportUrls = {
  filename: string;
  htmlUrl: string;
  jsonUrl: string;
};

export function buildExecutiveReportFilename(report: ExecutiveReport): string {
  const datePart = report.reporting_date || new Date().toISOString().slice(0, 10);
  return `misi-executive-report-${datePart}.json`;
}

export function createExecutiveReportExportUrls(
  report: ExecutiveReport,
): ExecutiveReportExportUrls | null {
  if (typeof window === "undefined" || typeof URL === "undefined") {
    return null;
  }

  const htmlBlob = new Blob([buildExecutiveReportHtml(report)], {
    type: "text/html",
  });
  const jsonBlob = new Blob([JSON.stringify(report, null, 2)], {
    type: "application/json",
  });

  return {
    filename: buildExecutiveReportFilename(report),
    htmlUrl: URL.createObjectURL(htmlBlob),
    jsonUrl: URL.createObjectURL(jsonBlob),
  };
}

export function revokeExecutiveReportExportUrls(
  urls: ExecutiveReportExportUrls | null,
): void {
  if (!urls || typeof URL === "undefined") {
    return;
  }

  URL.revokeObjectURL(urls.htmlUrl);
  URL.revokeObjectURL(urls.jsonUrl);
}

export function buildExecutiveReportHtml(report: ExecutiveReport): string {
  const dashboard = report.dashboard_kpis;
  const finance = report.finance_forecast;
  const selfDelivery = report.self_delivery_summary;
  const briefing = report.leadership_summary;

  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>${escapeHtml(report.report_name)}</title>
  <style>
    :root {
      color: #172026;
      font-family: Arial, Helvetica, sans-serif;
      line-height: 1.45;
    }
    body {
      margin: 0;
      background: #eef2f4;
    }
    main {
      max-width: 1120px;
      margin: 0 auto;
      padding: 32px;
      background: #ffffff;
    }
    header {
      border-bottom: 3px solid #134734;
      padding-bottom: 20px;
    }
    h1, h2, h3, p {
      margin: 0;
    }
    h1 {
      color: #0b2f24;
      font-size: 30px;
    }
    h2 {
      margin-top: 26px;
      color: #0b2f24;
      font-size: 20px;
    }
    h3 {
      color: #172026;
      font-size: 15px;
    }
    .meta {
      margin-top: 8px;
      color: #5c6970;
      font-size: 13px;
    }
    .note {
      margin-top: 14px;
      border-left: 4px solid #134734;
      background: #eef8f4;
      padding: 10px 12px;
      color: #29433b;
      font-size: 13px;
    }
    .grid {
      display: grid;
      gap: 12px;
    }
    .kpis {
      grid-template-columns: repeat(4, minmax(0, 1fr));
      margin-top: 16px;
    }
    .card {
      border: 1px solid #d7dee2;
      border-radius: 8px;
      padding: 14px;
      background: #fbfcfc;
    }
    .label {
      color: #627078;
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
    }
    .value {
      margin-top: 6px;
      color: #10241d;
      font-size: 22px;
      font-weight: 800;
    }
    .detail {
      margin-top: 4px;
      color: #65727a;
      font-size: 12px;
    }
    .two-col {
      grid-template-columns: repeat(2, minmax(0, 1fr));
      margin-top: 12px;
    }
    ul {
      margin: 10px 0 0;
      padding-left: 18px;
    }
    li {
      margin: 4px 0;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 12px;
      font-size: 12px;
    }
    th, td {
      border-bottom: 1px solid #dce2e5;
      padding: 8px;
      text-align: left;
      vertical-align: top;
    }
    th {
      color: #4b5961;
      font-size: 11px;
      text-transform: uppercase;
    }
    .risk {
      border-left: 4px solid #b53131;
    }
    .print-hint {
      margin-top: 18px;
      color: #5c6970;
      font-size: 12px;
    }
    @media print {
      body {
        background: #ffffff;
      }
      main {
        max-width: none;
        padding: 18mm;
      }
      .card {
        break-inside: avoid;
      }
    }
    @media (max-width: 760px) {
      main {
        padding: 20px;
      }
      .kpis, .two-col {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <p class="label">MiSi - Mitie Sales Intelligence</p>
      <h1>${escapeHtml(report.report_name)}</h1>
      <p class="meta">Generated ${escapeHtml(formatDateTime(report.generated_at))} for ${escapeHtml(report.audience.join(", "))}</p>
      <p class="note">${escapeHtml(report.data_note)}</p>
    </header>

    <section>
      <h2>Executive Position</h2>
      <div class="grid kpis">
        ${metricCard("Total pipeline", compactCurrency(dashboard.total_pipeline_value), `${dashboard.live_opportunity_count} live opportunities`)}
        ${metricCard("Weighted pipeline", compactCurrency(dashboard.weighted_pipeline_value), `${dashboard.strategic_must_win_count} strategic must-wins`)}
        ${metricCard("Gross margin", compactCurrency(dashboard.estimated_gross_margin), `${percentageValue(dashboard.average_margin_percentage)} blended margin`)}
        ${metricCard("Red risks", String(dashboard.high_risk_count), `${dashboard.urgent_deadline_count} urgent deadlines`)}
      </div>
    </section>

    <section>
      <h2>Leadership Summary</h2>
      <div class="card">
        <h3>${escapeHtml(briefing.headline)}</h3>
        <p class="detail">${escapeHtml(briefing.summary)}</p>
      </div>
      <div class="grid two-col">
        ${listCard("MD attention", briefing.md_attention)}
        ${listCard("Finance attention", briefing.finance_attention)}
        ${listCard("Sales attention", briefing.sales_attention)}
        ${listCard("Bid team attention", briefing.bid_team_attention)}
      </div>
    </section>

    <section>
      <h2>Top Opportunities</h2>
      ${table(
        ["Opportunity", "Buyer", "Stage", "Weighted value", "Risk", "Action"],
        report.top_opportunities.map((opportunity) => [
          opportunity.name,
          opportunity.buyer_name,
          opportunity.stage,
          currency(opportunity.weighted_pipeline_value),
          opportunity.calculated_risk_rating || opportunity.risk_rating,
          opportunity.calculated_recommended_action || opportunity.recommended_action,
        ]),
      )}
    </section>

    <section>
      <h2>LE1 Finance Forecast</h2>
      <div class="grid kpis">
        ${metricCard("Secured revenue", compactCurrency(finance.secured_revenue), `${compactCurrency(finance.secured_gross_margin)} secured gross margin`)}
        ${metricCard("Open weighted revenue", compactCurrency(finance.open_weighted_revenue), `${compactCurrency(finance.open_weighted_margin)} weighted margin`)}
        ${metricCard("Risk-adjusted revenue", compactCurrency(finance.risk_adjusted_revenue), `${compactCurrency(finance.risk_adjusted_margin)} risk-adjusted margin`)}
        ${metricCard("Forecast to FY end", compactCurrency(finance.forecast_to_financial_year_end), `FY ${escapeHtml(finance.financial_year)} April to March`)}
      </div>
      <p class="detail">Monthly forecast window: ${escapeHtml(finance.financial_year_months.map(monthLabel).join(" / "))}</p>
      ${table(
        ["Client", "Category", "Start", "Revenue to FY end", "Margin", "Risk-adjusted revenue"],
        finance.open_opportunities.slice(0, 8).map((item) => [
          item.client,
          item.forecast_category,
          item.forecast_start_month,
          currency(item.revenue_to_financial_year_end),
          percentageValue(item.margin_percentage),
          currency(item.risk_adjusted_revenue),
        ]),
      )}
    </section>

    <section>
      <h2>Self-Delivery Summary</h2>
      <div class="grid kpis">
        ${metricCard("Opportunity value", compactCurrency(selfDelivery.opportunity_value), `${selfDelivery.route_opportunities.length} route opportunities`)}
        ${metricCard("Value captured", compactCurrency(selfDelivery.value_captured), `${selfDelivery.accepted_count} accepted opportunities`)}
        ${metricCard("Value at risk", compactCurrency(selfDelivery.value_at_risk), `${selfDelivery.leakage_risks.length} leakage risks`)}
        ${metricCard("Conversion rate", percentage(selfDelivery.conversion_rate), `${selfDelivery.declined_count} declined opportunities`)}
      </div>
      ${table(
        ["Route opportunity", "Buyer", "Discipline", "Value", "Action"],
        selfDelivery.route_opportunities.slice(0, 6).map((item) => [
          item.name,
          item.buyer_name,
          item.discipline,
          currency(item.estimated_value),
          item.recommended_action,
        ]),
      )}
    </section>

    <section>
      <h2>Risks And Recommendations</h2>
      <div class="grid">
        ${report.risks_and_recommendations
          .map(
            (item) => `<article class="card risk">
              <p class="label">${escapeHtml(item.priority)} / ${escapeHtml(item.category)}</p>
              <h3>${escapeHtml(item.summary)}</h3>
              <p class="detail">${escapeHtml(item.recommended_action)}</p>
              <p class="detail">Owner: ${escapeHtml(item.owner ?? "Leadership team")} | Value: ${escapeHtml(item.commercial_value == null ? "Value TBC" : currency(item.commercial_value))}</p>
            </article>`,
          )
          .join("")}
      </div>
    </section>

    <section>
      <h2>Executive Actions</h2>
      ${table(
        ["Priority", "Owner", "Due", "Action", "Reason"],
        report.executive_actions.map((action) => [
          action.priority,
          action.owner,
          shortDate(action.due_date),
          action.recommended_action,
          action.reason,
        ]),
      )}
    </section>

    <p class="print-hint">Use the browser print command to save this MVP report as PDF if required.</p>
  </main>
</body>
</html>`;
}

function metricCard(label: string, value: string, detail: string): string {
  return `<article class="card">
    <p class="label">${escapeHtml(label)}</p>
    <p class="value">${escapeHtml(value)}</p>
    <p class="detail">${escapeHtml(detail)}</p>
  </article>`;
}

function listCard(title: string, items: string[]): string {
  return `<article class="card">
    <h3>${escapeHtml(title)}</h3>
    ${items.length > 0 ? `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : `<p class="detail">No items raised.</p>`}
  </article>`;
}

function table(headers: string[], rows: string[][]): string {
  if (rows.length === 0) {
    return `<div class="card"><p class="detail">No records returned for this section.</p></div>`;
  }

  return `<table>
    <thead><tr>${headers.map((header) => `<th>${escapeHtml(header)}</th>`).join("")}</tr></thead>
    <tbody>
      ${rows
        .map(
          (row) =>
            `<tr>${row.map((cell) => `<td>${escapeHtml(cell)}</td>`).join("")}</tr>`,
        )
        .join("")}
    </tbody>
  </table>`;
}

function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
