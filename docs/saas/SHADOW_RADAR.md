# Shadow Radar and Deep Opportunity Intelligence

Branch `feat/shadow-radar`, stacked on PR #5 (`feat/acquisition-engine`), which is stacked on PR #4. Written on 5 November 2026. Not merged or deployed. The live database, the collectors and the running test instance were not touched.

**Verdict: CONDITIONAL PASS.** The vertical slice works end to end on real captured evidence and live research. It is **not shown to predict buying better than simpler methods**, and three of the eight sensors need sources that are not yet available.

## What it does

The Shadow Radar treats an unadvertised need as a hidden state that leaves shadows in public records. The pipeline:

1. **Observation.**
2. **Organisation and site resolution.**
3. **Correlation in time.**
4. **Sensor.**
5. **Competing hypotheses.**
6. **Challenge.**
7. **Window.**
8. **Lead.**
9. **Investigation.**
10. **Contact, outreach and deal.**
11. **Recorded outcome.**

| Part | Where |
|---|---|
| Sensor registry and pure inference | `backend/app/intelligence/shadow_radar.py`: 8 sensors as inspectable data |
| New source: adjacent building works | `backend/app/ingestion/adjacent_works.py`. Contracts Finder (OGL), through the existing connector and request budget |
| Shared hypotheses, with immutable revisions | `backend/app/services/shadow.py`; tables `shadow_hypotheses` and `shadow_hypothesis_revisions` |
| Deep investigator | `backend/app/services/investigator.py`: a durable job that includes the Contact Navigator |
| Workspace learning | `si_dossiers` and `si_lead_feedback` (tenant-scoped, with row-level security); `/api/si/radar/scorecard` |
| Evaluation | `backend/app/intelligence/shadow_evaluation.py`, `backend/scripts/evaluate_shadow_radar.py`, `backend/reference_data/shadow_evaluation_2026-11-05.json` |
| Interface | Discover → Shadow Radar (`si-shadow.tsx`): one row per project; an investigation panel on the account; the investigation summarised on the deal |

### The rules that keep it honest

- **A hypothesis is never a fact.** Each lead lists, separately, what is published (verified), what is inferred and what is unknown, plus the rival explanations and what would disprove it.
- **No probabilities.** A lead's state describes its evidence, not a likelihood: one line of evidence, corroborated by independent sources, contradicted by later evidence, now advertised, or window passed.
- **Independence is counted by origin.**
  - Repeated notices about one project, and republished copies of one story, count once.
  - A procurement notice and a regulator judgement count as two.
  - Two notices from the same buyer count as one.
- **Competing hypotheses come from the same evidence.** A new building may mean a maintenance need for the owner, or a specialist package bought by the main contractor. Both are shown on one row, and a project-level dismissal ("outside our territory") covers both.
- **"Now advertised" is claimed only for the same project.** Another fire or security advert by the same organisation is shown as related, "may not concern this project". The exception is organisation-wide needs such as remediation.
- **No double-counting of value.** A purchasing consortium is never merged with the member it buys for; the owner is shown as *inferred*. The main contract's value is never used as the deal value.
- **Every date is kept.** Event date, publication date, first seen by SalesIntel, and retrieval date are all recorded. Observations are append-only. Hypotheses are retired, never deleted, and every assessment is kept as a revision.

## Sensors

| Sensor | Status | Evidence used |
|---|---|---|
| New premises (estate mobilisation) | **Active** | Building contract awarded or tendered; new or enlarged estate |
| Main contractor package (adjacent procurement) | **Active** | Building contract awarded, with the contractor named |
| Fire safety remediation | **Active** | Regulator finding; fire authority enforcement; remedial work procured; counter-evidence: a published resolution |
| Supplier transition | **Active** | Contract terminated or abandoned, repeated re-tendering, early re-let; counter-evidence: a new supplier appointed |
| Systems modernisation | **Active** | Building-services replacement works (rare after the conservative filter) |
| Portfolio consolidation | **Needs a source** | Companies House (no API key) and the regulator's register of mergers (not integrated) |
| Funded capital improvement | **Needs a source** | GOV.UK funding releases checked publish totals, not named recipients and scopes |
| New operational leader | **Needs a source** | Companies House officers (no key); found per account by the investigator instead |

## Sources assessed

| Source | Decision |
|---|---|
| Existing procurement collectors (Find a Tender, Contracts Finder, Public Contracts Scotland) | Used. Early market notices are treated as **outcomes, never inputs** |
| **Contracts Finder adjacent works** | **New and integrated.** Verified live: 6 requests returned 631 notices; 97 kept. Crown copyright, Open Government Licence v3.0, with attribution on every observation |
| Contract performance and termination notices | Used, through the existing derived observations |
| Regulator of Social Housing judgements; London Fire Brigade enforcement | Used (existing). Regulator pages hold only the current judgement |
| The Gazette | Existing insolvency feed; not a Shadow Radar input in this slice |
| Companies House | **Blocked:** no API key configured |
| CQC provider and location changes | Not integrated: API access terms not verified in this slice |
| planning.data.gov.uk | **Assessed and not used:** its planning-application dataset returned **0** records nationally on 5 November 2026 |
| Company announcements, news and recruitment | Read per account by the deep investigator (live web research), not collected continuously |
| Licensed corporate, estate and contact data | Not integrated; see `CONTACT_NAVIGATOR.md` |

**Classifier precision.**
- After tuning, a **held-out** random sample of 30 kept notices was judged by me: **26 of 30 (87%)** are genuine building projects plausibly needing fire or security systems. The four misses (ball courts, a clinical service, a demolition and a games area) were then excluded.
- Recall (projects missed) was not measured.

## Evidence the slice works (the ten proofs)

| # | Proof | Evidence |
|---|---|---|
| 1 | A relevant organisation is discovered from real evidence | 97 real projects from the 631-notice capture: for example Anchor Housing's £17.8m new build (main contractor Meldrum Group), and East London NHS Foundation Trust's new mental-health emergency department |
| 2 | Indirect observations produce a traceable hypothesis | Every lead has a dated timeline with source links, the sensor and its rule version |
| 3 | The system challenges itself | Counter-evidence marks a lead contradicted. The investigator asks challenge questions. **Live**, it found the trust's Hard FM contract and its CBRE appointment, so its verdict was "evidence against it" |
| 4 | A concise opportunity card | Organisation and site, requirement, why now, timeline, verified, inferred, unknown, other explanations, services, fit, window, relationship history, next action (screenshots 6, 8 and 9) |
| 5 | A meaningful dossier | Versioned sections with quoted, cited findings; rejected findings listed with reasons (screenshot 7) |
| 6 | Verified contact routes where available | Contact Navigator in the same job. Live: an enquiry form and a named person. Replay: a named estates director and an estates email |
| 7 | Outreach and progress | Browser journey: introduction approved, logged as sent, then a deal created with the investigation carried in |
| 8 | Persistent and tenant-isolated | Dossiers, feedback, jobs and contacts are private (PostgreSQL row-level security); hypotheses are shared public intelligence; another workspace sees the lead but none of the work |
| 9 | Survives restart; cost-controlled | Lease recovery tested for the investigation job. Investigation reserves $4. **Live: $1.29**, 14 searches, about 2 minutes |
| 10 | Comparable with conventional discovery | Time-safe evaluation against renewal and keyword baselines (below) |

### Live investigation of a real lead

East London NHS Foundation Trust, "New Mental Health Emergency Department Unit at Luton Centre for Mental Health". Run with your Anthropic key on a copy of the database:

- **Read:** 13 source pages, out of 59 retrieved.
- **Answered:** of 8 questions, 1 supported, 4 against and 3 open.
- **Findings against the hypothesis:**
  - a Find a Tender award for "Hard FM Services ELFT";
  - CBRE appointed for facilities transformation;
  - a facilities contract running from September 2025 to September 2028, with extension options.
- **Cost:** $1.29 at list price.

That is the intended behaviour: before calling, the salesperson learns an incumbent FM provider probably covers this.

## Evaluation: Shadow Radar against conventional discovery

`backend/reference_data/shadow_evaluation_2026-11-05.json`.

- **Design:** four decision dates, 30 days apart, from when the works capture begins, each with a 120-day horizon.
- **Inputs:** each arm sees only records published by each date.
- **Outcome:** the organisation publishes fire or security procurement afterwards, having not done so in the previous 90 days. Early market notices are outcomes, never inputs.

| Arm | Flagged | Hits | Precision (95% interval) | Share of outcomes found | Median days, evidence to outcome |
|---|---:|---:|---:|---:|---:|
| Shadow Radar | 109 | 11 | 10.1% (5.7–17.2%) | 2.5% | 98 |
| Renewal dates | 225 | 31 | 13.8% (9.9–18.9%) | 7.2% | 828 |
| Simple keywords | 201 | 24 | 11.9% (8.2–17.2%) | 5.5% | 205 |

By sensor: main contractor package 17.3% (9.4–29.7%), new premises 7.5%, remediation 6.2%.

**Conclusion: the Shadow Radar is not shown to beat the renewal or keyword baselines.** The intervals overlap, and it finds a smaller share of outcomes. Do not claim predictive superiority. The main-contractor sensor is the most promising, but it is not significant.

**Limitations:**
- The works capture covers about six months, so the outcome windows are short and partly cut off by the end of the data.
- Observations were back-filled. Publication dates are real, but SalesIntel did not hold them on those dates.
- Hits are judged at organisation level, not per hypothesis.
- A main contractor's subcontract package is never publicly advertised, so this test **cannot observe** that sensor's real outcome. The workspace outcome loop (feedback, conversations, deals) is the measure that can.

## Outcome learning loop

**Recorded per workspace:**
- relevance decisions;
- dismissals, each with a reason (not our service, outside territory, too small, already known, wrong organisation, evidence wrong, timing wrong, locked in with a supplier);
- disproved hypotheses (by feedback, or by an investigation that weakened them);
- contacts verified, conversations, meetings and confirmed requirements;
- deals qualified, won and lost;
- value won, on a stated basis;
- research cost;
- days from first signal to deal.

Margin is not recorded yet, and the scorecard says so.

## Not done, or not verified

- **Three sensors need sources** (above).
- **Live continuous collection is not scheduled.** The adjacent-works collector is built and verified with real calls, but it is not yet a launch agent (live collectors were not touched).
- **Contacts published on notices** are still fetched only from replay.
- **Investigator effect labels.** The live run labelled some company facts "supports" where they are context. The verdict uses only answered questions, but the labels need tightening.
- **Ownership and IP:** unresolved. Every new prompt names the workspace's own company. Older prompts still name the employer.

## Next milestone

**The AI Win Room.** When a Shadow Radar lead or a public tender produces documents, analyse them with page and clause references and turn the dossier into a bid/no-bid decision and pursuit plan, on the same job, spend and isolation foundations.

**In parallel:**
- schedule the adjacent-works collector;
- obtain a Companies House key, which unlocks two sensors;
- run a three-month forward test, so the radar is judged on leads it formed *before* the outcomes.
