"""任务触发与状态 API。"""

from __future__ import annotations

from datetime import date as date_cls

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import JobRun
from app.db.session import get_session_factory
from app.pipeline.daily_job import run_daily_job
from app.schemas import ApiResponse, JobOut

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _job_out(row: JobRun) -> JobOut:
    return JobOut(
        id=row.id,
        job_name=row.job_name,
        report_date=row.report_date,
        status=row.status,
        message=row.message,
        started_at=row.started_at,
        finished_at=row.finished_at,
    )


def _run_job_sync_wrapper(report_date: date_cls, force: bool) -> None:
    """BackgroundTasks 中运行异步任务。"""
    import asyncio

    SessionLocal = get_session_factory()

    async def _inner():
        with SessionLocal() as db:
            await run_daily_job(db, report_date, force=force)

    asyncio.run(_inner())


@router.post("/analyze", response_model=ApiResponse[dict])
async def trigger_analyze(
    background_tasks: BackgroundTasks,
    report_date: date_cls | None = Query(None, alias="date"),
    force: bool = Query(False),
    sync: bool = Query(False, description="同步执行（调试用）"),
    db: Session = Depends(get_db),
):
    d = report_date or date_cls.today()
    if sync:
        result = await run_daily_job(db, d, force=force)
        return ApiResponse(data=result)
    background_tasks.add_task(_run_job_sync_wrapper, d, force)
    return ApiResponse(
        data={"date": d.isoformat(), "status": "accepted", "message": "job queued"}
    )


@router.get("/{report_date}", response_model=ApiResponse[list[JobOut]])
def get_jobs(report_date: date_cls, db: Session = Depends(get_db)):
    rows = db.scalars(
        select(JobRun).where(JobRun.report_date == report_date).order_by(desc(JobRun.id))
    ).all()
    return ApiResponse(data=[_job_out(r) for r in rows])
