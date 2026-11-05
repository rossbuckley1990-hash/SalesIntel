"""Who is calling, and for which workspace.

SalesIntel does not handle passwords, MFA or password resets. A managed identity provider
(Microsoft Entra ID, Auth0, Clerk, WorkOS or similar) does, and issues a signed token that
SalesIntel verifies here: signature against the provider's published keys, issuer,
audience, expiry and a verified email.

The workspace comes from the caller's memberships. A browser may say which of its own
workspaces it wants (``X-SalesIntel-Workspace``); that is only a selection, and it is
refused unless the verified user is a member.

``dev`` mode signs tokens with a local key so automated tests and demos can exercise the
same verification path. It is refused unless ``APP_ENV`` is demo or test.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
import secrets

from fastapi import Depends, HTTPException, Request
import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models.tenancy import LOCAL_ORG_ID, Membership, User
from app.tenancy import ORG, SYSTEM, USER, can


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)  # SQLite returns naive datetimes

WORKSPACE_HEADER = 'x-salesintel-workspace'
DEV_ISSUER = 'https://dev-auth.salesintel.test'
DEV_AUDIENCE = 'salesintel-dev'


@dataclass(frozen=True)
class Caller:
    user_id: int | None  # None only in local mode
    email: str
    name: str


@dataclass(frozen=True)
class Context:
    user_id: int | None
    organisation_id: int
    role: str
    name: str

    def require(self, permission: str) -> None:
        if not can(self.role, permission):
            raise HTTPException(status_code=403, detail='Your role does not allow this.')


# ---------------------------------------------------------------- development signer (tests and demos only)

@lru_cache
def _dev_key():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    path = get_settings().dev_auth_key_file
    if path:
        with open(path, 'rb') as handle:
            return serialization.load_pem_private_key(handle.read(), password=None)
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def dev_token(subject: str, email: str, name: str = '', *, email_verified: bool = True, minutes: int = 60, **overrides) -> str:
    settings = get_settings()
    if settings.auth_mode != 'dev' or settings.app_env not in {'demo', 'test'}:
        raise RuntimeError('Development tokens exist only in dev mode with APP_ENV=demo or test.')
    moment = datetime.now(UTC)
    claims = {'iss': DEV_ISSUER, 'aud': DEV_AUDIENCE, 'sub': subject, 'email': email, 'email_verified': email_verified, 'name': name,
              'iat': moment, 'nbf': moment, 'exp': moment + timedelta(minutes=minutes)} | overrides
    return jwt.encode(claims, _dev_key(), algorithm='RS256', headers={'kid': 'dev'})


# ---------------------------------------------------------------- verification

@lru_cache
def _jwks_client(url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(url, cache_keys=True, lifespan=3600, timeout=5)


def verify(token: str) -> dict:
    settings = get_settings()
    try:
        if settings.auth_mode == 'dev':
            key, issuer, audience, algorithms = _dev_key().public_key(), DEV_ISSUER, DEV_AUDIENCE, ['RS256']
        else:
            key = _jwks_client(settings.oidc_jwks_url).get_signing_key_from_jwt(token).key
            issuer, audience = settings.oidc_issuer, settings.oidc_audience
            algorithms = [a.strip() for a in settings.oidc_algorithms.split(',') if a.strip()]
        claims = jwt.decode(token, key, algorithms=algorithms, audience=audience, issuer=issuer, leeway=30,
                            options={'require': ['exp', 'iat', 'iss', 'aud', 'sub']})
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail='Sign in again: your session is not valid.', headers={'WWW-Authenticate': 'Bearer'}) from exc
    if not claims.get('email') or claims.get('email_verified') is not True:
        raise HTTPException(status_code=403, detail='Verify your email address with your sign-in provider first.')
    return claims


def _bearer(request: Request) -> str:
    header = request.headers.get('authorization', '')
    scheme, _, token = header.partition(' ')
    if scheme.lower() != 'bearer' or not token:
        raise HTTPException(status_code=401, detail='Sign in to use SalesIntel.', headers={'WWW-Authenticate': 'Bearer'})
    return token.strip()


def current_caller(request: Request, db: Session = Depends(get_db)) -> Caller:
    """The verified person. Creates their user record the first time they sign in."""
    if get_settings().auth_mode == 'local':
        return Caller(user_id=None, email='', name='You')
    claims = verify(_bearer(request))
    moment = datetime.now(UTC)
    user = db.scalar(select(User).where(User.issuer == claims['iss'], User.subject == claims['sub']))
    if user is None:
        user = User(issuer=claims['iss'], subject=claims['sub'], email=claims['email'].lower(), email_verified=True,
                    name=(claims.get('name') or '')[:160], created_at=moment, last_seen_at=moment)
        db.add(user)
        db.commit()
    elif user.email != claims['email'].lower() or (claims.get('name') and user.name != claims['name'][:160]) \
            or _as_utc(user.last_seen_at) < moment - timedelta(minutes=10):
        user.email, user.last_seen_at = claims['email'].lower(), moment
        if claims.get('name'):
            user.name = claims['name'][:160]
        db.commit()
    db.info[USER] = user.id
    return Caller(user_id=user.id, email=user.email, name=user.name or user.email)


def current_context(request: Request, caller: Caller = Depends(current_caller), db: Session = Depends(get_db)) -> Context:
    if get_settings().auth_mode == 'local':
        return Context(user_id=None, organisation_id=LOCAL_ORG_ID, role='admin', name='You')
    memberships = db.scalars(select(Membership).where(Membership.user_id == caller.user_id)).all()
    wanted = request.headers.get(WORKSPACE_HEADER)
    if wanted:
        chosen = next((m for m in memberships if str(m.organisation_id) == wanted.strip()), None)
        if chosen is None:
            raise HTTPException(status_code=403, detail='You are not a member of that workspace.')
    elif len(memberships) == 1:
        chosen = memberships[0]
    elif not memberships:
        raise HTTPException(status_code=409, detail='Create or join a workspace first.')
    else:
        raise HTTPException(status_code=400, detail='Choose a workspace.')
    return Context(user_id=caller.user_id, organisation_id=chosen.organisation_id, role=chosen.role, name=caller.name)


def tenant_db(ctx: Context = Depends(current_context), db: Session = Depends(get_db)) -> Session:
    """The request's database session, bound to the caller's workspace for every query and write."""
    db.info[ORG] = ctx.organisation_id
    db.info[USER] = ctx.user_id
    db.info.pop(SYSTEM, None)
    return db


def new_invitation_token() -> str:
    return secrets.token_urlsafe(32)
