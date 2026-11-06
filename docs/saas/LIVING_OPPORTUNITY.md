# The Living Opportunity: one brief, one next move

Branch `feat/living-opportunity`, stacked on #11 (`feat/contract-atlas`) → #10 → #9 → … → `main`. Written on 6 November 2026.

- Nothing is merged or deployed. The live app, the live database and the collectors were not touched.
- No paid research was used: local tests run in demo mode (research refused), hosted tests replay research offline.
- Screenshots use fictional records only (`backend/app/services/living_fixtures.py`: Fernhill Parcels, Ashby Vale Council).

**Release blockers, unchanged:** employer IP and ownership, data licensing, and the product name. Do not deploy or commercialise.

## What changed for a salesperson

Every lead and every account now opens as a **Living Opportunity**: one brief, built from the records, that answers in order:

1. **What happened.** The strongest sourced fact as the headline, with its date, its basis (stated, published, inferred) and its source.
2. **Why it could matter.** The interpretation, with any rule of thumb labelled *Rule of thumb, not a fact*.
3. **What could be sold.** Services a source names (ticked) kept apart from services that are only possible (dashed).
4. **What could make it irrelevant.** Contrary evidence first, in red, then the standard ways this kind of opportunity falls away. A deep investigation that weakened the case is the first line.
5. **What to find out next.** The one question that could change the decision, why, and whether it has been answered.

Below the reveal:

- **Questions that decide it.** Ranked by what they could change (decisive, timing, access), each with its status: open, researching, answered, *answer is old: check again* (after four months), *not published: ask the customer*, *sources disagree*, or *research did not run* (it stays open). Each has a working action: research it (with its cost), or record the customer's answer.
- **Evidence, newest first.** Every dated item says what kind of date it is (reported, published, event, expected, first seen, researched, recorded), whether it supports or weakens the case (in words and an icon, not colour alone), and, when opened, what it establishes and **what it does not establish**. Items new since you last looked are marked.
- **Who is involved.** Only people and firms a source or your team recorded: a main contractor a source names, people named in research, contacts on the account. Someone who asked not to be contacted is never offered as a route and is marked as such. Then what is still unknown.
- **Path to a deal.** Steps that fit the kind of opportunity (a private signal, a published tender, a contract ending, a competitor's contract, a Shadow Radar hypothesis, an existing customer's expansion). A step is ticked only from what is recorded.
- **The story so far.** Built only from recorded events: the account opening, research, contacts, drafts, conversations and deals, in order.

### The Action Dock

One recommended move, decided once and the same wherever it appears (Discover, the account page, and the account record's `next_step` in the API), with:

- why it is recommended, what it produces, and its cost if it uses research;
- the move that would come first but cannot run here, with the reason (for example, web research switched off in demo mode, or no approved research budget, with a link to the budget page in the local app);
- up to three alternatives, and *Save as an account* for a lead that is not saved yet.

The moves are real actions, not links to elsewhere: research a question (gap research, inside the budget), find the right people (Contact Navigator), prepare an introduction (a draft built from the evidence, opened in Engage; nothing is sent), log a conversation, close a follow-up you set, set the next follow-up, qualify into a deal (the requirement the customer stated is carried into the form), and run a deep investigation. Acting on a lead that is not an account yet saves it first.

The order is a fixed rule, not a model's opinion:

1. Qualify, once the customer has stated a requirement.
2. *Decide bid or no bid*, for a published tender once its decisive question has been looked at.
3. A follow-up your team set itself.
4. Research the top open question.
5. Find the right people, if nobody who decides is named.
6. Prepare an introduction, if none is drafted.
7. Log the first contact, or set the next follow-up.
8. Save as an account; record what the customer said; run a deep investigation.

The first move that can run here is the recommendation.

### Discover, Accounts and Today

- **Discover** is a three-panel cockpit: the list, the brief, and the Action Dock. On a narrower screen the dock moves under the reveal, so *what happened* is always read first. The lead's original record (the six questions, or the Shadow Radar card) is kept one click away under *Source record*. Web research runs are summarised in one compact strip.
- **Accounts** open on the same brief and dock. The empty 26-week engagement strip and the nine-step play stepper are gone. *Qualify into a deal* is still available at any time from the account header. Every panel below is unchanged.
- **Today** opens with an intelligence briefing in five parts: *Discovered*, *Changed* (accounts with new evidence or activity since you last reviewed them), *Needs action*, *Could move revenue* (open deals, largest recorded value first; no forecast) and *Worth watching*. It no longer says "Nothing is waiting on you" when new leads were found.

## API and data

- `GET /api/si/brief/{key}` returns the brief for a lead key (`pr:`, `mo:`, `sh:`, `mc:`) or an account (`acct:<id>`). A lead that already has an account opens as that account, so research and conversations are never split.
- `POST /api/si/brief/{key}/reviewed` records that you read it. The browser records this when you move on after reading for more than a moment, so *new since you last looked* stays true while you read.
- `GET /api/si/brief/digest` feeds Today's *Changed* and *Worth watching* from the same briefs.
- Migration `0028_brief_reviews` adds one table, `si_brief_reviews` (workspace-scoped, row-level security on PostgreSQL). Nothing else in the schema changes.
- Gap research accepts the brief's question kinds (`need`, `package_status`, `eligibility`, `route`, `relationship_status`, `hypothesis_test`). They are researched like any free question: answers must be quoted from a retrieved page.
- Everything in the brief is computed by rules from stored records (`backend/app/services/brief.py`). No model writes any part of it.

## Acceptance tests

| Test | Evidence | Result |
| --- | --- | --- |
| A. 15-second reveal, judged by an independent salesperson | Not run. Needs real people; browser automation cannot show comprehension. | **Not done** |
| B. The user's own logistics prospect | Checked on a private copy of the live database (not in this repository). Reveal: the sourced £330m depot programme (June 2025), all services *possible*, the weakened investigation first among reasons it could be irrelevant, key question *have the packages been awarded and who controls them*. Nothing asserts procurement is open. | Pass (machine check) |
| C. Public tender | Ashby Vale (fictional): buyer, scope, deadline in words, named services, eligibility as the decisive question, source, *Decide bid or no bid* on the path. `living-opportunity.spec.ts`, `test_living_opportunity.py` | Pass |
| D. Private prospect | Fernhill (fictional): evidence reviewed, account saved from the dock, introduction drafted from the evidence, conversation logged, requirement carried into the deal. Stated and inferred stay apart throughout. | Pass |
| E. Continuity | Reload and a backend restart (a new process on the same database) give the same next move, story and *new since last review*. | Pass |
| F. No false intelligence | Contrary evidence leads; stale evidence flagged unless a sourced date is still ahead; injected text shown as what the page said; a search that did not run is never *not found*; not-found stays not found; old answers ask to be checked again; same-name links stay *unconfirmed*. | Pass (tests) |
| G. Security and commercial integrity | Briefs are per workspace (404 across workspaces, hosted test with two companies); suppressed contacts excluded; research blocked without a budget, with the reason; idempotency keys on research, people search, investigation and deal creation; nothing sent automatically. | Pass |
| H. Responsive and accessible | Desktop, tablet (820 px) and phone (390 px) with no sideways scrolling; axe WCAG 2.1 AA scans of Today, Discover with a brief open, the account page and the phone sheet; keyboard (j/k, focusable dock actions); reduced motion. | Pass (automated) |

## Measurements

Machine-measured on fictional records (`docs/saas/living/ux-measurements.json` and `before-after/before-measurements.json`). These are interaction counts and machine timings, not human evidence.

| | Before (`feat/contract-atlas`) | After |
| --- | --- | --- |
| Lead chosen → its summary on screen | under 0.1 s | 0.1 s (one extra request) |
| On first view: what happened | Yes | Yes |
| On first view: contrary evidence marked as against | No (listed as a plain fact) | Yes |
| On first view: named vs possible services | No | Yes |
| On first view: rules of thumb labelled | No | Yes |
| On first view: the key question | No | Yes |
| Lead → qualified deal | 6 clicks, 2 page changes | 6 clicks, 1 page change |
| Requirement retyped into the deal form | Yes | No (carried over) |
| Targeted research from a lead | Open the account, find the gap | 2 interactions (hosted replay test) |

The provisional targets in the brief are met by these machine checks, except the human one: *understand relevance within 10 seconds* needs Test A.

## Screenshots

Fictional records, local demo mode.

- After: `screenshots/23-living-discover-desktop.png`, `24-living-account-desktop.png`, `25-living-today-desktop.png`, `26-living-discover-mobile.png`.
- Before (the base branch, same records): `living/before-after/before-discover-desktop.png`, `before-account-desktop.png`, `before-today-desktop.png`, `before-discover-mobile.png`.
- The single-user shell shows the workspace's name in the sidebar; it is masked in every screenshot.

## Preserved

- Every account panel: sources, what we know, what needs confirming, suppliers (Contract Atlas), investigation, missing information, buying committee, people finder, interaction log, history, follow-ups, contacts, sites, deals and identity.
- Discover filters, saved views, keyboard navigation, the Runway layout, the Contract Atlas mode, Watch/Dismiss/Restore, web research and its durability.
- The original lead record (six questions, Shadow Radar card with its own investigation and *not relevant* controls) under *Source record*.
- Research budgets and ceilings, spend refusals, idempotency, tenant isolation and row-level security, contact suppression, source attribution, and *no AI win probability*.

## Limitations and unfinished work

- **No human testing.** Test A is not done, and no claim is made that people understand opportunities faster.
- **Win Path and the Win Room are not built.** After *Qualify*, the deal page is unchanged. Tender document analysis is not connected to the brief.
- **Relationships are a list, not a graph,** and come only from what sources name; most private records name no supplier.
- **Rules, not learning.** The next-move order and question ranking are fixed rules. They have not been tuned against outcomes and should not be until the frozen blind review is complete.
- **The single-user (local) app keeps its own indigo look;** the porcelain and graphite identity applies in the hosted product. The new screens take whichever identity they sit in.
- **"Changed" on Today** covers the 40 most recently updated accounts you have reviewed before, or watch.
- The brief is computed on every request; there is no caching yet.
