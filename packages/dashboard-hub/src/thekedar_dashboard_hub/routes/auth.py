"""Issue dashboard JWT tokens (demo/local bootstrap)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from thekedar_shared.auth import create_access_token
from thekedar_shared.settings import Settings, get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenRequest(BaseModel):
    tenant_id: str = Field(default="default")
    bootstrap_secret: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    tenant_id: str


@router.post("/token", response_model=TokenResponse)
def issue_token(
    body: TokenRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    if settings.environment in ("staging", "prod") and not settings.demo_mode:
        if body.bootstrap_secret != _bootstrap_secret(settings):
            raise HTTPException(status_code=403, detail="Invalid bootstrap secret")
    token = create_access_token(settings, tenant_id=body.tenant_id)
    return TokenResponse(access_token=token, tenant_id=body.tenant_id)


def _bootstrap_secret(settings: Settings) -> str | None:
    if settings.jwt_secret is None:
        return None
    return settings.jwt_secret.get_secret_value()
