import { describe, expect, it } from "vitest";
import { blocks, cited, inline } from "../src/features/workspace/chat-text";

describe("a research reply as the rep reads it", () => {
  it("keeps paragraphs, line breaks, lists and headings", () => {
    const text = "I found two.\n\n## Northgate\n**Northgate Distribution Ltd**, Wakefield\nWhy now:\n- A new site⟦1⟧\n- A named head of property⟦2⟧\n  responsible for new sites\n\n1. Call\n2. Ask";
    expect(blocks(text)).toEqual([
      { kind: "p", parts: [{ kind: "text", text: "I found two." }] },
      { kind: "h", level: 3, parts: [{ kind: "text", text: "Northgate" }] },
      { kind: "p", parts: [{ kind: "bold", parts: [{ kind: "text", text: "Northgate Distribution Ltd" }] }, { kind: "text", text: ", Wakefield" }, { kind: "br" }, { kind: "text", text: "Why now:" }] },
      { kind: "ul", items: [[{ kind: "text", text: "A new site" }, { kind: "cite", n: 1 }], [{ kind: "text", text: "A named head of property" }, { kind: "cite", n: 2 }, { kind: "text", text: " responsible for new sites" }]] },
      { kind: "ol", items: [[{ kind: "text", text: "Call" }], [{ kind: "text", text: "Ask" }]] },
    ]);
  });

  it("keeps only https links, and nothing else is markup", () => {
    expect(inline("[site](https://example.com/a) and [bad](javascript:alert(1)) <b>x</b>")).toEqual([
      { kind: "link", text: "site", href: "https://example.com/a" },
      { kind: "text", text: " and [bad](javascript:alert(1)) <b>x</b>" },
    ]);
  });

  it("lists the sources a reply cites, once each", () => {
    expect(cited("a⟦2⟧ b⟦1⟧ c⟦2⟧")).toEqual([2, 1]);
  });
});
