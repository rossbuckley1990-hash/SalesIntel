"use client";
import { Fragment, useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { ArrowUp, Check, ExternalLink, Loader2, MessageSquarePlus, Square } from "lucide-react";
import { blocks, type Inline } from "./chat-text";
import { Pill } from "./ds";
import { safeUrl } from "./radar-model";
import { goto, param, si, type Call } from "./si-api";
import { WhoToCall } from "./si-call";
import { newKey, type JobT } from "./si-people";
import type { SharedProps } from "./types";

type Fact = { text: string; detail: string; date: string; url: string; publisher: string };
export type ChatCard = {
  n: number; name: string; headline: string; summary: string; why_hidden: string; standing: "hidden" | "check_first" | "published"; standing_label: string;
  publishers: string[]; facts: Fact[]; location: string; sector: string; website: string; unknowns: string[]; status: "offered" | "saved"; lead_key: string | null; turn: number;
  timing: { phase: string; label: string; light: string; window: { start: string; end: string } | null; reasons: string[] };
  records: { notices: { title: string; category_label: string; source_url: string }[]; contracts: { title: string; supplier: string; end_date: string; status: string; source_url: string }[] };
  known: { known: boolean; prospect?: { name: string; status: string }; account?: { name: string; status: string; deals: { title: string; stage: string }[] } };
  people: { name: string; role: string; source_url: string; quote: string }[]; contact_routes: { kind: string; value: string; label: string; source_url: string }[];
  call?: Call;
};
type Source = { n: number; url: string; title: string };
type UserTurn = { role: "user"; text: string; job_id: number; at: string; job?: JobT | null };
type ReplyTurn = { role: "assistant"; text: string; sources: Source[]; steps: string[]; cards: number[]; cost_cents: number; status: string; note: string; at: string };
type Chat = { id: number; title: string; turns: (UserTurn | ReplyTurn)[]; cards: ChatCard[]; running: (JobT & { cancel_requested?: boolean }) | null; live: { text: string; steps: string[]; cards: ChatCard[] } | null;
  cost_cents: number; pages_seen: number; updated_at: string };
type Row = { id: number; title: string; updated_at: string; cards: number; saved: number; cost_cents: number };

const EXAMPLES = ["Logistics firms opening new warehouses in Yorkshire in the next year", "Care home groups that changed owner in the last twelve months",
  "Hotels in the North West with a recent fire, enforcement notice or refurbishment"];
const STANDING_TONE = { hidden: "green", check_first: "amber", published: "neutral" } as const;
const LIGHT = { green: "green", amber: "amber", red: "red", grey: "neutral" } as const;
const money = (cents: number) => `$${(cents / 100).toFixed(2)}`;
const when = (iso: string) => (/^\d{4}-\d\d-\d\d/.test(iso) ? new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(`${iso.slice(0, 10)}T00:00:00Z`))
  : /^\d{4}-\d\d$/.test(iso) ? new Intl.DateTimeFormat("en-GB", { month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(`${iso}-01T00:00:00Z`)) : iso);
const today = () => new Date().toISOString().slice(0, 10);
const host = (url: string) => { try { return new URL(url).hostname.replace(/^www\./, ""); } catch { return url; } };

function setChatParam(id: number | null) {
  const url = new URL(window.location.href);
  if (id) url.searchParams.set("chat", String(id)); else url.searchParams.delete("chat");
  window.history.replaceState({}, "", url);
}

function Parts({ parts, sources }: { parts: Inline[]; sources: Map<number, Source> }) {
  return <>{parts.map((p, i) => {
    if (p.kind === "text") return <Fragment key={i}>{p.text}</Fragment>;
    if (p.kind === "br") return <br key={i} />;
    if (p.kind === "bold") return <strong key={i}><Parts parts={p.parts} sources={sources} /></strong>;
    if (p.kind === "link") { const href = safeUrl(p.href); return href ? <a key={i} href={href} target="_blank" rel="noreferrer">{p.text}</a> : <Fragment key={i}>{p.text}</Fragment>; }
    const s = sources.get(p.n); const href = s && safeUrl(s.url);
    return href ? <a key={i} className="si-cite" href={href} target="_blank" rel="noreferrer" aria-label={`Source ${p.n}: ${s!.title || host(s!.url)}`}>{p.n}</a> : null;
  })}</>;
}

/** A reply's text: the little Markdown the model writes, with numbered sources. */
function ReplyText({ text, sources }: { text: string; sources: Map<number, Source> }) {
  return <div className="si-chat-text">{blocks(text).map((b, i) => {
    if (b.kind === "p") return <p key={i}><Parts parts={b.parts} sources={sources} /></p>;
    if (b.kind === "h") return b.level === 3 ? <h3 key={i}><Parts parts={b.parts} sources={sources} /></h3> : <h4 key={i}><Parts parts={b.parts} sources={sources} /></h4>;
    const List = b.kind;
    return <List key={i}>{b.items.map((item, j) => <li key={j}><Parts parts={item} sources={sources} /></li>)}</List>;
  })}</div>;
}

function Steps({ steps, working }: { steps: string[]; working: boolean }) {
  if (!steps.length && !working) return null;
  const count = (re: RegExp) => steps.filter((s) => re.test(s)).length;
  const searches = count(/^Searched/), reads = count(/^Read/), checks = count(/^(Checked|Worked|Prepared)/);
  const summary = `${searches} search${searches === 1 ? "" : "es"}, ${reads} page${reads === 1 ? "" : "s"} read, ${checks} check${checks === 1 ? "" : "s"}`;
  const list = <ol className="si-chat-steps">{steps.map((s, i) => <li key={i} className={s.startsWith("“") ? "si-chat-step-note" : undefined}>{s}</li>)}{working && <li className="si-chat-step-now"><Loader2 size={12} className="ds-spin" aria-hidden="true" /> Working…</li>}</ol>;
  return working ? <div aria-label="What it is doing">{list}</div> : <details className="si-chat-steps-done"><summary>What it did: {summary}</summary>{list}</details>;
}

function Link({ url, children }: { url: string; children: ReactNode }) {
  const href = safeUrl(url);
  return href ? <a href={href} target="_blank" rel="noreferrer">{children}</a> : <>{children}</>;
}

/** One opportunity, as SalesIntel's checks left it: what is stated and by whom, the timing by the app's rules, and what is still unknown. */
export function OpportunityCard({ card, onSave }: { card: ChatCard; onSave?: (n: number) => void }) {
  const tag = card.standing === "hidden" ? `Hidden · ${card.publishers.length} independent sources` : card.standing === "check_first" ? "Check first · one source" : "Already published";
  return (
    <article className="si-chat-card" aria-label={card.name}>
      <header className="si-chat-card-head">
        <div className="min-w-0"><h4>{card.name}</h4>{(card.location || card.sector) && <p className="si-chat-card-meta">{[card.sector, card.location].filter(Boolean).join(" · ")}</p>}</div>
        <Pill tone={STANDING_TONE[card.standing]} dot>{tag}</Pill>
      </header>
      {card.headline && <p className="si-chat-card-headline">{card.headline}</p>}
      <section aria-label="Dated facts"><ul className="si-chat-facts">{card.facts.map((f, i) => <li key={i}>
        <span className="si-chat-fact-date">{when(f.date)}{f.date > today().slice(0, f.date.length) ? " (expected)" : ""}</span>
        <span>{f.text}{f.detail && f.detail !== f.text && <span className="text-ds-ink-2"> – {f.detail}</span>}<span className="text-ds-muted"> · <Link url={f.url}>{f.publisher}</Link></span></span></li>)}</ul></section>
      {card.why_hidden && <p className="si-chat-card-why"><strong>Why it may be hidden:</strong> {card.why_hidden} <span className="text-ds-muted">(SalesIntel&rsquo;s reading, not a published fact)</span></p>}
      <p className="si-chat-card-line"><Pill tone={LIGHT[card.timing.light as keyof typeof LIGHT] || "neutral"}>{card.timing.label}</Pill>
        <span>{card.timing.reasons[0] || "No dated clue sets the timing."} <span className="text-ds-muted">By SalesIntel&rsquo;s timing rules; a phase, not a forecast.</span></span></p>
      {card.records.notices.map((r, i) => <p key={`n${i}`} className="si-chat-card-line">Published {r.category_label.toLowerCase() || "notice"}: <Link url={r.source_url}>{r.title}</Link></p>)}
      {card.records.contracts.map((r, i) => <p key={`c${i}`} className="si-chat-card-line">Published contract: <Link url={r.source_url}>{r.title}</Link>{r.supplier && `, supplied by ${r.supplier}`}{r.end_date && `, ending ${when(r.end_date)}`}</p>)}
      {!card.records.notices.length && <p className="si-chat-card-line text-ds-muted">No tender or early notice for it in SalesIntel&rsquo;s public records.</p>}
      {card.known.known && <p className="si-chat-card-line"><strong>Already yours:</strong> {card.known.account ? `an account (${card.known.account.status})` : `a saved prospect (${card.known.prospect?.status})`}.</p>}
      {card.call ? <WhoToCall key={`${card.n}-${card.call.line}`} call={card.call} />
        : (!!card.people.length || !!card.contact_routes.length) && <section aria-label="Who to approach" className="si-chat-card-people">
        {card.people.map((p, i) => <p key={i}><strong>{p.name}</strong>, {p.role} · <Link url={p.source_url}>{host(p.source_url)}</Link></p>)}
        {card.contact_routes.map((r, i) => <p key={`r${i}`}>{r.label || r.kind}: {r.value} · <Link url={r.source_url}>{host(r.source_url)}</Link></p>)}</section>}
      {!!card.unknowns.length && <p className="si-chat-card-line text-ds-muted">Not yet known: {card.unknowns.slice(0, 3).join("; ")}.</p>}
      {onSave && <footer className="si-chat-card-foot">{card.status === "saved" && card.lead_key
        ? <><span className="si-chat-saved"><Check size={14} aria-hidden="true" /> Saved to Discover</span><button className="ds-btn ghost sm" onClick={() => goto("find", { lead: card.lead_key! })}>Open in Discover <ExternalLink size={13} aria-hidden="true" /></button></>
        : <button className="ds-btn sm" onClick={() => onSave(card.n)}>Save to Discover</button>}</footer>}
    </article>
  );
}

function SourceList({ sources }: { sources: Source[] }) {
  if (!sources.length) return null;
  return <ol className="si-chat-sources" aria-label="Sources">{sources.map((s) => <li key={s.n}><span className="si-cite" aria-hidden="true">{s.n}</span><Link url={s.url}>{s.title || host(s.url)}</Link><span className="text-ds-muted"> · {host(s.url)}</span></li>)}</ol>;
}

/** The research chat: ask in your own words; each reply searches, reads, checks and offers cards you can save to Discover. */
export function SiChat({ notify, ask, onAsked }: { notify: SharedProps["notify"]; ask?: string; onAsked?: () => void }) {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [chatId, setChatId] = useState<number | null>(() => Number(param("chat")) || null);
  const [chat, setChat] = useState<Chat | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const asked = useRef("");
  const end = useRef<HTMLDivElement>(null);

  const loadRows = useCallback(async () => { try { setRows((await si<{ items: Row[] }>("/research-chats")).items); } catch { setRows([]); } }, []);
  useEffect(() => { void loadRows(); }, [loadRows]);
  const open = useCallback((id: number | null) => { setChatId(id); setChatParam(id); if (!id) setChat(null); }, []);
  useEffect(() => {
    if (!chatId) return;
    let live = true;
    si<Chat>(`/research-chats/${chatId}`).then((c) => { if (live) setChat(c); }).catch((e) => { if (live) { notify((e as Error).message, true); open(null); } });
    return () => { live = false; };
  }, [chatId, notify, open]);
  const runningId = chat?.running?.id;
  const shownId = chat?.id;
  useEffect(() => {
    if (!shownId || !runningId) return;
    const id = shownId;
    const t = setInterval(async () => {
      try {
        const next = await si<Chat>(`/research-chats/${id}`);
        setChat(next);
        if (!next.running) { clearInterval(t); void loadRows(); }
      } catch { clearInterval(t); }
    }, 1000);
    return () => clearInterval(t);
  }, [shownId, runningId, loadRows]);
  useEffect(() => { if (runningId) end.current?.scrollIntoView({ block: "nearest" }); }, [chat?.live?.text.length, chat?.turns.length, runningId]);

  const send = useCallback(async (text: string, fresh = false) => {
    const t = text.trim();
    if (t.length < 3) return notify("Describe what to look for first.", true);
    setBusy(true);
    try {
      const into = fresh ? null : chat;
      const next = into ? await si<Chat>(`/research-chats/${into.id}/messages`, { method: "POST", json: { text: t }, headers: { "Idempotency-Key": newKey() } })
        : await si<Chat>("/research-chats", { method: "POST", json: { text: t }, headers: { "Idempotency-Key": newKey() } });
      setChat(next);
      setDraft("");
      if (!into) { setChatId(next.id); setChatParam(next.id); void loadRows(); }
    } catch (e) { notify((e as Error).message, true); } finally { setBusy(false); }
  }, [chat, notify, loadRows]);
  useEffect(() => {
    if (ask && asked.current !== ask) { asked.current = ask; void send(ask, true); onAsked?.(); }
  }, [ask, send, onAsked]);

  async function stop() {
    if (!chat) return;
    try { setChat(await si<Chat>(`/research-chats/${chat.id}/stop`, { method: "POST" })); notify("Stopping after its current step. What it has done so far is kept."); }
    catch (e) { notify((e as Error).message, true); }
  }
  async function save(n: number) {
    if (!chat) return;
    try {
      const saved = await si<{ card: ChatCard; lead_key: string }>(`/research-chats/${chat.id}/cards/${n}/save`, { method: "POST" });
      setChat((c) => c && { ...c, cards: c.cards.map((x) => (x.n === n ? saved.card : x)) });
      notify(`${saved.card.name} saved to Discover.`);
      void loadRows();
    } catch (e) { notify((e as Error).message, true); }
  }

  const sources = new Map<number, Source>();
  chat?.turns.forEach((t) => { if (t.role === "assistant") t.sources.forEach((s) => sources.set(s.n, s)); });
  const cardsBy = new Map(chat?.cards.map((c) => [c.n, c]) || []);
  const working = !!chat?.running;
  const lastStep = chat?.live?.steps.at(-1);

  return (
    <div className="si-chat">
      <aside className="si-chat-list" aria-label="Conversations">
        <button className="ds-btn sm w-full justify-center" onClick={() => open(null)} disabled={!chat}><MessageSquarePlus size={14} aria-hidden="true" /> New conversation</button>
        {!!rows?.length && <>
          <ul className="si-chat-rows">{rows.map((r) => <li key={r.id}><button aria-current={r.id === chat?.id ? "true" : undefined} onClick={() => open(r.id)}>
            <span className="si-chat-row-title">{r.title}</span><span className="si-chat-row-meta">{when(r.updated_at.slice(0, 10))} · {r.cards} card{r.cards === 1 ? "" : "s"}{r.saved ? `, ${r.saved} saved` : ""}</span></button></li>)}</ul>
          <select className="ds-select si-chat-rows-select" aria-label="Open a conversation" value={chat?.id ?? ""} onChange={(e) => open(Number(e.target.value) || null)}>
            <option value="">Earlier conversations</option>{rows.map((r) => <option key={r.id} value={r.id}>{r.title}</option>)}</select></>}
      </aside>

      <section className="si-chat-main" aria-label="Research chat">
        {!chat && <div className="si-chat-empty">
          <h2>Find opportunities nobody has announced</h2>
          <p>Say who you want to find, in your own words. SalesIntel searches the web, reads the pages that matter and links dated facts that point to a need before any tender. It checks every opportunity before showing it: each fact links to a page it read, timing comes from SalesIntel&rsquo;s own rules, and it says what is still unknown.</p>
          <ul aria-label="Examples">{EXAMPLES.map((x) => <li key={x}><button className="si-chat-example" onClick={() => void send(x, true)} disabled={busy}>{x}</button></li>)}</ul>
        </div>}

        {chat && <ol className="si-chat-log" aria-label="Conversation">
          {chat.turns.map((t, i) => {
            if (t.role === "user") {
              const next = chat.turns[i + 1];
              const pending = !next || next.role !== "assistant";
              const job = t.job || null;
              return <Fragment key={i}>
                <li className="si-chat-user"><p>{t.text}</p></li>
                {pending && working && i === chat.turns.length - 1 && <li className="si-chat-reply" aria-busy="true">
                  <Steps steps={chat.live?.steps || []} working />
                  {chat.live?.text && <ReplyText text={chat.live.text} sources={sources} />}
                  {!!chat.live?.cards.length && <div className="si-chat-cards">{chat.live.cards.map((c) => <OpportunityCard key={c.n} card={c} />)}</div>}
                  <p className="si-chat-foot">{chat.running?.cancel_requested ? "Stopping after its current step…" : `Researching · up to ${money(chat.running?.estimated_cents || 0)} reserved`}
                    {!chat.running?.cancel_requested && <button className="ds-btn ghost sm" onClick={() => void stop()}><Square size={12} aria-hidden="true" /> Stop</button>}</p>
                </li>}
                {pending && !working && job && <li className="si-chat-reply"><p className="si-chat-note">{job.status === "cancelled" ? "Stopped before it started." : job.status === "failed" ? `This reply did not complete. ${job.error || ""}` : "Waiting to start…"}</p></li>}
              </Fragment>;
            }
            return <li key={i} className="si-chat-reply">
              <Steps steps={t.steps} working={false} />
              <ReplyText text={t.text} sources={sources} />
              {!!t.cards.length && <div className="si-chat-cards">{t.cards.map((n) => cardsBy.get(n)).filter(Boolean).map((c) => <OpportunityCard key={c!.n} card={c!} onSave={save} />)}</div>}
              <SourceList sources={t.sources} />
              <p className="si-chat-foot">{t.note && <span className="si-chat-note">{t.note}</span>}<span>This reply cost {money(t.cost_cents)}</span></p>
            </li>;
          })}
        </ol>}
        <div ref={end} />
        <p className="sr-only" role="status" aria-live="polite">{working ? lastStep || "Researching" : ""}</p>

        <form className="si-chat-composer" onSubmit={(e) => { e.preventDefault(); void send(draft); }}>
          <textarea className="ds-input" aria-label="Message" rows={2} value={draft} disabled={busy} onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void send(draft); } }}
            placeholder={chat ? "Ask a follow-up: dig into one, who decides there, more like these…" : "e.g. care groups opening homes in Yorkshire next year that nobody is tendering yet"} />
          <button className="ds-btn primary" aria-label="Send" disabled={busy || working || draft.trim().length < 3}><ArrowUp size={16} aria-hidden="true" /></button>
          <p className="si-chat-hint">Each reply uses API credit and stops at {money(300)}.{chat ? ` This conversation so far: ${money(chat.cost_cents)}.` : ""}</p>
        </form>
      </section>
    </div>
  );
}
