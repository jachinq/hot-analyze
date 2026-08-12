# AI 热点分析平台（hot-analyze）

依据 `PRD.md` / `TECH.md` 实现的 Python AI 分析服务：从 **hot-collector** 拉取热点，完成聚类 / 分类 / 摘要 / 日报，并通过 FastAPI + Vue3 展示。

## 技术栈

- Python 3.11+ / FastAPI / SQLAlchemy / APScheduler / uv
- AI：OpenAI 兼容协议（优先 LM Studio，可选 Ollama / DeepSeek 等）
- 前端：Vue 3 + Vite + TypeScript（**pnpm**）

## 快速开始

### 0. 一键启动（推荐，PowerShell 7+）

```powershell
# 方式一：PowerShell 7
pwsh ./start.ps1

# 方式二：双击 / cmd（自动查找 pwsh）
.\start.cmd
```

会自动同步依赖，并默认用 **Windows Terminal** 在当前窗口打开两个新 Tab（后端 / 前端）。

常用参数：

```powershell
pwsh ./start.ps1 -SkipInstall   # 跳过 uv sync / pnpm install
pwsh ./start.ps1 -Attached      # 在当前终端同时托管两个进程（Ctrl+C 一并退出）
pwsh ./start.ps1 -NewWindow     # 改为各开独立控制台窗口
```

- 前端：http://127.0.0.1:5173  
- API / OpenAPI：http://127.0.0.1:8000/docs  

### 1. 环境

```bash
cp .env.example .env
# 可选：填写 ENCRYPT_KEY / DEEPSEEK_API_KEY
# 生成 Fernet 密钥：
# uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

uv sync
```

编辑 `config.yaml`：采集服务地址、LM Studio 模型 ID、调度 cron 等。

### 2. 启动 API

```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- OpenAPI：http://127.0.0.1:8000/docs  
- 健康检查：http://127.0.0.1:8000/health  

### 3. 启动前端（开发）

前端使用 **pnpm** 管理依赖：

```bash
cd frontend
pnpm install
pnpm dev
```

浏览器打开 http://127.0.0.1:5173（Vite 已代理 `/api` → FastAPI）。

生产构建：`pnpm build`（产物在 `frontend/dist`，可由 FastAPI 挂载）。

### 4. 手动跑一次分析

需上游 hot-collector 提供：

`GET {collector.base_url}/api/hot/list?date=YYYY-MM-DD`

```bash
uv run python scripts/run_once.py --date 2026-08-11
# 或 HTTP：
# curl -X POST "http://127.0.0.1:8000/api/jobs/analyze?date=2026-08-11&sync=true"
```

## 主要 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/report/{date}` | 日报 + 条目 |
| GET | `/api/report/latest` | 最近日报 |
| GET | `/api/hot/category` | 分类热点 |
| GET | `/api/hot/search` | 历史检索 |
| GET | `/api/hot/ranking` | 排行 |
| GET | `/api/stats/today` | 首页统计 |
| GET/PUT | `/api/ai/config` | AI 配置（密钥脱敏） |
| POST | `/api/jobs/analyze` | 手动触发分析 |
| GET | `/api/jobs/{date}` | 任务状态 |

## 目录

见 `TECH.md` §2。核心代码在 `app/`，前端在 `frontend/`。

## Docker 部署（Debian）

生产将前端打进同一镜像，经 Compose 运行。拓扑：`hot-collector` 在宿主机，本地大模型在局域网其他机器。

详见 **[docs/DOCKER.md](docs/DOCKER.md)**。摘要：

```bash
cp .env.example .env          # 填写 ENCRYPT_KEY 等
# 编辑 config.docker.yaml：把大模型 IP 改成局域网真实地址
mkdir -p data && sudo chown -R 10001:10001 data
docker compose build && docker compose up -d
```

## 测试

```bash
uv run pytest
```

## 说明

- 默认每天 `08:00`（Asia/Shanghai）跑分析，可在 `config.yaml` → `scheduler` 调整。
- `prefer_local: true` 时优先 LM Studio（`http://127.0.0.1:1234/v1`），失败可降级到已启用的在线模型。
- 规则分类见 `app/rules/categories.yaml`；命中规则后仍可走合并 Prompt 生成摘要（可配置）。
- SQLite 默认路径：`./data/analyzer.db`。
