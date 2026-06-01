"""JWT authentication for dashboard and approval APIs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from thekedar_shared.settings import Settings, get_settings

_bearer = HTTPBearer(auto_error=False)

ALGORITHM = "HS256"
DEFAULT_TTL_HOURS = 24


@dataclass(frozen=True)
class AuthPrincipal:
    tenant_id: str
    subject: str = "dashboard-user"


def resolve_jwt_secret(settings: Settings) -> str:
    if settings.jwt_secret is not None:
        return settings.jwt_secret.get_secret_value()
    if settings.demo_mode or settings.environment == "local":
        return "thekedar-demo-jwt-local-only-32bytes!!"
    raise RuntimeError(
        "THEKEDAR_JWT_SECRET is required when THEKEDAR_DEMO_MODE is false "
        f"and THEKEDAR_ENVIRONMENT={settings.environment}"
    )


def create_access_token(
    settings: Settings,
    tenant_id: str,
    subject: str = "dashboard-user",
    hours: int = DEFAULT_TTL_HOURS,
) -> str:
    secret = resolve_jwt_secret(settings)
    payload = {
        "sub": subject,
        "tenant_id": tenant_id,
        "exp": datetime.now(UTC) + timedelta(hours=hours),
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_access_token(settings: Settings, token: str) -> AuthPrincipal:
    secret = resolve_jwt_secret(settings)
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc
    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing tenant_id")
    return AuthPrincipal(
        tenant_id=str(tenant_id),
        subject=str(payload.get("sub", "dashboard-user")),
    )


def get_current_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthPrincipal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decode_access_token(settings, credentials.credentials)
