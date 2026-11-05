"""Development sign-in for automated browser tests and demos. Mounted only when AUTH_MODE=dev,
which the settings refuse outside APP_ENV=demo or test. It issues the same signed tokens the
API verifies, so tests exercise the real verification path. It is not a password system."""
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from app import auth

router = APIRouter(prefix='/api/dev', tags=['development sign-in'])


class DevSession(BaseModel):
    model_config = ConfigDict(extra='forbid')
    email: str = Field(min_length=3, max_length=255, pattern=r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
    name: str = Field(min_length=1, max_length=160)


@router.post('/session')
def dev_session(payload: DevSession):
    email = payload.email.lower()
    return {'token': auth.dev_token(f'dev|{email}', email, payload.name), 'expires_in': 3600,
            'warning': 'Development sign-in: available only in demo and test environments.'}
