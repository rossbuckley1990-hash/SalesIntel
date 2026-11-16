/**
 * A research reply as the rep reads it. The model writes a little Markdown: paragraphs, line breaks, bullet and
 * numbered lists, headings, bold and links. A numbered source is marked ⟦n⟧ by SalesIntel after a cited passage.
 * Nothing else is interpreted, and only https links are kept, so a page the model read cannot inject markup.
 */
export type Inline = { kind: "text"; text: string } | { kind: "bold"; parts: Inline[] } | { kind: "link"; text: string; href: string } | { kind: "cite"; n: number } | { kind: "br" };
export type Block = { kind: "p"; parts: Inline[] } | { kind: "h"; level: 3 | 4; parts: Inline[] } | { kind: "ul" | "ol"; items: Inline[][] };

const TOKEN = /⟦(\d+)⟧|\*\*(.+?)\*\*|\[([^\]\n]+)\]\((https:\/\/[^\s)]+)\)/g;

export function inline(text: string): Inline[] {
  const out: Inline[] = [];
  let last = 0;
  for (const m of text.matchAll(TOKEN)) {
    if ((m.index ?? 0) > last) out.push({ kind: "text", text: text.slice(last, m.index) });
    if (m[1]) out.push({ kind: "cite", n: Number(m[1]) });
    else if (m[2]) out.push({ kind: "bold", parts: inline(m[2]) });
    else out.push({ kind: "link", text: m[3], href: m[4] });
    last = (m.index ?? 0) + m[0].length;
  }
  if (last < text.length) out.push({ kind: "text", text: text.slice(last) });
  return out;
}

function lines(texts: string[]): Inline[] {
  return texts.flatMap((t, i) => (i ? [{ kind: "br" } as Inline, ...inline(t)] : inline(t)));
}

export function blocks(text: string): Block[] {
  const out: Block[] = [];
  let para: string[] = [];
  let list: { kind: "ul" | "ol"; items: string[] } | null = null;
  const endPara = () => { if (para.length) out.push({ kind: "p", parts: lines(para) }); para = []; };
  const endList = () => { if (list) out.push({ kind: list.kind, items: list.items.map(inline) }); list = null; };
  for (const raw of text.replace(/\r/g, "").split("\n")) {
    const line = raw.trimEnd();
    if (!line.trim()) { endPara(); endList(); continue; }
    const head = /^(#{1,4})\s+(.*)$/.exec(line.trim());
    const bullet = /^\s*[-*•]\s+(.*)$/.exec(line);
    const numbered = /^\s*\d+[.)]\s+(.*)$/.exec(line);
    if (head) { endPara(); endList(); out.push({ kind: "h", level: head[1].length <= 2 ? 3 : 4, parts: inline(head[2]) }); continue; }
    if (bullet || numbered) {
      endPara();
      const kind = bullet ? "ul" : "ol";
      if (!list || list.kind !== kind) { endList(); list = { kind, items: [] }; }
      list.items.push((bullet || numbered)![1]);
      continue;
    }
    if (list && /^\s{2,}\S/.test(raw)) { list.items[list.items.length - 1] += ` ${line.trim()}`; continue; }  // a wrapped list item
    endList();
    para.push(line.trim());
  }
  endPara();
  endList();
  return out;
}

/** The numbers of the sources a text cites, in order. */
export function cited(text: string): number[] {
  return [...new Set([...text.matchAll(/⟦(\d+)⟧/g)].map((m) => Number(m[1])))];
}
