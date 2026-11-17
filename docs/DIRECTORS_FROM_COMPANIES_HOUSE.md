# Directors from Companies House: legitimate interests note and privacy text

Agreed on 17 November 2026: who to call about a lead can name the directors of a small firm from the Companies House register. This page records why that is a fair use of personal data, and the text a privacy notice should carry. It is a working draft by the product owner, not legal advice: have someone qualified check it before reps pay for SalesIntel.

## What SalesIntel does

- **Which companies.** Only a company that is active, is not a public limited company, files small-company or micro-entity accounts, and has at most four active directors. At any larger company a director rarely buys fire and security, so SalesIntel names none and suggests asking for the facilities or site manager.
- **What it keeps.** For each active director, only the first name, surname, role and appointment date. It never keeps a date of birth, nationality, country of residence, occupation, middle names or any address. Secretaries, corporate directors and anyone who has resigned are left out.
- **When it reads.** Only for a lead a rep is working on: when research gives the company number, or when the rep chooses the company on the lead page. SalesIntel does not build a list of directors, and it does not search the register for people.
- **Identity.** A company is found by its number, never by a similar name alone. A number that research gives must belong to a company whose registered name matches the lead's. A company the rep chooses from a search is taken as the rep's choice.
- **No route.** Companies House gives no phone number or email address. SalesIntel names the person and uses only a way in that a public source, the organisation's own website or the rep's team already gave.
- **Opting out.** Anyone the team marks "do not contact" is left out wherever they are named, the register included.
- **What the rep is told.** The text SalesIntel prepares for the rep says where each detail came from, asks them to check numbers against the CTPS and TPS do-not-call registers before a cold call, and to tell anyone they contact where their details were found.

The code is `backend/app/services/directors.py` and `fetch_directors` in `backend/app/ingestion/companies_house.py`.

## Legitimate interests assessment

**Purpose.** Reps selling fire and security services need to know who decides at a small business, so they can make one relevant business call instead of many. At a small owner-managed company that person is usually a director. This is a legitimate commercial interest, and the director also benefits when the approach concerns their duties for fire safety on the premises.

**Necessity.** The register is the authoritative public record of who directs a company, published under the Companies Act 2006 so that others can see who runs it. SalesIntel uses the least it can: the name and role, read for one company at a time for a lead already being worked on, and only where a director is likely to be the decision maker. A less intrusive way to reach the same result is to ask a main line for "the person responsible for fire safety", and SalesIntel still does that wherever a director is not the right person.

**Balance.** The data is about the person in their business role, not their private life. Directors of small companies can reasonably expect a business approach about their premises; they would not expect their home address or date of birth to be used, and SalesIntel keeps neither. The risk of harm is low: no profiling, no sale or sharing of lists, no email address built from a name. The person can object at any time, and the team's "do not contact" marking removes them wherever they appear.

**Outcome.** Legitimate interests is a reasonable basis for this use, with the safeguards above. Review the decision when reps first pay, when the data used changes, or if anyone objects.

## Text for the privacy notice

> **Directors of small companies.** When a SalesIntel user is working on a lead, SalesIntel may read the Companies House register for that one company. If it is a small company, SalesIntel shows the user the first name, surname, role and appointment date of its active directors, so that the user knows who is likely to decide on fire and security at the business. We do not keep dates of birth, nationalities, addresses or other details from the register, and we do not keep any contact details that Companies House publishes, because it publishes none for directors. Our lawful basis is legitimate interests. You can object at any time by contacting [contact address]; we will stop showing your details to users. You can also ask to see or delete what we hold, and you can complain to the Information Commissioner's Office (ico.org.uk).

Fill in [contact address] before the notice is published. The same notice should also describe the other sources of contact details: public pages found by research, and the organisation's own website, read by SalesIntel.
