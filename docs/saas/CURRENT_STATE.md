# SalesIntel current-state audit (Phase 0)

Verified on 5 November 2026 against `main` at `897aaaf`, which merged PRs #1, #2 and #3. Facts were checked by running the code, not read from earlier reports.

## Baseline

| Area | What exists | Verified how |
|---|---|---|
| Backend | FastAPI, SQLAlchemy 2, Alembic, 31 routers. Python 3.14. | 502 backend tests passed on `main` in an isolated worktree. |
| Migrations | 19 revisions, `0001` to `0019`. | They apply from scratch on SQLite **and on PostgreSQL 17** (60 tables). |
| Frontend | Next.js 16, React 19, Tailwind with `ds-*` design tokens. The SalesIntel workspaces are Today, Discover, Accounts, Engage and Deals; there are also about 20 "classic" tools. | 35 unit tests pass; 60 browser tests pass, 1 skipped. |
| Public procurement | Collectors for Find a Tender, Contracts Finder and Public Contracts Scotland, the renewal radar and a back-catalogue fill. They run as local macOS launch agents writing to SQLite. | Read-only check: all five agents run from the new folder, with recent successes recorded. |
| Private research | `prospect_research`: AI web research through OpenAI or Anthropic. Every finding needs a cited source, and contacts are only those published. | Covered by tests. **Jobs run on in-memory threads** and stop if the app restarts. |
| Accounts and CRM | `si_*` tables: accounts, links to their sources, sites, contacts, drafts, activities, tasks, deals, saved views and preferences. | Acceptance tests A to H, plus the PR #3 hardening. |
| Contacts | Each contact carries its basis (published or entered by a user), a source URL and quote, and a status (unverified, verified or do not contact). Opt-outs suspend drafts. | Covered by tests. **No enrichment provider is integrated.** |
| Documents and requirements | Legacy "living" tools: upload, requirements, decisions and assets. | Single-user, with no tenant scope. |
| Quotation and money | Exact decimals, approvals superseded when inputs change, won deals locked. | PR #3 tests. |
| Security | Loopback-only guard, Host and Origin checks, reset protection. | PR #3 tests. **No sign-in, single user only.** |
| CI | Backend, frontend and Playwright jobs on pull requests. | Green on `897aaaf`. |

## What can be reused rather than rebuilt

- The SalesIntel loop: services, router and the five workspaces. It became multi-tenant without rewriting a single endpoint.
- Public procurement connectors and the relevance classifier. They are shared, read-only public intelligence.
- The research engine, its evidence rules and the contact basis model.
- Exact money, the quotation lifecycle, suppression and the database preflight tools.

## Limitations found

1. Single-user legacy routers keep records without a workspace. Phase 1 does not serve them to hosted workspaces.
2. Research jobs are not durable.
3. The live SQLite database is not under Alembic (stamp-safe at `0019`).
4. The live install's `.venv/bin/pip` script still points at the pre-rename folder. Use `python -m pip` instead.
5. Ownership and confidentiality are unresolved, and the repository is public. See `OWNERSHIP_AND_DATA_RIGHTS.md`.
