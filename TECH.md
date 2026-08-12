# AI热点分析平台 — 技术方案

> 依据 `PRD.md` 制定。本方案覆盖系统架构、模块划分、数据模型、AI 流水线、API、前端、成本控制与部署。

---

## 1. 方案总览

### 1.1 定位

本项目为 **ai-analyzer（Python AI 分析服务）**，与上游 **hot-collector（Rust 采集服务）** 解耦：

| 角色 | 项目 | 职责 |
|------|------|------|
| 边缘采集 | hot-collector | 多源热点抓取，写入原始 SQLite，对外提供 `GET /api/hot/list` |
| 中心分析 | hot-analyze（本项目） | 拉取热点 → 聚类/分类/摘要 → 日报 → Web 展示 |

### 1.2 技术选型（与 PRD 对齐并落定）

| 模块 | 选型 | 说明 |
|------|------|------|
| 语言 / Web | Python 3.11+ / FastAPI | 异步友好，OpenAPI 自动文档 |
| 包管理 | uv | 依赖声明 `pyproject.toml`，锁定 `uv.lock`；不以 pip + requirements.txt 为主流程 |
| ORM / DB | SQLAlchemy 2.x + SQLite | 开发简单；表结构预留迁移到 PostgreSQL |
| 任务调度 | APScheduler | 每日分析 + 可选补跑 |
| AI 调用 | OpenAI 兼容 HTTP Client | 统一适配在线模型与本地 OpenAI 兼容端点 |
| 本地模型 | LM Studio（优先） | `provider: lmstudio`，默认 `http://127.0.0.1:1234/v1`；Ollama 作可选备选 |
| 前端 | Vue 3 + Vite + TypeScript | SPA，对接 FastAPI；也可同仓 `frontend/` |
| 配置 | YAML + 环境变量 | `config.yaml` 管业务，密钥走 env |
| 密钥加密 | Fernet（cryptography） | `ai_config.api_key` 落库加密 |
| 向量/聚类（可选） | sentence-transformers 或轻量 TF-IDF | 规则优先，向量聚类可开关 |

### 1.3 目标架构

```
┌─────────────────┐     GET /api/hot/list      ┌──────────────────────────────┐
│  hot-collector  │ ─────────────────────────► │  hot-analyze (本服务)         │
│  (Rust + SQLite)│                            │                              │
└─────────────────┘                            │  ┌─────────┐  ┌───────────┐ │
                                               │  │Scheduler│→ │ Pipeline  │ │
                                               │  └─────────┘  └─────┬─────┘ │
                                               │                     │       │
                                               │         ┌───────────┼────┐  │
                                               │         ▼           ▼    ▼  │
                                               │      规则分类    AI Provider │
                                               │      聚类/摘要   (LM Studio/│
                                               │                  在线模型)  │
                                               │                     │       │
                                               │                     ▼       │
                                               │              SQLite 结果库   │
                                               │                     │       │
                                               │                     ▼       │
                                               │              FastAPI + Vue  │
                                               └──────────────────────────────┘
```

---

## 2. 目录结构

```
hot-analyze/
├── PRD.md
├── TECH.md
├── README.md
├── config.yaml                 # 业务与调度配置
├── .env.example                # AI_KEY / ENCRYPT_KEY 等
├── .python-version             # uv 锁定解释器版本（如 3.11）
├── pyproject.toml              # 项目元数据与依赖声明（必需）
├── uv.lock                     # 依赖锁定文件（提交入库）
├── app/
│   ├── main.py                 # FastAPI 入口
│   ├── config.py               # 配置加载
│   ├── db/
│   │   ├── session.py
│   │   ├── models.py
│   │   └── migrate.py          # 简易建表 / Alembic 预留
│   ├── clients/
│   │   └── hot_collector.py    # 调用采集服务
│   ├── ai/
│   │   ├── base.py             # Provider 抽象
│   │   ├── openai_compat.py    # OpenAI / DeepSeek / 通义 / LM Studio
│   │   ├── ollama.py           # 可选：Ollama 备选本地端点
│   │   ├── factory.py          # 按配置创建客户端
│   │   ├── prompts.py          # 分类/摘要/日报 Prompt
│   │   └── cost.py             # Token 统计与限流
│   ├── pipeline/
│   │   ├── daily_job.py        # 每日任务编排
│   │   ├── cluster.py          # 热点聚合
│   │   ├── classify.py         # 规则 + AI 分类
│   │   ├── summarize.py
│   │   └── report.py           # 日报生成
│   ├── rules/
│   │   └── categories.yaml     # 分类关键词规则
│   ├── security/
│   │   └── crypto.py           # API Key 加解密
│   ├── api/
│   │   ├── report.py
│   │   ├── hot.py
│   │   ├── config_ai.py        # AI 配置管理（管理端）
│   │   └── deps.py
│   ├── scheduler/
│   │   └── jobs.py
│   └── schemas/                # Pydantic 响应模型
├── frontend/                   # Vue3 SPA
│   ├── src/
│   │   ├── views/Home.vue
│   │   ├── views/Category.vue
│   │   ├── views/History.vue
│   │   └── api/
│   └── ...
├── tests/
└── scripts/
    └── run_once.py             # 手动触发一次分析
```

---

## 2.1 开发与依赖（uv）

本项目统一使用 **uv** 管理 Python 环境与依赖，不以 `pip` + `requirements.txt` 作为主流程。

| 场景 | 命令 |
|------|------|
| 安装依赖（按 lock） | `uv sync` |
| 增加运行依赖 | `uv add <pkg>` |
| 增加开发依赖 | `uv add --dev <pkg>` |
| 移除依赖 | `uv remove <pkg>` |
| 本地启动 API | `uv run uvicorn app.main:app --reload` |
| 运行测试 | `uv run pytest` |
| 手动跑一次分析 | `uv run python scripts/run_once.py` |

约定：

- 依赖只写在 `pyproject.toml`，版本以 `uv.lock` 为准并提交仓库。
- 新增/变更依赖后执行 `uv lock`（或由 `uv add` 自动更新 lock），CI/协作方用 `uv sync` 复现环境。
- 应用与脚本一律通过 `uv run ...` 调用，避免误用系统全局 Python。

---

## 3. 核心模块设计

### 3.1 配置层

`config.yaml` 示例：

```yaml
collector:
  base_url: "http://127.0.0.1:8080"
  list_path: "/api/hot/list"
  timeout_sec: 30

scheduler:
  daily_cron: "0 8 * * *"   # 每天 08:00
  timezone: "Asia/Shanghai"

ai:
  prefer_local: true          # 本地模型优先（默认 LM Studio）
  max_calls_per_day: 2000
  max_tokens_per_day: 500000
  default_provider: lmstudio
  providers:
    - name: lmstudio
      provider: lmstudio      # 内部复用 OpenAI 兼容客户端
      api_url: "http://127.0.0.1:1234/v1"
      model: "local-model"    # 与 LM Studio 当前加载的模型 ID 一致
      enabled: true
      # api_key 可填任意非空占位（如 lm-studio），LM Studio 本地一般不校验
    - name: ollama
      provider: ollama
      api_url: "http://127.0.0.1:11434/v1"
      model: "qwen2.5"
      enabled: false          # 备选本地端点，默认关闭
    - name: deepseek
      provider: openai
      api_url: "https://api.deepseek.com/v1"
      model: "deepseek-chat"
      enabled: true
      # api_key 从环境变量 DEEPSEEK_API_KEY 读取，不写明文进 yaml

pipeline:
  cluster:
    enabled: true
    method: "tfidf"           # tfidf | embedding | title_sim
    similarity_threshold: 0.72
  classify:
    rule_first: true          # 规则命中则跳过 AI
    ai_fallback: true
  batch_size: 20              # AI 批处理条数，控成本

database:
  url: "sqlite:///./data/analyzer.db"

security:
  # ENCRYPT_KEY 环境变量，Fernet key
  encrypt_api_key: true
```

### 3.2 采集客户端

约定调用上游：

```
GET {collector.base_url}/api/hot/list?date=YYYY-MM-DD
```

建议约定响应（若上游尚未定稿，本侧用 Adapter 适配）：

```json
{
  "date": "2026-08-11",
  "items": [
    {
      "id": 1001,
      "title": "某公司发布AI模型",
      "source": "微博",
      "heat": 100000,
      "url": "https://...",
      "collected_at": "2026-08-11T10:00:00"
    }
  ]
}
```

失败策略：重试 3 次（指数退避）→ 写任务日志 → 当日任务标记 `failed`，支持补跑。

### 3.3 AI Provider 抽象

```python
class AIProvider(Protocol):
    async def chat_json(self, system: str, user: str, **kw) -> dict: ...
    async def chat_text(self, system: str, user: str, **kw) -> str: ...
```

- `OpenAICompatProvider`：统一覆盖 OpenAI / Claude 兼容网关 / DeepSeek / 通义 / **LM Studio**  
- `LM Studio`：走本地 OpenAI 兼容 API（默认 `http://127.0.0.1:1234/v1`），实现上复用 `OpenAICompatProvider`，`provider` 标识为 `lmstudio`  
- `OllamaProvider`（可选）：Ollama OpenAI 兼容端点或原生 `/api/chat`，作本地备选  
- `factory.get_active_provider()`：`prefer_local=true` 时**优先 LM Studio**，失败可降级到 Ollama（若启用）或在线模型（可配置）

所有调用经 `cost.py` 中间层：累计 token、次数，超限则拒绝或仅走规则路径。

### 3.4 每日分析流水线

```
daily_job(date)
  ├─ 1. fetch_hots(date)           # 采集服务
  ├─ 2. cluster(items)             # 标题相似度 / TF-IDF 聚合为 topic 组
  ├─ 3. for each cluster/item:
  │     ├─ rule_classify()         # categories.yaml 关键词
  │     ├─ if miss → ai_classify() # 输出 category / tags / importance
  │     └─ ai_summarize()          # 短摘要（可与分类合并为一次调用）
  ├─ 4. persist hot_analysis
  ├─ 5. generate_daily_report()    # AI 汇总重点事件 + 趋势
  └─ 6. persist daily_report + job_log
```

**成本优化（关键）：**

1. **规则优先**：关键词命中分类则跳过分类 AI  
2. **合并 Prompt**：单条一次调用同时产出 `category/summary/importance/tags`（与 PRD 4.4 输出对齐）  
3. **聚类后按簇调用**：同簇共用摘要，减少重复调用  
4. **本地优先 + 日限额**  
5. **幂等**：同一 `hot_id` + 分析日已存在则跳过

### 3.5 分类规则

`app/rules/categories.yaml`：

```yaml
categories:
  - name: 科技
    children: [AI, 软件, 硬件]
    keywords: [AI, 大模型, 芯片, GPT, 开源]
  - name: 财经
    children: [股票, 公司]
    keywords: [股市, A股, 财报, 上市]
  - name: 新闻
    children: [国内, 国际]
    keywords: [政策, 外交, 国务院]
  # ... 社会 / 娱乐 / 体育 / 军事 / 其他
```

规则打分：标题命中权重 > 来源权重；同分取列表顺序；均未命中 → `其他` 或交 AI。

二级分类：规则给一级；二级可由 AI 在同一 JSON 中返回 `sub_category`（表字段扩展，见下）。

---

## 4. 数据模型（在 PRD 基础上补全）

PRD 三张表保留，并增加运维与查询所需字段/表。

### 4.1 `hot_analysis`（扩展）

```sql
CREATE TABLE hot_analysis (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  hot_id        INTEGER NOT NULL,          -- 上游热点 ID
  report_date   DATE NOT NULL,             -- 归属日报日期
  title         TEXT NOT NULL,
  source        TEXT,
  heat          INTEGER DEFAULT 0,
  url           TEXT,
  category      TEXT,
  sub_category  TEXT,
  summary       TEXT,
  tags          TEXT,                      -- JSON 数组字符串
  importance    INTEGER DEFAULT 0,         -- 1-10
  cluster_id    TEXT,                      -- 聚合簇 ID
  analyze_time  DATETIME,
  UNIQUE(hot_id, report_date)
);
CREATE INDEX idx_ha_date_cat ON hot_analysis(report_date, category);
CREATE INDEX idx_ha_importance ON hot_analysis(report_date, importance DESC);
```

### 4.2 `daily_report`

```sql
CREATE TABLE daily_report (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  report_date   DATE NOT NULL UNIQUE,
  summary       TEXT,                      -- 一句话总览
  content       TEXT,                      -- Markdown / JSON 结构化正文
  hot_count     INTEGER DEFAULT 0,
  create_time   DATETIME
);
```

`content` 建议存结构化 JSON，前端渲染，同时可存一份 Markdown 便于导出：

```json
{
  "highlights": [
    {"title": "...", "impact": 5, "summary": "..."}
  ],
  "trends": ["人工智能", "消费市场"],
  "markdown": "2026年8月11日热点日报\n..."
}
```

### 4.3 `ai_config`

```sql
CREATE TABLE ai_config (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  name      TEXT UNIQUE,
  provider  TEXT NOT NULL,     -- openai | lmstudio | ollama
  model     TEXT NOT NULL,
  api_url   TEXT,
  api_key   TEXT,              -- Fernet 密文
  enabled   INTEGER DEFAULT 1,
  priority  INTEGER DEFAULT 100,
  updated_at DATETIME
);
```

### 4.4 增补表

```sql
-- AI 调用日志（安全与成本）
CREATE TABLE ai_call_log (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  provider     TEXT,
  model        TEXT,
  purpose      TEXT,           -- classify | summarize | report
  prompt_tokens INTEGER,
  completion_tokens INTEGER,
  success      INTEGER,
  error_msg    TEXT,
  created_at   DATETIME
);

-- 每日任务状态
CREATE TABLE job_run (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  job_name     TEXT,
  report_date  DATE,
  status       TEXT,           -- running | success | failed
  message      TEXT,
  started_at   DATETIME,
  finished_at  DATETIME
);
```

---

## 5. AI Prompt 约定

### 5.1 单条分析（对应 PRD 4.4）

System：你是热点分析助手，只输出合法 JSON，不要 Markdown。

User：

```
标题: ...
来源: ...
讨论热度: ...
可选分类: 新闻/科技/财经/社会/娱乐/体育/军事/其他

请输出:
{
  "title": "...",
  "category": "...",
  "sub_category": "...",
  "summary": "一句话摘要，不超过80字",
  "importance": 1-10,
  "tags": ["...", "..."]
}
```

解析失败：重试 1 次 → 降级为规则分类 + 标题截断作摘要。

### 5.2 日报生成（对应 PRD 4.5）

输入：当日 Top N（按 importance×heat）分析结果列表。  
输出：`summary` + `highlights` + `trends` + 可读 Markdown。

---

## 6. API 设计

统一前缀 `/api`，响应包一层可选：

```json
{ "code": 0, "data": {}, "message": "ok" }
```

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/report/{date}` | 日报 + 条目列表 |
| GET | `/api/report/latest` | 最近一份日报 |
| GET | `/api/hot/category` | `category` + `date` 查询分类热点 |
| GET | `/api/hot/search` | `date` / `category` / `keyword` 历史检索 |
| GET | `/api/hot/ranking` | 当日重要性/热度排行 |
| GET | `/api/stats/today` | 首页：总量、分类统计 |
| GET | `/api/ai/config` | 列出 AI 配置（密钥脱敏） |
| PUT | `/api/ai/config/{id}` | 更新配置（管理） |
| POST | `/api/jobs/analyze` | 手动触发某日分析（运维） |
| GET | `/api/jobs/{date}` | 任务状态 |

### 6.1 `GET /api/report/{date}`

```json
{
  "date": "2026-08-11",
  "summary": "今日热点主要集中在AI和财经",
  "hot_count": 256,
  "content": { "highlights": [], "trends": [], "markdown": "..." },
  "items": [
    {
      "hot_id": 1001,
      "title": "...",
      "category": "科技",
      "summary": "...",
      "importance": 8,
      "tags": ["人工智能"],
      "source": "微博",
      "heat": 100000
    }
  ]
}
```

### 6.2 `GET /api/hot/category`

Query：`category=科技&date=2026-08-11`  
返回该分类下按 importance、heat 排序的列表。

### 6.3 CORS

开发期允许前端 Vite 源；生产可由同域 Nginx 反代，关闭宽 CORS。

---

## 7. Web 前端方案

### 7.1 页面

| 页面 | 路由 | 内容 |
|------|------|------|
| 首页 | `/` | 今日总览、分类饼图/条形图、排行榜、AI 日报摘要 |
| 分类 | `/category/:name` | 该分类热点卡片：标题、摘要、影响、来源 |
| 历史 | `/history` | 日期 + 分类 + 关键词筛选 |

### 7.2 交互要点

- 首页默认加载「今日」；无数据时提示任务状态或昨日兜底  
- 重要性用星级或进度条（1–10 → ★）  
- 日报 Markdown 用轻量渲染库  

### 7.3 部署形态

- 开发：Vite 代理 `/api` → FastAPI  
- 生产：`frontend/dist` 由 FastAPI `StaticFiles` 挂载，或 Nginx 托管静态 + 反代 API  

---

## 8. 调度与运维

1. 应用启动时注册 APScheduler Cron（默认每天 08:00 Asia/Shanghai）  
2. 任务写入 `job_run`；失败可 `POST /api/jobs/analyze?date=` 补跑  
3. 日志：标准 logging，AI 调用另入 `ai_call_log`  
4. 健康检查：`GET /health`（DB + 可选 collector ping）  

---

## 9. 非功能需求落地

### 9.1 可扩展

- Provider 插件式注册  
- `categories.yaml` 用户可改，无需改代码  
- Collector Adapter 隔离上游字段变化  

### 9.2 AI 成本控制

| 手段 | 实现 |
|------|------|
| 本地优先 | `prefer_local` + 优先 LM Studio，失败再降级 |
| Token 统计 | 每次调用写 `ai_call_log`，日聚合校验 |
| 最大调用次数 | `max_calls_per_day` / `max_tokens_per_day` |
| 规则短路 | `rule_first` |
| 批大小 | `batch_size` / 按簇合并 |

### 9.3 数据安全

- `api_key` Fernet 加密存储；接口返回恒为 `****`  
- 调用日志不含完整 Key；Prompt 可选脱敏  
- `.env` 不入库；提供 `.env.example`  

---

## 10. 与 hot-collector 的接口契约（建议冻结）

| 项 | 约定 |
|----|------|
| 协议 | HTTP JSON |
| 列表 | `GET /api/hot/list?date=YYYY-MM-DD` |
| 必填字段 | `id`, `title`, `source`, `heat` |
| 可选 | `url`, `collected_at`, `raw` |
| 空数据 | `items: []`，分析侧生成空日报或跳过 |
| 鉴权 | 一期内网免鉴权；二期可加共享 Token Header |

---

## 11. 实施分期

### Phase 1 — MVP（建议 1–1.5 周）

- SQLite 建表 + FastAPI 骨架  
- LM Studio（本地优先）/ 一个在线 Provider  
- 规则分类 + 单条 AI 分析 + 日报  
- 定时任务 + 手动触发  
- 首页 + 分类页只读展示  

### Phase 2 — 完善（约 1 周）

- 聚类降本、成本限额、调用日志  
- 历史检索、排行榜、分类统计  
- AI 配置管理 UI  
- Key 加密  

### Phase 3 — 增强

- Embedding 聚类  
- 多模型路由与 A/B  
- 导出 Markdown/PDF  
- 采集节点多实例适配  

---

## 12. 风险与对策

| 风险 | 对策 |
|------|------|
| 上游接口字段不稳定 | Adapter + 契约测试 |
| 本地模型 JSON 不稳定 | 强约束 Prompt + 校验重试 + 规则降级 |
| AI 费用超预算 | 日限额 + 规则优先 + 本地优先 |
| 同日重复跑任务 | `UNIQUE(hot_id, report_date)` + job 状态机 |
| SQLite 并发写 | 分析任务单进程执行；Web 只读为主 |

---

## 13. 验收对照（PRD）

| PRD 条目 | 方案对应 |
|----------|----------|
| 4.1 在线/本地模型 | Provider 抽象 + yaml/DB 配置 |
| 4.2 每日分析任务 | APScheduler + `daily_job` 流水线 |
| 4.3 热点分类规则 | `categories.yaml` + rule_first |
| 4.4 AI 热点处理 | 统一 JSON Schema Prompt |
| 4.5 每日总结 | `report.py` + `daily_report` |
| 5 数据库 | 三表 + 扩展字段 + 日志/任务表 |
| 6 Web 展示 | Vue3 三页 |
| 7 API | `/api/report/{date}`、`/api/hot/category` 等 |
| 8 非功能 | 成本中间件 + Fernet + 调用日志 |
| 双项目约定 | Collector HTTP Client |

---

## 14. 下一步建议

1. 与 hot-collector 确认 `/api/hot/list` 最终响应 Schema  
2. 确认 LM Studio 本地加载的模型 ID，并写入 `config.yaml` 的 `ai.providers.lmstudio.model`  
3. 按 Phase 1 初始化仓库脚手架并实现第一条端到端流水线（拉取 → 分析 → 查日报）
