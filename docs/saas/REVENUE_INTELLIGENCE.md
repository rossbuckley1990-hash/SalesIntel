# Revenue Intelligence: Best Opportunities, Research on Demand, Buying Committee, Guided Plays, Results

Branch `feat/best-opportunities`, stacked on PR #7 (`feat/fluid-ui`), which sits on #6 → #5 → #4 → `main`. Written on 5 November 2026.

- Nothing is merged or deployed.
- The live database, collectors and launch agents were not touched. The 8041 test instance runs on its own copy (backed up before migration `0024`).
- No paid research was run for this work. Every research path was exercised on deterministic replay.

**Release blockers, unchanged:**
- Employer IP and ownership are unresolved.
- Data licensing for contact enrichment is unresolved.
- The product name is unresolved.
- The repository is public.

Rebranding does not resolve ownership. Do not commercialise or deploy.

## Repository state found

| PR | Branch | State | CI at last check |
|---|---|---|---|
| #4 | `feat/saas-foundation` → `main` | Open | Green |
| #5 | `feat/acquisition-engine` → #4 | Open | Green |
| #6 | `feat/shadow-radar` → #5 | Open | Green |
| #7 | `feat/fluid-ui` → #6 | Open | Backend and frontend green; Playwright was running at branch time |

`main` is at `897aaaf`. Migrations ran up to `0023`; this branch adds `0024`. The correct base for new work is #7's head (`ded1034`), because it carries the current interface.

## Benchmark: SalesIntel.io (public pages, 5 November 2026)

Almost everything published is vendor marketing. Examples: "95% accuracy", a "90-day refresh", "2,000+ researchers", "30+ signal categories", "800M+ false positives suppressed". No methodology, samples or independent audits are linked.

- Customer ROI figures (for example a 13% versus 15% win-rate lift for the same customer on two pages) have no baselines.
- G2 (4.3/5, 540 reviews) is the only independent signal found, and it has no detailed critique.

We took principles, not data, designs or copy:

| Their capability (as described) | What we built, originally, for fire and security |
|---|---|
| RepIntel: one ranked daily queue with the trigger inline | **Best opportunities** on Today: tiered, with reasons, no score |
| ICPIntel: lookalikes from closed-won, per-dimension fit | **Customer profile**: stated rules, plus patterns from this workspace's own wins once there are 5. Labelled as correlation, never shared across workspaces |
| Contact confidence and Research on Demand (human-verified, "one click") | **Contact confidence ladder** (6 levels, with freshness), and **Resolve this gap**: scoped, sourced research with honest outcomes. We have no human research team, and we say so |
| Buying committee mapping | **Buying committee** per play (new site, renewal, tender, expansion, supplier review), each person seated once |
| GTMCanvas / ProspectConnect (signal-triggered plays and sequences) | **Guided plays**: steps read from what was recorded. No sequences, no automatic sending, and no workflow editor (by mandate) |
| Revenue attribution (method undescribed) | **Acquisition-to-revenue events** with origin fixed at write time, and a Results view that states it shows order, not causation |

## What was built (vertical slices)

### B. My best opportunities — VERIFIED PASS (functional), CONDITIONAL (usefulness)

**Built:**
- `backend/app/services/best.py`: `opportunities()`, `profile()` and `results()`.
- `GET /api/si/best` and `GET /api/si/icp`.
- The "Your best opportunities" section on Today (`si-intel.tsx`, `BestOpportunities`).

**How it works:**
- Every lead from public procurement, private research and Shadow Radar is grouped to one row per organisation (account, or name key).
- Each row is placed in a tier: **act now**, **worth your time this week** or **keep in view**.
- **Act now** means one of:
  - a published deadline within 21 days;
  - a requirement the customer stated with no deal yet;
  - an overdue commitment.
- **This week** means one of:
  - a tender 22–60 days out;
  - a reported contract end within 120 days;
  - a corroborated or now-advertised Shadow Radar lead whose window is open;
  - an existing customer with a new signal;
  - private research saying "engage now".
- Within a tier the order is: published before inferred, then better fit to your profile, then existing relationships, then the soonest date.
- Every promoted row lists its reasons. Inferred leads carry a caution that they are a reason to investigate, not proof of a requirement.
- Leads for services you don't sell, and unverified candidates, are set aside and counted.

**Never used to rank:** signal count, report length, or any probability or score. The list contains no percentage, and a test checks this.

**Each card answers:**
- **Who:** organisation and site.
- **Why this customer:** fit to your stated profile.
- **Why now:** with its basis, published or inferred.
- **What we know:** sourced facts.
- **What we don't know.**
- **Who to speak to.**
- **What next:** one action.

The detail sits behind one disclosure; the first view stays short.

**On the real captured data** (8041 test copy, profile fire alarm, access control and CCTV, England, sectors health and housing):
- 337 organisations ranked: **18 act now, 47 this week, 272 in view**, with 47 set aside (39 services not sold, 8 unverified).
- The first version put 203 in "this week". Two rules were too loose: contract ends up to 12 months ahead, and single-evidence Shadow Radar windows. Both were tightened.

**Conditional:** the order is transparent but not validated against outcomes. The evaluation baseline stands: Shadow Radar was not shown to beat renewal dates or keywords. Nothing here claims otherwise.

### C. Research on demand ("Resolve this gap") — VERIFIED PASS

**Built:**
- Model `GapRequest` (`si_gap_requests`, tenant-scoped, row-level security on PostgreSQL), migration `0024`.
- `backend/app/services/gaps.py`.
- Job kind `gap_research`, which reserves $1.20 through the existing spend and lease machinery.
- `POST /api/si/accounts/{id}/gaps` and `GET /api/si/gaps/{id}`.
- The "Missing information" panel on the account.

**Questions it answers:**
- Find a role.
- Verify a contact.
- Current incumbent.
- Contract end.
- Site operator.
- Award notice.
- Evaluation criteria.
- Site status.

**Answers come only from quotes on retrieved pages**, checked with the investigator's validator. That rejects quotes not on the page, sources that were not actually retrieved, excluded aggregators and pages that try to instruct the AI.

| Outcome | When |
|---|---|
| Resolved with evidence | The organisation's own or an official page answers it |
| Partly resolved | Only a third party says it, or only a role route was found |
| Sources disagree | Different answers; both shown, neither chosen |
| Not found | It stays unknown: "nothing was guessed" |
| Research unavailable here | No provider: nothing searched, nothing charged |
| Needs a person to confirm | For example, new routes that match no role |

**Contact verification** marks a detail as current only if it is published on an official page. It records where and when, and does not change the user's own "verified" status. A naming-pattern guess or a deliverable inbox is never treated as proof.

**Requests:**
- Repeat clicks return the same request; "Ask again" re-asks.
- Opted-out contacts are refused.
- Jobs recover after a worker dies (existing lease tests).
- A failed or cancelled job shows as "Did not complete".

### D. Contact confidence and buying committee — VERIFIED PASS (on existing sources), CONDITIONAL (coverage)

**Built:** `backend/app/services/committee.py`.

**Six levels, with freshness** (fresh up to 90 days, ageing, stale after 365 days or when flagged):
1. Recently re-verified.
2. Provider-verified.
3. Publicly sourced.
4. Unverified possible contact.
5. Role known, no named person.
6. No usable route.

Opted-out contacts are shown as "Do not contact" and are never usable.

**Committees follow the play:**
- **New site:** estates, facilities, fire safety, main contractor's package manager, procurement.
- **Renewal:** procurement, contract manager, facilities, finance.
- **Tender, expansion and supplier review:** templates of their own.

Each person is seated **once**, by their own title. A first version counted one Director of Estates and Facilities as procurement and facilities too, which is now fixed and tested. A missing role offers **Find this person**, a `find_role` gap request.

**Conditional:**
- Contacts still come only from the existing Contact Navigator: official pages, published notices and saved research.
- Hunter and Apollo were assessed only as possible licensed providers. They are **not integrated**: no terms, credentials or authority. The provider-independent `EnrichmentProvider` interface (from #5) remains the integration point, so the "Provider-verified" level is unused today.

### E. Guided revenue plays — VERIFIED PASS for Play 1 (New site); CONDITIONAL for plays 2–5

**Built:** `backend/app/services/plays.py`, `GET /api/si/accounts/{id}/play`, and the Play panel on the account.

**Which play an account gets** comes from its evidence:

| Evidence | Play |
|---|---|
| Shadow Radar sensor | New site, or supplier review |
| Public category | Tender, or renewal |
| Private research | New site |
| Existing customer | Expansion |
| No evidence | **Account development**. It is never assumed to be a new site or a tender, and this is tested |

**Each play has:**
- a trigger and its evidence;
- a commercial hypothesis;
- the investigation;
- stakeholders and gaps;
- next actions;
- qualification criteria;
- outcome tracking.

**Steps:** evidence, investigate, people, missing information, approach, contact, follow-up, requirement, qualify.

- Each step's state is read from records (dossier, contacts, gap requests, drafts, activities, tasks, deals), never ticked by hand.
- **What next** puts qualification first as soon as a requirement is confirmed, then the selling steps in order.
- Missing information supports the play but never blocks it.

**Play 1 is accepted end to end in the browser (Scenario A).** Plays 2–5 have detection, templates, gaps and steps, and are covered by backend tests for expansion and account development. They have no browser acceptance of their own yet.

### F. Results and attribution — VERIFIED PASS (event model), CONDITIONAL (no live outcomes yet); Win Room — NO-GO (not started)

**The event model** extends the existing `si_funnel_events` table rather than adding a second model. It adds: time, account, deal, a reference, `origin` (the discovery record the account came from, fixed when the event is written), source type, and the won amount with its basis.

**Events now recorded:**

| Area | Events |
|---|---|
| Lead | Presented (once a day per lead), opened |
| Research | Investigation started, contacts found, contact verified, gap requested or resolved |
| Engagement | Introduction prepared, outreach recorded, customer response, meeting booked, requirement confirmed, follow-up |
| Deal | Created (qualified), every stage, won (amount and basis) or lost |

**Deals → "Results from discovery"** shows, by Shadow Radar, public, private or added by hand:
- accounts reaching each step;
- research spend;
- cost per researched account, per account with contacts and per qualified deal;
- days to first outreach;
- won value by basis (total contract value or annual, never mixed).

It states that order is not causation.

**Conditional:**
- There are no real outcomes yet.
- Earlier events (before `0024`) are unattributed.
- Gross margin is still not recorded on deals.

**Win Room:** document analysis (ITT, RFQ, specifications, evaluation criteria) is **not started**. The integration path is the deal record and the play's qualification criteria. Per the mandate it did not delay the acquisition slice.

## Acceptance scenarios

| Scenario | Evidence | Verdict |
|---|---|---|
| **A. Undiscovered private or unadvertised customer** (Harbourside Community Health, synthetic, discovered from two independent published works records; replayed research) | `e2e-hosted/best-opportunities.spec.ts`. On Today's list with reasons and an "inferred" caution; investigated; evidence against itself shown; Morgan Reid as a publicly sourced route; incumbent resolved from the board papers with the injected page refused; site operator "Not found"; introduction prepared; requirement logged; play moves to qualify; deal created; Results shows it; everything persists across reload | **VERIFIED PASS** (replay) |
| **B. Public procurement** | The existing `e2e-hosted/acquisition.spec.ts` (notice captured, official procurement route, grounded introduction, follow-up, deal), plus the new Tender and Renewal play detection and gaps in the backend | **CONDITIONAL PASS**: no document analysis (Win Room), and no browser test of the tender play itself |
| **C. Existing customer expansion** | `test_an_existing_customer_s_new_site_is_one_account_and_an_expansion_play`. The event links to the existing customer (no duplicate account), the list shows "Existing customer with a new signal", and the play is Estate expansion | **VERIFIED PASS** (backend); not yet in the browser |

**Adversarial controls covered** (new tests plus the existing suite):
- duplicated and syndicated sources (independence by origin);
- an injected page;
- an unquotable claim;
- a contradictory contract end ("Sources disagree");
- not found stays unknown;
- no provider ("Research unavailable", no cost);
- an opted-out contact refused;
- repeated clicks (idempotent);
- a job interrupted by restart (lease recovery);
- spend limits (429, nothing charged);
- cross-tenant access to gap requests and plays (404, plus row-level security);
- inferred leads never shown as confirmed;
- future information kept out of historical evaluation (existing time-safety tests);
- one person never seated twice.

## Measured user journey (automated browser, replayed research, this Mac)

| Step | Seconds | Clicks |
|---|---:|---:|
| Understand why the lead matters | 0.7 | 0 |
| Start an investigation | 2.5 | 2 |
| Review the critical findings | 4.4 | 2 |
| Identify a usable contact route | 4.4 | 2 |
| Prepare first contact | 9.0 | 5 |
| Set the next commercial action | 9.6 | 7 |
| Return next morning and continue | 0.4 | 0 |

Source: `docs/saas/ux-timings.json`.

**How to read these numbers:**
- They are machine timings, with replayed research that returns instantly.
- A live investigation took about 2 minutes on 5 November (#6).
- Typing time is excluded.
- They show the interaction count is low. They are **not** human usability results, and there is no comparison against the earlier build.

**Cost:**
- The replay meter reports simulated costs ($0.17 per gap question, $0.38 per investigation). These are not real spend.
- The only live measurement remains the #6 investigation at **$1.29**.
- The gap research reservation is $1.20.

## Source quality and false positives found

- The existing works classifier lets through "Refurbishment of the Irrigation System at Mowsbury Golf Course" (Bedford). It is not building works with fire or security scope. This is consistent with the 87% held-out precision in #6, and it now appears on the daily list as "keep in view".
- The buying committee double-counted one person across roles. Fixed.
- The unlinked-account play asserted a new building. Fixed.
- Both of the first two prioritisation rules were too loose. Tightened.
- On a phone, the account page scrolled sideways. Screen-reader-only step labels had no positioned ancestor, so labels for steps scrolled off-screen widened the page. Fixed, and the phone test now opens an account and checks its width.

## Testing (local)

- **Backend:** 587 passed, 1 skipped (the RLS test on SQLite), on SQLite and on PostgreSQL with row-level security as an ordinary role. New: `test_best_opportunities.py` (8 tests), plus the schema test for `si_gap_requests`.
- **Frontend:** 35 unit tests and TypeScript pass.
- **Browser, hosted:** 11 of 11 pass, including the two new journeys (Scenario A desktop, and the list and an account on a phone).
- **Browser, local:** 60 passed, 1 skipped (unchanged). The axe WCAG 2.1 AA scans of all five workspaces are included.
- **Screenshots** from the running app: `docs/saas/screenshots/10, 11, 13 and 14`.

## Not done, or not verified

- **Win Room** document analysis (not started).
- **Plays 2–5** browser acceptance.
- **Scenario B** tender play and documents, and **Scenario C** in the browser.
- **Learned customer profile** with real wins (needs 5 in a workspace).
- **Licensed enrichment** (Hunter or Apollo).
- **Human research on demand.**
- **A live, bounded and authorised paid evaluation** of gap research quality and cost.
- **Measuring commercial relevance** (presented → opened is now recorded; judgements need real users).
- **Gross margin on deals.**
- **The ownership, licensing and naming blockers** above.
