# PR #9: The Real Opportunity Challenge (quality gate)

Branch `feat/opportunity-quality`, stacked on PR #8 (`feat/best-opportunities`), which sits on #7 → #6 → #5 → #4 → `main`. Written on 5 November 2026.

- Nothing is merged or deployed.
- The live installation, database, collectors and launch agents were not touched. The evaluation ran on an isolated copy of a copy.
- No paid research was run.

**Release blockers, unchanged:** employer IP and ownership, data licensing, and the product name. Do not deploy or commercialise.

## Verdict in one paragraph

**The engineering is a VERIFIED PASS.** That covers the five suspected defects, plus two more found by the evaluation, the paid-research gate, and the review workflow.

**The claim that SalesIntel finds better opportunities is a NO-GO.** It is not yet proven. The blind human review is built and frozen, but no salesperson has judged it yet, and I will not stand in for them.

What the objective measures do show:
- PR #8's daily list was over half (53%) leads whose record named no service a typical installer sells. This PR removes them.
- The evidence on the list is far fresher than the renewal and keyword baselines: a median of 66 days, against 835 and 610.

**On real data, Shadow Radar contributes nothing to the daily list.** Its leads rest on one line of evidence, or are contradicted. This is reported, not tuned around.

## Phase 1: actual state

| PR | Branch | State | CI |
|---|---|---|---|
| #4 | `feat/saas-foundation` → `main` | Open | Green |
| #5 | `feat/acquisition-engine` → #4 | Open | Green |
| #6 | `feat/shadow-radar` → #5 | Open | Green |
| #7 | `feat/fluid-ui` → #6 | Open | Green |
| #8 | `feat/best-opportunities` → #7 | Open | Green (backend, frontend, Playwright) |

**Migrations:**
- Run up to `0024` before this PR.
- This PR adds `0025_blind_review`, which is additive: `si_review_decisions`, with row-level security.
- Migrate any copy before running it.

**Verdict: VERIFIED PASS.**

## Phase 2: adversarial product-correctness review

Every defect was first reproduced by a test that failed: the recorded failing run is in `docs/saas/evaluation/defects-before-fix.txt`, 7 of 7 failing. Then the smallest fix was made. Tests are in `backend/tests/test_opportunity_quality.py`.

| # | Suspected defect | Reproduced? | Smallest fix | Verdict |
|---|---|---|---|---|
| 1 | Private prospects assigned a New Site play without new-site evidence | **Yes.** Every prospect link returned `new_site`, including a leadership change and an unsourced "rumoured depot" | New site only with a **sourced, stated** signal (new site, relocation or planning application). A documented supplier problem becomes Supplier review; anything else is Account development, whose description no longer claims "added by your team" | VERIFIED PASS |
| 2 | Contact details treated as verified without proving the person–role association | **Yes, in three places.** (a) The Navigator copied the model's person name onto an email route whose own quote does not name them. (b) "Verify contact" marked a named person's address current when the page published the address without the name. (c) A named contact whose source quote does not name them still showed as "Publicly sourced" | (a) A route keeps a person's name only if its own quoted source names them, otherwise it stays a role route. (b) The official page must name the person and state the role, otherwise the result is "partial" and the contact is not upgraded. (c) Such a contact is level 4, and says why | VERIFIED PASS |
| 3 | Distinct organisations grouped on normalised names | **Yes.** A public trust and a private firm with the same name became one row | Rows merge only through a confirmed account link, or an identical published buyer name. Otherwise each lead is its own row | VERIFIED PASS |
| 4 | Lead-presented metrics recorded from API reads | **Yes.** Every `GET /best` recorded "presented" | Reads record nothing. The interface reports a lead only after its card has been at least half on screen for a second (`POST /best/seen`, validated keys, once a day). PR #8's test, which encoded the defect, was corrected | VERIFIED PASS |
| 5 | Golf-course irrigation false positive | **Yes** | `irrigation` added to the classifier's exclusions. The real capture now keeps 96 of 631 notices (was 97); the test now asserts it as noise | VERIFIED PASS |
| 6 | *Found by the evaluation:* adjacent fire work counted as "what you sell", or as "not stated" | **Yes.** "Fire risk assessment" mapped to no service, so it counted as "services not stated" and a near deadline made it "act now". "Extinguishers" and "sprinklers" never matched their codes (plural against singular), and passive fire counted as fire alarm | Adjacent work is its own service: fire risk assessment, extinguishers, passive fire protection, smoke control, with settings options. The daily list now needs a positive match to a service you sell, or an existing relationship | VERIFIED PASS |
| 7 | *Found by the evaluation:* free-text locations judged outside your territory | **Yes.** "Selby, North Yorkshire" was "outside" a territory of England, because the text does not contain "England", and tenders in Northern Ireland reached "act now" for a Great Britain profile | An English region means England; another named nation means outside; anything else is "not confirmed", never outside. Leads outside your stated territory are kept in view, not on today's list | VERIFIED PASS |

**Also verified:**
- tenant isolation of review decisions and the budget;
- provenance (quotes must be on retrieved pages);
- suppression (an opted-out contact is refused for research);
- recovery (existing lease tests);
- cost limits (below).

## Live paid research needs an approved budget, with a hard ceiling

- An administrator approves (or tops up) a **research budget** (Team → Research budget, `POST /api/si/research-budget`), between $1 and $1,000 per approval.
- The approval is written to the audit trail.
- With a live, paid provider, **every** job must reserve against that budget as well as the daily limits, in the same conditional update, so concurrent requests cannot overrun it.
- No budget gives "Live web research needs a research budget approved by an administrator". A used-up budget gives "used up". In both cases nothing is queued or charged.
- Jobs settle to their measured cost.
- Replayed (simulated) research never needs a budget.
- Tested: refusal, administrator-only approval, the audit record, the ceiling holding against a second reservation, and settlement.
- The 8041 test instance, which uses your real Anthropic key, now refuses any live research until a budget is approved there.

**Verdict: VERIFIED PASS.**

## Phase 3: blinded evaluation

### Protocol

Fixed in `backend/app/intelligence/opportunity_review.py` before sampling:

- **Date:** as of 5 November 2026. Only evidence published by then is used; 3 later-dated items were dropped and counted.
- **Reference profile:** one for every arm, a UK installer of fire alarms, access control, CCTV, intruder and emergency lighting, in England, Scotland and Wales.
- **Arms**, each sampled with seed `20261105`:

| Arm | What it is | Pool | Sampled |
|---|---|---:|---:|
| SalesIntel (this PR) | The focused daily list | 33 | 11 (6 public, 5 private; no Shadow Radar lead qualified) |
| SalesIntel (PR #8 rules) | The same list, built with PR #8's mapping and no service match required | 74 | 11 |
| Renewal dates | Published contract ends within 120 days | 41 | 12 |
| Keywords | Titles naming a fire or security system | 400 | 12 |

- **Blinding:**
  - Reviewers see neutral evidence only: organisation, site, title, kind of source, summary, dated evidence with links, services mentioned.
  - They never see the arm, rank, tier, reasons, fit or next action. The protocol (arms, windows, sizes, seed) is in a sealed key that is not served, and a test checks exactly which fields are served.
  - Each reviewer's decisions are stored separately, and a reviewer starts with no one else's answers.
  - Results unblind the arms, so they are for administrators only, after reviewers finish.
- **Rubric** (9 questions):
  - genuine fire or security relevance;
  - correct organisation and site;
  - requirement confirmed or hypothesised;
  - already advertised;
  - a legitimate reason to contact;
  - who to speak to;
  - a reliable route;
  - evidence strength and freshness;
  - worth pursuing (this week, this month, later, no);
  - plus minutes spent, and a note.
- **Agreement:** percent agreement and Cohen's kappa on relevance, with disagreements listed.
- **Missed opportunities:** items judged relevant that SalesIntel's list did not contain.
- **The AI that produced the leads judges nothing.**
- **Dataset:**
  - `backend/reference_data/evaluation/opportunities-2026-11-05.json`: 37 blinded items, served to reviewers.
  - `opportunities-2026-11-05.key.json`: sealed.
  - Reproducible with `backend/scripts/build_review_set.py` on an isolated copy.
  - Named individuals are removed (counts only) and no contact details are included; a test checks this.
  - Public records are Open Government Licence. Company research appears as short summaries, titles and source links, not page text.

### Results so far

**Adjudicated:** not yet, with **0 of 37 items judged by humans**. Precision, actionable yield, reason to contact, identity and route availability are all pending. **No improvement is claimed.**

**Objective measures** (facts from the records, over each whole pool):

| | SalesIntel (this PR) | SalesIntel (PR #8 rules) | Renewal | Keywords |
|---|---:|---:|---:|---:|
| Names a service the reference installer sells | 100%¹ | 47% | 34% | 70% |
| Adjacent or unidentified service | 0%¹ | **53%** | 66% | 30% |
| Already advertised (open tender) | 45% | 42% | 0% | 12% |
| Median evidence age (days) | **66** | 140 | 835 | 610 |
| Sources represented | public 28, private 5 | public 69, private 5 | public 41 | public 337, Shadow Radar 57, private 6 |

¹ By construction of the new rule. This shows the rule is applied, not that relevance improved: the human review decides that, including whether the rule now drops good leads.

**Within the samples, a business route is on record for:**
- SalesIntel: 7 of 11 (all public notices give an official route; 1 of 5 private leads has one).
- Renewal: 12 of 12.
- Keywords: 9 of 12.

**Verdict:**
- The evaluation framework, dataset and blinding are a **VERIFIED PASS**.
- Proof of improvement is a **NO-GO**, pending human judgement.

## Phase 4: improvements to the acquisition experience

- **Best opportunities is a focused day:**
  - only "act now" and "this week" leads (up to 10);
  - each needs a positive service match or an existing relationship;
  - everything else is counted ("N more kept in view in Discover"), not listed;
  - on a quiet day, at most 3 in-view leads are shown, labelled as such.
- **One specific next step**, built from the lead's own evidence and your stated capabilities:

| Lead | Next step |
|---|---|
| Tender | The deadline date, mandatory requirements against your stated accreditations, questions only through the buyer's portal |
| Renewal | The named supplier and end date; ask how they will replace it |
| Leadership change | Introduce yourself to the new leader |
| New site | Who will specify and maintain fire and security |
| Published finding | Who is accountable, and by when |
| Overdue promise or stated requirement | Comes first |

  It is deterministic, not model-written.
- **Deep investigation** without a Shadow Radar hypothesis now tests the account's own evidence: the named contract and incumbent, the tender's scope, or the specific private signal. Each claim gets a confirm question and a challenge question.
- **Resolve this gap:** contract end added to the new-site and develop plays (could the incumbent absorb the new site?), and site operator added to expansion. With the existing role search, the current supplier, contract end, site operator and decision-maker are each one click.
- **Buying committee:** fixes 2a–2c above mean a verified-looking contact must be tied to its person by its source.

**Verdict: VERIFIED PASS (tested); usefulness CONDITIONAL on the human review.**

## Phase 5: showcase from real public evidence

**Source:** `docs/saas/evaluation/SHOWCASE.md`, generated by `backend/scripts/build_showcase.py`.

**Selection rule, fixed before looking:** the top lead of each source type on the daily list for the reference profile.

- **Public:**
  - Ipswich Borough Council, "Door Entry Systems – Service Maintenance": a Find a Tender notice with a deadline of 9 November 2026.
  - It shows why it was discovered, the evidence, the play (Public tender), what would disprove it, the unknowns (current supplier, scope), the stakeholders to find, the official route (the buyer's portal) and the next step.
- **Private:**
  - Campeys of Selby: a 190,527 sq ft warehouse opened at Sherburn 42, from company and trade announcements.
  - Play: New site (a sourced, stated new-site signal).
  - Next step: ask who will specify and maintain its fire and security.
  - Bespoke Property Management (a new Head of Facilities) was the top private lead before fix 7. Once Yorkshire counted as England it ranks lower, and it now gets Account development, not New site (fix 1).
- **Shadow Radar: none.**
  - 95 active leads, made up of 61 on one line of evidence, 32 contradicted by later evidence, and 2 now advertised (shown as public leads instead).
  - **Causes:** the adjacent-works source gives one record per project; three sensors still need sources (Companies House key, merger register, funding recipients); the planning data has no national coverage.

**Not shown:** deep research and contact discovery for these leads. They need an approved research budget, by design.

**Verdict: CONDITIONAL PASS.** Real, explained and replayable, but only two of three sources produced a lead, and none is yet judged worth pursuing by a salesperson.

## Phase 6: quality and ROI scorecard

| Measure | Status |
|---|---|
| Independently adjudicated precision | **Pending:** 0 of 37 judged |
| Actionable lead yield (worth pursuing this week or month) | **Pending** |
| Contact-route coverage (objective, sampled) | SalesIntel 7 of 11, renewal 12 of 12, keywords 9 of 12 |
| Research cost | **$0** spent for this PR. Live research is gated by an approved budget; replay costs are simulated and not reported as spend |
| Share of discoveries leading to a meaningful sales action | **Not measurable yet.** Exposure is now recorded honestly (on screen), and the Results view counts accounts reaching outreach, meetings, requirements and deals. It needs pilot users |

### Prospective outcome tracking (design)

Ready to run with consenting pilot salespeople:

**Who and how long:**
- 3 to 6 salespeople, each consenting in writing.
- 8 weeks, each using their own territory and profile.

**Before starting:**
- An administrator approves a research budget with a written purpose, for example $50 for 8 weeks, which the server enforces.
- Each salesperson completes the blind review (37 items, about 2 minutes each) **before** using the product, so judgements are not anchored on SalesIntel's reasons.

**What is recorded automatically** (no message content and no personal data beyond the contact routes salespeople choose to save):
- leads actually seen;
- leads opened;
- investigations;
- gaps resolved;
- contacts found or verified;
- outreach;
- responses and meetings;
- requirements confirmed;
- deals, with stage, won or lost, and value with its basis.

**Weekly check:** each salesperson marks every account they opened that week as relevant, not relevant (with a reason), or already known. This is the existing feedback model.

**Measures:**
- **Precision:** opened accounts judged relevant.
- **Actionable yield:** accounts reaching outreach within 14 days.
- **Conversation rate.**
- **Meetings and requirements per 10 leads seen.**
- **Cost:** per researched account, per usable verified contact, and per qualified opportunity.
- **Time** to first meaningful action.
- **Repeat weekly use.**

All measures are compared with a renewal-date and keyword list each salesperson sees side by side for 2 of the 8 weeks.

**Rules:**
- No outcome is entered on anyone's behalf.
- Nothing is reported until it happened.
- Intervals are always shown.
- Any claim of improvement needs intervals that separate.

**Verdict: CONDITIONAL.** Machinery ready; no pilot run.

## Engineering acceptance (local, final run)

- **Backend:** 615 passed, 1 skipped (the RLS test on SQLite), on SQLite and on PostgreSQL with row-level security as an ordinary role. New:
  - `test_opportunity_quality.py`: defects 1–6, the budget gate, focus, next actions, evidence questions;
  - `test_blind_review.py`: blinding, per-reviewer storage, administrator-only results, kappa and Wilson intervals, the frozen-set protocol, no personal data.
- **Frontend:** 35 unit tests and TypeScript pass.
- **Browser (hosted):** 12 of 12, including the new blind review and budget journey.
- **Browser (local):** 60 passed, 1 skipped (unchanged), with axe WCAG 2.1 AA scans.
- **Screenshots** of the running application:
  - 10–14: the hosted journeys, regenerated;
  - 15: the blind review;
  - 16: **the daily list on the real captured data** for the reference installer (10 leads: 8 act now, 2 this week, 286 kept in view);
  - 17: the research budget, with none approved.

## Known limitations found while reviewing the real-data list

- **Service names in plural or combined forms are under-detected.** Examples: "Access Controls", and "Fire & Intruder Alarms", which reads only as intruder. The patterns are shared with Renewal Radar, so they were not changed here. This can cause missed leads, not false ones; the blind review's "missed opportunities" measure will show how often.
- **Fixed in this PR:** an early market notice's expected tender date was described as a "deadline". The reason now says which date it is.
- **The list is mostly public tenders for a profile with no private research of its own.** Private leads appear only where a workspace has run company research.

## Next product phase

**The AI Win Room:** analysing real tender packs, specifications, commercial schedules and evaluation criteria, with page and clause references, to tell a bid team exactly what is required to compete. It should start **after** this quality gate has human judgements, so it builds on an acquisition engine proven to find leads worth bidding for.
