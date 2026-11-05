"""The research a job can run. Each handler holds the job's lease and checks for cancellation between steps."""
from __future__ import annotations

from datetime import UTC, datetime

from app.config import get_settings
from app.models.prospect import ProspectSearch
from app.services import navigator
from app.services.ai_costs import research_provider
from app.services.jobs import Run, handler
from app.services.si_core import preferences


def _seller(run: Run) -> str:
    return preferences(run.db).get('company_name') or ''


@handler('contact_navigator')
def contact_navigator(run: Run) -> dict:
    settings = get_settings()
    meter = research_provider(settings) if run.job.params.get('use_ai', True) else None
    if meter is not None:
        meter.ceiling_cents = run.job.estimated_cents
    run.meter = meter
    result = navigator.run(run.db, run.job.account_id, meter, seller=_seller(run),
                           fetch_notices=settings.navigator_fetch_published_notices or settings.research_provider == 'replay', step=run.step)
    if meter is not None:
        run.job.usage, run.job.actual_cents = meter.summary(), meter.cents
    if meter is None:
        result['note'] = 'Web research is not available here, so only official notices and saved research were checked.'
    return result


@handler('prospect_search')
def prospect_search(run: Run) -> dict:
    from app.services.prospect_research import run_search
    settings = get_settings()
    meter = research_provider(settings)
    if meter is None:
        raise ValueError('Web research is not available here, so no API credit is used.')
    meter.ceiling_cents = run.job.estimated_cents
    run.meter = meter
    run.step('Searching the web for organisations that match your brief')
    search = ProspectSearch(query=run.job.params['query'], mode='discover', status='running', model='', prospect_ids=[], sources_reviewed=0,
                            created_at=datetime.now(UTC))
    run.db.add(search)
    run.db.flush()
    run_search(run.db, search, post=meter, settings=settings, seller=_seller(run), replayed=meter.simulated)
    run.job.usage, run.job.actual_cents = meter.summary(), meter.cents
    if search.status != 'complete':
        return {'status': 'failed', 'stage': 'Research did not complete', 'message': search.error or 'The research did not complete.', 'prospect_ids': []}
    return {'status': 'succeeded', 'stage': 'Complete', 'prospect_ids': search.prospect_ids, 'search_id': search.id,
            'message': f"{len(search.prospect_ids)} organisation(s) found, each with its sources. Signals are reasons to investigate, not confirmed requirements."}
