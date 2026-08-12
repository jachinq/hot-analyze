"""日报 API。"""

from __future__ import annotations

import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import DailyReport, HotAnalysis
from app.pipeline.daily_job import _row_to_dict
from app.pipeline.preference import effective_importance
from app.schemas import ApiResponse, HotItemOut, ReportOut

router = APIRouter(prefix="/api/report", tags=["report"])


def _build_report(db: Session, report: DailyReport) -> ReportOut:
    content = None
    if report.content:
        try:
            content = json.loads(report.content)
        except json.JSONDecodeError:
            content = {"markdown": report.content}
    rows = list(
        db.scalars(
            select(HotAnalysis).where(HotAnalysis.report_date == report.report_date)
        ).all()
    )
    rows = sorted(
        rows,
        key=lambda r: (
            effective_importance(r.importance, r.category),
            int(r.heat or 0),
        ),
        reverse=True,
    )
    items = [HotItemOut(**_row_to_dict(r)) for r in rows]
    return ReportOut(
        date=report.report_date,
        summary=report.summary,
        hot_count=report.hot_count or len(items),
        content=content,
        items=items,
    )


@router.get("/latest", response_model=ApiResponse[ReportOut])
def get_latest_report(db: Session = Depends(get_db)):
    report = db.scalar(select(DailyReport).order_by(desc(DailyReport.report_date)).limit(1))
    if not report:
        raise HTTPException(status_code=404, detail="no report")
    return ApiResponse(data=_build_report(db, report))


@router.get("/{report_date}", response_model=ApiResponse[ReportOut])
def get_report(report_date: date, db: Session = Depends(get_db)):
    report = db.scalar(select(DailyReport).where(DailyReport.report_date == report_date))
    if not report:
        raise HTTPException(status_code=404, detail=f"report not found: {report_date}")
    return ApiResponse(data=_build_report(db, report))
