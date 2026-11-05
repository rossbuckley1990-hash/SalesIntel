import { describe, expect, it } from "vitest";
import { pounds } from "../src/features/workspace/si-api";

describe("exact amounts", () => {
  it("shows API decimal strings without floating-point drift", () => {
    expect(pounds("1340.00")).toBe("£1,340.00");
    expect(pounds("4.555")).toBe("£4.555");
    expect(pounds("0.30")).toBe("£0.30");
    expect(pounds("1234567.5")).toBe("£1,234,567.50");
    expect(pounds(12500)).toBe("£12,500");
  });
  it("never invents a value", () => {
    expect(pounds(null)).toBe("Unknown");
    expect(pounds(undefined)).toBe("Unknown");
    expect(pounds("")).toBe("Unknown");
  });
});
