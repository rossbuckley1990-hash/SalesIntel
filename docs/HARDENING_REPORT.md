# Hardening the sales loop: risk report

Branch `fix/harden-sales-loop` (from `main` at `17bf166`). Not merged or deployed.

**Exit criterion:** the discovery-to-won workflow is independently verified, commercially consistent and safe for continued local development. It is **met for local, single-user development**. It is **not met for an external or multi-user pilot**; the blockers are listed in section 6.

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

## 4. Background collectors after the folder move: needs action

Read-only checks found:
- Four collectors are still running processes started on 4 November from `/Users/ross/Documents/MiSi - Mitie Sales Intelligence`. The fifth, contracts finder, cannot start (exit 78).
- No collector has recorded a success in the live database since **07:07 on 5 November**.
- The running processes hold the moved database open by file handle but resolve other paths against the old folder. They write lock, retry and report files there.
- SQLite places its rollback journal next to the path it was *opened* with. A crash during a write would leave the recovery journal in a different directory from the database, which **risks corruption**.
- Any new connection they make would create an empty database at the old path. None exists yet, and the live database passed its integrity check at 09:23.

Fix (needs your authorisation; it replaces only the paths, which I checked):

```bash
cd /Users/ross/Documents/SalesIntel && for f in .runtime/launch-agents/com.misi.market.*.plist; do n=$(basename "$f" .plist); launchctl bootout gui/$(id -u)/$n 2>/dev/null; cp "$f" ~/Library/LaunchAgents/; launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/$n.plist; done
```

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

**Full results:**
- Backend: 498 passed.
- Frontend unit tests: 33 passed. TypeScript: passed.
- Playwright: 59 passed, 1 skipped (visual QA that needs an explicitly configured demo API), 0 failed.
- Rehearsed in a clean checkout without `.env`.
- **The GitHub Actions workflow itself has not run yet.** It first runs when the PR is opened, and its result is the independent verification.

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

## 7. Remaining risks for local development

- The collectors issue in section 4 until the agents are reinstalled.
- No sign-in, so the app must stay local; the guard enforces this.
- The legacy pipeline and finance tools still use floating-point money.
- Draft and quotation approval have no second-person control.
