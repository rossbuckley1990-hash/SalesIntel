# Contact Navigator

The Contact Navigator answers one question: who should I speak to, and how can I legitimately reach them? It is code in `backend/app/services/navigator.py`, run as a durable job and shown in the account's "Find the right people" panel.

## How it works

1. **Roles.** It chooses roles from the opportunity type. A public body gets procurement, estates and fire safety. A private company gets estates, operations or managing director, and fire safety. Security services in scope add a security manager. These are labelled as typical roles, not claims about who works there.

2. **Sources, cheapest first:**
   - **The official procurement notice.** The notice itself is always offered as a route. The buyer's published procurement contact is added only when `NAVIGATOR_FETCH_PUBLISHED_NOTICES` is on, or from replay in tests. The shared collectors deliberately strip contact points from stored notices.
   - **Research already saved for the account.**
   - **Web research through the AI provider.** It is budgeted, durable and capped per job.
   - **Licensed enrichment providers,** through `EnrichmentProvider`. **None is registered.**

3. **Validation.** Every finding goes through deterministic code, and the model's output is never trusted on its own.
   - **Source:** it must be a page the research actually retrieved, and the quote must appear in that page's excerpt.
   - **Person:** the quote must name the person and their role and this organisation, unless the page is on the organisation's own site or an official procurement site. Someone a newer source places at another employer is flagged `may_have_moved`.
   - **Email:** it must appear verbatim in the quote and be on the organisation's own domain or an official procurement source. Free and personal mailboxes are never accepted, and nothing is constructed from a name pattern.
   - **Telephone:** it must appear verbatim.
   - **Web form:** it must be on the organisation's own domain.
   - **Website:** it is accepted only if a retrieved page on that host names the organisation in full.
   - **Hostile pages:** a page containing instructions to the AI is discarded entirely.
   - **Provider data:** it is "provider-verified" only when the provider reports the mailbox deliverable *and* gives a check date. Deliverability is never treated as proof that the person holds the role. Data from another employer is rejected. Old data is marked `stale`; disagreeing sources are marked `conflict`.

4. **Saving.** Findings are saved into the account's existing contacts. Each records its quality, verification method, date, source, quote, flags and a use restriction. Official procurement contacts say: "Use only for questions about it, through the route the notice specifies."

5. **Suppression.** An opt-out is stored as a hash of the email, the telephone number, and the name on that account. It survives:
   - refreshed research;
   - new sources;
   - deletion of the record;
   - manual re-entry.

   Lifting it is a deliberate, audited action.

6. **Ranking.** Contacts are ordered by:
   - role relevance;
   - route directness;
   - evidence quality;
   - freshness.

   Model confidence is never used. Every route shows why it ranks where it does.

7. **Results:**
   - **Success:** named decision-makers with direct business contact details, or an official procurement contact.
   - **Partial:** *"Relevant decision-maker role identified, but no verified direct business contact details found."*
   - **Nothing found:** *"No reliable business contact route was found in the permitted sources."*

## Contact quality levels

| Level | Meaning |
|---|---|
| Publicly sourced business contact | Stated verbatim by the organisation or an official notice, checked as above |
| Provider-verified business contact | A licensed provider reported it deliverable and gave a date. This says nothing about the person's role |
| Unverified possible contact | Provider data without verification. Shown, never preferred |
| Role identified, person unknown | The organisation refers to the role but publishes no person or route |
| No reliable business contact route | A job result; nothing is saved |

## Licensed providers: evaluation only, nothing called

This is a desk review of public material on 5 November 2026. It is not verified with either provider.

| | Hunter | Apollo |
|---|---|---|
| API access | API access is described on its Data Platform plans and is credit-based ([pricing](https://hunter.io/pricing), [data platform](https://hunter.io/data-platform), [plan guide](https://help.hunter.io/en/articles/9920233-which-plan-is-right-for-me-all-in-one-outreach-platform-plan-or-a-data-platform-plan)) | Its documentation says all customers get basic public API access, with more by plan ([API pricing](https://docs.apollo.io/docs/api-pricing), [API](https://www.apollo.io/lp/api)) |
| Pricing | Credit costs per call are reported by third parties; not confirmed | Third-party tier prices conflict; not confirmed |
| Data sources | Says it is sourced from publicly available information | Not established from primary terms |
| UK GDPR and permitted use | Vendor and blog claims only; no legal terms reviewed | Its legal terms could not be retrieved; UK terms unverified |
| Decision | Not integrated | Not integrated |

**Before either is registered:**
- read the provider's current terms, data-processing agreement and data sources;
- confirm UK GDPR and PECR fit for B2B outreach, with a documented legitimate-interests assessment;
- confirm the pricing and the per-call credit cost;
- run a trial on a small, consented test set and measure accuracy against known contacts;
- then add an `EnrichmentProvider` subclass and list it in `CONTACT_ENRICHMENT_PROVIDERS`.

The per-job spending limit applies to providers too.
