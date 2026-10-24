# Executed verification — 24 October 2026

All application and document checks below used invented fixture data in isolated SQLite databases. No original commercial database was used. Browser tests start a fresh guarded demo database under `.runtime/e2e-*` and bind to loopback ports 3100/8011.

| Check | Executed result |
| --- | --- |
| Baseline backend | 73 tests passed before changes |
| Baseline frontend | 19 tests passed before changes |
| Final backend | 107 tests passed; original Starlette/httpx deprecation warning remains |
| Frontend unit suite | 27 tests passed |
| Playwright end-to-end | 12 tests passed in the final complete run |
| TypeScript | `tsc --noEmit` passed |
| Production compilation | Next.js production build passed; `/`, `/classic` and not-found generated |
| Production smoke | Compiled app served HTTP 200 on loopback; Today and actual WebGL field loaded without browser errors; 390px viewport had no page overflow |
| PDF/Word | Dossier and business case exported as nonempty files, rendered and visually inspected; Word source-register spacing and row pagination corrected |
| Excel | LibreOffice Calc recalculated the exported scenario: £248,000→£314,000 GM, £136,800→£165,600 expected contribution, £28,800 difference; no formula errors |
| Forecast reconciliation | Revenue difference £0.00; margin difference −£0.01 from legacy monthly rounding, within disclosed £0.02 tolerance |
| Secret pattern scan | No credential-pattern matches in the 63 scanned new/changed source files; no environment file contents were inspected or printed, and the original database was not queried |
| Git hygiene | Explicit source staging, ignored databases/runtime/exports, `git diff --check` clean |

## Browser coverage

Playwright exercises the four required journeys through real APIs and persistence: A question to evidence, local decision, dossier and three file downloads; B reversible scenario to saved business case; C actual snapshots to leadership briefing; D risk investigation to an owned action with completion evidence. Additional checks cover reviewed CSV import and audit undo, live scenario morphing with the same canvas, editable Excel download, exact-line tender extraction/capture, outage retry, classic finance and buyer views, and context transfer from Field to Finance and My Work.

Axe WCAG 2 A/AA and 2.1 AA scans pass on Today, Opportunities, Finance, My Work, Assets, Outcomes and the field data view. Native dialog keyboard/Escape and command navigation are exercised. These automated checks are not a substitute for a complete screen-reader usability audit.

The WebGL checks mount/unmount repeatedly, resize, force actual context loss, validate the data fallback and check resource counts. The same graph retains stable texture/geometry counts; unmount returns active engines to zero and frames stop. Reduced-motion defaults to records; explicit 3D sleeps after initial layout and wakes for keyboard interaction. Waiting for the selected evidence and fonts avoids measuring legitimate initial layout as an animation loop.

Longer rendering revealed and fixed a duplicate RAF scheduling issue during adaptive-quality resize. The corrected production smoke recorded zero duplicate frames, 31 textures/17 geometries for the 13-record focus scene, adaptive quality 0.85 and approximately 32–36 FPS in headless Chromium. Test scenes with an added decision action contain 32 textures/18 geometries. Repeated-mount samples vary with machine load; they are diagnostics, not a device benchmark. A physical Apple Silicon 60 FPS target is **not certified**. The accessible view is fully usable without WebGL.

## Backend coverage

Tests include decimal arithmetic, zero/invalid/nonfinite assumptions, fiscal-year boundaries and penny conservation; the complete signal-to-outcome slice; all eight asset types and PDF/DOCX/XLSX generation; long tender-row PDF pagination; version persistence; missing values; evidence reviews; source-preserving imports, XLSX mapping, duplicates, percentage limits, stale previews and unspecified-update preservation; prerequisite cycles and completion gating; durable completion evidence; snapshot differences; atomic undo and stale-record conflict protection; production-mode refusal; inert spreadsheet formula strings; fresh Alembic upgrades, idempotency and downgrade with legacy tables retained.

PostgreSQL migration execution, concurrent multi-user races, external live connectors, Entra ID, role enforcement and production infrastructure remain unverified and are deployment gates. Existing legacy financial Float columns and finance semantics have not been certified for enterprise reporting.

## Reproduce

Stop another development server in this checkout before running browser tests.

```sh
.venv/bin/python -m pytest backend/tests -q
pnpm --dir frontend test
pnpm --dir frontend typecheck
pnpm --dir frontend test:e2e
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8001 pnpm --dir frontend build
MISI_FRONTEND_MODE=production bash scripts/living-dev.sh
```

The Playwright report is written to `frontend/playwright-report/`, failure traces to `frontend/test-results/`, and locally retained execution logs/export samples to `.runtime/`. These are deliberately ignored by Git. Saved screenshots in `docs/living/evidence/` show the actual running application, not design mockups. Sample exports in `.runtime/dossier.pdf`, `.runtime/business-case.docx` and `.runtime/scenario.xlsx` are synthetic working documents; they are not customer deliverables or approved bids.

## Notable defects found and fixed

- React effect replay attempted to reuse a deliberately lost WebGL context: every engine effect now owns a new canvas.
- Adaptive quality could queue a second RAF while resizing: all render scheduling uses the same guarded request method.
- Long requirements could exceed a PDF table page: in-row splitting preserves content and repeated headers.
- Missing import annual values could inherit contract totals, and legacy probability parsing clamped excessive percentages: the reviewed import path now preserves unknowns, rejects excessive values and derives margin only on an explicit annual basis.
- Saved action evidence previously existed only in an audit reason: it now persists beside validated prerequisites and can be reopened.
- Workspace-specific focus could lose the opportunity on navigation: selection now belongs to the shared shell and URL.

## Saved visual and output evidence

- [Today, desktop](evidence/today-desktop.png)
- [Intelligence Field](evidence/intelligence-field.png)
- [Scenario Lab](evidence/scenario-lab.png)
- [Today, 390px mobile](evidence/today-mobile.png)
- [Machine-readable check summary](evidence/checks.json)
- [Synthetic dossier PDF](examples/synthetic-opportunity-dossier.pdf)
- [Editable business case](examples/synthetic-delivery-business-case.docx)
- [Financial scenario workbook](examples/synthetic-financial-scenario.xlsx)

The three committed examples match saved assets in the isolated local demo. They contain only invented data and retain draft review status. New installations can generate equivalent examples through the documented journeys.
