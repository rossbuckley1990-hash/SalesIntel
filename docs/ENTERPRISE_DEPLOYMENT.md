# SalesIntel Enterprise Authentication And Deployment Plan

This document describes how SalesIntel should move from a local MVP into a secure internal web application for Mitie Fire & Security.

Status: planning only. Authentication, authorization, production deployment automation, and user-level audit logging are not implemented in the current MVP. Do not treat the local demo as secure for real confidential data.

## Executive Summary

SalesIntel will hold commercially sensitive sales, tender, finance, buyer, competitor, self-delivery, and AI-generated decision-support data. Before internal pilot use with real data, SalesIntel should add:

- Microsoft Entra ID login for single sign-on.
- Backend-enforced role-based access control.
- User-level audit logs for material actions.
- PostgreSQL as the production database.
- Managed secrets, private networking, backups, monitoring, and incident response.
- Deployment controls that keep OpenAI keys, database credentials, and source connector credentials out of browser code.

The frontend should remain a presentation and workflow surface. The FastAPI backend should remain the policy boundary for secrets, data access, AI calls, import validation, connector execution, audit logging, and commercial decision logic.

## Data Sensitivity

SalesIntel data should be classified as internal sensitive by default.

Examples of sensitive commercial data:

- Pipeline values, weighted values, probability, and stage movement.
- Bid/no-bid recommendations and pursuit rationale.
- Buyer intelligence, relationship status, procurement drivers, and pain points.
- Competitor assessments, pricing behaviour, weaknesses, and counter-strategies.
- Self-delivery capture opportunities, leakage risks, and displaced supplier notes.
- LE1-style finance forecasts, margin assumptions, risk adjustments, and warnings.
- Executive actions, owners, deadlines, escalation reasons, and commercial value.
- AI prompts, structured AI outputs, prompt metadata, and linked source records.

Examples of personal or role-identifying data:

- Internal user names, roles, owners, and approvers.
- Buyer contact names or role details if stored later.
- Audit log actor identifiers, IP addresses, user agents, and timestamps.

Security implications:

- Real internal data should not be uploaded into an unauthenticated local demo.
- Access should be granted by business need, not by application availability.
- Finance and bid recommendations should be auditable because they can influence commercial decisions.
- AI analysis should never silently become the source of truth. It should remain decision support with traceability.

## Target Enterprise Architecture

```text
User browser
  |
  | HTTPS, Entra ID sign-in
  v
Next.js frontend
  |
  | Bearer token from Entra ID
  v
FastAPI backend
  |-- JWT validation and role checks
  |-- Application services
  |-- Upload ingestion
  |-- Source connector jobs
  |-- OpenAI or Azure OpenAI calls
  |-- Audit logging
  |
  v
PostgreSQL production database

Managed services:
  - Microsoft Entra ID
  - Azure Key Vault or equivalent secret store
  - Azure Database for PostgreSQL Flexible Server or equivalent
  - Azure Blob Storage for approved retained uploads, if needed
  - Application Insights / Log Analytics or equivalent observability
```

Recommended Azure-aligned deployment:

- Frontend: Azure Static Web Apps, Azure App Service, or containerized Next.js behind HTTPS.
- Backend: Azure App Service, Azure Container Apps, or AKS if platform standards require Kubernetes.
- Database: Azure Database for PostgreSQL Flexible Server with backups, private access, and encryption at rest.
- Secrets: Azure Key Vault accessed through managed identities where possible.
- Logs and metrics: Application Insights and Log Analytics, with export to the corporate SIEM if required.
- File storage: Azure Blob Storage with private containers if raw upload retention is approved.

## Microsoft Entra ID Login Plan

SalesIntel should use Microsoft Entra ID (formerly Azure AD) for internal single sign-on.

Recommended flow:

1. Register a SalesIntel frontend application in the Mitie Entra tenant.
2. Register or expose a SalesIntel backend API application with a stable audience.
3. Use Authorization Code with PKCE for browser login.
4. The frontend obtains an access token for the SalesIntel API.
5. The frontend sends the access token to the backend in the `Authorization: Bearer <token>` header.
6. The backend validates token signature, issuer, audience, expiry, tenant, and required claims using the Entra JWKS endpoint.
7. The backend maps group or app role claims to SalesIntel application roles.
8. The backend enforces authorization on every protected endpoint.

Implementation options:

- Frontend: Auth.js / NextAuth with Microsoft Entra provider, or MSAL browser if Mitie standards prefer Microsoft libraries.
- Backend: FastAPI dependency that validates JWTs using Entra discovery metadata and JWKS.
- Role source: Entra app roles are preferred for clean application permissions. Entra security groups can also work if group claim size and nested group behaviour are understood.

Important rules:

- Do not place Entra client secrets in frontend code.
- Do not trust frontend-only role checks.
- Do not accept unsigned or locally decoded tokens.
- Do not implement local password login for internal users unless there is an explicit security exception.
- Do not add partial auth gates that create a false sense of protection.

Future configuration names may include:

```text
ENTRA_TENANT_ID=
ENTRA_CLIENT_ID=
ENTRA_API_AUDIENCE=
ENTRA_ISSUER=
ENTRA_JWKS_URL=
SESSION_SECRET=
```

These are not required for the current local MVP and should only be added when auth is actually implemented.

## Role-Based Access Plan

Authorization must be enforced in the backend. The frontend may hide controls for clarity, but hidden buttons are not security.

### Initial Roles

| Role | Purpose | Typical access |
| --- | --- | --- |
| Admin | Operate SalesIntel and manage secure configuration | Manage users and roles, source connectors, settings, import controls, audit views, and system health |
| Sales User | Own and progress pipeline opportunities | Read dashboards, edit assigned opportunities, upload controlled trackers if permitted, run opportunity analysis, create executive actions |
| Finance User | Review LE1 forecast, margin, and risk-adjusted revenue | Read pipeline and finance views, edit or approve forecast assumptions, export finance review packs, view finance warnings |
| Read-Only Executive | Consume board-level command centre outputs | Read dashboards, reports, opportunity detail, leadership briefing, finance forecast, self-delivery summary, and executive actions |

Optional later roles:

- Bid Manager: manage tender workflow, bid/no-bid evidence, deadlines, clarifications, and submission readiness.
- Commercial Manager: review margin, contract risk, pricing assumptions, and commercial mitigations.
- Connector Operator: manage source refreshes without broader admin privileges.

### Permission Model

Use deny-by-default permissions. Suggested permission groups:

- `dashboard:read`
- `opportunity:read`
- `opportunity:write`
- `opportunity:analyse`
- `tracker:upload`
- `market_signal:read`
- `market_signal:refresh`
- `buyer:read`
- `buyer:write`
- `competitor:read`
- `competitor:write`
- `finance:read`
- `finance:write`
- `executive_action:read`
- `executive_action:write`
- `report:export`
- `admin:manage_users`
- `admin:manage_connectors`
- `audit:read`

Suggested role mapping:

| Permission | Admin | Sales | Finance | Read-only executive |
| --- | --- | --- | --- | --- |
| Dashboard and reports | Yes | Yes | Yes | Yes |
| Opportunity read | Yes | Yes | Yes | Yes |
| Opportunity write | Yes | Assigned or permitted sectors | No, unless approved | No |
| Run opportunity AI analysis | Yes | Yes | Yes for finance-relevant opportunities | Optional read-only action with audit |
| Tracker upload | Yes | Controlled permission | No | No |
| Market refresh | Yes | Controlled permission | No | No |
| Finance forecast write | Yes | No | Yes | No |
| Executive actions write | Yes | Yes | Yes | No |
| User and role admin | Yes | No | No | No |
| Audit log read | Yes | Limited if approved | Limited finance events if approved | No by default |

## Audit Logging Plan

SalesIntel should add append-only audit records before any internal pilot with real data.

Audit records should include:

- `id`
- `timestamp`
- `actor_user_id`
- `actor_upn`
- `actor_display_name`
- `actor_roles`
- `action`
- `entity_type`
- `entity_id`
- `outcome`
- `reason`
- `request_id` or correlation ID
- `source_ip`
- `user_agent`
- `before_hash` or redacted before summary where appropriate
- `after_hash` or redacted after summary where appropriate
- `metadata_json`

Events to audit:

- Login success and failure where available.
- Token validation failure and access denied events.
- User and role changes.
- Tracker uploads, rows imported, rows skipped, and validation failures.
- Source connector refreshes and source-run errors.
- Opportunity create, update, stage change, owner change, and bid/no-bid change.
- AI opportunity analysis requests and validation failures.
- Leadership briefing generation.
- Finance forecast assumption changes.
- Executive action creation, update, completion, and overdue changes.
- Executive report exports.
- Admin settings changes.

Audit design principles:

- Append-only by application convention.
- Redact secrets and unnecessary personal data.
- Store enough metadata to explain who did what and why.
- Keep raw prompts out of normal frontend responses.
- Make audit retention explicit before production.
- Export security-significant events to the central logging or SIEM platform if required.

## Production Database Plan

SQLite remains appropriate for the local demo. PostgreSQL should be used for internal pilot and production.

PostgreSQL requirements:

- `DATABASE_URL` controls the runtime database connection.
- Use SQLAlchemy models that avoid SQLite-only behaviour.
- Use the `psycopg` driver for PostgreSQL connections.
- Add Alembic migrations before real data is introduced.
- Use managed PostgreSQL with encryption at rest.
- Use private networking where the deployment platform supports it.
- Use least-privilege database credentials.
- Enable automated backups and point-in-time restore.
- Test restore procedures before production go-live.
- Add connection pooling appropriate to the hosting model.
- Separate dev, test, staging, and production databases.

Recommended migration path:

1. Keep SQLite for local development and demo workflows.
2. Add Alembic migrations from the current SQLAlchemy model state.
3. Provision a staging PostgreSQL database.
4. Run seed data and test suites against PostgreSQL in CI.
5. Validate imports, dashboard aggregation, finance forecast, AI storage, and report export against PostgreSQL.
6. Switch internal pilot environments to PostgreSQL only.

## Secure Deployment Plan

### Environments

Use separate environments:

- Local: developer-only, synthetic data by default, SQLite allowed.
- Development: shared engineering environment, synthetic or approved test data.
- Staging: production-like controls and masked data where possible.
- Production: real data, Entra ID, RBAC, audit logs, PostgreSQL, backups, monitoring, and support process.

### Secrets

Store secrets in a managed secret store, not in Git or browser-accessible variables.

Production secrets may include:

- `OPENAI_API_KEY` or Azure OpenAI credentials.
- PostgreSQL credentials if managed identity is not available.
- OAuth or Entra client secrets for confidential backend flows.
- Source connector credentials.
- Session signing secrets if server-side sessions are used.

### Network And HTTP Controls

Production should enforce:

- HTTPS only.
- HSTS.
- CORS restricted to the production frontend origin.
- Security headers including CSP, `X-Content-Type-Options`, and frame protections appropriate to the hosting model.
- Backend API not directly exposed beyond required routes if an application gateway or API gateway is available.
- Private database access.
- Rate limiting on upload, AI, auth-sensitive, and connector-trigger endpoints.

### CI/CD Controls

Deployment pipeline should include:

- Backend tests.
- Frontend type checks and tests.
- Dependency vulnerability scanning.
- Secret scanning.
- Container image scanning if containers are used.
- Database migration dry-run for staging.
- Manual approval gate for production.
- Versioned release notes and rollback plan.

### Observability

Production monitoring should include:

- Request latency and error rate.
- Dashboard endpoint latency.
- Upload failures and validation error trends.
- Connector run success, failure, and stale-source warnings.
- OpenAI or Azure OpenAI call failures and invalid JSON responses.
- Finance forecast calculation errors.
- Authentication failure rates and access-denied events.
- Database connection pool pressure.

Alerts should route to the agreed service owner, with escalation for repeated connector failures, backend errors, and auth anomalies.

## AI And Data Governance

AI calls must remain backend-only.

Controls to add before internal pilot:

- Prompt templates versioned in code.
- Structured JSON schemas for all AI outputs.
- Output validation before persistence.
- Model name and prompt version stored with analysis results.
- User, timestamp, and source record IDs stored for AI-triggered actions.
- Minimal required context sent to the model.
- No secrets, raw credentials, or unnecessary personal data in prompts.
- Clear UI distinction between source facts, rule-based scoring, and AI recommendations.

If corporate policy prefers Azure OpenAI, keep the service wrapper abstract enough to swap providers without exposing credentials to the frontend.

## Source Connector Governance

Public and internal connectors should follow the same governance model:

- Approved source list.
- Source terms or licence note.
- Connector owner.
- Last checked timestamp.
- Source URL or attribution.
- Records found and records imported.
- Error history.
- Rate limits and backoff.
- No scraping that violates source terms.

Connectors that require credentials should use the backend secret store only.

## Rollout Plan

### 1. Secure MVP Foundation

- Add Entra ID app registrations.
- Add backend JWT validation.
- Add role and permission model.
- Add audit log table and audit service.
- Add Alembic migrations.
- Add PostgreSQL staging database.
- Add production-ready CORS and security headers.

### 2. Internal Pilot

- Map Entra users, groups, or app roles to SalesIntel roles.
- Restrict pilot access to approved users.
- Use approved internal test or pilot data.
- Enable audit logging for imports, AI analysis, finance changes, and exports.
- Validate LE1 and forecast definitions with Finance.
- Run backup and restore tests.
- Review personal data handling before buyer contact storage.

### 3. Production Readiness

- Complete security review.
- Complete dependency and container scanning.
- Confirm data retention and audit retention policy.
- Configure monitoring alerts and support ownership.
- Complete incident response and rollback runbooks.
- Perform performance testing against expected data volumes.
- Complete a restore drill from production-style backup.

### 4. Scalable Webapp

- Move long-running imports, connectors, and AI jobs to background workers.
- Add scheduled connector runs.
- Add report scheduling.
- Add saved views and user preferences.
- Add data quality dashboards.
- Add formal change management for rules, prompts, and forecast logic.

## Implementation Checklist For Future Auth Work

Do this when auth implementation begins:

- Add a backend auth module with Entra discovery and JWT validation.
- Add a user/role mapping model or Entra app-role mapping config.
- Add FastAPI dependencies for `require_user` and `require_permission`.
- Add tests for missing token, invalid token, expired token, wrong audience, and missing role.
- Add route-level permissions to sensitive endpoints.
- Add audit middleware or service calls for material actions.
- Add frontend login/logout and authenticated API client handling.
- Add a clear unauthorized and forbidden UI state.

Do not do this:

- Do not add fake login forms.
- Do not use static shared passwords.
- Do not rely on frontend-only route protection.
- Do not commit Entra secrets or database credentials.
- Do not enable production access to SQLite.
- Do not widen CORS to `*`.
- Do not log raw access tokens, OpenAI keys, prompts with unnecessary sensitive data, or database URLs with credentials.

## Definition Of Done For Enterprise Pilot

SalesIntel should not enter an internal pilot with real sensitive data until:

- Entra ID login works.
- Backend role checks protect sensitive endpoints.
- Audit logging captures material actions.
- PostgreSQL is used outside local development.
- Secrets are in a managed secret store.
- Backups and restore have been tested.
- CORS and security headers are production-specific.
- AI calls remain backend-only.
- Upload limits and validation remain enforced.
- Source attribution is stored for imported public-market data.
- Security and data owners agree the pilot data set is appropriate.
