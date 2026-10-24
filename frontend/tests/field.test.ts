import { describe, it, expect } from "vitest";
import { boundedScale, commercialGraph } from "../src/features/field/graph";
import {
  stepSpring,
  SPRING,
  mulberry32,
} from "../src/features/field/engine/spring";
import { Timeline } from "../src/features/field/engine/timeline";
import type {
  LivingOpportunity,
  Detail,
} from "../src/features/workspace/types";
const opportunity = {
  id: 12,
  buyer_name: "Test buyer",
  name: "Known source record",
  stage: "Qualification",
  risk_rating: "Red",
  financials: { estimated_gross_margin: null },
} as LivingOpportunity;
describe("commercial data grammar", () => {
  it("bounds visual scale and preserves unknown as a distinct neutral marker", () => {
    expect(boundedScale(null, 100)).toBe(1);
    expect(boundedScale(0, 100)).toBe(0.85);
    expect(boundedScale(1000, 100)).toBeCloseTo(1.45);
    expect(boundedScale(25, 100)).toBeCloseTo(1.15);
  });
  it("does not invent relationships or value for a portfolio", () => {
    const graph = commercialGraph(
      [opportunity],
      null,
      "estimated_gross_margin",
    );
    expect(graph.edges).toEqual([]);
    expect(graph.nodes[0]).toMatchObject({
      id: "opportunity:12",
      unknown: true,
      numericValue: null,
      value: "Unknown",
    });
  });
  it("links only recorded evidence and actions to the focus opportunity", () => {
    const detail = {
      opportunity,
      buyer: null,
      evidence: [
        {
          id: 9,
          field_name: "capacity",
          field_value: null,
          value_type: "unknown",
          confidence_score: 0,
          rationale: "Not confirmed",
        },
      ],
      actions: [
        {
          id: 4,
          owner: "Reviewer",
          due_date: null,
          status: "open",
          recommended_action: "Check capacity",
        },
      ],
    } as unknown as Detail;
    const g = commercialGraph([opportunity], detail, "estimated_gross_margin");
    expect(g.nodes).toHaveLength(3);
    expect(g.edges.map((e) => [e.source, e.target])).toEqual([
      ["opportunity:12", "field:9"],
      ["opportunity:12", "action:4"],
    ]);
    expect(g.nodes[1].value).toBe("Evidence missing");
  });
});
describe("BREAKOUT motion contracts", () => {
  for (const config of [SPRING.smooth, SPRING.camera, SPRING.bouncy])
    it(`is independent of frame partitions at damping ${config.damping}`, () => {
      const whole = stepSpring(0, 0, 1, 1, config);
      let part: [number, number] = [0, 0];
      for (let i = 0; i < 120; i++)
        part = stepSpring(...part, 1, 1 / 120, config);
      expect(part[0]).toBeCloseTo(whole[0], 8);
      expect(part[1]).toBeCloseTo(whole[1], 8);
    });
  it("interrupts choreography without executing pending actions", () => {
    let calls = 0;
    const t = new Timeline().at(0.5, () => calls++).play();
    t.update(0.2);
    t.stop();
    t.update(1);
    expect(calls).toBe(0);
    t.at(0.1, () => calls++).play();
    t.update(0.2);
    t.update(0.2);
    expect(calls).toBe(1);
  });
  it("makes assembly repeatable without changing financial state", () => {
    const a = mulberry32(13),
      b = mulberry32(13);
    expect([a(), a(), a()]).toEqual([b(), b(), b()]);
  });
});
