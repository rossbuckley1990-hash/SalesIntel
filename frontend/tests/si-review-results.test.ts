/**
 * The blind review's results screen renders what the server returns, including the diagnosis registered before any answer.
 * The fixture is the server's own output on a synthetic set; `backend/tests/test_review_diagnosis.py` keeps the two in step.
 */
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { Results, type ResultsT } from "@/features/workspace/si-review";
import fixture from "./fixtures/review-results.json";

const results = fixture as unknown as ResultsT;
const render = (r: ResultsT) => renderToStaticMarkup(createElement(Results, { r }));

describe("blind review results", () => {
  it("shows the diagnosis registered before any answer, beside the pre-specified comparisons", () => {
    const html = render(results);
    expect(html).toContain("Comparisons, decided before the review");
    expect(html).toContain("Diagnosis, registered before any answer (6 November 2026)");
    expect(html).toContain("Otherwise missed");
    expect(html).toContain("Where leads drop out");
    for (const step of results.diagnosis!.steps) expect(html).toContain(step.label);
    for (const arm of Object.values(results.arms)) expect(html).toContain(arm.label);
  });

  it("shows a share for every method at every step, in the acceptance test's order", () => {
    const table = render(results).split("Where leads drop out")[1].split("</table>")[0];
    const rows = table.split("<tr").slice(2);  // after the caption and the header row
    expect(rows).toHaveLength(results.diagnosis!.steps.length);
    rows.forEach((row, n) => {
      expect(row).toContain(results.diagnosis!.steps[n].label);
      expect(row.match(/%/g)?.length ?? 0).toBeGreaterThanOrEqual(Object.keys(results.arms).length);
    });
  });

  it("still renders results from a server that has no diagnosis", () => {
    const html = render({ ...results, diagnosis: undefined });
    expect(html).toContain("Comparisons, decided before the review");
    expect(html).not.toContain("Where leads drop out");
  });
});
