# Contract Atlas: who holds the fire and security work

Branch `feat/contract-atlas`, stacked on #10 (`feat/local-research-budget`) → #9 → … → #4 → `main`. Written on 6 November 2026.

- Nothing is merged or deployed.
- The live database, collectors and live app were not touched. The work ran on private copies in `~/.salesintel/atlas`.
- Live research spent $5.97 of the $10 approved for this evaluation.

**Release blockers, unchanged:** employer IP and ownership, data licensing, and the product name. Do not deploy or commercialise.

## What a salesperson can do now

In **Discover → Contract Atlas** a salesperson can:
- search a **contractor** or a **customer** by name;
- filter by service, region, and when the published term ends.

A **contractor record** shows:
- its identity:
  - its Companies House number where a source publishes one;
  - the names it is published under;
  - its parent company where a reviewed registry filing shows one;
  - look-alike names kept apart for review;
- the services it is named for, and every published contract, with:
  - status, scope (maintenance or installation) and route (framework appointment, call-off or direct award);
  - value with its basis, sources and timeline;
- **Worth investigating:** contracts in your services and territory where a published date gives a reason to engage. Each reason says:
  - what the records show, why it can matter, and other explanations;
  - what would rule it out, what is still unknown, and the next check.
- **Reported by public sources:** the contractor's customers named in its case studies, customer pages, press releases and FM announcements. Each one:
  - is researched on request, inside the research budget;
  - shows the page's own words, and whether the quote was found on the page;
  - says whether the work is current or historical.

A **customer record** shows:
- the suppliers it published, and those public pages report;
- otherwise, plainly: *Current supplier not publicly established*;
- any Shadow Radar signals about it, in the same structure.

**Into the sales workflow:**
- **Investigate** turns a competitor-held contract into an account, linked to the contract and its evidence, without retyping anything.
- From there the existing workflow applies: the play, Resolve this gap, the buying committee, Find the right people, introductions, qualification and deals.
- Every account also shows **Who supplies them**.

## Architecture decision

- **No second Market Network.**
  - Contractor identities are built from the suppliers named on the Market Network's canonical contracts (`market_contracts`).
  - Each link points at the canonical contract, which keeps its sources, dates and value with its basis.
  - The new shared tables hold only what did not exist: identity, the names a contractor is published under, its links to contracts, and conflicts for review.
- **Identity is conservative.** One company number is one contractor. A name without a number joins a numbered contractor only when it is the identical legal name, ignoring case, punctuation, "&"/"and" and "Limited"/"Ltd", and that name has a single published number. Otherwise:
  - a parent and its subsidiary never merge;
  - a name published with two numbers becomes a conflict for a person;
  - look-alike names, such as a "(Leeds)" branch note, a lot number or a missing "Ltd", are flagged for review and never merged.
  - Company numbers are validated: a published "0" is not a number.
- **Shared facts and private research are kept apart.**
  - **Shared and read-only:** published contracts and contractor identities are public facts. Workspaces read them; only a system session builds them. The tenancy layer refuses any workspace write.
  - **Private to each workspace:** researched relationships (`atlas_relationships`) are protected by PostgreSQL row-level security. Which competitor a company researches is its own business.
- **What we know, and what we think, stay apart.** Published facts and researched reports each carry their source. Reasons to investigate are built from published dates; they never carry a probability, a likelihood or a confidence score.
- **AI only where needed.**
  - Everything public is deterministic: building identities takes 0.5 seconds for 1,705 contracts.
  - The language model is used only to read unstructured pages (case studies and announcements), inside the research budget, with each job's cost ceiling enforced before every call.
- **A private relationship is kept only if the pages support it.**
  - The page must be one the search returned, and it must name the supplier, the customer and any intermediary.
  - A quote counts as verified only when it appears word for word.
  - A date or a stated duration is kept only when those words are on the page.
  - No value or end date is ever recorded.
  - A case study more than three years old is historical.
  - Claims that fail these checks are kept apart, counted and never shown as relationships.

**Migration** `0027_contract_atlas` is additive: four shared tables, plus one workspace table with row-level security.

## Verdicts

| Capability | Verdict | Evidence |
|---|---|---|
| Contractor identity, names, groups, conflicts | **VERIFIED PASS** | Adversarial tests on a fictional market. On the sample of real data, 9 of 9 company numbers and 10 of 10 name-based joins are confirmed independently against the raw records |
| Reconstructing published contracts | **VERIFIED PASS** | 53 published relationships for 24 contractors. Independently checked against the raw records: supplier, customer and end date 100%, values 51 of 51 |
| Framework, ceiling, scope and date distinctions | **VERIFIED PASS** | Tested. Status was consistent with the published end in 39 of 39 cases |
| Private-relationship investigator | **CONDITIONAL PASS** | The workflow is complete and tested, and it rejects every unsupported claim. On 8 random contractors it found 0 supportable relationships for $5.97. Its excerpt-only check also rejects some real ones (see below) |
| Contract change reasons, and Shadow Radar in the same structure | **CONDITIONAL PASS** | Built from published dates; tested. No live Shadow Radar data exists to combine with yet |
| The Atlas screens, and their link to accounts and plays | **VERIFIED PASS** | Hosted and local browser tests with accessibility scans |
| Workspace isolation | **VERIFIED PASS** | API and browser tests, on SQLite and PostgreSQL with row-level security |
| Subcontract and FM delivery chains | **CONDITIONAL** | Recorded only when a source states them (tested on fixtures). The real sample found none, because no private relationship passed the evidence checks |
| Sell2Wales and Northern Ireland sources | **NO-GO (not started)** | Their terms and interfaces are not yet checked, so nothing was collected |
| Better commercial results than existing discovery | **NO-GO (not claimed)** | The counts are below. Judging quality needs salespeople, as in the blind review |

## The Contract Atlas challenge

Reproducible with `backend/scripts/atlas_challenge.py`. It runs only on the isolated copy.

1. **Frozen sample.** `docs/saas/atlas/challenge-sample.json` holds the rule and the random seed, drawn before any result was seen.
   - 24 contractors were drawn from 1,054, stratified by the number of published contracts and by identity.
   - A second seeded draw chose 8 of them for private research.
2. **Reconstruction.** The Atlas records for each contractor.
3. **Independent check.**
   - **Public relationships:** a separate parser and name normaliser re-read every raw source record.
   - **Private relationships:** a fresh fetch of every reported page looks for the quote, the supplier and the customer.
4. **Commercial utility.**
   - The reference salesperson (the review's reference installer) is compared with the Renewal Radar and Shadow Radar.
   - Only accounts not already pursued count.

Results, with any organisation in the blind review withheld, are in `docs/saas/atlas/challenge-results.json`.

### Public relationships, checked independently against the raw records

| Check | Passed |
|---|---:|
| Supplier named in the source | 53 / 53 |
| Customer named in the source | 53 / 53 |
| Company number in the source (numbered links) | 9 / 9 |
| Name joined to a numbered contractor, the same name published with the number | 10 / 10 |
| End date as published | 39 / 39 |
| Value as published | 51 / 51 |
| Status consistent with the published end | 39 / 39 |
| Service words present in the source | 53 / 53 |
| Scope consistent with the source wording | 33 / 33 |
| Unsupported assertions | 0 |
| False supplier matches | 0 |

- **Value fields:** the first run flagged 2 values. Both were the same framework ceiling, which the source publishes as the tender's `amountGross`. The checker did not read that field yet. It was widened, and the Atlas was unchanged.
- **Service and scope checks** confirm the words are in the source. Whether each classification is commercially right is in the private review sheet, for a person to judge.

### Private relationships, from public pages

- **The run:** 8 contractors were drawn at random from the frozen sample and researched live (Anthropic, `claude-opus-5-5`, web search). It cost **$5.97** of the $10 budget, about $0.75 per contractor, and the model read 35 to 54 pages for each.

| Outcome | Contractors |
|---|---:|
| No published customer relationship found | 4 |
| Claims made, but none supported by the retrieved pages (4 claims, hidden) | 3 |
| Stopped at its $1.50 cost ceiling during the search, so nothing was kept | 1 |
| **Relationships reported** | **0** |

**What the independent live re-fetch of the 4 rejected claims found:**
- **One page refused the request.**
- **Three name the customer on the full live page.** The pipeline checks only the excerpts the search returned, which did not include the customer, so it is strict enough to throw away some real relationships:
  - a CCTV and access-control maintenance listing on a procurement aggregator, for a sister company with a different legal name from the sampled contractor;
  - a contract listing with no quote at all;
  - a training job, which is not fire or security systems.
- **None of the four would have been a correct, in-scope relationship** for the sampled contractor as recorded. Precision was kept; recall was low.

**What this shows:**
- **Small suppliers rarely publish who their customers are.** Of the 24 sampled contractors, 12 have a single published contract and no company number.
- **The value of private research probably lies with national and regional integrators,** who publish case studies. Within its budget the random subset included none.
- **Cost is not fully capped per run.** The run that hit its ceiling spent $1.54 on one search call of 320,000 input tokens. The ceiling is checked before each call, so a single large call can exceed it slightly.
- **The next improvements:**
  - check the full page with a guarded fetch (public HTTPS hosts only), rather than the search excerpt alone;
  - cap the search phase, so the structuring step always has budget left.

A private review sheet, with every claim, its source and a sample of 30 classifications, is in `~/.salesintel/atlas/challenge/review-sheet.csv` (on this Mac, not in the repository). Judging correctness needs a person.

### Commercial utility for the reference salesperson

- **Atlas:** 317 accounts not already pursued, each with a published supplier relationship, a specific reason, and a next action. 305 of them have a published end date.
- **Renewal Radar:** 325 accounts. 196 accounts are on both lists, 121 only on the Atlas, and 129 only on the Renewal Radar.
- **Shadow Radar:** no live data.
- **Contact routes:** no stored notice carries a named contact, because the collectors deliberately strip contact points. The Contact Navigator fetches the official route on request.
- **What this shows:** these are counts of what each list can show. They are not a judgement of quality, and no improvement is claimed.

The Atlas's public leads come from the same canonical contracts as the Renewal Radar. What it adds:
- the competitor's whole book;
- the identity rules;
- links to accounts;
- private relationships from public pages.

## Limitations

- **Private contracts are mostly unpublished.** Finding nothing is a common and honest answer. Case studies show past work, not current contracts.
- **Regions** come from the buyer's postcode area, or from the notice's own region when it names just one. 19% of links have no single region.
- **Identity rests on published names and numbers.** Look-alike names are flagged, not resolved; that takes a person or a licensed registry match.
- **Sources:** Sell2Wales and Northern Ireland are not collected.
- **Subcontracts:** no subcontract chain is ever inferred, so FM delivery chains appear only where a source states them.
- **Screenshots** use an entirely fictional market (20 to 22). Until the blind review is locked, no real-data screenshot is published.
