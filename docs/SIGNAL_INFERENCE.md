# Signal inference

SalesIntel cannot see whether a customer is unhappy or a contractor is struggling, so it reasons from what is published. The engine turns public observations into dated, source-linked events, joins them to customers and contracts, proposes competing explanations and decides what each one justifies. Results appear in **Renewal Radar**: on the contract they concern, or as an **Inferred signal** when no contract applies.

An inference is not a finding about any company. Do not repeat one to a customer as fact. SalesIntel records a contractor as responsible only when a source says so.

## How it works

1. **Observe.** Automatic sources are procurement notices, London Fire Brigade attendance and inspection records, Regulator of Social Housing judgements and Gazette insolvency notices. A small curated file holds facts a person read at source, and each is labelled analyst assisted.
2. **Link.** Observations join a customer by published name, and a contract only when the service and title match.
3. **Hypothesise and challenge.** Each signal type has rival explanations, such as ageing assets or a planned capital programme. Each is marked supported, possible, not established or contradicted.
4. **Corroborate.** Two notices from one source are not independent. A fire safety finding is corroborated only by fire work, and holding a contract is context rather than corroboration.
5. **Arbitrate.** Each hypothesis is Pursue, Verify, Monitor or Dismiss, with reasons. Pursue justifies investigation and needs independent sources. It never means a contract exists.
6. **Monitor.** Each evaluation re-decides every hypothesis. Earlier reasoning is kept. Later evidence removes only what it answers, and a derived observation the rules no longer produce is retracted with a date.

The radar worker collects open sources once a day and re-evaluates when records or observations change. No model is called. Unchanged data is recognised by fingerprint. Collection runs only while this Mac is awake and logged in.

## Backtest result

**Indirect signals have not been shown to beat the Renewal Radar.** Run `backend/scripts/backtest_signal_inference.py` to repeat this. The latest result is in `backend/reference_data/signal_backtest_2026-11-02.json`.

The test used 263 settled core and bundled contracts, each judged 270 days before its published end, using only records available by then. 39 were followed by a matching official notice.

| Arm | Flagged | Precision | False positive rate | Coverage | One-sided p |
|---|---:|---:|---:|---:|---:|
| Renewal date only | 263 | 14.8% | 100% | 100% | n/a |
| Official early notices | 1 | 0% | 0.4% | 0% | 1.0 |
| Indirect signals, same service | 0 | n/a | 0% | 0% | n/a |
| Sensitivity: any signal at the customer | 14 | 21.4% | 4.9% | 7.7% | 0.34 |

- Primary test: no same-service indirect signal existed before any decision date.
- Sensitivity test: 21.4% against 14.8% is not distinguishable from chance. Its 95% interval is 7.6% to 47.6%.
- Multiple independent sources: none of the flagged contracts had them.
- Tenders from April 2024: of 306, 12 were foreseeable from a held contract. Of the other 294, 7 had an earlier indirect signal.
- Run cost: about 20 seconds and no model spend. No signal has yet been validated, so a cost per validated signal cannot be given.

The test cannot judge the strongest new sources. Regulator pages hold only the current judgement, the fire service period after the policy change starts in November 2024, and historical committee papers are not collected. Treat this as an unproven engine rather than a disproved one. Every Pursue and Verify hypothesis is dated when made, and `prospective_scorecard` scores them against later notices. That forward test cannot leak and needs about 12 months.

An early design counted published early re-lets as signals. They are the outcome being predicted, so they were removed before these results.

## Measured quality

- Contract attribution: on reading all 23 contract links, 8 were right. After tightening, 8 of the remaining 14 are right, or 57%. That second figure re-reads the same records, so it is not an independent measure. Contract-level hypotheses reach only Verify or Monitor.
- Unsupported claims: a regulator finding about a customer no longer marks its contractor, after this appeared in live output.
- "Emergency" no longer matches emergency lighting, which had produced 700 false emergency procurements.

## Limits

- **Companies House:** with `COMPANIES_HOUSE_API_KEY` in the ignored root `.env`, the radar worker checks up to 100 companies a day, and rechecks each every 30 days. It reads company status, overdue accounts and corporate controllers for suppliers on live contracts and watched competitors. Without a key this step does nothing. It never reads individuals, and one overdue filing is only watched.
- **Committee papers:** Leeds, Camden and others refused automated requests, and those refusals are respected. Kent allowed its committee list but its document search failed. There is no automatic reader for minutes, board papers or contract performance reports, so performance and dissatisfaction signals are rarely filled.
- **HSE enforcement register:** not reachable from this machine.
- **Fire service data:** London only, and only sites in the published NHS site list.
- **Regulator data:** social landlords only. Up to 80 pages are read a day, so the full list takes several days.
- **Gazette:** no supplier in SalesIntel has matched yet. Matches rely on exact names, so confirm the company number.
- **Names:** customers with different published names can fail to join.
- **Spend data:** no council or NHS spending files are read, so repeated expenditure patterns are not detected.
