"""
SENTINEL Gateway — Auth Middleware
====================================
JWT-based tenant authentication via python-jose.
Every request must carry:  Authorization: Bearer <token>
Tokens are issued at POST /auth/token with tenant credentials.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext

from sentinel.config import settings

logger = logging.getLogger("sentinel.auth")

# ── Crypto utilities ───────────────────────────────────────────────────────────

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── Token creation / decoding ──────────────────────────────────────────────────

def create_access_token(tenant_id: str, expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.jwt_expire_minutes)
    )
    payload = {"sub": tenant_id, "exp": expire, "iat": datetime.utcnow()}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> str:
    """Returns tenant_id or raises HTTPException 401."""
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.jwt_algorithm]
        )
        tenant_id: Optional[str] = payload.get("sub")
        if not tenant_id:
            raise ValueError("missing sub claim")
        return tenant_id
    except JWTError as exc:
        logger.warning("JWT decode failure: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── FastAPI dependency ─────────────────────────────────────────────────────────

async def get_current_tenant(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    """FastAPI dependency — inject into any route that requires authentication."""
    return decode_token(credentials.credentials)
