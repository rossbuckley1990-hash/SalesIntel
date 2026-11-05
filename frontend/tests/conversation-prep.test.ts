import { describe, expect, it } from "vitest";
import { buildConversationPrep } from "../src/features/workspace/conversation-prep";

describe("conversation preparation", () => {
  it("preserves supporting and alternative observations, source dates and uncertainty", () => {
    const result = buildConversationPrep({ organisation: "Example Trust", location: "Wales", headline: "Explore a review", thesis: "A hypothesis to check.", supporting_observation_ids: ["one"], counter_observation_ids: ["two"], unknowns: ["Current provider"], contact_name: "", contact_role: "Estates team", engagement: "Ask how visits are coordinated.", verification_action: "Confirm the site." }, [
      { id: "one", source_title: "Estate report", source_url: "https://example.org/estate", published_date: "2026-01-01", fact: "An upgrade was planned." },
      { id: "two", source_title: "Update", source_url: "javascript:alert(1)", published_date: null, fact: "The work was completed." },
      { id: "other", source_title: "Unrelated", source_url: "https://example.org/other", published_date: null, fact: "Unrelated." },
    ]);
    expect(result).toContain("Research hypothesis — verify before use");
    expect(result).toContain("Current provider");
    expect(result).toContain("Estate report · 2026-01-01 · https://example.org/estate");
    expect(result).toContain("The work was completed.");
    expect(result).toContain("source link unavailable");
    expect(result).not.toContain("javascript:");
    expect(result).not.toContain("Unrelated.");
  });
});
