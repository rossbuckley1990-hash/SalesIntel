# Hardening the sales loop: risk report

Branch `fix/harden-sales-loop` (from `main` at `17bf166`). Not merged or deployed. Updated on 5 November 2026 for the final acceptance and release gate (section 8).

**Exit criterion:** the discovery-to-won workflow is independently verified, commercially consistent and safe for continued local development. It is **met for local, single-user development**. It is **not met for an external or multi-user pilot**; the blockers are listed in section 6, and the risks are separated by category in section 9.

## 1. Defects reproduced and fixed

| Defect | Reproduced | Fix |
|---|---|---|
| A deal could be won on an obsolete approved quotation: changing scope, services, type of work or rates after approval left the status `approved`. | `test_hardening.py` failed against the previous code: the status stayed `approved` after a scope change. | Each quotation records a fingerprint of its inputs. Material changes supersede the approval, which is kept as versioned history with a reason. Approval checks the draft still matches; winning re-checks the approved fingerprint. Non-material edits, such as the next step, leave it alone. |
| A draft approved before its recipient opted out stayed approved and sendable. | `test_hardening.py` failed: the draft stayed `approved` after `do_not_contact`. | Unsent drafts to that person become `suppressed`. Approving or logging them is refused, and lifting the opt-out does not silently re-approve: the draft must be saved and approved again. Outbound interactions with a suppressed contact are refused; inbound ones can still be recorded. Sent history is untouched. |

## 2. Other fixes found during the work

- **Exact money.**
  - Quotation rates, quantities and totals are exact decimals carried as strings.
  - Quantities must be whole numbers.
  - Unit rates allow up to four decimal places and are never silently rounded.
  - Line totals round half up to the penny, and the total appears only when every line is priced.
  - Negative, NaN, infinite, oversized, boolean and float-artefact inputs are rejected with the field named; a rejected input changes nothing.
  - The screens show amounts without converting them through floating point.
  - Remaining: the deal's own estimated value and the legacy pipeline `Opportunity` still store floats. They are validated to the penny but not used for quotation arithmetic.
- **Cross-site requests and DNS rebinding.** Browsers send "simple" cross-site POSTs without a CORS preflight, so another website could approve drafts or complete tasks through bodyless endpoints. A domain rebound to `127.0.0.1` could also read every record. A request guard now:
  - requires a local Host header;
  - requires a loopback client, unless remote access is explicitly enabled;
  - refuses state-changing requests from foreign origins.
- **Accidental data loss.** `seed.py --reset` and `reset_empty.py` dropped every table in whatever `DATABASE_URL` was set, including the live one. `reset_db` now refuses outside demo and test mode unless `SALESINTEL_CONFIRM_RESET` names the file.
- **A suspended draft hid the next introduction.** Engage reopened it by default; it now reopens only drafts that can still be used.
- **Browser suite.** `porcelain-support.spec.ts` called a server on port 8002 that the test setup never starts. It now uses the suite's server.

## 3. Database (no records changed, nothing stamped)

`backend/scripts/db_preflight.py` provides `inspect`, `reconcile`, `backup`, `verify` and `restore` (to a new path only). The procedure is in `docs/DATABASE_OPERATIONS.md`.

On the live database:
- the integrity check passes, and there are 60 tables and 86,709 rows;
- `alembic_version` is empty;
- reconciliation against a schema built from the migrations alone finds no differences in tables, columns, types, nullability, foreign keys or indexes at `0019`, so stamping would be accurate.

Stamping is left as a recorded decision for you. A verified backup is at `.runtime/backups/false-alarm-pilot-v2-20261105T092340Z.db`.

## 4. Background collectors after the folder move: resolved with authorisation

**What happened.**
- After the project folder was renamed, four collectors were still running from `/Users/ross/Documents/MiSi - Mitie Sales Intelligence`.
- The fifth, Contracts Finder, could not start (exit 78).
- No collector had recorded a success since 07:07 on 5 November.
- The running processes held the moved database open by file handle but wrote lock, retry and journal files against the old folder. A crash mid-write could have left SQLite's recovery journal in a different directory from the database.

**What was done, at 09:51 on 5 November, with your authorisation.**
- A verified backup was taken first (`false-alarm-pilot-v2-20261105T095122Z.db`).
- All five launch agents were reinstalled from `/Users/ross/Documents/SalesIntel`. Their files differ from the previous ones only in the folder path.

The command used:

```bash
cd /Users/ross/Documents/SalesIntel && for f in .runtime/launch-agents/com.misi.market.*.plist; do n=$(basename "$f" .plist); launchctl bootout gui/$(id -u)/$n 2>/dev/null; cp "$f" ~/Library/LaunchAgents/; launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/$n.plist; done
```

**Evidence, separated by how it was obtained.**

| Evidence | Kind | Result |
|---|---|---|
| Collector runs within a minute of the reinstall (09:51–09:52) | Recorded by the collectors in `market_source_states` | Find a Tender, Contracts Finder, Public Contracts Scotland and the renewal radar each recorded a success |
| `launchctl list` at 12:04 UTC | Personally verified, read-only | All five `com.misi.market.*` agents loaded with last exit status 0 |
| Installed plists | Personally verified, read-only | `WorkingDirectory` and every program path point to `/Users/ross/Documents/SalesIntel` and its `.venv` |
| Running processes | Personally verified, read-only | Five Python processes, each with working directory `/Users/ross/Documents/SalesIntel`, each holding only `/Users/ross/Documents/SalesIntel/.runtime/false-alarm-pilot-v2.db` |
| Latest successes at 12:04 UTC | Read-only query of the live database | Find a Tender 11:54, Contracts Finder 11:54, renewal radar 11:23 (hourly), Public Contracts Scotland 09:52 (daily). The backfill had used its daily budget (96 requests) at 01:37, as designed |
| Database at 12:04 UTC | `db_preflight.py inspect` (read-only) | Integrity `ok`; 60 tables; 86,788 rows; `alembic_version` present but empty |
| Old folder | Personally verified | No database file. Only `.runtime` logs and lock files, and a `frontend` build cache, remain |

Nothing was restarted for this verification. One historical failure is unrelated to the move: the Public Contracts Scotland back-window `pcs_2024_09_103` failed three times on 30 October and has not been retried.

The old folder can be deleted once you no longer want its logs. That is your decision; it has not been touched.

## 5. Adversarial acceptance challenge

| Challenge | Evidence | Result |
|---|---|---|
| Approved quotation, then a modified scope | `test_hardening.py`; `e2e/hardening.spec.ts` | Approval superseded and shown; won refused; re-approval creates version 2 |
| Suppressed contact with an approved draft | `test_hardening.py`; `e2e/hardening.spec.ts` | Draft suspended, approval disabled, logging refused, Today excludes it, history intact |
| Persistence across a restart | `test_adversarial.py` starts the real API process, writes over HTTP, kills it and starts a new one; plus the browser reload test | Account, history, follow-up, evidence and deal all intact |
| Duplicate organisation records | `test_adversarial.py`, `test_salesintel_journey.py` | Two notices and one research record give one account (one confirmed link, two unconfirmed); re-linking is idempotent; different company numbers stay separate |
| Follow-up and activity continuity | `test_adversarial.py` | Reschedule, then logging completes the old follow-up and creates the next in one step; Today and the next step follow |
| Fractional pence and invalid inputs | `test_hardening.py` (money) | 3 × £4.555 = £13.67; 0.1 × 3 = £0.30 exactly; 12 invalid inputs rejected without changing state |
| Procurement collectors and classification | 180 collector and classification tests; relevance acceptance test D | Pass; irrelevant alarm, CCTV and security contexts stay excluded |
| No unauthorised sends or paid calls | `test_adversarial.py` blocks every non-loopback connection and DNS lookup for the whole loop to won; demo mode refuses AI research; CI blanks keys | No external connection attempted; there is no send endpoint |

The results after the release gate are in section 8.

## 6. What a five-salesperson pilot still needs

None of these can be securely built and tested without an identity provider and a hosting decision, so they are not implemented:

1. **Authentication.** Single sign-on, for example Microsoft Entra ID with OpenID Connect, and session handling. The local guard must stay until this exists.
2. **User identity on records.** Owner and creator on accounts, contacts, drafts, activities, tasks and deals, and an audit trail of who changed what. Today every record is anonymous.
3. **Authorisation.** Decide what is shared by the team (accounts, evidence) and what is personal (drafts, tasks). Restrict quotation approval to named approvers, so a salesperson cannot approve their own quotation.
4. **Data isolation.** If the product serves anyone beyond one company, data must be separated per organisation. The Mitie-specific naming and data raise the ownership and confidentiality question first.
5. **Hosting.** A private network or VPN, TLS, secret management (API keys held server-side per environment), managed backups, and moving from SQLite to PostgreSQL for concurrent users.
6. **Privacy compliance.** A UK GDPR data protection impact assessment for contact data, a retention policy, and a shared, auditable suppression list rather than a per-contact flag.
7. **Cost control.** Per-user limits and logging for paid AI research.
8. **Operations.** The live database under Alembic (section 3), and durable research jobs (AI Research progress is still held in memory).

## 7. Decision for you: public repository, Mitie naming and IP

- **The repository `rossbuckley1990-hash/SalesIntel` is public.** This was verified on 5 November with `gh repo view`. An earlier statement in this work said it was private; that was wrong.
- Names and data specific to Mitie Fire & Security remain in the code, documents, launch-agent labels (`com.misi.*`), the database file names and fixtures.
- Whether you, Mitie or both own this work, and whether any of it is confidential to your employer, is **unresolved**. Renaming the product to SalesIntel does not settle ownership.
- Nothing here changes visibility, history or employer-specific material. Those need your decision, and possibly your employer's or a lawyer's. Options include making the repository private, removing Mitie-specific material, or confirming ownership in writing.

## 8. Final acceptance and release gate

**Verification of the implementations, not only the tests.**

| Area | What was checked in the code | Finding |
|---|---|---|
| A. Quotation integrity | `inputs_fingerprint`, `supersede`, `build_quote`, `approve_quote`, `quote_is_current`, `move_stage` | Sound for open deals. Defect found: a **won** deal could still have its scope, services, work type or rates edited, or be moved back to an open stage or to lost. That superseded the approval behind an issued handover and left the account marked as a customer. Fixed: a won deal is closed. Stage changes and commercial edits are refused with 409, and the page shows the scope and quotation as locked. A lost deal can still be reopened, which clears the loss reason. |
| B. Contact suppression | `update_contact`, `_suppressed`, `save_draft`, `approve_draft`, `log_draft_sent`, `log_activity`, the Today queue | Sound. Every path that approves, logs or records outbound contact checks the opt-out. |
| C. Host, origin and loopback | `app/security.py` | Sound for local use: `localhost` and `127.0.0.1` on port 3000 both work. `testserver` remains in the default allowed hosts; it is only reachable by name on a machine whose DNS resolves it. It should be removed before any hosted pilot. |
| D. Backup, verify, restore and reset | `db_preflight.py`, `reset_db` | Sound. Backups are online, checksummed and integrity-checked, and restore never overwrites. Residual: `reset_db` trusts `APP_ENV`, so `APP_ENV=demo` combined with the live `DATABASE_URL` would allow an erase. That needs deliberate misconfiguration. |
| E. Continuity across a restart | `test_adversarial.py` starts the real API process on an isolated file, writes over HTTP, kills it and starts a new process | Account, history, follow-up, evidence and deal intact. The loop to won makes no external connection. |

**Adversarial pass: defects reproduced, then fixed narrowly.** Each test in `backend/tests/test_release_gate.py` and `frontend/tests/si-dates.test.ts` failed against the previous code.

| Defect | Severity | Reproduction (before the fix) | Fix |
|---|---|---|---|
| Logging an interaction on one account with `complete_task_ids` could mark **another account's** follow-ups as done | High (cross-account modification) | 200; the other account's task was closed | Every follow-up named is checked against the account before anything is written; otherwise 404 and no write |
| Drafts and tasks could point at **another account's deal** | High (cross-account linkage) | 200 for both | The deal must belong to the account; otherwise 404 |
| A won deal could be edited or re-staged after handover | High (quotation inconsistency, incorrect stage transition) | 200 for scope, services, rates and stage changes | As in A above |
| Just after midnight in British Summer Time, the "Tomorrow" button scheduled follow-ups for **today**, and Today hid tasks due that day | High (follow-up date errors for six months of the year) | `inDays(1)` returned today's date at 00:30 BST; a task due 11 June was missing from Today at 00:30 BST | The browser formats the local date, not UTC. The server uses the UK calendar (`uk_today()`, Europe/London) for due, overdue and Today |

**Challenged and found sound:**
- **Duplicate activities and double-submit.** The logging and approval buttons disable while a request is in flight. A second "log as sent" is refused because the draft is already logged. Re-approval is idempotent. There is no idempotency key for a retried network request, which matters only once the app is hosted (section 9).
- **Approval bypass.** Approval needs a current fingerprint, no missing inputs and no estimated quantities; winning re-checks the approved fingerprint.
- **Partial writes.** Every write endpoint runs in one transaction that rolls back on any refusal. This is now proven for the cross-account follow-up case.
- **Destructive operations.** Only saved-view deletion exists in the SalesIntel API. Reset and restore are guarded as in D.
- **Unsafe frontend assumptions.** Money is shown from exact strings, not floats. Suspended and won states are mirrored from the server, which remains the authority.

**Test isolation.** `test_config.py::test_cors_defaults_to_local_frontend_only` read the developer's `.env`. It failed on this machine because the local `.env` lists the same two origins in another order. It now constructs settings without `.env`, which is what its name says it tests. The assertion is unchanged.

**CI.** The Playwright GPU lifecycle test timed out on one run (`42005948089`) at its final step with the canvas present. A passing run took 35 s of the 60 s budget at about 10 frames a second under software WebGL; the failing runner was about 33% slower overall. The test now has a tripled time budget for itself only (`test.slow()`). No assertion changed. It passes locally and in CI.

**Intentional skip.** `e2e/populated-visual-qa.spec.ts` captures screenshots against a demo API named in `MISI_QA_DEMO_URL`. CI sets no such API, so it skips. It asserts no behaviour that the other 60 browser tests do not.

**Results** (local, on the final commit; CI results for the exact head are linked from the PR):
- Backend: 502 passed, including migrations from scratch in CI.
- Frontend unit tests: 35 passed. TypeScript: passed.
- Playwright: 60 passed, 1 skipped (above), 0 failed.

## 9. Risks by category

**Merge blockers:** none open once CI passes on the final commit.

**Local-development limitations** (acceptable for one person on this Mac):
- There is no sign-in, so the app must stay local. The request guard enforces this.
- One user only. Draft and quotation approval have no second-person control.
- The legacy pipeline, finance tools and the deal's own estimated value still store floating-point money. Quotation arithmetic is exact.
- The live database is not yet under Alembic. Stamping is safe and awaits your decision (section 3).
- `reset_db` trusts `APP_ENV` (section 8, D).
- AI Research job progress is held in memory and is lost on restart.
- The classic workspace's seven-day default dates still use UTC. They are outside the SalesIntel loop.

**External-pilot blockers** (detail in section 6):
1. Authentication, such as single sign-on with Microsoft Entra ID.
2. Record ownership: owner and creator on every record.
3. Role-based approval, so a salesperson cannot approve their own quotation or draft.
4. Data isolation per organisation.
5. Hosting: a private network, TLS, managed secrets and backups, and PostgreSQL. Remove `testserver` from the allowed hosts.
6. Privacy: a UK GDPR data protection impact assessment, retention, and a shared suppression list.
7. An audit trail of who changed what.
8. Paid-API cost controls: per-user limits and logging.
9. Durable research jobs, and idempotency keys for retried writes.
10. The ownership and confidentiality decision in section 7.
