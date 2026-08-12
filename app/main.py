"""FastAPI 入口。"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import config_ai, hot, jobs, report, settings
from app.config import ROOT_DIR, get_config
from app.db.migrate import init_db
from app.db.session import get_engine
from app.scheduler.jobs import shutdown_scheduler, start_scheduler
from app.settings.runtime import get_runtime_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    start_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(title="AI热点分析平台", version="0.1.0", lifespan=lifespan)

cfg = get_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.cors.allow_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(report.router)
app.include_router(hot.router)
app.include_router(config_ai.router)
app.include_router(jobs.router)
app.include_router(settings.router)


@app.get("/health")
async def health():
    ok_db = True
    try:
        with get_engine().connect() as conn:
            conn.exec_driver_sql("SELECT 1")
    except Exception as e:
        ok_db = False
        db_err = str(e)
    else:
        db_err = None

    collector_ok = None
    try:
        runtime = get_runtime_config()
        url = f"{runtime.collector.base_url.rstrip('/')}/health"
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(url)
            collector_ok = r.status_code < 500
    except Exception:
        collector_ok = False

    status = "ok" if ok_db else "degraded"
    return {
        "status": status,
        "db": ok_db,
        "db_error": db_err,
        "collector": collector_ok,
    }


# 生产：挂载前端静态资源
_frontend_dist = ROOT_DIR / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=_frontend_dist / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        if full_path.startswith("api/") or full_path == "health":
            return {"detail": "not found"}
        index = _frontend_dist / "index.html"
        file_path = _frontend_dist / full_path
        if full_path and file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(index)
