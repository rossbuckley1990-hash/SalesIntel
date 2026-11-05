import { describe, expect, it } from "vitest";
import { valueLine } from "../src/features/workspace/renewal-radar";

const base = { published_total: null, estimated_annualised: null, framework_ceiling: null, basis: "", scope_note: "" };

describe("radar value line", () => {
  it("never presents an estimate or ceiling as published spend", () => {
    expect(valueLine({ ...base, type: "estimated_annualised", estimated_annualised: 240382 })).toBe("£240,382 a year (estimated)");
    expect(valueLine({ ...base, type: "framework_ceiling", framework_ceiling: 1000000 })).toBe("£1,000,000 framework ceiling");
    expect(valueLine({ ...base, type: "published_total", published_total: 5000 })).toBe("£5,000 published total");
    expect(valueLine({ ...base, type: "unknown" })).toBe("Value not published");
  });
});
