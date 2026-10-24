# MiSi Security

MiSi will handle sensitive internal commercial data for Mitie Fire & Security. Even during prototype work, the system should be designed as if pipeline values, buyer intelligence, competitor intelligence, finance forecasts, and pursuit recommendations are confidential.

## Security Principles

- Frontend code must never contain OpenAI API keys.
- All OpenAI calls must go through the backend.
- Internal commercial data is sensitive by default.
- Sample data must remain synthetic.
- Source connectors must follow source terms and permissions.
- AI output must be validated before display or persistence.
- Users should be able to see why an insight was generated.
- Access control, audit logging, and data retention should be designed before internal pilot use.

## Current MVP Hardening Controls

Implemented controls in the local MVP:

- `.env` and `.env.*` are ignored; `.env.example` contains placeholders only.
- The frontend reads only `NEXT_PUBLIC_API_BASE_URL`; OpenAI credentials are not used in browser code.
- CORS defaults are restricted to `http://localhost:3000` and `http://127.0.0.1:3000`, and wildcard origins are rejected by settings validation.
- Tracker uploads are limited to CSV/XLSX extensions, recognised CSV/XLSX content types, and a configurable 5MB default size limit before parsing.
- OpenAI-backed endpoints return structured validation errors and do not return raw prompts to the frontend.
- Internet intelligence scans use backend-only OpenAI web search and return source-attributed structured findings for review.
- Public-source connector output stores `source_type`, `source_url`, and a source attribution note on imported market signals.
- Source connector run history stores connector name, timestamps, status, record counts, and errors.

Prototype limitations that still need resolution before internal pilot:

- No authentication, authorization, or user-level audit logging is implemented yet.
- Local SQLite databases are unencrypted files on the developer machine.
- Uploaded source files are parsed into records only; a formal raw-file retention policy is not implemented.

The enterprise authentication, RBAC, audit logging, PostgreSQL, and secure deployment plan is documented in `docs/ENTERPRISE_DEPLOYMENT.md`. That document is planning guidance only; it does not indicate that authentication is active in the current MVP.

## Why OpenAI Keys Must Not Be In Browser Code

Browser code is public to the user and inspectable by design. Anything shipped to the frontend can be viewed through developer tools, downloaded JavaScript bundles, source maps, network requests, or browser extensions.

If an OpenAI API key is placed in frontend code, it can be extracted and misused. That creates several risks:

- Unauthorized API usage and unexpected cost.
- Exposure of prompts or sensitive commercial context.
- Loss of control over which data is sent to OpenAI.
- Inability to enforce server-side validation and audit logging.
- Difficulty rotating keys without breaking deployed clients.
- Potential breach of internal security policy.

The backend must be the only component that reads `OPENAI_API_KEY`. The frontend should request analysis from MiSi backend endpoints, and the backend should decide what context is allowed to be sent.

## Secret Handling

Secrets include:

- `OPENAI_API_KEY`
- Database credentials once PostgreSQL is used
- Tender source API keys
- Internal integration credentials
- Session signing keys
- OAuth client secrets

Rules:

- Do not commit secrets.
- Keep `.env.example` placeholder-only.
- Use local `.env` for developer secrets.
- Use a managed secret store for deployed environments.
- Rotate exposed or suspected-exposed credentials immediately.
- Do not log secrets, prompts containing unnecessary sensitive data, or raw source payloads with confidential content.

## Data Classification

### Public

Examples:

- Public tender notices where terms allow use.
- Public buyer organization names.
- Public procurement dates and URLs.

Public data still needs source attribution and terms-aware handling.

### Internal Sensitive

Examples:

- Sales pipeline values.
- Win probability.
- Forecast scenarios.
- Bid/no-bid recommendations.
- Self-delivery capacity assumptions.
- Competitor strategy notes.
- Executive action plans.

This data should require authenticated access once auth exists.

### Personal Data

Examples:

- Buyer contact names.
- Email addresses.
- Phone numbers.
- Role details tied to a person.

Personal data should only be stored where there is a clear lawful and business basis. Retention and access rules must be reviewed before scaled use.

## OpenAI Data Controls

All OpenAI calls should be made through backend services that:

- Minimize data sent to only what the task needs.
- Use structured JSON schemas for outputs.
- Validate model responses before storage or display.
- Store prompt version, model, timestamp, and linked source IDs.
- Avoid sending secrets or unnecessary personal data.
- Make confidence and evidence visible.
- Keep internet research query-driven and source-attributed rather than uncontrolled scraping.

AI output should never silently overwrite source-of-truth commercial data. It should create a recommendation, classification, summary, or action candidate that can be reviewed.

## Source Connector Security

Connectors must:

- Respect source terms of use.
- Avoid scraping that violates site terms.
- Store source attribution, source URL where available, and retrieval timestamps or connector run timestamps.
- Store retrieval timestamps.
- Avoid bypassing access controls.
- Use licensed APIs where required.
- Rate-limit requests.
- Clearly mark connector errors and stale data.

Connector output should be treated as untrusted until normalized and validated.

## Frontend Security Expectations

The frontend should:

- Read only `NEXT_PUBLIC_*` environment variables.
- Avoid exposing backend internals.
- Avoid storing sensitive data in local storage.
- Render AI and source content safely.
- Avoid injecting raw HTML from source connectors or AI output.
- Show confidence, risk, evidence, and recommended action clearly.

## Backend Security Expectations

The backend should:

- Own authentication and authorization when added.
- Enforce role-based access to sensitive modules.
- Validate all inputs.
- Validate all AI outputs.
- Sanitize uploaded files.
- Restrict accepted upload file types.
- Store upload metadata and import status.
- Log security-relevant actions.
- Avoid returning secrets or excessive internal data to the frontend.

## Upload Security

CSV/XLSX ingestion should:

- Restrict file size before parsing.
- Restrict filename extensions and content types.
- Treat uploaded files as untrusted.
- Validate headers and row types.
- Avoid executing formulas or macros.
- Store raw files only when there is a defined retention policy.
- Produce clear import errors.

## Audit Logging

Before internal pilot, MiSi should record:

- User login and logout events.
- File uploads.
- Connector runs.
- AI analysis requests.
- Bid/no-bid decision changes.
- Forecast changes.
- Executive action creation and completion.
- Permission changes.

Audit records should include actor, timestamp, action, target entity, and relevant metadata.

## Minimum Security Gates By Stage

### Prototype

- No real secrets committed.
- Backend-only OpenAI keys.
- Synthetic data only unless explicitly approved.
- Basic input validation.

### MVP

- Controlled local environment.
- Auth plan documented.
- Upload validation.
- Source attribution.
- AI JSON validation.

### Internal Pilot

- Authentication.
- Role-based access.
- Audit logging.
- Secret manager.
- Data retention rules.
- Security review of personal data.

### Scalable Webapp

- Production-grade hosting security.
- PostgreSQL with managed backups.
- Monitoring and alerting.
- Formal incident response.
- Regular dependency and vulnerability review.
