import { describe, expect, it } from "vitest";
import { publicResearchExport, publicSourceLabel } from "../src/features/workspace/public-source-labels";

describe("public research presentation", () => {
  it("normalises legacy system messages and export provenance while preserving source URLs", () => {
    expect(publicSourceLabel("RightClick-X returned context")).toBe("public source discovery returned context");
    expect(publicResearchExport({ origin: "rightclick_x", rightclick_identifier: "123", message: "RightClick-X returned context", source_url: "https://example.org/record" })).toEqual({ origin: "public_api", public_source_identifier: "123", message: "public source discovery returned context", source_url: "https://example.org/record" });
  });
});
