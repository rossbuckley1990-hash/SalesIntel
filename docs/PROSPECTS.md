# Prospects: private-sector research with inferred timing

Prospects finds private-sector organisations that show signs they will need fire and security services, before they go to market. It complements the Opportunity Finder, which covers published public procurement.

## How to use it

1. Open **Prospects** under Find.
2. Choose **Discover companies** and describe the companies you want, or pick a play (new warehouses, retailers facing rising theft, PSTN switch-off exposure, a new head of facilities, a competitor in difficulty, and more). Or choose **Research a company** and name one.
3. SalesIntel researches for three to six minutes and saves the results. You can leave the page.
4. Each prospect shows a traffic light for timing, the signals, who decides, published contact routes and a suggested approach.
5. Use **Deepen research** on a promising prospect to look harder for people, contacts and dated clues. It updates the same record.
6. **Add to pipeline** creates an opportunity for qualification. **Watch** and **Dismiss** keep the list focused.

## Signals

Research looks across 26 signal types in seven groups:

| Group | Examples |
|---|---|
| Growth | New sites and warehouses, expansion, acquisitions, investment, hiring facilities or security staff |
| Change | New decision makers, outsourcing or restructures, relocations |
| Risk | Thefts and break-ins, fires and false alarms, enforcement or prosecutions, insurer or audit requirements, compliance deadlines |
| Estate | Refurbishments, planning applications, ageing buildings or systems |
| Incumbent | Reported service problems, the incumbent in financial difficulty, supplier changes, competitor activity |
| Requirement | Stated requirements, RFIs, public complaints about safety or security |
| Strategy | Cost consolidation, technology or ESG strategy, major events and seasonal peaks |

Every signal is marked stated (a source says it) or inferred, and links to its source where one exists.

## Timing: the traffic light

A purchase is rarely announced in advance, so SalesIntel infers timing from clues that are not the purchase itself, in the way a traffic light's timing can be inferred from the traffic around it. Each dated clue implies a window, using industry rules of thumb:

| Clue | Window it implies |
|---|---|
| System installed, building opened or refurbished | Replacement typically 10 to 15 years later for fire alarm and intruder panels, 6 to 10 for CCTV, 8 to 12 for access control |
| Fire or security supplier appointed | Re-procurement prepared from about 2.5 years, contracts commonly 3 to 5 years; little appetite to change in the first year |
| Contract end stated | The nine months before the end |
| Financial year end | Budgets set two to six months before it |
| New estates, facilities or security leader | Supplier reviews in the first nine months |
| New site opening | Procurement three to twelve months before opening |
| Incident, or the incumbent in difficulty | A review within four to six months |
| Compliance deadline tied to the organisation | The year before the deadline |

Windows from independent kinds of clue that overlap are shown as converging. The result is a phase, never a probability:

- **Engage now**: a firm clue is active now, or independent clues converge now.
- **Prepare**: a window opens within 12 months, or only weak inferred clues are active.
- **Not yet**: recently contracted, or the window is more than a year away. Incidents, incumbent difficulty, stated contract ends and deadlines override a recent contract.
- **Timing unknown**: no dated clue specific to the organisation.

A deadline that applies to everyone, such as the PSTN switch-off on 31 January 2027, counts only when a source ties it to the organisation; otherwise it is shown as context.

## People and contact details

SalesIntel shows a person only where a public source names them in a professional role at the organisation, and keeps the exact quote that does so. It shows a contact detail only where a source states it verbatim for business use. It never guesses or constructs email addresses, and it rejects personal email domains. Anything that fails these checks is removed and counted.

Confirm details before use, keep to business contacts, and honour any request not to be contacted (UK GDPR and PECR).

## Limits

- Research uses Claude with web search and costs Anthropic API credit per search.
- Public sources rarely name the incumbent fire or security provider; it is often unknown.
- Rules of thumb vary by site and system. Treat timing as a prompt to check, not a forecast.
- The code is in `backend/app/services/prospect_research.py` and `backend/app/intelligence/timing_inference.py`.
