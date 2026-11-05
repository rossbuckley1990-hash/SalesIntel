# ADR-001: A simple multi-tenant foundation on the existing FastAPI and Next.js product

Status: accepted for Phase 1 (5 November 2026). Phase 0 audit: `docs/saas/CURRENT_STATE.md`.

## Context

SalesIntel works for one person on one Mac:
- SQLite, no sign-in, and a loopback-only request guard;
- about 30 API routers, of which only the SalesIntel loop (`/api/si`) is the product's future;
- local launch agents collecting public procurement data;
- research jobs run on in-memory threads.

The mandate is to become a secure SaaS for individual salespeople and company teams, without rewriting what works.

## Decisions

1. **Keep FastAPI, SQLAlchemy, Alembic and Next.js.** Grow the existing SalesIntel loop rather than build a second product.

2. **Identity comes from a managed provider through OpenID Connect.** SalesIntel verifies the provider's signed tokens:
   - the signature is checked against the published keys, with asymmetric algorithms only;
   - the token must carry the issuer, audience, expiry, subject and a *verified* email.

   SalesIntel stores the issuer and subject, never a password. Sign-up, multi-factor authentication, password reset and session lifetime belong to the provider.

   The recommended first provider is **Microsoft Entra ID**, configured as a multi-tenant app. UK fire and security companies largely run Microsoft 365, and Phase 4's mailbox and calendar work needs Entra anyway. Individuals without a company directory can use the provider's consumer or external-identity option.

   The code is provider-agnostic: Auth0, Clerk or WorkOS work through the same three settings.

3. **The workspace is the tenant.** A user can belong to several workspaces.
   - The browser may *choose* among its own workspaces with `X-SalesIntel-Workspace`. The server checks the membership and never trusts the id.
   - Roles: administrator, sales manager, salesperson, bid and commercial contributor, and read-only reviewer.
   - Permissions are checked on the server, on every endpoint.

4. **Isolation is enforced by the database session, not by remembering to filter.**
   - Each private table carries `organisation_id`.
   - SQLAlchemy events add the workspace filter to every read, update and delete, including `Session.get`, counts and joins.
   - Every write is stamped with the workspace. Moving a record to another workspace, or pointing at another workspace's record, is refused.
   - A session with no workspace fails closed.
   - Request sessions cannot write shared public data, and cannot touch the single-user legacy tables at all.

   This is defence in depth beneath the explicit checks already in the services. *Rejected:* separate databases or schemas per tenant, which cost too much to operate at this stage; and relying on per-query filters alone, which is error-prone.

   *Next layer:* PostgreSQL row-level security policies on the same column, as a second line of defence (planned).

5. **Shared public intelligence, private everything else.**
   - Public procurement records (`market_*`) are shared and read-only to workspaces.
   - A workspace's review of a notice, its accounts, contacts, drafts, activities, tasks, deals, quotations, research and audit trail are private.
   - Uniqueness is per workspace, so two companies can both pursue the same notice without either learning of the other.

6. **Hosted mode serves only scoped routes.**
   - With `AUTH_MODE=oidc`, only the health, version, workspace and SalesIntel APIs are mounted.
   - Each legacy tool returns only after it is scoped and tested.
   - The local single-user install (`AUTH_MODE=local`) is unchanged, so your live data and collectors are unaffected.

7. **PostgreSQL for hosting; SQLite stays local.**
   - Migrations run on both, and CI proves it.
   - Migration `0020` moves existing records into the local workspace.
   - It refuses a downgrade that would mix companies' records.
   - The live local database is not migrated without your authorisation; see `DATABASE_OPERATIONS.md`.

8. **Win probability is empirical and gated** (`services/si_assess.py`).
   - Commercial fit and win readiness are rule-based and available at once.
   - Seller confidence is kept separate.
   - A number appears only after 30 or more comparable outcomes, with at least 5 wins and 5 losses, and a time-ordered backtest that beats the workspace's base rate.

9. **Simple infrastructure** (planned, not built):
   - **Compute:** one API container, one worker container and the Next.js app, on a managed container platform in a UK or EU region.
   - **Database:** managed PostgreSQL with point-in-time recovery.
   - **Job queue:** PostgreSQL-backed, using `SELECT … FOR UPDATE SKIP LOCKED`. No Redis or Celery.
   - **Files:** S3-compatible object storage with workspace-prefixed keys and server-side encryption.
   - **Document parsing:** in a worker with no outbound network access.
   - **Errors:** Sentry for error reporting.
   - **Billing:** Stripe, at Phase 5.
   - *Rejected:* Kubernetes, Kafka and microservices. None of them solves a problem this product has yet.

## Cost estimate

These are list-price assumptions to be confirmed before committing to anything.

**AI**, at the Claude Sonnet 5.5 list price of $2 / $10 per million input / output tokens, and web search at $10 per 1,000 searches:

| Activity | Assumption | Cost per run |
|---|---|---|
| Account research (find a prospect, with sources) | 40k input, 4k output, 8 searches | about $0.20 |
| Tender pack analysis (Phase 3) | 150 pages ≈ 120k input, 10k output, plus a second validation pass | about $0.70 |
| One active salesperson per month | 40 research runs and 4 tender packs | about $11 |

- Prompt caching and the Batch API reduce these figures.
- Paid research is **off** in hosted workspaces until `RESEARCH_DAILY_LIMIT_PER_WORKSPACE` is set, and it is counted per workspace per day.

**Infrastructure**, for the first design partners (50 users or fewer):

| Item | Monthly range |
|---|---|
| Containers: API, worker, web | $20–60 |
| Managed PostgreSQL with backups | $25–70 |
| Object storage | under $5 |
| Error monitoring | $0–30 |
| Identity: Entra ID workforce sign-in into a multi-tenant app | No charge for customers using their own directory; check external-identity pricing for individuals |

That totals roughly **$75–170 a month before AI usage**. AI costs scale with use and are capped per workspace.

## Consequences

- **The isolation guarantee is structural.** A new tenant table only needs the `TenantScoped` mixin to inherit it. Tests prove it across every SalesIntel endpoint on SQLite and PostgreSQL.
- **The legacy single-user tools are unavailable to hosted workspaces** until each one is migrated: documents and requirements, the classic pipeline, dossiers and research jobs.
- **The workspace's audit log records who changed which fields.** It does not copy values, to avoid duplicating personal data.
