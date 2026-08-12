"""每日分析任务编排。"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session
from tqdm import tqdm

from app.clients.hot_collector import HotCollectorClient
from app.config import get_config
from app.db.models import DailyReport, HotAnalysis, JobRun
from app.pipeline.cluster import _normalize_title, cluster_hots
from app.pipeline.report import generate_daily_report
from app.pipeline.summarize import analyze_item

logger = logging.getLogger(__name__)


async def run_daily_job(
    db: Session,
    report_date: date | None = None,
    *,
    force: bool = False,
    show_progress: bool = False,
) -> dict[str, Any]:
    report_date = report_date or date.today()
    job = JobRun(job_name="daily_analyze", report_date=report_date, status="running")
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        client = HotCollectorClient()
        items = await client.fetch_hots(report_date)
        logger.info("fetched %s hots for %s", len(items), report_date)
        if show_progress:
            print(f"拉取热点 {len(items)} 条，开始聚类…", flush=True)

        # 当日已有分析结果（非 force 时跳过 AI）
        existing_map: dict[int, HotAnalysis] = {}
        if not force:
            for row in db.scalars(
                select(HotAnalysis).where(HotAnalysis.report_date == report_date)
            ).all():
                existing_map[row.hot_id] = row

        clusters = cluster_hots(items)
        if show_progress:
            already = len(existing_map)
            print(
                f"聚类完成：{len(clusters)} 簇"
                + (f"（库中已有 {already} 条，将跳过重复 AI）" if already and not force else "")
                + "，开始分析…",
                flush=True,
            )

        # 本次运行内按归一化标题缓存，避免相同标题重复调 AI
        ai_by_title: dict[str, dict[str, Any]] = {}
        stats = {"ai_calls": 0, "skipped": 0, "reused": 0}

        analyses: list[dict[str, Any]] = []
        cluster_iter = tqdm(
            clusters,
            desc="分析热点",
            unit="簇",
            disable=not show_progress,
            dynamic_ncols=True,
        )
        for cluster in cluster_iter:
            rep = cluster.representative
            title_short = (rep.title or "")[:28]
            pending = [
                it for it in cluster.items if force or it.id not in existing_map
            ]

            # 全员已分析且非强制：直接跳过 AI
            if not pending and not force:
                cluster_iter.set_postfix_str(f"已分析跳过 {title_short}", refresh=False)
                stats["skipped"] += 1
                continue

            result: dict[str, Any] | None = None
            title_key = _normalize_title(rep.title)

            # 1) 本次已分析过相同标题
            if title_key and title_key in ai_by_title:
                result = ai_by_title[title_key]
                cluster_iter.set_postfix_str(f"标题缓存 {title_short}", refresh=False)
                stats["reused"] += 1
            # 2) 库中同簇已有结果：复用，不调 AI
            elif not force:
                for it in cluster.items:
                    row = existing_map.get(it.id)
                    if row is not None:
                        result = _analysis_row_to_result(row)
                        cluster_iter.set_postfix_str(f"复用库内 {title_short}", refresh=False)
                        stats["reused"] += 1
                        break

            # 3) 需要新调 AI
            if result is None:
                cluster_iter.set_postfix_str(title_short, refresh=True)
                result = await analyze_item(db, rep)
                stats["ai_calls"] += 1
                if title_key:
                    ai_by_title[title_key] = result

            now = datetime.now()
            for it in pending:
                record = {
                    "hot_id": it.id,
                    "report_date": report_date,
                    "title": it.title,
                    "source": it.source,
                    "heat": it.heat,
                    "url": it.url,
                    "category": result.get("category"),
                    "sub_category": result.get("sub_category"),
                    "summary": result.get("summary"),
                    "tags": json.dumps(result.get("tags") or [], ensure_ascii=False),
                    "importance": result.get("importance", 5),
                    "cluster_id": cluster.cluster_id,
                    "analyze_time": now,
                }
                existing = existing_map.get(it.id) or db.scalar(
                    select(HotAnalysis).where(
                        HotAnalysis.hot_id == it.id,
                        HotAnalysis.report_date == report_date,
                    )
                )
                if existing:
                    if force:
                        for k, v in record.items():
                            if k in ("hot_id", "report_date"):
                                continue
                            setattr(existing, k, v)
                        existing_map[it.id] = existing
                else:
                    row = HotAnalysis(**record)
                    db.add(row)
                    existing_map[it.id] = row
            db.commit()

        all_rows = db.scalars(
            select(HotAnalysis).where(HotAnalysis.report_date == report_date)
        ).all()
        analyses = [_row_to_dict(r) for r in all_rows]

        if show_progress:
            print(
                f"AI 调用 {stats['ai_calls']} 次，"
                f"跳过 {stats['skipped']} 簇，复用 {stats['reused']} 簇；生成日报…",
                flush=True,
            )
        cfg = get_config()
        content = await generate_daily_report(
            db, report_date, analyses, top_n=cfg.pipeline.report_top_n
        )
        report = db.scalar(select(DailyReport).where(DailyReport.report_date == report_date))
        content_json = json.dumps(content, ensure_ascii=False)
        if report is None:
            report = DailyReport(
                report_date=report_date,
                summary=content.get("summary"),
                content=content_json,
                hot_count=len(analyses),
                create_time=datetime.now(),
            )
            db.add(report)
        else:
            report.summary = content.get("summary")
            report.content = content_json
            report.hot_count = len(analyses)
            report.create_time = datetime.now()

        job.status = "success"
        job.message = (
            f"analyzed {len(analyses)} items, clusters={len(clusters)}, "
            f"ai_calls={stats['ai_calls']}, skipped={stats['skipped']}, reused={stats['reused']}"
        )
        job.finished_at = datetime.now()
        db.commit()
        if show_progress:
            print(f"完成：{job.message}", flush=True)
        return {
            "job_id": job.id,
            "date": report_date.isoformat(),
            "status": "success",
            "hot_count": len(analyses),
            "message": job.message,
            "ai_calls": stats["ai_calls"],
            "skipped": stats["skipped"],
            "reused": stats["reused"],
        }
    except Exception as e:
        logger.exception("daily job failed: %s", e)
        job.status = "failed"
        job.message = str(e)[:2000]
        job.finished_at = datetime.now()
        db.commit()
        return {
            "job_id": job.id,
            "date": report_date.isoformat(),
            "status": "failed",
            "message": job.message,
        }


def _analysis_row_to_result(row: HotAnalysis) -> dict[str, Any]:
    tags: list[str] = []
    if row.tags:
        try:
            tags = json.loads(row.tags)
        except json.JSONDecodeError:
            tags = []
    return {
        "title": row.title,
        "category": row.category,
        "sub_category": row.sub_category,
        "summary": row.summary,
        "importance": row.importance or 5,
        "tags": tags,
        "from_ai": False,
    }


def _row_to_dict(row: HotAnalysis) -> dict[str, Any]:
    tags: list[str] = []
    if row.tags:
        try:
            tags = json.loads(row.tags)
        except json.JSONDecodeError:
            tags = []
    return {
        "hot_id": row.hot_id,
        "title": row.title,
        "source": row.source,
        "heat": row.heat,
        "url": row.url,
        "category": row.category,
        "sub_category": row.sub_category,
        "summary": row.summary,
        "tags": tags,
        "importance": row.importance,
        "cluster_id": row.cluster_id,
    }
