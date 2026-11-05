"""An offline review pack: one self-contained HTML file a salesperson opens in their browser to judge the blinded items.

Why a file, not a login:
- reviewers never touch the development server;
- the pack holds only what reviewers may see: the blinded items, the rubric and the dataset fingerprint;
- its content security policy forbids every network request, so nothing is sent anywhere while they work.

How it works:
- answers are saved in the browser as the reviewer goes;
- at the end the reviewer downloads one answers file and sends it to whoever runs the review;
- that file names the dataset by its fingerprint, and is refused on import if it does not match;
- each reviewer gets their own order of items, to spread fatigue and order effects."""
from __future__ import annotations

import html
import json
import random

from app.intelligence import opportunity_review as review


def render(review_set: dict, commitment: dict, *, reviewer: str) -> str:
    if review.digest(review_set) != commitment['dataset_sha256']:
        raise ValueError('The review set does not match its commitment.')
    order = [i['id'] for i in review_set['items']]
    random.Random(f"{commitment['dataset_sha256']}:{reviewer}").shuffle(order)
    payload = {'format': 'salesintel-review/1', 'set_key': review_set['set_key'], 'as_of': review_set['as_of'],
               'dataset_sha256': commitment['dataset_sha256'], 'reviewer_label': reviewer, 'rubric': review_set['rubric'],
               'instructions': review_set['instructions'], 'items': review_set['items'], 'order': order}
    data = json.dumps(payload, ensure_ascii=False).replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')
    return TEMPLATE.replace('__TITLE__', html.escape(f'Opportunity review: {reviewer}')).replace('__DATA__', data)


TEMPLATE = r"""<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:; form-action 'none'; base-uri 'none'">
<meta name="referrer" content="no-referrer">
<title>__TITLE__</title>
<style>
:root { --ink: #15181d; --ink-2: #3b414b; --muted: #687080; --line: #e4e6ea; --line-2: #c8ccd3; --paper: #ffffff; --wash: #f5f5f3;
        --accent: #c2410c; --accent-soft: #fdf0e8; --good: #166534; --good-soft: #e9f5ed; color-scheme: light; }
* { box-sizing: border-box; }
html, body { margin: 0; background: var(--wash); color: var(--ink); font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }
main { max-width: 1120px; margin: 0 auto; padding: 28px 16px 64px; }
h1 { font-size: 26px; line-height: 1.15; letter-spacing: -0.02em; margin: 0 0 6px; }
h2 { font: 600 26px/1.15 Georgia, "Times New Roman", serif; letter-spacing: -0.01em; margin: 8px 0 2px; }
p { margin: 0 0 10px; }
a { color: var(--ink); text-underline-offset: 2px; }
.eyebrow { font-size: 11px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); margin-bottom: 6px; }
.muted { color: var(--muted); }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; }
.card { background: var(--paper); border: 1px solid var(--line); border-radius: 12px; padding: 20px; }
.grid { display: grid; gap: 18px; align-items: start; }
@media (min-width: 980px) { .grid { grid-template-columns: minmax(0, 1fr) 420px; } }
.top { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: flex-end; gap: 12px; margin-bottom: 16px; }
.count { font: 600 22px/1 ui-monospace, SFMono-Regular, Menlo, monospace; text-align: right; }
.pill { display: inline-block; border: 1px solid var(--line-2); border-radius: 999px; padding: 1px 9px; font-size: 12px; color: var(--ink-2); background: var(--paper); }
nav.items { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 16px; }
nav.items button { min-width: 50px; height: 28px; border: 1px solid var(--line); background: var(--paper); color: var(--muted); border-radius: 6px; font: 11px ui-monospace, Menlo, monospace; cursor: pointer; }
nav.items button.done { background: var(--good-soft); color: var(--good); border-color: transparent; }
nav.items button[aria-current="true"] { border-color: var(--ink); color: var(--ink); }
ul.facts { list-style: none; padding: 0; margin: 10px 0 0; }
ul.facts li { padding: 8px 0; border-top: 1px solid var(--line); color: var(--ink-2); font-size: 14px; }
ul.facts li:first-child { border-top: 0; }
.basis { font-size: 12px; color: var(--muted); }
fieldset { border: 0; padding: 0; margin: 0 0 14px; }
legend { font-weight: 600; font-size: 13.5px; margin-bottom: 6px; padding: 0; }
.options { display: flex; flex-wrap: wrap; gap: 6px; }
.options label { display: inline-flex; align-items: center; gap: 6px; border: 1px solid var(--line-2); border-radius: 7px; padding: 4px 10px; font-size: 13px; cursor: pointer; background: var(--paper); }
.options label:has(input:checked) { border-color: var(--ink); background: var(--ink); color: #fff; }
.options input { accent-color: var(--accent); margin: 0; }
input[type=text], textarea { width: 100%; font: inherit; border: 1px solid var(--line-2); border-radius: 8px; padding: 8px 10px; background: var(--paper); color: var(--ink); }
textarea { min-height: 64px; resize: vertical; }
.row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; justify-content: space-between; }
button.btn { font: 600 14px/1 inherit; font-family: inherit; border-radius: 8px; padding: 10px 14px; border: 1px solid var(--line-2); background: var(--paper); color: var(--ink); cursor: pointer; }
button.btn.primary { background: var(--ink); border-color: var(--ink); color: #fff; }
button.btn:disabled { opacity: 0.45; cursor: not-allowed; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.check { display: flex; gap: 10px; align-items: flex-start; margin: 10px 0; font-size: 14px; }
.check input { margin-top: 4px; accent-color: var(--accent); }
.note { background: var(--accent-soft); border-radius: 10px; padding: 12px 14px; font-size: 13.5px; color: var(--ink-2); }
.status { font-size: 12.5px; color: var(--good); min-height: 18px; }
</style>
</head>
<body>
<main id="app"></main>
<p class="status" id="live" role="status" aria-live="polite" style="max-width:1120px;margin:0 auto;padding:0 16px"></p>
<script type="application/json" id="pack">__DATA__</script>
<script>
(function () {
  "use strict";
  var P = JSON.parse(document.getElementById("pack").textContent);
  var STORE = "salesintel-review:" + P.set_key + ":" + P.reviewer_label;
  var byId = {};
  P.items.forEach(function (i) { byId[i.id] = i; });
  var S = read() || { name: "", attested: false, started_at: "", finished_at: "", at: 0, answers: {}, seconds: {}, notes: {} };
  var shownAt = null;
  var app = document.getElementById("app");

  function read() { try { var raw = window.localStorage.getItem(STORE); return raw ? JSON.parse(raw) : null; } catch (e) { return null; } }
  function write() { try { window.localStorage.setItem(STORE, JSON.stringify(S)); } catch (e) { /* the download still works */ } }
  function say(text) { document.getElementById("live").textContent = text; }
  function done(id) { var a = S.answers[id] || {}; return P.rubric.every(function (q) { return !!a[q.key]; }); }
  function doneCount() { return P.order.filter(done).length; }
  function firstOpen() { var i = P.order.findIndex(function (id) { return !done(id); }); return i < 0 ? P.order.length : i; }
  function current() { return S.started_at && S.at < P.order.length ? P.order[S.at] : null; }
  function tick() {
    var id = current();
    if (id && shownAt) { S.seconds[id] = (S.seconds[id] || 0) + Math.round((Date.now() - shownAt) / 1000); }
    shownAt = id ? Date.now() : null;
  }
  document.addEventListener("visibilitychange", function () { if (document.hidden) { tick(); shownAt = null; write(); } else if (current()) { shownAt = Date.now(); } });

  function h(tag, attrs) {
    var el = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "on") { Object.keys(attrs.on).forEach(function (ev) { el.addEventListener(ev, attrs.on[ev]); }); }
      else if (attrs[k] === true) { el.setAttribute(k, ""); }
      else if (attrs[k] !== false && attrs[k] !== null && attrs[k] !== undefined) { el.setAttribute(k, attrs[k]); }
    });
    for (var i = 2; i < arguments.length; i++) {
      var c = arguments[i];
      if (c === null || c === undefined || c === false) continue;
      (Array.isArray(c) ? c : [c]).forEach(function (x) { el.appendChild(typeof x === "string" ? document.createTextNode(x) : x); });
    }
    return el;
  }
  function safeUrl(u) { try { var x = new URL(u); return x.protocol === "https:" || x.protocol === "http:" ? x.href : null; } catch (e) { return null; } }
  function day(d) { try { return new Date(d + "T12:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" }); } catch (e) { return d; } }
  function slug(s) { return (s || "reviewer").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "reviewer"; }

  function download() {
    tick(); write();
    var all = doneCount() === P.order.length;
    if (all && !S.finished_at) { S.finished_at = new Date().toISOString(); write(); }
    var out = { format: P.format, kind: "review", set_key: P.set_key, dataset_sha256: P.dataset_sha256,
      reviewer: { label: P.reviewer_label, name: S.name.trim() }, attested: !!S.attested, started_at: S.started_at, finished_at: all ? S.finished_at : "",
      decisions: P.order.filter(function (id) { return S.answers[id] && Object.keys(S.answers[id]).length; })
        .map(function (id) { return { item_id: id, answers: S.answers[id], seconds: S.seconds[id] || 0, note: S.notes[id] || "" }; }) };
    var blob = new Blob([JSON.stringify(out, null, 1)], { type: "application/json" });
    var a = h("a", { href: URL.createObjectURL(blob), download: "opportunity-review-" + P.set_key + "-" + slug(S.name) + ".json" });
    document.body.appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 0);
    say(all ? "Answers file downloaded. Send it to the person running the review." : "Progress file downloaded: " + doneCount() + " of " + P.order.length + " items judged.");
  }

  function load(file) {
    var r = new FileReader();
    r.onload = function () {
      try {
        var d = JSON.parse(r.result);
        if (d.dataset_sha256 !== P.dataset_sha256) { say("That file is for a different review set, so it was not loaded."); return; }
        S.name = (d.reviewer && d.reviewer.name) || S.name; S.attested = !!d.attested; S.started_at = d.started_at || new Date().toISOString();
        (d.decisions || []).forEach(function (x) { if (byId[x.item_id]) { S.answers[x.item_id] = x.answers || {}; S.seconds[x.item_id] = x.seconds || 0; S.notes[x.item_id] = x.note || ""; } });
        S.at = firstOpen(); write(); render(); say("Your saved answers were loaded.");
      } catch (e) { say("That file could not be read."); }
    };
    r.readAsText(file);
  }

  function header() {
    return h("div", { "class": "top" },
      h("div", null, h("p", { "class": "eyebrow" }, "Opportunity review · as of " + day(P.as_of)), h("h1", null, "Judge each opportunity on its evidence"),
        h("p", { "class": "muted" }, "Set " + P.set_key + " · fingerprint " + P.dataset_sha256.slice(0, 12) + (S.name ? " · " + S.name : ""))),
      h("div", null, h("p", { "class": "count" }, doneCount() + "/" + P.order.length), h("p", { "class": "muted", style: "text-align:right;margin:4px 0 8px" }, "judged"),
        h("button", { "class": "btn", type: "button", on: { click: download } }, "Download my answers")));
  }

  function start() {
    var name = h("input", { type: "text", id: "name", autocomplete: "name", value: S.name });
    var alone = h("input", { type: "checkbox", id: "alone" });
    var blind = h("input", { type: "checkbox", id: "blind" });
    var go = h("button", { "class": "btn primary", type: "submit", disabled: true }, "Start the review");
    function check() { go.disabled = !(name.value.trim().length >= 2 && alone.checked && blind.checked); }
    [name, alone, blind].forEach(function (x) { x.addEventListener("input", check); x.addEventListener("change", check); });
    var file = h("input", { type: "file", accept: "application/json,.json", id: "resume", on: { change: function (e) { if (e.target.files[0]) load(e.target.files[0]); } } });
    app.replaceChildren(h("form", { "class": "card", style: "max-width:680px", "aria-label": "Start the review",
        on: { submit: function (e) { e.preventDefault(); if (go.disabled) return; S.name = name.value.trim(); S.attested = true; S.started_at = new Date().toISOString(); S.at = firstOpen(); write(); render(); } } },
      h("p", { "class": "eyebrow" }, "Opportunity review · as of " + day(P.as_of)),
      h("h1", null, P.order.length + " opportunities to judge"),
      h("p", { "class": "muted" }, "About two minutes each. Your answers are saved in this browser as you go, and you can stop and come back."),
      h("p", { "class": "note" }, P.instructions),
      h("label", { "for": "name", style: "display:block;font-weight:600;font-size:13.5px;margin:14px 0 6px" }, "Your name"), name,
      h("label", { "class": "check", "for": "alone" }, alone, h("span", null, "I will work alone, and will not discuss any item with anyone until the review is closed.")),
      h("label", { "class": "check", "for": "blind" }, blind, h("span", null, "I will judge each item only on the evidence shown, and will not look for how the items were found.")),
      h("div", { "class": "row", style: "margin-top:14px" }, go,
        h("label", { "for": "resume", "class": "muted", style: "font-size:13px" }, "Started on another computer? Load your answers file ", file))));
    check();
  }

  function itemView() {
    var id = current(), it = byId[id], answers = Object.assign({}, S.answers[id] || {});
    var save = h("button", { "class": "btn primary", type: "submit" }, S.at === P.order.length - 1 ? "Save and finish" : "Save and next");
    function check() { save.disabled = !P.rubric.every(function (q) { return !!answers[q.key]; }); }
    var note = h("textarea", { id: "note", "aria-label": "Note (optional)" }); note.value = S.notes[id] || "";
    var form = h("form", { "class": "card", "aria-label": "Your judgement",
        on: { submit: function (e) { e.preventDefault(); if (save.disabled) return; tick(); S.answers[id] = answers; S.notes[id] = note.value; S.at = Math.min(S.at + 1, P.order.length);
          if (S.at < P.order.length && done(P.order[S.at])) S.at = firstOpen(); write(); say("Saved " + id + "."); render(); } } },
      P.rubric.map(function (q) {
        return h("fieldset", null, h("legend", null, q.question), h("div", { "class": "options" }, q.options.map(function (o) {
          var input = h("input", { type: "radio", name: q.key, value: o[0], checked: answers[q.key] === o[0],
            on: { change: function () { answers[q.key] = o[0]; check(); } } });
          return h("label", null, input, o[1]);
        })));
      }),
      h("label", { "for": "note", style: "display:block;font-weight:600;font-size:13.5px;margin:4px 0 6px" }, "Note (optional)"), note,
      h("div", { "class": "row", style: "margin-top:14px" },
        h("button", { "class": "btn", type: "button", disabled: S.at === 0, on: { click: function () { tick(); S.at = Math.max(0, S.at - 1); write(); render(); } } }, "Previous"), save),
      h("p", { "class": "muted", style: "font-size:12px;margin-top:8px" }, "Answer every question to save."));
    check();
    var facts = (it.facts || []).map(function (f) {
      var url = safeUrl(f.url);
      return h("li", null, f.text, f.date ? h("span", { "class": "mono muted" }, " · " + f.date) : null,
        url ? [" · ", h("a", { href: url, target: "_blank", rel: "noopener noreferrer" }, "source ↗")] : null,
        h("div", { "class": "basis" }, f.basis));
    });
    var card = h("article", { "class": "card", "aria-label": "Item " + id },
      h("p", null, h("span", { "class": "mono muted" }, id), " ", h("span", { "class": "pill" }, it.record_type)),
      h("h2", null, it.organisation), it.site ? h("p", { style: "margin:0" }, it.site) : null, it.location ? h("p", { "class": "muted", style: "margin:0" }, it.location) : null,
      h("p", { style: "margin-top:8px;color:var(--ink-2)" }, it.title),
      h("section", { "aria-label": "Evidence", style: "margin-top:14px;border-top:1px solid var(--line);padding-top:10px" },
        h("p", { "class": "eyebrow" }, "Evidence"), facts.length ? h("ul", { "class": "facts" }, facts) : h("p", { "class": "muted" }, "No dated evidence.")));
    var nav = h("nav", { "class": "items", "aria-label": "Items" }, P.order.map(function (x, n) {
      return h("button", { type: "button", "class": done(x) ? "done" : "", "aria-current": n === S.at ? "true" : null,
        on: { click: function () { tick(); S.at = n; write(); render(); } } }, (done(x) ? "✓ " : "") + x);
    }));
    app.replaceChildren(header(), nav, h("div", { "class": "grid" }, card, form));
    shownAt = Date.now();
  }

  function finished() {
    app.replaceChildren(header(), h("div", { "class": "card", style: "max-width:680px" },
      h("h1", null, doneCount() === P.order.length ? "All " + P.order.length + " items judged" : doneCount() + " of " + P.order.length + " items judged"),
      h("p", null, "Download your answers and send the file to the person running the review. Keep a copy until they confirm it arrived."),
      h("p", { "class": "muted" }, "You can still go back and change an answer before you send it."),
      h("div", { "class": "row" }, h("button", { "class": "btn", type: "button", on: { click: function () { S.at = 0; write(); render(); } } }, "Review my answers"),
        h("button", { "class": "btn primary", type: "button", on: { click: download } }, "Download my answers"))));
  }

  function render() { if (!S.started_at) start(); else if (S.at >= P.order.length) finished(); else itemView(); window.scrollTo(0, 0); }
  render();
})();
</script>
</body>
</html>
"""
