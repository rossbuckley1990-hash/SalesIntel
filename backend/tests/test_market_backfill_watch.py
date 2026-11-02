from datetime import UTC,datetime
import importlib.util
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db import Base
from app.models.market_network import MarketSourceState

path=Path(__file__).resolve().parents[1]/'scripts'/'market_backfill_watch.py'
spec=importlib.util.spec_from_file_location('market_backfill_watch',path)
watch=importlib.util.module_from_spec(spec); spec.loader.exec_module(watch)


def test_budget_survives_session_restart_and_resets_daily():
    engine=create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine,tables=[MarketSourceState.__table__])
    now=datetime(2026,10,28,tzinfo=UTC)
    with Session(engine) as db:
        assert watch.reserve_budget(db,2,now)
        assert watch.reserve_budget(db,2,now)
    with Session(engine) as db:
        assert not watch.reserve_budget(db,2,now)
        assert watch.reserve_budget(db,2,datetime(2026,10,29,tzinfo=UTC))
    engine.dispose()


def test_completed_windows_are_not_selected_again():
    engine=create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine,tables=[MarketSourceState.__table__])
    with Session(engine) as db:
        assert watch.candidates(db,2021,2021)==(2021,(2021,1,3))
        db.add(MarketSourceState(source_key='contracts_finder_backfill_2021',watermark=datetime(2022,1,1,tzinfo=UTC)))
        db.add(MarketSourceState(source_key='pcs_2021_01_3',last_success_at=datetime(2026,1,1,tzinfo=UTC)))
        db.commit()
        assert watch.candidates(db,2021,2021)==(None,(2021,1,103))
        db.add(MarketSourceState(source_key='pcs_2021_01_103',last_success_at=datetime(2026,1,1,tzinfo=UTC)))
        db.commit()
        assert watch.candidates(db,2021,2021)==(None,(2021,2,3))
        db.add(MarketSourceState(source_key='pcs_2021_02_3',failure_count=3,last_error='HTTP 503'))
        db.commit()
        assert watch.candidates(db,2021,2021)==(None,(2021,2,103))
        assert watch.failed_windows(db,2021,2021)==['pcs_2021_02_3']
    engine.dispose()
