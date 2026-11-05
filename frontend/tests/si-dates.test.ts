import { afterEach, describe, expect, it, vi } from "vitest";
import { dayLabel, inDays } from "../src/features/workspace/si-api";

const zone = process.env.TZ;
afterEach(() => { vi.useRealTimers(); process.env.TZ = zone; });

describe("follow-up dates use the salesperson's calendar", () => {
  it("schedules 'tomorrow' for tomorrow just after midnight in British Summer Time", () => {
    process.env.TZ = "Europe/London";
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-10T23:30:00Z")); // 00:30 BST on 11 June
    expect(inDays(0)).toBe("2026-06-11");
    expect(inDays(1)).toBe("2026-06-12");
    expect(dayLabel(inDays(1))).toBe("Tomorrow");
    expect(dayLabel("2026-06-10")).toBe("Yesterday");
  });
  it("is unchanged in winter", () => {
    process.env.TZ = "Europe/London";
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-01-15T09:00:00Z"));
    expect(inDays(7)).toBe("2026-01-22");
  });
});
