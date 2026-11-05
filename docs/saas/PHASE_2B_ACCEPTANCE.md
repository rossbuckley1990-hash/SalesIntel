# Phase 2B: independent acceptance report, the AI customer acquisition engine

Branch `feat/acquisition-engine`, stacked on PR #4 (`feat/saas-foundation`, still open and unmerged). Written on 5 November 2026.

Nothing was merged or deployed. The live local install, its database and its collectors were not touched.

**Verdict: CONDITIONAL PASS.** The vertical slice works end to end and is adversarially tested on synthetic, replayed data. It has not been evaluated against live sources or a real identity provider, and the ownership blocker stands.

## What is implemented

| Area | Implemented |
|---|---|
| **A. Hosted security** | Access tokens only: ID tokens are refused, and a required API scope or app role is checked. A Microsoft Entra profile adds a per-directory issuer with an allow-list, a `tid`+`oid` identity, and `xms_edov` for a verified email. Hosted mode refuses SQLite. PostgreSQL row-level security covers 19 tenant tables, with FORCE, kept in sync from the session; startup refuses a database role that bypasses it. Idempotency keys protect account, deal, quote-approval, activity, logged-send and research writes. Research jobs are durable: leases, recovery, retries with backoff, cancellation, per-call cost recording, and a per-job cost ceiling. Daily AI limits per workspace and per person are reserved atomically before any job is queued. |
| **B. Discovery** | Settings: services, territory, sectors, contract sizes, capabilities and target. Results come in five kinds: published procurement, contract ending, private signal, customer expansion and unverified candidate. Each has the six-question brief, with fit shown openly and the sourced "why now" kept apart from inferred timing. Private web research runs as a durable job. |
| **C. Contact Navigator** | Roles; four source types (the official notice, saved research, budgeted web research, and a provider adapter with none registered); deterministic validation; suppression by hash; flags for stale data, conflicting sources and people who may have moved; ranking by role relevance and evidence; and the explicit partial result. See `CONTACT_NAVIGATOR.md`. |
| **D. Experience** | Discover shows the brief and a "Find the right people" button. The account page has one ranked list of who to contact, with sources, quotes, dates, quality and use restrictions. Research status survives refreshes. From there the salesperson prepares a grounded introduction, records engagement and the follow-up, and qualifies the deal. On a phone, the Discover detail sheet opens only when chosen. |

## What was genuinely tested

**Backend** (`backend/tests/test_acquisition.py`, `test_research_restart.py`, plus earlier suites). Run on SQLite **and** on PostgreSQL 17, under row-level security as an ordinary non-superuser role:

| Proof | Test | Result |
|---|---|---|
| Public notice → verified procurement route → named lead → grounded introduction | `test_public_notice_to_a_verified_procurement_route_and_named_lead` | Pass |
| Private brief → sourced prospect → people → no fabricated contacts | `test_private_brief_to_sourced_prospect_people_and_no_fabricated_contacts` | Pass: the guessed address, the injected personal email and the directory-only name were all rejected |
| Roles-only and nothing-found results stated plainly | `test_roles_only_is_a_reported_partial_result_and_nothing_is_invented` | Pass |
| Suppression survives refresh, deletion and manual re-entry; lifting it is deliberate and audited | `test_suppression_survives_repeated_research_and_new_sources` | Pass |
| A person who moved employer; stale and conflicting provider data | `test_a_person_who_moved_employer_and_stale_or_conflicting_provider_data_are_flagged` | Pass (mock provider) |
| Research output, contacts and jobs isolated between companies | `test_research_output_contacts_and_jobs_are_private_to_their_workspace` | Pass |
| Raw SQL refused across workspaces by row-level security | `test_postgres_row_level_security_refuses_raw_sql_across_workspaces` | Pass on PostgreSQL; skipped on SQLite, which has none |
| Concurrent paid requests cannot bypass the limit | `test_spending_limits_cannot_be_bypassed_by_concurrent_requests` | Pass: 8 concurrent requests, exactly 3 accepted within 100 cents |
| A retried or concurrent write is applied once | `test_a_retried_write_is_applied_once` | Pass |
| A dead worker is recovered; retries; cancellation releases the reservation | `test_jobs_recover_from_a_dead_worker_retry_and_cancel` | Pass |
| A real API process killed mid-research, restarted, research finished | `test_research_survives_the_server_being_killed_mid_run` | Pass: 2 attempts, no duplicate contacts, the interrupted call charged at its estimate |
| ID tokens and missing scopes refused; Entra checked per directory | `test_id_tokens_and_tokens_without_the_api_scope_are_refused`, `test_entra_multi_tenant_tokens_are_checked_per_directory` | Pass, with stand-in keys |

**Totals:**
- Backend: 556 passed, 1 skipped (the RLS test on SQLite). PostgreSQL was required, as in CI.
- Procurement collector and classification tests: 160 passed. Existing collection is unaffected.
- Frontend: 35 unit tests and TypeScript pass.
- Local browser suite: 60 passed, 1 skipped (unchanged).
- Hosted browser suite: 4 of 4 passed.

**Two full browser journeys** (`frontend/e2e-hosted/acquisition.spec.ts`):
1. **Public, desktop.** Sign up and set up; Discover shows the six-question brief; the account; the research refreshed mid-run; the official procurement route, the named Head of Assets and the departmental routes, each with source and quote; a grounded introduction approved and logged as sent; the follow-up on Today; the engagement logged; a qualified deal; the assessment shows no invented probability.
2. **Private, on a phone (390 × 844).** Territory Yorkshire, sector Logistics; durable web research with a refresh mid-run; a sourced prospect plus an *unverified* candidate kept separate; the partial people result stated plainly; no fabricated contact shown; injected pages reported as rejected; a call logged; then a rival company cannot see the account, the research or the person.

**Screenshots from the running software** are in `docs/saas/screenshots/`:
- `1-discover-brief-desktop.png`
- `2-people-public-desktop.png`
- `3-deal-desktop.png`
- `4-discover-private-mobile.png`
- `5-people-private-mobile.png`

**Defects found and fixed during acceptance:**
- **Research job results.** Usage and cost were lost when a job finished.
- **Spend ledger.** A cost cut off by a crash was missing from the ledger.
- **Domain check on public accounts.** Addresses for public bodies could never be accepted because the domain was unknown. The website is now confirmed from a retrieved page that names the organisation.
- **The "why now" label.** It presented inferred timing as published.
- **Logged sends.** The key for logging a send was too short, so logging failed.
- **Mobile Discover.** The detail sheet hid the controls on a phone.
- **Account page.** Contacts were listed twice.
- **Lifting an opt-out.** It did not stick against later research.
- **Audit view.** The audit trail read without a workspace binding; row-level security correctly returned nothing.

## Not verified (external integrations)

- **The live research provider.** All research was replayed offline, and the live Anthropic path was not called. Costs below are simulated from realistic usage figures.
- **The live fetch of published notice contacts** (`NAVIGATOR_FETCH_PUBLISHED_NOTICES`). Only the replay is tested.
- **A real identity provider.** The Microsoft Entra app registration and browser sign-in (MSAL) are not done; only the verification path is tested, with stand-in keys.
- **Hunter and Apollo.** Desk review only; neither is integrated or called.

## Contact discovery coverage in the tested sample

The sample is four synthetic organisations; no real-world coverage has been measured.

| Organisation | Result | Routes |
|---|---|---|
| Example Housing Trust (public notice) | Success: official procurement contact | Procurement email and phone (official notice), the notice, a named Head of Assets (role only), assets team email and phone |
| Northgate Distribution (private research) | Partial | A named Head of Property (role only), switchboard, enquiry form. Rejected: a guessed direct email, an injected personal email, a directory-only name, and a person now at another employer |
| Quiet Fields Care | Partial: role only | None |
| Nobody Publishes Ltd | Nothing found | None |

Fabricated, guessed, personal or wrong-employer details accepted: **none.** That covers the 4 adversarial items in the Northgate research, plus a provider record placing a person at another employer, tested separately.

## AI research costs and limits

- **Prices** are list prices from the Anthropic API reference: Claude Sonnet 5.5 at $2 / $10 per million input / output tokens, and web search at $10 per 1,000 searches. An unknown model is priced at $10 / $50, so a limit is never under-counted.
- **Measured per run (simulated):** Contact Navigator $0.19 (40k input, 4.4k output, 6 searches); prospect search about $0.19. The reservations are $0.30 and $0.60, which are also the per-job ceilings.
- **Daily limits:** a hosted workspace's limit is 0 (off) until set; a local install's is $10; demo and test get $1 per workspace and $0.60 per person. The limits are atomic under concurrency, and a recovered job is charged at least its estimate.
- **Not counted:** fetching notices (free) and enrichment providers (none enabled).

## Outstanding blockers

**Security:**
- A real identity provider, plus MSAL in the browser.
- A production database role created without SUPERUSER or BYPASSRLS. The startup check enforces this.
- Secrets management, rate limiting, monitoring and backups for hosted PostgreSQL.

**Privacy:**
- A documented UK GDPR legitimate-interests assessment for B2B contact research.
- PECR checks for electronic marketing to individual subscribers and sole traders.
- A retention policy for research and contacts.
- Handling of data subject requests.
- A data protection impact assessment before any external pilot.

**Ownership:** unresolved; see `OWNERSHIP_AND_DATA_RIGHTS.md`. The repository is public. New prompts in this work use the workspace's own company name; the older prompts still name the employer.

**Merge order:** PR #4 must be decided and merged first. The live database then needs your authorised migration to `0022`.

## Next milestone

**Phase 3, the AI Win Room.** Read the customer's requirements and work out how to win.
- Upload tender documents through durable jobs.
- Extract requirements with exact file, page and clause references.
- Flag contradictions and amendments.
- Compare requirements with the recorded capabilities.
- Turn that into a source-grounded bid/no-bid recommendation and a pursuit plan.
- Build it on the Phase 2B job, spend and isolation foundations.

**In parallel (needs your decision):** connect Entra sign-in, then run a small, authorised live evaluation of research and Navigator coverage on real organisations.
