# Ownership and data rights: release gate inventory

Status on 5 November 2026: **unresolved. This is a release blocker.** Nothing in this document is legal advice. It records facts found in the repository so that you, and if needed your employer or a lawyer, can decide.

## 1. Facts about the repository

| Fact | Evidence |
|---|---|
| Visibility | `rossbuckley1990-hash/SalesIntel` is **public** (checked with `gh repo view`, 5 November 2026). |
| Licence | **None.** There is no `LICENSE` file, so no reuse rights are granted, but the code is publicly readable. |
| History | 30 commits since 24 October 2026. Authors: `Ross Buckley` (GitHub noreply), `Bucko` (personal Gmail), and `MiSi Engineering <misi-local@example.invalid>`. |
| Original name | "MiSi – Mitie Sales Intelligence". It was renamed to SalesIntel in PR #1. `backend/pyproject.toml` still describes the package as "FastAPI backend for MiSi - Mitie Sales Intelligence". |
| Where and when it was written | **Not established from the repository.** Whether it was written on employer time or equipment, using employer information, or within the scope of your employment cannot be determined from code. |

## 2. Employer-specific material

The word "Mitie" appears 246 times in 70 files (`git grep -io mitie`).

| Category | Where | Why it matters |
|---|---|---|
| AI instructions written for the employer | `backend/app/intelligence/opportunity_analysis.py:113,125`, `opportunity_research.py:404,410,1149`, `structured_analysis.py:132`, `internet_research.py:179`, `executive_summary.py:240`, `prompt_contract.py:26,43`, `early_opportunities.py:62` | The prompts tell the model it is an analyst "for Mitie Fire & Security" and ask "What should Mitie do next?". This is employer-specific commercial framing. |
| Employer group logic | `backend/app/intelligence/renewal_radar.py:66` (`OWN_GROUP = mitie\|marlowe`), `renewal_intelligence.py:138`, `signal_inference.py:370` | It treats contracts held by Mitie or Marlowe as "own group" (retention, not new business). That encodes knowledge of the employer's corporate group. |
| Data model | `market_signals.likely_mitie_fit` (`models/market_signal.py:24`, `db.py:105`), `FIT_TO_MITIE` (`routers/market_opportunities.py:23`), `market_signal_conversion.py` (16 mentions) | Employer naming is built into the schema and the scoring. |
| Interface | `frontend/src/features/workspace/shell.tsx` hard-codes the workspace name "Mitie Fire & Security". The classic workspace has 70+ mentions across `classic/*.tsx` and `classic-light.css`. | Employer branding. |
| Tests and docs | `tests/test_renewal_radar_integration.py`, `test_signal_inference.py`, `docs/PRODUCT_SPEC.md`, `ENTERPRISE_DEPLOYMENT.md` and others | They repeat the assumptions above. |
| Runtime names | The launch agents `com.misi.market.*`, and `MISI_*` environment and script names | These are only labels, but they record where the product came from. |

**Potential employer commercial assumptions** (they need a review, not just a rename):
- "self-delivery fit", engineering capacity and margin fields in the classic pipeline;
- the "own group" retention rule;
- the service taxonomy and the fit rules in `market_signal_conversion.py`.

If any of these reflect the employer's internal methods, pricing or strategy, renaming them does not change where they came from.

**Actual employer or customer information.** None was found in the repository. The checks: the sample data says it is synthetic; the fixtures use `example.*` domains; the reference data is public registers and public notices.

Not checked: the local database `.runtime/false-alarm-pilot-v2.db` (86,788 rows, not in Git), which mainly holds collected public notices; and anything you typed into it, or uploaded, while using it.

## 3. Third-party sources

| Source | Code | Licence stated in the repository | Status |
|---|---|---|---|
| London Fire Brigade incident records | `ingestion/lfb_*` | Open Government Licence (`backend/LFB_IMPORT.md`) | Documented |
| NHS ERIC estates returns | `ingestion/eric_*` | Open Government Licence, plus NHS England terms (`backend/ERIC_IMPORT.md`) | Documented |
| Find a Tender (OCDS) | `ingestion/market_find_tender*`, `find_a_tender.py` | Not stated | **Verify** the terms of reuse and attribution |
| Contracts Finder | `ingestion/market_contracts_*` | Not stated | **Verify** |
| Public Contracts Scotland | `ingestion/market_scotland.py` | Not stated | **Verify** |
| Companies House | `ingestion/companies_house.py`, `reference_data/companies_house_reviewed_psc.json` | Not stated | **Verify**, including the API terms. The PSC file holds only company-to-company control links. |
| Planning Data England, via `rightclick-x` | `docs/PUBLIC_SOURCE_NETWORK.md` | Upstream licence applies. `rightclick-x` is your own repository, cloned at runtime. | **Verify** both |
| AI web research (OpenAI or Anthropic) | `services/prospect_research.py` | Provider terms; each finding cites its source page | Republishing third-party page content needs care |
| `Breakout.zip` source, ported into `frontend/src/features/field/engine/*` | `docs/living/BREAKOUT_PORT.md` | **No licence or author recorded** | **Unknown provenance** |

**Personal data.** Procurement notices publish named buyer contacts, and research can record named people with quoted sources. That is personal data under UK GDPR, whatever its source.

## 4. What is clean, and the separation path

**Written for SalesIntel 3.0, with no employer-specific content:**
- the tenancy layer (`app/tenancy.py`, `app/auth.py`, `models/tenancy.py`, `routers/workspaces.py`, migration `0020`);
- the assessment (`services/si_assess.py`);
- the hosted shell (`frontend/src/features/hosted`, `lib/session.ts`) and their tests.

They still sit in, and depend on, the repository whose ownership is open.

**Options, from least to most effort.** These are not a recommendation.
1. **Ownership confirmed in writing.** Your employer confirms in writing that it claims no rights in SalesIntel. Then remove the employer material in section 2 before any commercial use.
2. **Separation inside this repository.** Remove or rewrite the components in section 2:
   - the prompts, as neutral instructions that use the workspace's own company name;
   - the own-group rule, as each workspace's own group list;
   - `likely_mitie_fit` becomes `fit`, through a migration;
   - the classic workspace is retired or rebranded.

   This removes the branding. It does **not** settle ownership of the code already written.
3. **Clean-room rebuild.** Write a functional specification without employer information. Build a new repository from it, reusing only material whose provenance is clear: public-data connectors written from public API documentation, and the generic platform code. Replace or relicense the `Breakout` engine, or remove it.

**Until this is decided:**
- no commercial use, no public SaaS deployment, and no customer data;
- engineering continues on synthetic and openly licensed public data.

Changing the repository's visibility is your decision; it has not been changed.
