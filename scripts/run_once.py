"""手动触发一次分析。"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.migrate import init_db
from app.db.session import get_session_factory
from app.pipeline.daily_job import run_daily_job


def parse_date(s: str | None) -> date:
    if not s:
        return date.today()
    return datetime.strptime(s, "%Y-%m-%d").date()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run hot-analyze pipeline once")
    parser.add_argument("--date", help="YYYY-MM-DD", default=None)
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制重新 AI 分析（默认会跳过当日已分析过的记录）",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="不显示进度条",
    )
    args = parser.parse_args()

    # 降低第三方/配置刷屏；任务进度走 tqdm / print
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("app").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)

    init_db()
    report_date = parse_date(args.date)
    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        result = await run_daily_job(
            db,
            report_date,
            force=args.force,
            show_progress=not args.quiet,
        )
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
