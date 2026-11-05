import json
from datetime import UTC, datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.config import Settings
from app.db import Base
from app.models.market_opportunity import MarketOpportunity, MarketOpportunityDossier, MarketOpportunityRevision
from app.services.opportunity_dossier import DossierUnavailable, create_dossier, latest_dossier

NOW = datetime(2026, 11, 4, tzinfo=UTC)
GOOD = 'https://www.example.gov.uk/estates-strategy'


@pytest.fixture
def db():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine, tables=[MarketOpportunity.__table__, MarketOpportunityRevision.__table__, MarketOpportunityDossier.__table__])
    with Session(engine, expire_on_commit=False) as session:
        item = MarketOpportunity(dedup_key='renewal:x', first_seen=NOW, last_evaluated=NOW)
        session.add(item)
        session.flush()
        version = MarketOpportunityRevision(opportunity_id=item.id, fingerprint='f', created_at=NOW, result={
            'customer': 'Example Council', 'title': 'Fire alarm maintenance', 'category_label': 'Pre-tender', 'nation': 'England',
            'supplier': 'Incumbent Ltd', 'timing': '2027-03-31', 'timing_basis': 'Published end date', 'value': {'basis': 'Published'},
            'brief': {'contract_lifecycle': '3 years', 'procurement_route': 'Open', 'missing_information': []},
            'evidence': [{'source_url': 'https://www.find-tender.service.gov.uk/Notice/1'}]})
        session.add(version)
        session.flush()
        item.current_revision_id = version.id
        session.commit()
        yield session
    engine.dispose()


def dossier(url):
    return {'headline': 'Engage estates before the spring re-tender.', 'summary': 'S', 'recommendation': {'stance': 'pursue', 'rationale': 'R'},
            'buyer': {'overview': 'O', 'estate': 'E', 'priorities': ['P'], 'developments': [{'date': '2026', 'development': 'D', 'relevance': 'R', 'source_url': url}]},
            'contract': {'position': 'P', 'incumbent': 'I', 'timeline': 'T', 'route': 'R'},
            'signals': [{'signal': 'S', 'basis': 'stated', 'direction': 'supports', 'source_url': 'https://invented.example/x'}],
            'decision_roles': [{'role': 'Head of Estates', 'why': 'Owns budget'}], 'win_strategy': {'angle': 'A', 'themes': [], 'proof_points': []},
            'risks': [], 'questions': [], 'next_steps': [], 'unknowns': [], 'sources': [{'title': 'Made up', 'url': 'https://invented.example/y'}]}


def fake_provider(calls, pause=False):
    def post(payload):
        calls.append(payload)
        if 'tools' in payload:
            if pause and len(calls) == 1:
                return {'stop_reason': 'pause_turn', 'content': [{'type': 'web_search_tool_result', 'content': [{'type': 'web_search_result', 'url': GOOD, 'title': 'Estates strategy'}]}]}
            return {'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': 'The council plans a new depot.', 'citations': [{'url': GOOD, 'title': 'Estates strategy', 'cited_text': 'new depot'}]}]}
        return {'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': json.dumps(dossier(GOOD))}]}
    return post


def test_dossier_keeps_only_searched_sources_and_is_saved(db):
    calls = []
    result = create_dossier(db, 1, post=fake_provider(calls, pause=True), settings=Settings(anthropic_model='claude-opus-5-5'), now=NOW)
    assert len(calls) == 3  # paused search, resumed search, structuring
    assert calls[1]['messages'][1]['role'] == 'assistant'
    assert calls[0]['tools'][0]['type'] == 'web_search_20260209' and 'output_config' not in calls[0]
    assert 'output_config' in calls[2] and 'tools' not in calls[2]
    assert 'Example Council' in calls[0]['messages'][0]['content']
    assert result['buyer']['developments'][0]['source_url'] == GOOD
    assert result['signals'][0]['source_url'] == ''
    assert [s['url'] for s in result['sources']] == [GOOD]
    assert latest_dossier(db, 1)['headline'] == result['headline'] and result['model'] == 'claude-opus-5-5'


def test_missing_key_and_unknown_opportunity(db):
    with pytest.raises(DossierUnavailable):
        create_dossier(db, 1, settings=Settings(anthropic_api_key=None))
    with pytest.raises(LookupError):
        create_dossier(db, 99, post=fake_provider([]))
    assert latest_dossier(db, 1) is None
