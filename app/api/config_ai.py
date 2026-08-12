"""AI 配置管理 API。"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.ai.factory import clear_provider_cache
from app.config import get_config
from app.db.models import AIConfigRow
from app.schemas import AIConfigOut, AIConfigUpdate, ApiResponse
from app.security.crypto import encrypt_secret, mask_secret

router = APIRouter(prefix="/api/ai", tags=["ai-config"])


def _to_out(row: AIConfigRow) -> AIConfigOut:
    return AIConfigOut(
        id=row.id,
        name=row.name,
        provider=row.provider,
        model=row.model,
        api_url=row.api_url,
        api_key=mask_secret(row.api_key),
        enabled=bool(row.enabled),
        priority=row.priority or 100,
        updated_at=row.updated_at,
    )


@router.get("/config", response_model=ApiResponse[list[AIConfigOut]])
def list_ai_config(db: Session = Depends(get_db)):
    rows = db.scalars(select(AIConfigRow).order_by(AIConfigRow.priority)).all()
    return ApiResponse(data=[_to_out(r) for r in rows])


@router.put("/config/{config_id}", response_model=ApiResponse[AIConfigOut])
def update_ai_config(
    config_id: int,
    body: AIConfigUpdate,
    db: Session = Depends(get_db),
):
    row = db.get(AIConfigRow, config_id)
    if not row:
        raise HTTPException(status_code=404, detail="config not found")
    if body.model is not None:
        row.model = body.model
    if body.api_url is not None:
        row.api_url = body.api_url
    if body.enabled is not None:
        row.enabled = body.enabled
    if body.priority is not None:
        row.priority = body.priority
    if body.api_key is not None and body.api_key not in ("", "****"):
        encrypt = get_config().security.encrypt_api_key
        row.api_key = encrypt_secret(body.api_key) if encrypt else body.api_key
    row.updated_at = datetime.now()
    db.commit()
    db.refresh(row)
    clear_provider_cache()
    return ApiResponse(data=_to_out(row))
