"""热点查询 API。"""

from __future__ import annotations

from datetime import date as date_cls

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import DailyReport, HotAnalysis, JobRun
from app.pipeline.daily_job import _row_to_dict
from app.schemas import ApiResponse, CategoryStat, HotItemOut, TodayStats

router = APIRouter(prefix="/api", tags=["hot"])


@router.get("/hot/category", response_model=ApiResponse[list[HotItemOut]])
def hot_by_category(
    category: str = Query(...),
    report_date: date_cls | None = Query(None, alias="date"),
    db: Session = Depends(get_db),
):
    d = report_date or date_cls.today()
    rows = db.scalars(
        select(HotAnalysis)
        .where(HotAnalysis.report_date == d, HotAnalysis.category == category)
        .order_by(desc(HotAnalysis.importance), desc(HotAnalysis.heat))
    ).all()
    return ApiResponse(data=[HotItemOut(**_row_to_dict(r)) for r in rows])


@router.get("/hot/search", response_model=ApiResponse[list[HotItemOut]])
def hot_search(
    report_date: date_cls | None = Query(None, alias="date"),
    category: str | None = Query(None),
    keyword: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = select(HotAnalysis)
    if report_date:
        q = q.where(HotAnalysis.report_date == report_date)
    if category:
        q = q.where(HotAnalysis.category == category)
    if keyword:
        like = f"%{keyword}%"
        q = q.where(
            (HotAnalysis.title.like(like))
            | (HotAnalysis.summary.like(like))
            | (HotAnalysis.tags.like(like))
        )
    q = q.order_by(desc(HotAnalysis.report_date), desc(HotAnalysis.importance)).limit(limit)
    rows = db.scalars(q).all()
    return ApiResponse(data=[HotItemOut(**_row_to_dict(r)) for r in rows])


@router.get("/hot/ranking", response_model=ApiResponse[list[HotItemOut]])
def hot_ranking(
    report_date: date_cls | None = Query(None, alias="date"),
    by: str = Query("importance", pattern="^(importance|heat)$"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    d = report_date or date_cls.today()
    order = desc(HotAnalysis.importance) if by == "importance" else desc(HotAnalysis.heat)
    rows = db.scalars(
        select(HotAnalysis)
        .where(HotAnalysis.report_date == d)
        .order_by(order, desc(HotAnalysis.heat))
        .limit(limit)
    ).all()
    return ApiResponse(data=[HotItemOut(**_row_to_dict(r)) for r in rows])


@router.get("/stats/today", response_model=ApiResponse[TodayStats])
def stats_today(
    report_date: date_cls | None = Query(None, alias="date"),
    db: Session = Depends(get_db),
):
    d = report_date or date_cls.today()
    hot_count = (
        db.scalar(
            select(func.count()).select_from(HotAnalysis).where(HotAnalysis.report_date == d)
        )
        or 0
    )
    cat_rows = db.execute(
        select(HotAnalysis.category, func.count())
        .where(HotAnalysis.report_date == d)
        .group_by(HotAnalysis.category)
    ).all()
    categories = [CategoryStat(category=c or "其他", count=int(n)) for c, n in cat_rows]
    categories.sort(key=lambda x: -x.count)
    report = db.scalar(select(DailyReport).where(DailyReport.report_date == d))
    job = db.scalar(
        select(JobRun)
        .where(JobRun.report_date == d, JobRun.job_name == "daily_analyze")
        .order_by(desc(JobRun.id))
        .limit(1)
    )
    return ApiResponse(
        data=TodayStats(
            date=d,
            hot_count=int(hot_count),
            categories=categories,
            has_report=report is not None,
            report_summary=report.summary if report else None,
            job_status=job.status if job else None,
        )
    )
