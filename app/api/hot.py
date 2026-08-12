"""热点查询 API。"""

from __future__ import annotations

from datetime import date as date_cls

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import DailyReport, HotAnalysis, JobRun
from app.pipeline.topics import rows_to_topics
from app.schemas import ApiResponse, CategoryStat, TodayStats, TopicItemOut

router = APIRouter(prefix="/api", tags=["hot"])


@router.get("/hot/category", response_model=ApiResponse[list[TopicItemOut]])
def hot_by_category(
    category: str = Query(...),
    report_date: date_cls | None = Query(None, alias="date"),
    db: Session = Depends(get_db),
):
    d = report_date or date_cls.today()
    rows = list(
        db.scalars(
            select(HotAnalysis).where(
                HotAnalysis.report_date == d, HotAnalysis.category == category
            )
        ).all()
    )
    return ApiResponse(data=rows_to_topics(rows, by="importance"))


@router.get("/hot/search", response_model=ApiResponse[list[TopicItemOut]])
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
    matched = list(db.scalars(q).all())
    if not matched:
        return ApiResponse(data=[])

    # 关键词命中任一成员 → 拉回同日同簇全部成员再聚合成话题
    if report_date:
        day_rows = list(
            db.scalars(
                select(HotAnalysis).where(HotAnalysis.report_date == report_date)
            ).all()
        )
    else:
        dates = {r.report_date for r in matched}
        day_rows = list(
            db.scalars(select(HotAnalysis).where(HotAnalysis.report_date.in_(dates))).all()
        )

    topics = rows_to_topics(day_rows, by="importance")
    hit_ids = {int(r.hot_id) for r in matched}
    filtered = [
        t
        for t in topics
        if t.hot_id in hit_ids or any(m.hot_id in hit_ids for m in t.members)
    ]
    if category:
        filtered = [t for t in filtered if (t.category or "") == category]
    return ApiResponse(data=filtered[:limit])


@router.get("/hot/ranking", response_model=ApiResponse[list[TopicItemOut]])
def hot_ranking(
    report_date: date_cls | None = Query(None, alias="date"),
    by: str = Query("importance", pattern="^(importance|heat)$"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    d = report_date or date_cls.today()
    rows = list(
        db.scalars(select(HotAnalysis).where(HotAnalysis.report_date == d)).all()
    )
    return ApiResponse(data=rows_to_topics(rows, by=by, limit=limit))


@router.get("/stats/today", response_model=ApiResponse[TodayStats])
def stats_today(
    report_date: date_cls | None = Query(None, alias="date"),
    db: Session = Depends(get_db),
):
    d = report_date or date_cls.today()
    rows = list(
        db.scalars(select(HotAnalysis).where(HotAnalysis.report_date == d)).all()
    )
    hot_count = len(rows)
    topics = rows_to_topics(rows, by="importance")
    cat_map: dict[str, int] = {}
    for t in topics:
        c = t.category or "其他"
        cat_map[c] = cat_map.get(c, 0) + 1
    categories = [CategoryStat(category=c, count=n) for c, n in cat_map.items()]
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
            hot_count=hot_count,
            topic_count=len(topics),
            categories=categories,
            has_report=report is not None,
            report_summary=report.summary if report else None,
            job_status=job.status if job else None,
        )
    )
