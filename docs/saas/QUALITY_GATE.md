# PR #9: The Real Opportunity Challenge (quality gate)

Branch `feat/opportunity-quality`, stacked on PR #8 (`feat/best-opportunities`), which sits on #7 → #6 → #5 → #4 → `main`. Written on 5 November 2026, with the evaluation-integrity corrections added the same day.

- Nothing is merged or deployed.
- The live installation, database, collectors and launch agents were not touched. The evaluation was built from an isolated copy of a copy.
- No paid research was run.

**Release blockers, unchanged:** employer IP and ownership, data licensing, and the product name. Do not deploy or commercialise.

## Verdict in one paragraph

**The engineering is a VERIFIED PASS.** It covers:
- the five suspected defects, and two more found by the first evaluation;
- the paid-research budget gate;
- the evaluation-integrity corrections below, each with a test that failed first;
- the separation of qualified and exploratory discovery.

**The evaluation method is now independently defensible.**
- The key is sealed outside the repository, under a published commitment.
- Every item needs two independent reviews, and every disagreement an adjudication.
- The server refuses to unblind before the review is complete, locked and the key verified.
- Reviewers see only source records.
- Every method is a random sample of its own list, with conservative intervals.

**The claim that SalesIntel finds better opportunities is still a NO-GO.** The new frozen set has 44 items and none has been judged. Two salespeople need to complete it, and I will not stand in for them.

**Exploratory private-sector discovery is no longer hidden.**
- Credible changes that never mention fire or security now have their own labelled list, separate from the qualified list.
- Whether they are worth a salesperson's time is one of the things the review measures.

## Evaluation integrity corrections

Each was first reproduced by a test that failed. The recorded run is `docs/saas/evaluation/integrity-before-fix.txt`: 15 failed and 2 errors, out of 17 tests. Tests are in `backend/tests/test_evaluation_integrity.py` and `backend/tests/test_discovery_pathways.py`.

| # | Issue | What was wrong | Correction |
|---|---|---|---|
| 1 | The sealed key was in a public repository | The v1 key mapping each item to its method was committed in `1b37e42`, and this repository is public. v1's screenshots and documents also showed how 18 other real leads were found: SalesIntel's real-data daily list, and 8 Shadow Radar leads | v1 is **withdrawn unjudged**. The v2 key is written outside the repository (`~/.salesintel/evaluation`, mode 600). Only a commitment is published: the dataset's SHA-256, and the SHA-256 of the key with a 256-bit random salt. Every v1 lead, and every lead published with its method, is excluded from v2. A first v2 draw that predated the screenshot check was discarded before anyone saw it. The showcase now skips reviewed organisations, and screenshots mask real leads on SalesIntel's lists. History was not rewritten and nothing was force-pushed |
| 2 | Precision came from the first reviewer | `results()` used each item's first decision, and called one review "complete" | Every measure now comes from final labels. An item needs complete reviews from at least two independent reviewers. A disagreement on relevance, reason to contact or pursue needs a recorded adjudication: consensus of the reviewers, or an independent third reviewer who did not review it, always with a rationale. Kappa is measured on the reviewers' own answers, before adjudication |
| 3 | Unblinding relied on a confirmation dialog | Any administrator could see results at any time | The server refuses results (409) until three things hold: every item has two complete reviews and every disagreement is resolved; the review is locked, after which answers cannot change; and the private key is supplied and matches the commitment |
| 4 | What reviewers saw revealed the method | "Company research" appeared only on SalesIntel items (5 of 5) and "Building works record (indirect)" only on baseline items (3 of 3). Every summary was SalesIntel's own generated reasoning ("Window open until April 2027"). The service list for private leads was the AI's guess. Evidence lines carried internal names ("radar:") | Reviewers now see only the source records: organisation, site, location, the record's own title, the kind of record, and dated facts with links. There is no summary, service list, inference or internal name. Dates SalesIntel calculated are labelled "Calculated from published records". Item order and ids use the secret salt |
| 5 | Shared leads and sampling were miscounted | "Missed by SalesIntel" checked SalesIntel's sample, not its list. The SalesIntel estimate pooled a stratified sample (every private lead, but 6 of 28 public) without weighting | Each method is now a simple random sample of its own list. A lead sampled by two methods is judged once and counts in each. Membership of a list is kept separately from sampling, so "missed" means "not on the list". Results report n, frame and list sizes, Wilson intervals and pairwise overlap. Differences use Newcombe intervals, Bonferroni-adjusted, and are conservative given shared leads. **A difference is claimed only if the adjusted interval excludes zero** |
| 6 | *Found:* the keyword baseline read SalesIntel's text | It searched SalesIntel's own "why now" sentence, which for private leads always mentions fire and security | It now searches only the record's own words |
| 7 | *Found:* private leads qualified on the AI's guesses | The research model's guessed service list, and its "engage now" timing, put private leads on the daily list | See the pathways below |

**What blinding cannot hide.** The kind of record differs by method by design: SalesIntel's qualified list favours open tenders, and the renewal baseline is award records. The kind of record is material evidence, so it stays visible. To account for that, results are also shown by kind of record. The blinding audit is kept in the sealed key, so it cannot become a clue.

## Two discovery pathways

**Qualified discovery** is an evidenced requirement for a service you sell. The evidence can be:
- a notice whose own title names the service; or
- a company's current, sourced, stated requirement, finding or incident whose words name it.

An existing relationship also qualifies. Indirect evidence never qualifies, and nor do the AI's guessed services or timing.

**Exploratory discovery** is a credible change at an organisation or site that may justify investigation: a new site, a move, an expansion, a new facilities leader, a supplier problem, or a building project. It needs:
- a stated, sourced signal (or published indirect records that have not been contradicted);
- dated within a year;
- inside your territory.

Strategy statements, funding rounds and competitor news are excluded as too weak. Each exploratory lead is shown separately, under "Worth investigating":
- it is marked **Need not confirmed**, with its other uncertainties (single source, indirect records);
- its next step is an investigation that ends in "confirm there is a need before any pitch";
- at most five are shown a day; the rest are in Discover.

It never pads, reorders or joins the qualified list. A test checks that the qualified list is identical with the exploratory pathway switched off.

**On the real data** (the reference installer, 5 November 2026):
- **Qualified: 28 leads, all public notices.** The 5 private leads that PR #9 first listed qualified only on the AI's guesses. The 2 with genuine fire-enforcement evidence are over a year old, so they are kept in view, not listed.
- **Exploratory: 72 credible changes,** 13 private and 59 from indirect public records. PR #9 first counted all of these as "kept in view", never shown.

Whether they help, without adding noise, is measured by the review: exploratory is its own arm, with a rule fixed in advance. It is supported as useful if at least 30% of its sample is judged worth investigating. Its noise rate is reported against the keyword baseline.

**Tests changed, with the reason.**
- PR #8's fixture tests expected a corroborated Shadow Radar lead on the qualified list.
- It now appears on the exploratory list, and the tests check the same reasons and cautions there, plus its uncertainty label.
- An existing customer's new site still qualifies, through the relationship.

## Phase 1: actual state

| PR | Branch | State | CI |
|---|---|---|---|
| #4 | `feat/saas-foundation` → `main` | Open | Green |
| #5 | `feat/acquisition-engine` → #4 | Open | Green |
| #6 | `feat/shadow-radar` → #5 | Open | Green |
| #7 | `feat/fluid-ui` → #6 | Open | Green |
| #8 | `feat/best-opportunities` → #7 | Open | Green (backend, frontend, Playwright) |
| #9 | `feat/opportunity-quality` → #8 | Open | Green at `1b37e42` (run 42110829987), before these corrections |

**Migrations:**
- `0025_blind_review` added review decisions.
- `0026_review_integrity` adds reviewer identity and channel, adjudications, and each set's open, locked or revealed state, all with row-level security.
- Both are additive. Migrate any copy before running it.

**Verdict: VERIFIED PASS.**

## Phase 2: adversarial product-correctness review

Every defect was first reproduced by a test that failed. The recorded failing run is `docs/saas/evaluation/defects-before-fix.txt`, 7 of 7 failing. Then the smallest fix was made. Tests are in `backend/tests/test_opportunity_quality.py`.

| # | Suspected defect | Reproduced? | Smallest fix | Verdict |
|---|---|---|---|---|
| 1 | Private prospects assigned a New Site play without new-site evidence | **Yes.** Every prospect link returned `new_site`, including a leadership change and an unsourced "rumoured depot" | New site only with a **sourced, stated** signal (new site, relocation or planning application). A documented supplier problem becomes Supplier review; anything else is Account development, whose description no longer claims "added by your team" | VERIFIED PASS |
| 2 | Contact details treated as verified without proving the person–role association | **Yes, in three places.** (a) The Navigator copied the model's person name onto an email route whose own quote does not name them. (b) "Verify contact" marked a named person's address current when the page published the address without the name. (c) A named contact whose source quote does not name them still showed as "Publicly sourced" | (a) A route keeps a person's name only if its own quoted source names them, otherwise it stays a role route. (b) The official page must name the person and state the role, otherwise the result is "partial" and the contact is not upgraded. (c) Such a contact is level 4, and says why | VERIFIED PASS |
| 3 | Distinct organisations grouped on normalised names | **Yes.** A public trust and a private firm with the same name became one row | Rows merge only through a confirmed account link, or an identical published buyer name. Otherwise each lead is its own row | VERIFIED PASS |
| 4 | Lead-presented metrics recorded from API reads | **Yes.** Every `GET /best` recorded "presented" | Reads record nothing. The interface reports a lead only after its card has been at least half on screen for a second (`POST /best/seen`, validated keys, once a day), on either list | VERIFIED PASS |
| 5 | Golf-course irrigation false positive | **Yes** | `irrigation` added to the classifier's exclusions. The real capture now keeps 96 of 631 notices (was 97) | VERIFIED PASS |
| 6 | *Found by the evaluation:* adjacent fire work counted as "what you sell", or as "not stated" | **Yes** | Adjacent work is its own service: fire risk assessment, extinguishers, passive fire protection, smoke control | VERIFIED PASS |
| 7 | *Found by the evaluation:* free-text locations judged outside your territory | **Yes** | An English region means England; another named nation means outside; anything else is "not confirmed", never outside | VERIFIED PASS |

**Live paid research needs an approved budget, with a hard ceiling.**
- An administrator approves the budget, between $1 and $1,000 per approval, and each approval is audited.
- With a live provider, every job reserves against it, in the same conditional update as the daily limits.
- With no budget, or a used-up one, the request is refused and nothing is queued or charged.

**Verdict: VERIFIED PASS.**

## Phase 3: the blinded evaluation (protocol v2)

Fixed in `backend/app/intelligence/opportunity_review.py`, and committed publicly in `backend/reference_data/evaluation/opportunities-2026-11-05-v2.commitment.json` before any judgement.

- **Date and profile:** as of 5 November 2026. One reference profile for every arm: a UK installer of fire alarms, access control, CCTV, intruder and emergency lighting, in England, Scotland and Wales.
- **Arms:** each a simple random sample of up to 10 from its own list. The seed and salt are random, and sealed in the key.

| Arm | What it is | List | Frame (published leads excluded) | Sampled |
|---|---|---:|---:|---:|
| Qualified | SalesIntel's daily list | 28 | 11 | 10 |
| Exploratory | SalesIntel's exploratory list | 72 | 59 | 10 |
| PR #8 rules | The list as PR #8 built it | 74 | 43 | 10 |
| Renewal | Published contract ends within 120 days | 41 | 24 | 10 |
| Keyword | The record's own words name a fire or security system | 385 | 351 | 10 |

- **The frozen set:**
  - **Size:** 44 distinct items from 50 draws. Two leads were sampled by qualified, PR #8 and renewal, one by qualified and PR #8, and one by PR #8 and renewal. At about two minutes each, that is roughly 90 minutes per reviewer.
  - **Personal data:** named individuals removed, and no contact details.
  - **Licence:** public records are Open Government Licence.
- **Reproducibility:** the private key and the database snapshot beside it reproduce the set exactly (`backend/scripts/build_review_set.py`). After the review, anyone can check the key against the commitment with `--verify`.
- **Primary comparisons:**
  - qualified against renewal, and against keyword;
  - on two measures: relevant, and actionable (worth pursuing this week or month).
- **Secondary comparisons:**
  - qualified against PR #8, on relevant and noise;
  - exploratory against keyword, on worth investigating and noise.

### How two salespeople do it safely

- They receive an **offline review pack**: one HTML file each, downloaded from the local evaluation server.
  - It holds only the blinded items and the rubric.
  - Its content security policy forbids every network request, which the browser test confirms.
  - It contains no key, and gives each reviewer their own order.
- Each reviewer confirms they will work alone and not look for how items were found. They then judge every item; answers save as they go.
- They send back one answers file. It is checked against the set's fingerprint and the rubric before import.
- The evaluation owner then resolves disagreements, locks the review and reveals the key, all on their own Mac.
- `docs/saas/evaluation/REVIEWER_GUIDE.md` is for the reviewers; `docs/saas/evaluation/RUNBOOK.md` is for the owner. `scripts/evaluation-server.sh` runs the app on 127.0.0.1, on a fresh database, with no credentials and no paid calls.

### Results so far

**0 of 44 items judged. No improvement is claimed.**

Objective facts about each whole list:

| | Qualified | Exploratory | PR #8 rules | Renewal | Keyword |
|---|---:|---:|---:|---:|---:|
| The record names a service the profile sells | 100%¹ | 1%² | 41% | 34% | 57% |
| Already advertised (open tender) | 54% | 0% | 42% | 0% | 12% |
| Median evidence age (days) | 27 | 101 | 140 | 835 | 638 |

¹ By construction of the qualified rule. This shows the rule is applied, not that relevance improved.

² The exploratory list holds changes, not requirements. One of its 72 records names a service, but not as a requirement.

**Verdict:**
- The method, dataset, blinding and safeguards are a **VERIFIED PASS**.
- Proof of improvement is a **NO-GO** until both reviewers finish.

## Phase 4: improvements to the acquisition experience

- **Best opportunities is a focused day.**
  - It shows only "act now" and "this week" qualified leads (up to 10). Each has a positive service match from the evidence, or an existing relationship.
  - On a quiet day, at most 3 qualified leads kept in view are added, labelled as such.
  - Exploratory leads follow under "Worth investigating", at most 5, labelled.
- **One next step per lead,** built deterministically from its own evidence: a bid decision, a renewal question, a new leader, a new site, or a published finding. For exploratory leads it is always an investigation.
- **Deep investigation, Resolve this gap and the buying committee** are as before. The committee now needs a contact to be tied to their person by the source.

**Verdict: VERIFIED PASS (tested); usefulness CONDITIONAL on the human review.**

## Phase 5: showcase from real public evidence

`docs/saas/evaluation/SHOWCASE.md` is regenerated from the evaluation snapshot by `backend/scripts/build_showcase.py`. **Its selection rule, fixed before looking:** the top lead of each source type, from the qualified list where that type has one, otherwise from the exploratory list, labelled as such.

**Verdict: CONDITIONAL PASS.** The leads are real, explained and replayable, but none is yet judged worth pursuing by a salesperson.

## Phase 6: quality and ROI scorecard

| Measure | Status |
|---|---|
| Independently adjudicated relevance and actionability, against the baselines | **Pending:** 0 of 44 judged by two reviewers |
| Exploratory usefulness and noise | **Pending:** the rule (at least 30% worth investigating) was fixed in advance |
| Research cost | **$0** for this PR. Live research needs an approved budget |
| Share of discoveries leading to a sales action | **Not measurable yet.** Exposure is recorded honestly; it needs pilot users |

The prospective pilot design is unchanged:
- 3 to 6 consenting salespeople, for 8 weeks;
- each completes the blind review before using the product;
- outcomes are recorded automatically, with weekly relevance checks;
- intervals are always shown, and nothing is entered on anyone's behalf.

**Verdict: CONDITIONAL.** The machinery is ready; no pilot has run.

## Acceptance for the next phase (the AI Win Room)

The next phase may start only when all five of these hold:
1. **The method is defensible.** Done.
2. **Both reviewers have completed the sample.** Not yet.
3. **Disagreements are recorded and resolved transparently.** The machinery is ready; there are none yet.
4. **Relevance and actionability are measured against the baselines.** Not yet.
5. **Exploratory private opportunities are not silently excluded** because fire or security words are absent. Done, and tested.

## Engineering acceptance (local, final run)

The final run's results are recorded in the PR description, with the final commit and the GitHub Actions run.

**Screenshots of the running application:**
- 10: both pathways, with real organisations masked so no screenshot can unblind a reviewed item;
- 15: the reviewer's view;
- 18: the offline review pack;
- 19: the evaluation controls, with the results still sealed.

The old real-data screenshot 16 is removed. Its leads are excluded from v2.

## Known limitations

- **Plural and combined service names are under-detected,** for example "Access Controls". The patterns are shared with Renewal Radar. This can cause missed leads, not false ones. The review's "missed" measures will show how often.
- **The exploratory list is mostly indirect public records** (59 of 72). Private leads appear only where a workspace has run company research.
- **Blinding cannot hide the kind of record,** which is material evidence. Results are also reported by kind of record.
