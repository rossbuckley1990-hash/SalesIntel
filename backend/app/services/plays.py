"""Guided revenue plays: from the signal that opened an account to a qualified deal, one prepared step at a time.

A play is chosen from what the account's evidence actually is (a new building, a contract ending, a published
tender, an existing customer's new site, a documented supplier change). Each step's state is read from what has
been recorded (dossier, contacts, gap research, drafts, activities, follow-ups, deals), never ticked by hand, so the
play cannot claim progress that did not happen.
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.crm import Account, AccountLink, Activity, DealRecord, Draft, Task
from app.models.gaps import GapRequest
from app.models.shadow import Dossier
from app.services import committee as cm

PLAYS = {
    'new_site': {'label': 'New site', 'hypothesis': 'A new or enlarged building will need fire and security systems designed, installed and then maintained.',
                 'qualify': ['A named person confirms there is a fire or security requirement for the site', 'Who buys it: the owner directly, or the main contractor as a package',
                             'When the systems are specified, installed and handed over', 'Who will maintain them after handover, and whether an incumbent covers it']},
    'renewal': {'label': 'Contract renewal', 'hypothesis': 'A published contract is reaching its end; the buyer will extend, re-tender or bring it in house.',
                'qualify': ['The published term and any extension options', 'Whether the buyer intends to re-tender, and when',
                            'How the current supplier is performing, from the buyer, not assumed', 'The route to market: framework, open tender or direct award']},
    'public_tender': {'label': 'Public tender', 'hypothesis': 'A published procurement is open or expected; respond through the buyer\'s portal and rules.',
                      'qualify': ['Eligibility and mandatory requirements, from the notice and documents', 'Evaluation method and weightings, as published',
                                  'Deadlines and clarification window', 'Whether you can deliver and price it competitively']},
    'expansion': {'label': 'Estate expansion', 'hypothesis': 'An existing customer\'s new site or contract event may extend your relationship.',
                  'qualify': ['The new site belongs to the same organisation (not a namesake)', 'Whether your current contract covers it',
                              'Who decides for the new site', 'Timing of fit-out or handover']},
    'develop': {'label': 'Account development', 'hypothesis': 'No new-site, tender or supplier-change evidence: establish directly whether there is a need. Any signal is a reason to call, not a requirement.',
                'qualify': ['Who is responsible for fire and security, and who decides', 'What is in place today and who maintains it',
                            'Any contract end, change or pain the customer states', 'Timing and budget route for any change']},
    'supplier_review': {'label': 'Potential supplier review', 'hypothesis': 'A documented supplier change or performance event may open a conversation about alternatives.',
                        'qualify': ['The documented event, verified from its source', 'Whether it affects this customer\'s service',
                                    'Who owns the relationship and whether they are reviewing it', 'Any contract term that governs change']},
}
SENSOR_PLAY = {'estate_mobilisation': 'new_site', 'adjacent_package': 'new_site', 'modernisation': 'new_site', 'remediation': 'supplier_review',
               'supplier_transition': 'supplier_review', 'consolidation': 'expansion', 'funded_capital': 'new_site', 'leadership_change': 'new_site'}
GAPS = {  # (gap, subject, question) the play needs answered, beyond the committee
    'new_site': [('site_status', 'Site status', 'Has construction started, and when does the new site open?'),
                 ('site_operator', 'Who will run the site', 'Who will operate and maintain the new building after handover?'),
                 ('incumbent', 'Current fire and security supplier', 'Which company currently maintains this organisation\'s fire or security systems?'),
                 ('contract_end', 'Contract end date', 'When does the current fire and security maintenance contract end, and could it absorb the new site?')],
    'renewal': [('contract_end', 'Contract end date', 'When does the current contract end, and are there extension options?'),
                ('incumbent', 'Current supplier', 'Which company currently holds this contract?'),
                ('award_document', 'Original award notice', 'Where is the original contract award notice published?')],
    'public_tender': [('evaluation_criteria', 'Evaluation criteria', 'What are the published evaluation criteria and weightings?'),
                      ('incumbent', 'Current supplier', 'Which company currently provides this service?')],
    'expansion': [('site_status', 'New site status', 'Has the new site opened, and who operates it?'),
                  ('incumbent', 'Current supplier at the new site', 'Which company maintains fire or security systems at the new site?'),
                  ('site_operator', 'Who will run the site', 'Who operates the new site day to day, and who decides on its fire and security?')],
    'develop': [('incumbent', 'Current fire and security supplier', 'Which company currently maintains this organisation\'s fire or security systems?'),
                ('contract_end', 'Contract end date', 'When does the current fire or security maintenance contract end?')],
    'supplier_review': [('incumbent', 'Current supplier', 'Which company currently provides fire or security services here?'),
                        ('contract_end', 'Contract end date', 'When does the current contract end?')],
}


def play_for(db: Session, account: Account) -> str:
    links = db.scalars(select(AccountLink).where(AccountLink.account_id == account.id).order_by(AccountLink.id)).all()
    if account.status == 'customer' and len(links) > 0:
        return 'expansion'
    for link in links:
        if link.entity_type == 'shadow_hypothesis':
            from app.services import shadow
            found = shadow.current(db, link.entity_id)
            if found:
                return SENSOR_PLAY.get(found[1]['sensor'], 'new_site')
        if link.entity_type == 'market_opportunity':
            from app.services.si_core import _mo
            found = _mo(db, link.entity_id)
            category = (found[1].get('category') if found else '') or ''
            return 'public_tender' if category in ('live_procurement', 'official_early_signal') else 'renewal'
        if link.entity_type == 'prospect':
            # Only sourced, stated evidence of a site makes this a new-site play; otherwise develop the account.
            from app.models.prospect import Prospect
            row = db.get(Prospect, link.entity_id)
            sourced = {x.get('type') for x in ((row.data.get('signals') if row else None) or [])
                       if x.get('source_url') and x.get('basis') in ('stated', 'published')}
            if sourced & {'new_site', 'relocation', 'planning_application'}:
                return 'new_site'
            if 'incumbent_poor_performance' in sourced:
                return 'supplier_review'
            return 'develop'
    return 'develop'  # no linked evidence: never assume a new building or a tender


def view(db: Session, account_id: int) -> dict:
    account = db.get(Account, account_id)
    if account is None:
        raise LookupError('Account not found')
    play = play_for(db, account)
    spec = PLAYS[play]
    links = db.scalars(select(AccountLink).where(AccountLink.account_id == account_id)).all()
    dossier = db.scalar(select(Dossier).where(Dossier.account_id == account_id).order_by(Dossier.version.desc()))
    people = cm.committee(db, account_id, play)
    requests = db.scalars(select(GapRequest).where(GapRequest.account_id == account_id).order_by(GapRequest.id.desc())).all()
    drafts = db.scalars(select(Draft).where(Draft.account_id == account_id)).all()
    acts = db.scalars(select(Activity).where(Activity.account_id == account_id).order_by(Activity.occurred_at.desc())).all()
    open_tasks = db.scalars(select(Task).where(Task.account_id == account_id, Task.status == 'open')).all()
    deals = db.scalars(select(DealRecord).where(DealRecord.account_id == account_id)).all()

    latest = {}
    for r in requests:  # the newest request for each gap answers it
        latest.setdefault((r.gap, r.subject), r)
    gaps = []
    for gap, subject, question in GAPS[play]:
        r = latest.get((gap, subject))
        gaps.append({'gap': gap, 'subject': subject, 'question': question, 'request': request_dict(r) if r else None,
                     'open': r is None or r.status not in ('resolved',)})
    for role in people['roles'][:3]:  # the first roles of the committee are the ones to find
        if role['gap']:
            r = latest.get(('find_role', role['label']))
            gaps.append({'gap': 'find_role', 'subject': role['label'], 'question': f"Who is the {role['label'].lower()}, and how can they be reached?",
                         'request': request_dict(r) if r else None, 'open': r is None or r.status != 'resolved'})

    outbound = [a for a in acts if a.direction == 'outbound' and a.kind in ('call', 'email', 'meeting', 'site_visit')]
    requirement = next((a for a in acts if a.outcome == 'requirement_captured' or (a.requirements or '').strip()), None)
    covered = [r for r in people['roles'] if r['status'] == 'covered']
    routes = [r for r in people['roles'] if r['status'] != 'gap']
    open_gaps = [g for g in gaps if g['open']]
    steps = [
        {'key': 'evidence', 'label': 'Signal and evidence', 'state': 'done' if links else 'todo',
         'detail': f"{len(links)} linked source{'s' if len(links) != 1 else ''}" if links else 'Link the record that brought you here'},
        {'key': 'investigate', 'label': 'Investigate', 'state': 'done' if dossier else 'next',
         'detail': ({'weakened': 'Done: evidence found against it, read before acting', 'strengthened': 'Done: the research supports it',
                     'unresolved': 'Done: not settled, open questions listed'}[dossier.verdict] if dossier else 'Test the hypothesis against public evidence'),
         'action': None if dossier else 'investigate'},
        {'key': 'people', 'label': 'Find the right people', 'state': 'done' if covered else 'partial' if routes else 'next',
         'detail': f"{len(covered)} of {len(people['roles'])} roles named" + (f"; {len(routes) - len(covered)} reachable by a role route" if len(routes) > len(covered) else ''),
         'action': None if covered else 'people'},
        {'key': 'gaps', 'label': 'Resolve missing information', 'state': 'done' if not open_gaps else 'partial' if len(open_gaps) < len(gaps) else 'next',
         'detail': 'Nothing essential missing' if not open_gaps else f"{len(open_gaps)} question{'s' if len(open_gaps) != 1 else ''} open", 'action': 'gaps' if open_gaps else None},
        {'key': 'approach', 'label': 'Prepare the approach', 'state': 'done' if drafts else 'next', 'detail': 'Introduction drafted' if drafts else 'Draft an introduction from the evidence',
         'action': None if drafts else 'engage'},
        {'key': 'contact', 'label': 'Make contact', 'state': 'done' if outbound else 'next',
         'detail': f"Last: {outbound[0].kind.replace('_', ' ')} on {outbound[0].occurred_at.date():%-d %b}" if outbound else 'Log the first call, email or visit', 'action': None if outbound else 'log'},
        {'key': 'follow_up', 'label': 'Set the next step', 'state': 'done' if open_tasks else 'next',
         'detail': f"Next follow-up {min(t.due_on for t in open_tasks):%-d %b}" if open_tasks else 'Schedule the follow-up', 'action': None if open_tasks else 'log'},
        {'key': 'requirement', 'label': 'Confirm a requirement', 'state': 'done' if requirement else 'next',
         'detail': 'The customer stated a requirement' if requirement else 'Only the customer can confirm it', 'action': None if requirement else 'log'},
        {'key': 'qualify', 'label': 'Qualify into a deal', 'state': 'done' if deals else 'next' if requirement else 'todo',
         'detail': f"Deal: {deals[0].title}" if deals else 'Once a requirement is confirmed', 'action': None if deals else 'qualify' if requirement else None},
    ]
    # What needs doing next: qualify as soon as a requirement is confirmed; otherwise the selling steps in order.
    # Missing information supports the play but never blocks it, so it comes last.
    order = ['qualify', 'investigate', 'people', 'approach', 'contact', 'follow_up', 'requirement', 'gaps']
    by_key = {s['key']: s for s in steps}
    nxt = next((by_key[k] for k in order if by_key[k]['state'] in ('next', 'partial') and by_key[k].get('action')), None)
    for s in steps:
        if s['state'] == 'next' and s is not nxt:
            s['state'] = 'todo'
    outcome = {'deal_id': deals[0].id, 'stage': deals[0].stage} if deals else None
    return {'account_id': account_id, 'play': play, 'label': spec['label'], 'hypothesis': spec['hypothesis'], 'qualify': spec['qualify'],
            'steps': steps, 'next': nxt, 'gaps': gaps, 'committee': people, 'outcome': outcome,
            'done': sum(1 for s in steps if s['state'] == 'done'), 'total': len(steps), 'as_of': datetime.now(UTC).isoformat()}


def request_dict(r: GapRequest) -> dict:
    return {'id': r.id, 'gap': r.gap, 'subject': r.subject, 'question': r.question, 'status': r.status, 'summary': r.summary, 'findings': r.findings,
            'rejected': r.rejected, 'sources': r.sources, 'job_id': r.job_id, 'cost_cents': r.cost_cents, 'created_at': r.created_at.isoformat(),
            'resolved_at': r.resolved_at.isoformat() if r.resolved_at else None}
