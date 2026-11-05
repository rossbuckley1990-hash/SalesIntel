# SalesIntel 2.0: engineering report

Branch `feat/salesintel-2`. Status: the first complete sales loop (Phases 1 and 2) is built and tested end to end. A first version of the fire and security conversion slice (Phase 4) is built and tested at API level; Phase 3 is partly done. Nothing has been pushed or deployed.

## 1. Baseline: what was true before this work

| Area | Finding |
|---|---|
| Works on real data | UK procurement collection (Find a Tender, Contracts Finder, Public Contracts Scotland) on a schedule; Renewal Radar classification and categories; signal inference with arbitration; private prospect research and deep research dossiers (Claude, paid per run). |
| Synthetic only | The living workspace demo (`APP_ENV=demo`: synthetic opportunities, actions, assets, finance). The Classic workspace says its connectors include fixtures. |
| Duplicated experiences | Four discovery surfaces (Opportunity Finder, Prospects, AI Research, Classic research). Three task systems (`ExecutiveAction`, `ResearchLeadAction`, and now SalesIntel tasks). Several "organisation" notions (`BuyerProfile`, `ResearchLead.organisation`, `Prospect`, `MarketEntity`) and several "opportunity" notions (`Opportunity`, `MarketOpportunity`, `MarketSignal`, `ResearchLead`, `Prospect`). |
| Missing | No account record joining research, contacts, interactions and deals; no interaction log; no follow-ups tied to accounts; no quotation workflow. |
| Persistence | Records persist in SQLite. Not durable across a restart: AI Research job progress is in memory (`ResearchJobManager._jobs`); prospect searches run in a thread and previously stayed "running" for ever after a restart (now marked failed after 20 minutes). |
| Schema management | The live database has an empty `alembic_version`: schema comes from `create_all` and lightweight compatibility code, not migrations. Migrations exist and are kept current, but they have never been applied to the live file. |
| Redundant entry | Promoting a radar lead created a pipeline record that lost the original research context, which then had to be rebuilt by hand. |
| Backtest | Outcomes were dated by a notice's planned approach date, not its publication date, so a notice published before a hypothesis could count as its outcome, and future-dated notices counted. Fixed; see section 8. |

## 2. Competitor patterns used

These are design judgements from general product knowledge. The live interfaces were not browsed for this work, so treat them as inferred.

| Product | Pattern | Where it appears in SalesIntel |
|---|---|---|
| Stotles | Procurement results with buyer context and a reason to act | Discover rows lead with a WHY NOW line and published/inferred labels |
| Clay | Progressive enrichment; missing data shown, not hidden | "What still needs confirming" on every account; scope answers carry a basis |
| Apollo | Contact routes beside the record; sequence-style follow-up | Contacts with source quotes; a follow-up set in the same step as logging |
| Attio | One connected record for company, people, history | Accounts: evidence, contacts, sites, history, deals and identity on one page |
| Close | Action queue; log an activity without leaving the list | Today queue with inline Log, Done, Tomorrow, Next week |
| Pipedrive | Visual stage board; the next action is obvious | Deals board and stage stepper with one "Move to …" button |
| HubSpot | Guided record with a timeline and tasks | Account timeline and follow-ups |
| Sales Navigator | Decision makers and why they matter | "Who to contact" with influence and the source quote |
| Simpro, Uptick, Joblogic | Discipline-specific scope and quoting | Scope questions per discipline (BS 5839 visits, panels, devices, doors…), quotation lines from scope |

## 3. What was implemented

- **Commercial memory** (`backend/app/models/crm.py`, migration `0019_salesintel_crm`). Eleven additive tables: accounts, account links, sites, contacts, drafts, activities, tasks, deal records, saved views, preferences and funnel events.
- **Identity resolution** (`backend/app/services/si_core.py`):
  - a Companies House number links records as confirmed;
  - the same name after removing legal suffixes links as unconfirmed;
  - a shared distinctive name is only suggested;
  - different company numbers are never merged;
  - sites are never inferred from names.
- **Unified Discover**: one ranked feed over radar records and prospects, with WHY NOW statements, published/inferred labels, natural-language interpretation with stated gaps, filters, saved views, and watch/dismiss. Inferred timing never outranks a published deadline.
- **Today**: a queue built from scheduled follow-ups, drafts, stalled deals and watched-account changes, each with its reason and an inline action.
- **Engage** (`backend/app/services/si_engage.py`):
  - introductions are built only from recorded evidence, with unknowns as visible gaps;
  - approval is blocked while placeholders remain;
  - a draft becomes an interaction only when the user confirms they sent it themselves;
  - do-not-contact is enforced.
- **Deals**:
  - conversion requires a confirmed requirement and freezes the origin evidence;
  - it reuses the radar and prospect promotion paths, so the legacy pipeline `Opportunity` and its finance tools stay in step;
  - values are nullable, with a basis;
  - scope has discipline-specific questions and a basis on every answer;
  - the quotation draft totals only entered quantities and rates, and estimated quantities or missing inputs block approval;
  - winning needs an approved quotation and captures a handover record.
- **Five-workspace shell** (`frontend/src/features/workspace/si-*.tsx`): Today, Discover, Accounts, Engage and Deals. The original screens remain under Tools and are linked from each lead.
- **Safety**:
  - paid AI research is refused in demo mode;
  - there is no endpoint that sends anything;
  - funnel events store an event name and day only.

## 4. The journey

1. **Discover**: search "fire alarm maintenance in Scotland". SalesIntel states what it understood and what it cannot match.
2. **Read why**: for example, "Published term ends 31 March 2027; current arrangement not confirmed". The named supplier is shown as "Reported, not necessarily today's incumbent".
3. **Investigate as account**: one click creates the account, or links to an existing one with the basis shown.
4. **The account page** shows why this customer, what we know, what still needs confirming, who to contact, sites, history and the next step.
5. **Prepare introduction**: Engage opens with the draft already written from the evidence, the best contact chosen, and the gaps listed.
6. **Approve, then log**: approve, send it from your own email, tick "I sent this message myself", then Log as sent. The follow-up is created in the same step.
7. **Today** shows the follow-up. Logging the call can complete it.
8. **Qualify into a deal** with the confirmed requirement. The deal keeps the original notice and the conversation history.
9. **Win the deal**: scope, then a quotation draft, then approval, then won with a reason. The handover record is captured automatically.

## 5. Screenshots

Captured from the running application against an isolated copy of the live database (real public procurement records, test interactions). They are not committed to the repository.

## 6. How to run the demonstration without API credit

```bash
bash scripts/living-e2e-server.sh   # demo database, synthetic fixtures, AI disabled
# open http://127.0.0.1:3100/?view=find and follow the journey above
```

The browser acceptance test runs the same journey automatically with `pnpm --dir frontend test:e2e e2e/salesintel-journey.spec.ts`.

## 7. Database and API changes

- **Migration `0019_salesintel_crm`**: additive tables `si_accounts`, `si_account_links`, `si_sites`, `si_contacts`, `si_drafts`, `si_activities`, `si_tasks`, `si_deals`, `si_saved_views`, `si_preferences`, `si_funnel_events`. Nothing existing is altered or dropped.
- **API `/api/si`**: Today, Discover (search, status, link to account, web research), accounts, suggestions and confirmed links, contacts, sites, introductions, drafts (save, approve, log), activities, tasks, deals (create, update stage, scope, quote, approve), preferences, saved views, and metrics.
- **Changed behaviour**:
  - `create_dossier` and prospect research refuse to run in demo mode;
  - interrupted prospect searches are expired;
  - the backtest's outcome dating is fixed.

## 8. Tests

| Suite | Result |
|---|---|
| Backend (pytest) | 482 passed, including acceptance tests A to E, G and H (`backend/tests/test_salesintel_journey.py`) and the backtest leakage test |
| Frontend unit (vitest) | 31 passed |
| Type check | Passed |
| Browser (Playwright) | 56 passed, 1 skipped, 1 failed, out of 58. Includes `salesintel-journey.spec.ts`: the journey on the real API, reload persistence, deduplication, demo-mode refusal of paid research, axe (WCAG 2.1 AA) on all five workspaces, and no horizontal overflow at 390px |
| Known failure | `porcelain-support.spec.ts` calls a server on port 8002 that the test configuration never starts. The spec is unchanged and the failure predates this work. |
| Environment note | After the project folder moved, `frontend/.next` kept absolute paths to the old folder, and Turbopack failed on `/classic`. Clearing that build cache fixed it. Clear it again after any future move. |

**Backtest after the leakage fix:**
- There are 18 hypotheses on record, and none has yet been followed by a notice published after it.
- The historical arms are unchanged: 26 of 257 renewals were re-procured (10.1%), and customer signals flagged 10 with 10% precision (p = 0.66).
- No predictive advantage is claimed.

## 9. Limitations and restrictions

- **Ownership and naming need a decision.** The repository contains Mitie-specific naming, the workspace label "Mitie Fire & Security", and assumptions built around Mitie. Renaming to SalesIntel does not settle who owns the work or whether it contains confidential employer information. This is a legal and product decision for you, not an engineering one.
- **No sign-in.** The app has no authentication and binds to this machine only. Do not expose it to other users until authentication, per-user data separation and hosting are designed.
- **No email or calendar integration.** Interactions are logged by hand by design. The integration boundary is the activity and draft API, so a Microsoft 365 connector would create activities through it, with approval rules, rather than sending directly.
- **Region matching is text-based.** Public notices carry a nation, not a region. Private research is matched on its location text.
- **Deduplication is deliberately conservative.** The same name links as unconfirmed, and nothing is merged automatically.
- **The quotation is a draft for internal review**, not an offer. Rates must be entered by a person.
- **Durability gaps remain.** AI Research job progress is in memory, and the live database is not under migration control (section 1).
- **The background collectors still point at the old folder.** After the project moved, the scheduled launchd workers kept running from `/Users/ross/Documents/MiSi - Mitie Sales Intelligence`. Regenerated agent files are in `.runtime/launch-agents/`; installing them needs your approval.

## 10. Next milestone

Make SalesIntel safe for a small team pilot:
- authentication and per-user ownership of accounts, tasks and drafts;
- applying migrations to the live database under Alembic;
- a durable job table for AI research;
- an approved Microsoft 365 integration that logs sent mail and meetings as activities.

After that, measure the pilot with the funnel events already being recorded: leads investigated, drafts, activities, meetings, deals and quotes.
