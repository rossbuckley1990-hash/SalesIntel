"""The patch brief API: the five leads for a rep's patch, the reps themselves, and the brief as text for the owner to send."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from pydantic import Field
from sqlalchemy.orm import Session

from app.auth import tenant_db
from app.routers.atlas import _ensure as ensure_atlas
from app.routers.salesintel import Strict, permitted, run
from app.services import patch

router = APIRouter(prefix='/api/si/patch', tags=['patch'], dependencies=[Depends(permitted)])


class RepIn(Strict):
    name: str = Field(min_length=1, max_length=60)
    regions: list[str] = Field(default_factory=list, max_length=12)
    services: list[str] = Field(default_factory=list, max_length=12)
    sectors: list[str] = Field(default_factory=list, max_length=12)
    targets: list[str] = Field(default_factory=list, max_length=25)
    active: bool = True


class ActiveIn(Strict):
    name: str = Field(min_length=1, max_length=60)


def _view(db: Session, rep: str | None) -> dict:
    ensure_atlas(db)  # each lead's brief reads who holds what from the shared contract index
    return patch.view(db, rep)


@router.get('')
def get_patch(rep: str | None = Query(None, max_length=60), db: Session = Depends(tenant_db)):
    """Five leads for the rep's patch (the active rep unless one is named), chosen by the rule the response states."""
    return run(db, lambda: _view(db, rep))


@router.get('/text', response_class=PlainTextResponse)
def patch_text(rep: str | None = Query(None, max_length=60), db: Session = Depends(tenant_db)):
    """The same five as plain text, for the owner to paste into an email. SalesIntel sends nothing."""
    def work():
        ensure_atlas(db)
        return patch.text(db, rep)
    return run(db, work)


@router.get('/reps')
def get_reps(db: Session = Depends(tenant_db)):
    """The reps and the one whose patch is on screen. Light: every screen asks, so a verdict is recorded against the right rep."""
    return run(db, lambda: patch.reps(db))


@router.put('/reps')
def save_rep(payload: RepIn, db: Session = Depends(tenant_db)):
    def work():
        saved = patch.save_rep(db, payload.model_dump(exclude={'active'}), active=payload.active)
        return _view(db, saved['name'])
    return run(db, work)


@router.post('/active')
def choose_rep(payload: ActiveIn, db: Session = Depends(tenant_db)):
    def work():
        patch.choose_rep(db, payload.name)
        return _view(db, payload.name)
    return run(db, work)


@router.delete('/reps/{name}')
def remove_rep(name: str, db: Session = Depends(tenant_db)):
    def work():
        patch.remove_rep(db, name)
        return _view(db, None)
    return run(db, work)
