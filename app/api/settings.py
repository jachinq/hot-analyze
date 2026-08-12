"""系统运行时配置 API（collector / AI 全局 / scheduler / pipeline）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.ai.factory import clear_provider_cache
from app.schemas import (
    AIProviderTestRequest,
    ApiResponse,
    CollectorTestRequest,
    ConnectionTestResult,
    SystemSettingsOut,
    SystemSettingsUpdate,
)
from app.scheduler.jobs import reload_scheduler
from app.settings.connectivity import test_ai_provider, test_collector
from app.settings.runtime import (
    ai_globals_dict,
    get_runtime_config,
    update_section,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _to_out() -> SystemSettingsOut:
    cfg = get_runtime_config()
    return SystemSettingsOut(
        collector=cfg.collector.model_dump(),
        ai=ai_globals_dict(cfg),
        scheduler=cfg.scheduler.model_dump(),
        pipeline=cfg.pipeline.model_dump(),
    )


@router.get("", response_model=ApiResponse[SystemSettingsOut])
def get_settings():
    return ApiResponse(data=_to_out())


@router.put("", response_model=ApiResponse[SystemSettingsOut])
def put_settings(body: SystemSettingsUpdate, db: Session = Depends(get_db)):
    if body.collector is None and body.ai is None and body.scheduler is None and body.pipeline is None:
        raise HTTPException(status_code=400, detail="no settings to update")

    scheduler_changed = False
    try:
        if body.collector is not None:
            update_section(db, "collector", body.collector.model_dump())
        if body.ai is not None:
            update_section(db, "ai", body.ai.model_dump())
            clear_provider_cache()
        if body.scheduler is not None:
            update_section(db, "scheduler", body.scheduler.model_dump())
            scheduler_changed = True
        if body.pipeline is not None:
            update_section(db, "pipeline", body.pipeline.model_dump())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if scheduler_changed:
        reload_scheduler()

    return ApiResponse(data=_to_out())


@router.post("/test/collector", response_model=ApiResponse[ConnectionTestResult])
async def test_collector_connection(body: CollectorTestRequest):
    result = await test_collector(
        base_url=body.base_url,
        list_path=body.list_path,
        timeout_sec=body.timeout_sec,
    )
    return ApiResponse(data=ConnectionTestResult(**result))


@router.post("/test/ai-provider", response_model=ApiResponse[ConnectionTestResult])
async def test_ai_provider_connection(
    body: AIProviderTestRequest,
    db: Session = Depends(get_db),
):
    result = await test_ai_provider(
        db,
        config_id=body.id,
        name=body.name,
        provider=body.provider,
        api_url=body.api_url,
        model=body.model,
        api_key=body.api_key,
        timeout_sec=body.timeout_sec,
    )
    return ApiResponse(data=ConnectionTestResult(**result))
