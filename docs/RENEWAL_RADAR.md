# UK Renewal Radar

The radar is SalesIntel's single UK view of fire and security contract opportunities. It reads every procurement record SalesIntel stores, joins records of the same contract across sources, and files each one under a category with a priority tier and a next action. Rules are deterministic. No model is called, no probability is given, no contact is invented and nobody is contacted.

Open it from **Renewal Radar** in the workspace navigation, or at `/?view=radar`. Start SalesIntel on this Mac's real database with:

```sh
pnpm dev:live
```

## Categories

| Category | Meaning |
|---|---|
| Pre-tender opportunity | A possible upcoming procurement, inferred from a contract's published or estimated end date. |
| Official early signal | A published pipeline, planning or market engagement notice that has not reached a tender. |
| Live procurement | A published tender with an open deadline, including frameworks in the sector. |
| Contract defence | A contract in the renewal window whose published supplier names Mitie or Marlowe. |
| Uncertain: verify first | Something contradicts or weakens the picture, such as a passed end date, a possible replacement or a term read only from wording. |

A historical award is stored as a contract but never becomes an opportunity.

## Reading a record

- **Date basis:** only a date the source gives for the award counts as published. A tender's planned date, a duration added to a start date and a term stated in wording are estimates. Estimates are marked and kept in a separate field.
- **Extensions:** "can run to" is the published latest date, or a date worked out from extension wording, which says so. A contract whose initial term has passed stays listed for checking if an extension could still be running.
- **Value:** published total, estimated annualised value and framework ceilings are kept apart. Sources in this data publish no annual figure, so "published annual" is normally empty. No value is guaranteed or fully addressable, and a bundled contract's value covers wider work.
- **Priority:** tier 1 is ready for commercial work, tier 2 needs one more fact and tier 3 is background. The record lists the reasons. Published value alone does not decide the order.
- **Fit:** core names the system and its service, bundled sits inside wider maintenance, adjacent is passive fire or fire risk assessment work, and framework is an agreement rather than an individual contract.
- **Link confidence:** exact means a shared reference or repeat of the same record, strong means the same buyer and supplier with a matching date or value, and possible means a similar title and end date only. Link confidence says nothing about the commercial opportunity. A similar title never confirms a replacement.

## How it runs

Five launch agents run after this macOS user logs in: the three source monitors, the Contracts Finder and Scotland backfill, and `com.misi.market.renewal.radar`. **Nothing is collected while the Mac is off or asleep.** Checkpoints catch up on return where the source still allows it. Continuous collection needs an always-on host; see [MARKET_NETWORK.md](MARKET_NETWORK.md).

Monitors store new records and re-evaluate only when records change or the day changes. The radar worker runs hourly, makes at most one selective history lookup a day and writes `radar-YYYY-MM-DD.md` and `.csv` to `.runtime/renewal-radar/` from the database. Health is at `/api/market-network/opportunities/health`, and a source is shown as fresh, stale, failing or never run. Three failures in a row always show as failing.

For a first load or an extended history pull:

```sh
PYTHONPATH=backend .venv/bin/python backend/scripts/renewal_radar.py --load --refresh --report
PYTHONPATH=backend .venv/bin/python backend/scripts/renewal_radar.py --find-a-tender --tender-first-year 2021 --load --refresh
```

Loading is idempotent, so rerunning it adds nothing that is already stored. Do not use the Find a Tender `stages` parameter. On sampled days it returned 18 to 42 percent fewer tender notices than an unfiltered page, and it omitted all 38 notices then held by the SalesIntel monitor.

## Coverage and limits

- **Find a Tender:** an unbroken weekly run back to 10 October 2022. This was a collection-priority decision, not proof older contracts do not matter. Long contracts published earlier and only there can be missing. The radar looks up older weeks selectively around large or long contracts it knows from elsewhere, and the run can be extended without starting again.
- **Contracts Finder:** targeted fire and security searches back to 2021, then the live monitor. Search rows hold a reduced copy of the notice.
- **Public Contracts Scotland:** an input to the UK list, not a separate feed. Award notices publish no contract dates, so Scottish end dates are often estimates.
- **Wales and Northern Ireland:** covered through Find a Tender and Contracts Finder only. Sell2Wales and eTendersNI are not read, so lower-value contracts can be missing.
- **Private sector:** not covered.
- **Own group:** only supplier names containing Mitie or Marlowe are matched. Other group companies are not.
- **Access:** SalesIntel has no sign-in, and the local application binds to this Mac only. It is not ready to be exposed to a team network as it stands.

A published end date omits unrecorded extensions, and a buyer can re-let through a framework or below a publication threshold with no notice appearing. Classification reads published wording, not evidence of current delivery. Verify the current position before any approach.

The audit of lead quality, and how to repeat it, is in `backend/reference_data/renewal_radar_audit_2026-11-02.json`.
