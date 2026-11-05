# SalesIntel 3.0: release status, security and privacy checklist

Updated on 5 November 2026 for the first SalesIntel 3.0 pull request.

**Status key**
- **Implemented**: in the code.
- **Tested**: proven by an automated test that would fail without it.
- **Blocked**: needs a decision, credentials or access I do not have.
- **Planned**: not started.

## Phase verdicts

| Phase | Verdict | Evidence | Conditions |
|---|---|---|---|
| **0. Baseline and architecture** | **VERIFIED PASS** | `CURRENT_STATE.md`: baseline re-run, existing migrations proven on PostgreSQL 17. `ADR-001`. `OWNERSHIP_AND_DATA_RIGHTS.md`. | — |
| **1. Secure multi-user foundation** | **CONDITIONAL PASS** | `test_tenancy.py`, `test_tenancy_migration.py`, `test_assessment.py` on SQLite **and** PostgreSQL; `e2e-hosted/team-journey.spec.ts`. | 1. No real identity provider is connected yet: the production path is tested with a stand-in key set, not a live provider. 2. PostgreSQL row-level security is not yet added as a second layer. 3. Legacy single-user tools are not served to hosted workspaces. 4. Your live local database needs your authorisation to be migrated to `0020`. |
| **2. First acquisition loop, signed in** | **CONDITIONAL PASS** | Browser test: sign up, create a workspace, set services, territory and target, discover a sourced public notice, open the account, prepare a grounded introduction, approve it, log it as sent, follow up on Today, log the conversation, qualify, create the deal. Then assess it, see no invented probability, and confirm persistence after reload. A second company sees none of it. | Contact enrichment providers are not integrated. Research does not run in hosted workspaces until an allowance is set, and its jobs are not durable. The Territory Autopilot is not built. |
| **3. AI Win Room** | **NO-GO** (not started) | The rule-based fit, readiness and gated probability are the base it will build on. | Document intelligence is still single-user legacy code. |
| **4. Advanced acquisition** | **NO-GO** (not started) | — | — |
| **5. Commercial readiness** | **NO-GO** (not started) | — | The ownership decision comes first. |

## Security and privacy checklist

| Control | Status | Where |
|---|---|---|
| Managed authentication: OIDC tokens verified for signature, asymmetric algorithm, issuer, audience, expiry and verified email | Implemented, tested | `app/auth.py`; forged, unsigned, HS256, expired, wrong-issuer, wrong-audience and impostor-key tokens are all refused |
| No passwords stored; multi-factor authentication, reset and sessions handled by the provider | Implemented by design | `models/tenancy.py:User` |
| Development sign-in impossible outside demo and test | Implemented, tested | `Settings.check_safe_to_serve`; `/api/dev/session` exists only in dev mode |
| Connecting a real provider, such as a Microsoft Entra app registration | **Blocked** | Needs your tenant, app registration and redirect URLs |
| Workspaces, memberships, five roles, permissions checked on the server | Implemented, tested | `app/tenancy.py:PERMISSIONS`; the reviewer, salesperson, contributor and manager cases |
| Browser-supplied workspace id treated as a choice, checked against membership | Implemented, tested | A spoofed header gets 403 |
| Every private record scoped by `organisation_id`: reads, `get`, counts, writes, references | Implemented, tested | 22 cross-tenant attacks on SalesIntel endpoints all get 404; session-level refusal tests |
| Fail closed without a workspace; hosted sessions cannot reach legacy tables or write public data | Implemented, tested | `test_the_session_itself_refuses_unscoped_or_foreign_access` |
| Hosted mode mounts only scoped routes | Implemented, tested | `test_hosted_mode_exposes_only_tenant_scoped_routes` |
| Quotation approval needs permission, records the approver's identity, and the deal owner cannot approve | Implemented, tested | `test_roles_are_enforced_by_the_server` |
| Invitations single-use, bound to one email, expiring, stored only as a hash | Implemented, tested | `test_invitations_cannot_be_misused` |
| Audit trail of who changed what, without copying values, per workspace | Implemented, tested | `si_audit_events` |
| Paid research off by default and capped per workspace per day | Implemented, tested | `RESEARCH_DAILY_LIMIT_PER_WORKSPACE`; 429 with no call made |
| PostgreSQL migrations, backfill into the local workspace, schema parity, downgrade guard | Implemented, tested | `test_tenancy_migration.py`; CI runs both databases |
| PostgreSQL row-level security as a second layer | Planned | — |
| Durable research jobs, retries and per-workspace cost accounting | Planned | — |
| Encrypted secrets, file storage with workspace prefixes, sandboxed parsing | Planned | ADR-001 decision 9 |
| Rate limiting, monitoring and error reporting, backups and restore drills | Planned | `db_preflight.py` covers local SQLite only |
| UK GDPR and PECR: lawful-basis record, retention, subject requests, data protection impact assessment, shared suppression | Planned | Per-contact opt-out and draft suspension exist (PR #3) |
| Billing and entitlements | Planned | — |
| Ownership and IP decision | **Blocked: your decision** | `OWNERSHIP_AND_DATA_RIGHTS.md` |
| Deployment to production | **Not authorised; not done** | — |

## Acceptance challenges A to D

| Challenge | Covered now | Not yet |
|---|---|---|
| **A. Public tender pursuit** | Contract and buyer identified from a sourced notice; the record is preserved privately in the workspace | Document pack ingestion, requirement extraction with page references, contradictions, a defensible bid or no-bid, a pursuit plan (Phase 3) |
| **B. Private new business** | Evidence-backed reason, account dossier, a grounded draft saved but never sent, contact and follow-up tracking, qualification, deal, history preserved, isolation proven | Stakeholder role discovery and verified contact routes through providers (Contact Navigator) |
| **C. Commercial integrity** | Scope changed after approval; missing pricing; duplicate accounts; the wrong person approving; invalid probability assumptions (gated); replayed invitations; cross-workspace references | Idempotency keys for retried writes; cancelled and restarted research; conflicting document amendments |
| **D. Contact safety** | Suppressed drafts; no verified email (role-only routes); another workspace requesting contacts | A provider returning stale or conflicting data; a contact changing employer; prompt-injection tests on research sources |

## Next milestone: Phase 2b, "Pilot-ready acquisition loop"

This is a single phase whose end state can be shown to two or three real salespeople at an authorised design-partner business.

1. **Real sign-in.** Microsoft Entra ID multi-tenant app registration and MSAL in the browser. Your setup decision is required.
2. **Durable research.** A PostgreSQL job table with retries, cancellation, per-workspace token and search accounting, and the allowance enforced at the worker.
3. **Contact Navigator v1:**
   - likely roles for each opportunity, labelled as roles, not people;
   - a provider-agnostic enrichment interface with the five-level contact quality model;
   - published-source discovery first;
   - no paid provider until its licence, data sources and permitted use are verified.
4. **PostgreSQL row-level security** policies, and idempotency keys on write endpoints.
5. **A hosted staging environment**, private and with no customer data, only after you authorise the ownership path and the deployment.
