# 多阶段构建：前端静态资源 + Python 依赖 → 精简运行时镜像
# 注意：不要写 # syntax=docker/dockerfile:1，国内拉取 auth.docker.io 常超时

############################
# 1) 前端构建
############################
FROM node:22-alpine AS frontend

WORKDIR /src
RUN corepack enable

# 国内网络可取消下一行注释，或构建时传入：
# docker compose build --build-arg NPM_REGISTRY=https://registry.npmmirror.com
ARG NPM_REGISTRY=
RUN if [ -n "$NPM_REGISTRY" ]; then npm config set registry "$NPM_REGISTRY"; fi

COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY frontend/ ./
RUN pnpm build

############################
# 2) Python 依赖（uv）
############################
FROM python:3.11-slim-bookworm AS python-deps

# 用 pip 安装 uv，避免再拉取 ghcr.io/astral-sh/uv（国内常超时）
ARG PIP_INDEX_URL=https://pypi.org/simple
ENV PIP_INDEX_URL=${PIP_INDEX_URL} \
    UV_INDEX_URL=${PIP_INDEX_URL} \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    UV_PROJECT_ENVIRONMENT=/app/.venv

RUN pip install --no-cache-dir "uv==0.8.4"

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

############################
# 3) 运行时（最小）
############################
FROM python:3.11-slim-bookworm AS runtime

# scikit-learn 需要 libgomp；curl 用于健康检查；tzdata 用于调度时区
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgomp1 \
        curl \
        tzdata \
    && ln -snf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo Asia/Shanghai > /etc/timezone \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 appuser \
    && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin appuser

WORKDIR /app

COPY --from=python-deps /app/.venv /app/.venv
COPY app ./app
COPY --from=frontend /src/dist ./frontend/dist
# 默认配置；生产请用 compose 挂载覆盖
COPY config.docker.yaml ./config.yaml

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Shanghai \
    DATABASE_URL=sqlite:////app/data/analyzer.db

RUN mkdir -p /app/data \
    && chown -R appuser:appuser /app/data

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health >/dev/null || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
