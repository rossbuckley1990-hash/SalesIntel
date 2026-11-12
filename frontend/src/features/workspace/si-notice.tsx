"use client";
/** Two sections of the Living Opportunity, both read straight from stored public records.
 *  NoticeFacts: what the opportunity's own notice states (value, dates, scoring, lots, requirements, documents).
 *  FieldView: what the published contract record says about this buyer, the published holder, the suppliers that win
 *  this kind of work and what it went for. A missing figure means the record does not give one; nothing is estimated. */
import { useState, type ReactNode } from "react";
import { ArrowUpRight, FileText } from "lucide-react";
import { hostOf, safeUrl } from "./radar-model";
import { goto } from "./si-api";

export type NoticeT = {
  stage?: "planning" | "tender" | "award"; title?: string; description?: string; reference?: string;
  buyer?: { name?: string; locality?: string; postcode?: string; region?: string; website?: string; type?: string };
  value?: { amount: number; gross?: number | null; currency?: string; basis?: string; kind: "estimate" | "award"; label: string };
  term?: { start?: string; end?: string; max_end?: string; months?: number | null; renewal?: string; has_renewal?: boolean; varies_by_lot?: boolean; label?: string };
  deadlines?: { key: string; label: string; date: string; time?: string; note?: string; days?: number }[];
  procedure?: { method?: string; method_label?: string; details?: string; category?: string; above_threshold?: boolean; sme_suitable?: boolean; vcse_suitable?: boolean };
  criteria?: { split?: { label: string; weight: number }[] | null; summary?: string; same_for_all_lots?: boolean; lot_count?: number;
    lots?: { lot: string; title: string; items: { type: string; name: string; weight: number | null; detail: string }[] }[] };
  requirements?: string[];
  lots?: { id: string; title: string; description?: string; value?: number | null; value_label?: string }[];
  portal?: string;
  documents?: { type: string; label: string; title?: string; url: string; published?: string }[];
  cpv?: { id: string; description?: string }[];
  places?: string[];
  bids?: { lots?: number; fewest?: number; most?: number; label: string; bid_range?: { low: number; high: number; label: string } };
  suppliers?: { name: string; size?: string }[];
  source_url?: string; source?: string;
  pointers?: { label: string; text: string }[];
};
type SupplierT = { name: string; contractor_id: number; yours: boolean };
type LastTime = { bids?: string; bid_range?: string; scoring?: string; procedure?: string };
type CardT = { key: string; title: string; buyer: string; suppliers: SupplierT[]; supplier_count: number; services: string[]; similar: boolean; route: string; call_off: boolean;
  framework: boolean; status: { code: string; label: string }; end: string; awarded: string; value: string; source: string; last_time?: LastTime };
export type FieldT = {
  available: boolean; coverage: string; services?: string[];
  buyer?: { key: string; contracts: number; similar: number; suppliers: string[]; supplier_count: number; frameworks: number; next_end: { end: string; title: string; key: string } | null; items: CardT[] };
  winners?: { items: { contractor_id: number; name: string; contracts: number; buyers: number; latest: string; latest_buyer: string; in_region: number; this_buyer: boolean; yours: boolean }[];
    suppliers: number; contracts: number; basis: string; caveat: string } | null;
  prices?: { where: string; recent: { key: string; buyer: string; supplier: string; title: string; awarded: string; value: string; source: string }[];
    range?: { count: number; low: number; median: number; high: number; label: string; basis: string } } | null;
  ways?: { label: string; text: string; key?: string }[];
  incumbent?: { state: "in_term" | "past" | "none"; names: string[]; suppliers: SupplierT[]; text: string; contract?: CardT; caveat: string; others: number; last_time?: LastTime };
  compared?: { label: string; text: string }[];
  holder?: { suppliers: SupplierT[]; contracts: number; buyers: number; also_ending: number; with_this_buyer: number; last_time: LastTime } | null;
};

const STAGE: Record<string, string> = { planning: "Early notice", tender: "Tender notice", award: "Award notice" };
const SIZE: Record<string, string> = { sme: "SME", large: "Large company", micro: "Micro business", small: "Small business", medium: "Medium-sized business" };

function day(iso: string) {
  const d = new Date(`${iso.slice(0, 10)}T00:00:00`);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}
/** A count of days as a person says it. The count itself comes from the API, so the page and the brief never disagree. */
export function daysLabel(days: number) {
  if (days === 0) return "today";
  if (days === 1) return "tomorrow";
  if (days === -1) return "yesterday";
  return days > 0 ? `in ${days} days` : `${-days} days ago`;
}
const pct = (w: number) => (Math.abs(w - Math.round(w)) < 0.05 ? String(Math.round(w)) : w.toFixed(1));
const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

function Out({ url, label, icon }: { url: string; label?: string; icon?: ReactNode }) {
  const href = safeUrl(url);
  if (!href) return null;
  return <a className="lo-source" href={href} target="_blank" rel="noreferrer">{icon}{label || hostOf(href)}<ArrowUpRight size={12} aria-hidden="true" /></a>;
}
function Supplier({ s }: { s: SupplierT }) {
  return <button className="lo-co" onClick={() => goto("find", { mode: "atlas", contractor: s.contractor_id })} title="Open this supplier in the Contract Atlas">
    {s.name}{s.yours && <span className="lo-you">Your company</span>}</button>;
}
function Row({ q, children }: { q: string; children: ReactNode }) {
  return <section><h4 className="lo-q">{q}</h4>{children}</section>;
}
function Last({ t }: { t?: LastTime }) {
  const rows = [["Procedure", t?.procedure], ["Bids", t?.bids], ["Spread", t?.bid_range], ["Scoring", t?.scoring]].filter((r) => r[1]) as [string, string][];
  if (!rows.length) return null;
  return <dl className="lo-last" aria-label="How it was bought last time">{rows.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>;
}

// ------------------------------------------------------------------ what the notice says

export function NoticeFacts({ n }: { n: NoticeT }) {
  const [more, setMore] = useState(false);
  const stage = n.stage || "tender";
  const ahead = (n.deadlines || []).filter((d) => (d.days ?? 0) >= 0);
  const main = ["submission", "engagement", "notice_expected"].map((k) => ahead.find((d) => d.key === k)).find(Boolean) || ahead[0] || null;
  const split = n.criteria?.split || null;
  const quality = split?.find((s) => s.label === "Quality")?.weight;
  const price = split?.find((s) => s.label === "Price")?.weight;
  const [termHead, ...termRest] = (n.term?.label || "").split(", ");
  const text = n.description || "";
  const long = text.length > 420;
  const scoring = n.criteria?.lots || [];
  const shown = n.criteria?.same_for_all_lots ? scoring.slice(0, 1) : scoring.slice(0, 4);
  const buyer = n.buyer;
  const where = [buyer?.locality, buyer?.postcode].filter(Boolean).join(" ");
  const procedure = [n.procedure?.method_label, n.procedure?.above_threshold ? "above the procurement threshold" : "",
    n.procedure?.sme_suitable ? "marked suitable for smaller suppliers" : "", n.procedure?.vcse_suitable ? "marked suitable for voluntary and community organisations" : ""].filter(Boolean) as string[];
  const hasFigures = !!(n.value || main || termHead || n.criteria?.summary || n.bids || n.suppliers?.length);
  return (
    <section className="lo-section" aria-label="What the notice says">
      <div className="lo-section-head"><h3>What the notice says</h3>
        <span className="lo-meta">{STAGE[stage]}{n.reference && <> · {n.reference}</>}{n.source_url && <> · <Out url={n.source_url} label="Read the notice" /></>}</span></div>

      {hasFigures && <dl className="lo-figs">
        {n.value && <div className="lo-fig"><dt className="lo-q">{n.value.kind === "award" ? "Awarded value" : "Estimated value"}</dt>
          <dd><span className="v">{n.value.label}</span><span className="n">{n.value.basis || "As published"}</span></dd></div>}
        {main && <div className="lo-fig" data-tone={(main.days ?? 99) <= 7 ? "urgent" : (main.days ?? 99) <= 14 ? "soon" : undefined}><dt className="lo-q">{main.label}</dt>
          <dd><span className="v">{day(main.date)}</span><span className="n">{main.time && <>{main.time} · </>}<b>{daysLabel(main.days ?? 0)}</b></span></dd></div>}
        {stage === "award" && !!n.suppliers?.length && <div className="lo-fig"><dt className="lo-q">Awarded to</dt>
          <dd><span className="v sm">{n.suppliers[0].name}</span><span className="n">{n.suppliers.length > 1 ? `and ${plural(n.suppliers.length - 1, "other supplier")}` : SIZE[n.suppliers[0].size || ""] || "Named on the award"}</span></dd></div>}
        {stage === "award" && n.bids && <div className="lo-fig"><dt className="lo-q">Competition</dt>
          <dd><span className="v sm">{n.bids.label}</span>{n.bids.bid_range && <span className="n">{n.bids.bid_range.label}</span>}</dd></div>}
        {termHead && <div className="lo-fig"><dt className="lo-q">Contract term</dt>
          <dd><span className="v">{termHead}</span><span className="n">{[termRest.join(", "), n.term?.start ? `from ${day(n.term.start)}` : "", n.term?.varies_by_lot ? "varies by lot" : ""].filter(Boolean).join(" · ") || "As published"}</span></dd></div>}
        {stage !== "award" && n.criteria?.summary && <div className="lo-fig"><dt className="lo-q">How it is scored</dt>
          {quality !== undefined && price !== undefined ? <dd><span className="v">{pct(quality)} / {pct(price)}</span><span className="n">Quality / price, per cent</span>
            <span className="lo-scorebar" aria-hidden="true"><i style={{ width: `${quality}%` }} /><i className="p" style={{ width: `${price}%` }} /></span></dd>
            : <dd><span className="v sm">{n.criteria.summary}</span></dd>}</div>}
      </dl>}

      <div className="lo-grid lo-rows">
        {text && <Row q={stage === "award" ? "What was bought" : "Scope, in the buyer’s words"}>
          <p className={long && !more ? "lo-clamp" : ""}>{text}</p>
          {long && <button className="lo-more" onClick={() => setMore(!more)} aria-expanded={more}>{more ? "Show less" : "Read it all"}</button>}
        </Row>}
        {!!n.deadlines?.length && <Row q="Key dates">
          <ul className="lo-dates">{n.deadlines.map((d) => <li key={d.key} data-past={(d.days ?? 0) < 0 || undefined}>
            <span className="what">{d.label}{d.note && <small>{d.note}</small>}</span>
            <span className="when">{day(d.date)}{d.time && `, ${d.time}`}</span>
            <span className="left">{daysLabel(d.days ?? 0)}</span></li>)}</ul>
        </Row>}
        {!!shown.length && stage !== "award" && <Row q="Scoring">
          {shown.map((lot) => <div key={lot.lot} className="lo-score">
            {!n.criteria?.same_for_all_lots && <p className="lo-score-lot">Lot {lot.lot}{lot.title && `: ${lot.title}`}</p>}
            <ul>{lot.items.slice(0, 8).map((c, i) => <li key={i}><span className="what">{c.name}{c.detail && <small>{c.detail}</small>}</span>
              <span className="kind">{c.type === "other" ? "" : c.type}</span><span className="w">{c.weight === null ? "not weighted" : `${pct(c.weight)}%`}</span></li>)}</ul>
          </div>)}
          {n.criteria?.same_for_all_lots && (n.criteria.lot_count || 0) > 1 && <p className="lo-note">The same for all {n.criteria.lot_count} lots.</p>}
          {!n.criteria?.same_for_all_lots && scoring.length > shown.length && <p className="lo-note">{plural(scoring.length - shown.length, "more lot")} in the notice.</p>}
        </Row>}
        {!!n.lots?.length && <Row q={`${n.lots.length} lots`}>
          <ul className="lo-lots">{n.lots.slice(0, 8).map((l) => <li key={l.id}><span className="id">Lot {l.id}</span><span className="what">{l.title}{l.description && <small>{l.description}</small>}</span>
            <span className="w">{l.value_label || ""}</span></li>)}</ul>
          {n.lots.length > 8 && <p className="lo-note">{plural(n.lots.length - 8, "more lot")} in the notice.</p>}
        </Row>}
        {!!n.requirements?.length && <Row q="Stated conditions"><ul className="lo-list">{n.requirements.map((r) => <li key={r}>{r}</li>)}</ul></Row>}
        {!!n.pointers?.length && <Row q="Worth knowing"><ul className="lo-points">{n.pointers.map((p) => <li key={p.label}><strong>{p.label}.</strong> {p.text}</li>)}</ul></Row>}
        {stage === "award" && (n.suppliers?.length || 0) > 1 && <Row q="Awarded to"><ul className="lo-list">{n.suppliers!.map((s) => <li key={s.name}>{s.name}{SIZE[s.size || ""] && <span className="lo-muted"> · {SIZE[s.size || ""]}</span>}</li>)}</ul></Row>}
        {(n.portal || !!n.documents?.length) && <Row q="Documents">
          <ul className="lo-docs">
            {n.portal && <li><Out url={n.portal} label="Open the tender portal" /><span className="lo-muted">where the documents and submissions are handled</span></li>}
            {n.documents?.slice(0, 6).map((d) => <li key={d.url}><Out url={d.url} label={d.title || d.label} icon={<FileText size={12} aria-hidden="true" />} />
              <span className="lo-muted">{[d.title && d.label !== d.title ? d.label : "", d.published ? `published ${day(d.published)}` : ""].filter(Boolean).join(" · ")}</span></li>)}
          </ul>
        </Row>}
        {(buyer?.name || !!procedure.length || !!n.cpv?.length) && <Row q="Buyer and route">
          {buyer?.name && <p>{buyer.name}{buyer.type && <span className="lo-muted"> · {buyer.type}</span>}{where && <span className="lo-muted"> · {where}</span>}
            {buyer.region && buyer.region !== buyer.locality && <span className="lo-muted"> · {buyer.region}</span>}{buyer.website && <> <Out url={buyer.website} /></>}</p>}
          {!!procedure.length && <p>{procedure.join(", ").replace(/^./, (c) => c.toUpperCase())}.</p>}
          {!!n.cpv?.length && <p className="lo-note">Classified as {n.cpv.slice(0, 3).map((c) => (c.description ? `${c.description} (${c.id})` : c.id)).join("; ")}
            {n.cpv.length > 3 && ` and ${n.cpv.length - 3} more`}.{!!n.places?.length && ` Delivered in ${n.places.slice(0, 3).join(", ")}.`}</p>}
        </Row>}
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ the competitive field

function Contract({ c, open }: { c: CardT; open: (key: string) => void }) {
  return (
    <li className="lo-contract">
      <button className="t" onClick={() => open(c.key)} title="Open this contract">{c.title}</button>
      <p className="m">{c.suppliers.map((s, i) => <span key={s.contractor_id}>{i > 0 && ", "}<Supplier s={s} /></span>)}{c.supplier_count > c.suppliers.length && ` and ${c.supplier_count - c.suppliers.length} more`}</p>
      <p className="s"><span data-code={c.status.code}>{c.status.label}</span>{c.value && <> · {c.value}</>}{c.route && <> · {c.route}</>}{c.source && <> · <Out url={c.source} /></>}</p>
      <Last t={c.last_time} />
    </li>
  );
}

export function FieldView({ f, own }: { f: FieldT; own?: string }) {
  const open = (key: string) => goto("find", { lead: key });
  if (!f.available) return (
    <section className="lo-section" aria-label="The competitive field">
      <div className="lo-section-head"><h3>The competitive field</h3><span className="lo-meta">From published contract records</span></div>
      <p className="lo-muted">The contract record has not been built in this workspace yet. {f.coverage}</p>
    </section>);
  const inc = f.incumbent;
  const hold = f.holder;
  const buyer = f.buyer;
  const others = (buyer?.items || []).filter((c) => c.key !== inc?.contract?.key && c.key !== own);
  const winners = f.winners?.items || [];
  const prices = f.prices;
  return (
    <section className="lo-section" aria-label="The competitive field">
      <div className="lo-section-head"><h3>The competitive field</h3>
        <span className="lo-meta">From published contract records{!!f.services?.length && <> · {f.services.join(", ").toLowerCase()}</>}</span></div>
      <div className="lo-grid lo-rows">
        {inc && <Row q="Published holder">
          <p className={inc.state === "none" ? "lo-muted" : "lo-lede"}>{inc.text}</p>
          {!!inc.suppliers.length && <p className="lo-cos">{inc.suppliers.map((s) => <Supplier key={s.contractor_id} s={s} />)}
            {inc.contract?.source && <Out url={inc.contract.source} label="The award notice" />}</p>}
          {inc.contract?.value && <p className="lo-note">Published value: {inc.contract.value}. Awarded {inc.contract.awarded ? day(inc.contract.awarded) : "on an unpublished date"}.</p>}
          <Last t={inc.last_time} />
          {inc.others > 0 && <p className="lo-note">{plural(inc.others, "other published contract")} for similar work with this buyer.</p>}
          <p className="lo-note">{inc.caveat}</p>
        </Row>}
        {hold && <Row q="The published holder">
          <p className="lo-cos">{hold.suppliers.map((s) => <Supplier key={s.contractor_id} s={s} />)}</p>
          <p>{plural(hold.contracts, "published contract")} with {plural(hold.buyers, "buyer")} in the record{hold.with_this_buyer > 1 && <>, {hold.with_this_buyer} of them with this buyer</>}
            {hold.also_ending > 0 && <>. {hold.also_ending} other{hold.also_ending === 1 ? " is" : "s are"} approaching {hold.also_ending === 1 ? "its" : "their"} published end</>}.</p>
          <Last t={hold.last_time} />
          <p className="lo-note">From the published record. It does not confirm who delivers the work today.</p>
        </Row>}
        {!!f.compared?.length && <Row q="This time against last">
          <ul className="lo-points">{f.compared.map((c) => <li key={c.label}><strong>{c.label}.</strong> {c.text}</li>)}</ul>
        </Row>}
        {buyer && <Row q="This buyer’s record">
          {!buyer.contracts ? <p className="lo-muted">No other published contract with this buyer in the records collected.</p> : <>
            <p>{plural(buyer.contracts, "published contract")} with this buyer in the record{buyer.similar > 0 && <>, {buyer.similar} for similar work</>}
              {buyer.supplier_count > 0 && <>, naming {plural(buyer.supplier_count, "supplier")}</>}{buyer.frameworks > 0 && <>; {plural(buyer.frameworks, "framework appointment")}</>}.</p>
            {!!others.length && <ul className="lo-contracts">{others.slice(0, 4).map((c) => <Contract key={c.key} c={c} open={open} />)}</ul>}</>}
          <button className="lo-link" onClick={() => goto("find", { mode: "atlas", customer: buyer.key })}>Everything published for this buyer</button>
        </Row>}
        {!!winners.length && f.winners && <Row q="Who wins this work">
          <ol className="lo-winners">{winners.map((w) => <li key={w.contractor_id}>
            <span className="who"><Supplier s={w} />{w.this_buyer && <span className="lo-here">Holds work with this buyer</span>}</span>
            <span className="what">{plural(w.contracts, "contract")} · {plural(w.buyers, "buyer")}{w.in_region > 0 && <> · {w.in_region} in this region</>}
              {w.latest && <> · latest {day(w.latest)}{w.latest_buyer && `, ${w.latest_buyer}`}</>}</span></li>)}</ol>
          <p className="lo-note">{f.winners.basis} {f.winners.suppliers > winners.length && `${f.winners.suppliers} suppliers across ${f.winners.contracts} contracts in all. `}{f.winners.caveat}</p>
        </Row>}
        {prices && <Row q="What similar work went for">
          {prices.range && <><p className="lo-range"><strong>{prices.range.label}</strong></p><p className="lo-note">{prices.range.basis}</p></>}
          {!!prices.recent.length && <ul className="lo-prices">{prices.recent.map((p) => <li key={p.key}>
            <span className="v">{p.value}</span>
            <span className="what"><button className="t" onClick={() => open(p.key)} title="Open this contract">{p.title}</button>
              <small>{p.buyer} · {p.supplier}{p.awarded && ` · awarded ${day(p.awarded)}`}{p.source && <> · <Out url={p.source} /></>}</small></span></li>)}</ul>}
          {!prices.range && <p className="lo-note">Recent published awards for similar work in {prices.where}. Too few carry a yearly value to state a typical range.</p>}
        </Row>}
        {!!f.ways?.length && <Row q="Ways in">
          <ul className="lo-points">{f.ways.map((w) => <li key={w.label}><strong>{w.label}.</strong> {w.text}
            {w.key && <> <button className="lo-link inline" onClick={() => open(w.key!)}>Open it</button></>}</li>)}</ul>
        </Row>}
      </div>
      <p className="lo-note lo-coverage">{f.coverage}</p>
    </section>
  );
}
