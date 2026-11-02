from copy import deepcopy
from datetime import UTC, datetime
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.db import Base
from app.models.market_network import MarketEntity, SourceRevision
from app.services.market_network import ingest_market_release
from app.services.market_relationships import ingest_reviewed_psc_snapshot
from app.services.market_cross_source import company_award_context

NOW=datetime(2026,10,28,tzinfo=UTC)


def db_session():
    engine=create_engine('sqlite://', connect_args={'check_same_thread':False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return Session(engine)


def procurement(record_id):
    ocid='ocds-test-123'
    return {'source_key':'contracts_finder', 'release_id':record_id, 'ocid':ocid,
            'source_url':'https://www.contractsfinder.service.gov.uk/Notice/test', 'published_at':NOW,'retrieved_at':NOW,
            'raw':{'id':record_id, 'ocid':ocid, 'tender':{'title':'Fire alarm maintenance'},'buyer':{'name':'Public Buyer'},
                   'parties':[{'id':'supplier','identifier':{'scheme':'GB-COH','id':'03304503'}}],
                   'awards':[{'id':'a1','date':'2023-02-21T00:00:00Z','suppliers':[{'id':'supplier','name':'Supplier Ltd'}]}]}}


def filing():
    return {'company_number':'03304503','company_name':'Supplier Ltd',
            'source_url':'https://find-and-update.company-information.service.gov.uk/company/03304503/persons-with-significant-control',
            'retrieved_at':'2026-10-28T00:00:00Z','controllers':[{'company_number':'12345678','company_name':'Controller Ltd',
            'notified_on':'2024-11-27','ceased_on':None,'nature_of_control':['ownership-of-shares-75-to-100-percent']} ]}


def test_join_preserves_both_sources_and_does_not_transfer_award_to_controller():
    with db_session() as db:
        ingest_market_release(db,procurement('first'))
        ingest_market_release(db,procurement('duplicate'))
        ingest_reviewed_psc_snapshot(db,filing())
        supplier=db.scalar(select(MarketEntity).where(MarketEntity.identifier_value=='03304503'))
        parent=db.scalar(select(MarketEntity).where(MarketEntity.identifier_value=='12345678'))
        links=company_award_context(db,supplier.id)
        assert len(links)==1
        result=links[0]
        assert result['supplier']=='Supplier Ltd' and result['control']['controller']=='Controller Ltd'
        assert result['notice']['source_key']=='contracts_finder' and result['control']['source_key']=='companies_house_reviewed'
        assert result['notice']['source_url'].startswith('https://www.contractsfinder.service.gov.uk/')
        assert result['control']['source_url'].startswith('https://find-and-update.company-information.service.gov.uk/')
        assert 'later than the award date' in result['timing']
        assert 'not identified as the awarded supplier' in ' '.join(result['unknowns'])
        assert company_award_context(db,parent.id)==[]


def test_evidence_identifiers_must_be_rechecked_and_no_fuzzy_name_join():
    with db_session() as db:
        ingest_market_release(db,procurement('first')); ingest_reviewed_psc_snapshot(db,filing())
        supplier=db.scalar(select(MarketEntity).where(MarketEntity.identifier_value=='03304503'))
        assert len(company_award_context(db,supplier.id))==1
        notice=db.scalar(select(SourceRevision).where(SourceRevision.source_key=='contracts_finder'))
        raw=deepcopy(notice.raw); raw['parties'][0]['identifier']['id']='87654321'; notice.raw=raw
        db.flush()
        assert company_award_context(db,supplier.id)==[]


def test_revised_registry_snapshot_must_explicitly_reference_subject_and_controller():
    with db_session() as db:
        ingest_market_release(db,procurement('first')); ingest_reviewed_psc_snapshot(db,filing())
        supplier=db.scalar(select(MarketEntity).where(MarketEntity.identifier_value=='03304503'))
        source=db.scalar(select(SourceRevision).where(SourceRevision.source_key=='companies_house_reviewed'))
        raw=deepcopy(source.raw); raw['controllers'][0]['company_number']='87654321'; source.raw=raw
        db.flush()
        assert company_award_context(db,supplier.id)==[]
