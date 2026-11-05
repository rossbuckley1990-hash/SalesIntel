# Running the blind review (for the evaluation owner)

This is how two independent salespeople judge the frozen set, and how the result is unblinded without anyone being
able to peek first. Reviewers never touch the development server and never see the key.

## What exists

| What | Where | Who may see it |
|---|---|---|
| The served set (44 items, blinded) | `backend/reference_data/evaluation/opportunities-2026-11-05-v2.json` | Anyone. It is the stimulus. |
| Its commitment: the dataset's SHA-256, the salted key's SHA-256, the protocol and the code version | `…/opportunities-2026-11-05-v2.commitment.json` | Anyone. Published before any judgement. |
| The private key: which method found each item, the seed and the salt | `~/.salesintel/evaluation/opportunities-2026-11-05-v2.key.json` (this Mac only, mode 600) | Nobody, until the review is locked. |
| The database snapshot the set was drawn from | `~/.salesintel/evaluation/opportunities-2026-11-05-v2.snapshot.db` | Nobody. It is a copy of private data. |

The withdrawn v1 set and its key are still in the Git history of this public repository (commit `1b37e42`).

- **Nothing was lost:** no one ever judged v1.
- **v2 is protected:** every v1 lead is excluded from v2, and so is every lead that v1's screenshots and documents showed with its method (18 leads, listed privately in `~/.salesintel/evaluation/withdrawn/published-exposures.json`). Nothing public says how any v2 item was found.
- **History stays as it is:** rewriting it needs your explicit decision.

## Steps

1. **Choose two reviewers.**
   - They should be salespeople who have not worked on SalesIntel.
   - Do not tell them how items were found, and do not send them the repository link, this runbook or the key.
2. **Start the local evaluation server.**
   - Run it from the SalesIntel checkout: `scripts/evaluation-server.sh`.
   - It runs on this Mac only, on a fresh private database, with no credentials and no paid calls.
   - Open http://127.0.0.1:3051, sign up with your own email, and go to **Blind review**.
3. **Send the packs.**
   - In **Run the evaluation → 1**, download one pack per reviewer ("Reviewer A", "Reviewer B").
   - Email each person their own pack, with `REVIEWER_GUIDE.md`.
4. **Import the answers.**
   - When each answers file arrives, import it in step 2.
   - The app checks the file against the set's fingerprint, and every answer against the rubric. Importing it twice changes nothing.
5. **Resolve disagreements.**
   - Step 3 lists every item where the two reviewers differ on relevance, reason to contact, or whether to pursue.
   - For each one, either hold a short call with both reviewers (consensus), or ask an independent third salesperson.
   - Record the final answer, who decided, and why. The methods stay hidden throughout.
6. **Lock the review** (step 4). This is possible only when every item has two complete reviews and every disagreement is resolved. After it, no answer can change.
7. **Reveal** (step 5).
   - Choose the private key file. The server accepts it only if it matches the published commitment.
   - The results then appear: per method, with 95% intervals, the pre-specified comparisons and their verdicts, agreement, and every disagreement with how it was resolved.
8. **Record the results.**
   - Copy the results into `QUALITY_GATE.md`, unedited.
   - Then the key may be published, so anyone can check it: `.venv/bin/python backend/scripts/build_review_set.py --verify <key file>`.

## Rules

- Do not judge any item yourself, and never let SalesIntel's AI judge.
- Do not change ranking rules because of what reviewers said until the results are recorded.
- If a reviewer learns how items were found before finishing, record it and leave their answers out.
- Never redraw the set to get a different sample. The build refuses to overwrite a frozen set.
- Until the review is locked, publish no screenshot or document that shows SalesIntel's lists on real data. The showcase already skips every reviewed organisation.
