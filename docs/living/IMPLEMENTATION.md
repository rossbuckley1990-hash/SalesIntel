# MiSi Living Intelligence — implementation record

## Baseline, 24 October 2026

Inspected the supplied Next.js 16 / React 19 frontend, FastAPI / SQLAlchemy backend and selected source files in Breakout.zip. The archive is unchanged. Source-only extraction is in a temporary directory; node_modules, Git, browser profiles, generated output and macOS metadata are excluded. Existing environment-file contents are not inspected or printed; the original misi.db is not queried or modified. The demonstration uses a separate database and disables external model calls.

Executed baseline: 73 backend tests passed; 19 frontend tests passed; TypeScript check and Next.js production build passed. Backend emits an existing Starlette/httpx deprecation warning. System Git is blocked by the Xcode licence; the installed Codex Git executable works. The existing repository has no tracked source files.

Existing capability: structured OpenAI research, manual-assist import, field-level provenance, market signal conversion, buyer/competitor records, tracker imports, rule-based qualification, reports and April–March finance summaries. Public connectors are fixtures, not live feeds. Authentication/RBAC are plans, not implemented controls. Existing self-delivery supplier names are heuristic placeholders and must not be presented as verified incumbents. Existing finance tables use Float; new financial records use Numeric/Decimal without destructive conversion of original records.

## Product and implementation

The default Today surface prioritises evidence-backed actions, portfolio totals with explicit bases, approved snapshot movement and recent assets. Task-led navigation connects a semantic table view to an optional Intelligence Field. Discover searches permitted local records with provenance; new drafts retain unknown values. Explicit local review persists decisions/actions. The first working slice ends with a versioned dossier, export and outcome record.

Feature boundaries: workspace shell, Today, Discover, opportunity/evidence review, field, scenario lab, asset studio, actions/outcomes, imports. The original features remain available through a modularised classic workspace. Backend services own calculations, qualification, snapshots, assets and audit/undo. No model provider is introduced.

Visual language: graphite canvas, off-white text, green decisions, cyan evidence, amber uncertainty, red recorded risk. Large editorial hierarchy, compact tabular numbers, restrained borders, modest radius, generous spacing. 3D is only loaded in Field. Objects represent persisted IDs; edges are recorded foreign-key/entity relationships. Size maps selected non-negative financial metric through a disclosed bounded square-root scale; unknown values have a fixed outlined marker excluded from the quantitative scale. Inspection always shows exact values and provenance. Motion/drag changes presentation only.

Scenario calculations: Decimal inputs; annual revenue × delivery-cost ratios by self-delivery share; bid and mobilisation costs kept separate from gross margin; explicit probability-weighted contribution. Monthly April–March allocation conserves pennies. Saving requires an explicit action and never overwrites the source opportunity. LE1 remains the existing service pending Finance approval of definitions.

## Validation and rollout boundaries

Tests cover the complete persisted workflow, asset formats/content, arithmetic, import preview/commit, duplicate/stale review protection, undo, unknown values and snapshot differences. Browser checks cover daily use, keyboard/reduced motion, WebGL fallback, repeated mounts, resizing and exports. Production readiness requires Entra ID, server roles, trusted actor identity, PostgreSQL migration/restore tests, approved finance definitions, managed secrets, connector approval and security review. Local review records are explicitly unauthenticated and are not enterprise approvals.
