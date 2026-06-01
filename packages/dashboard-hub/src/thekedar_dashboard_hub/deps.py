"""Dashboard API dependencies."""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session
from thekedar_shared.auth import AuthPrincipal, get_current_principal


def get_session(request: Request) -> Session:
    factory = request.app.state.session_factory
    session = factory()
    try:
        yield session
    finally:
        session.close()


def get_tenant(
    principal: Annotated[AuthPrincipal, Depends(get_current_principal)],
) -> str:
    return principal.tenant_id
