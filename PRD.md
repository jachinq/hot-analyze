# AI热点分析整理系统需求说明书

# 1. 项目概述

## 1.1 项目名称

AI热点分析平台（AI Hot Analyzer）

## 1.2 项目目标

读取热点采集系统数据，通过 AI 大模型进行：

* 热点聚合
* 分类
* 摘要
* 趋势分析
* 每日总结

形成用户可阅读的热点日报系统。

---

# 2. 系统架构

```
              SQLite
                 |
                 |
          Python任务服务
                 |
       -------------------
       |                 |
    规则处理          AI模型
                         |
              -----------------
              |
        在线模型 / 本地模型

              |
              v

          分析结果数据库

              |
              v

          Web展示页面

```

---

# 3. 技术要求

| 模块    | 技术          |
| ----- | ----------- |
| 语言    | Python      |
| Web框架 | FastAPI     |
| 数据库   | SQLite      |
| 任务调度  | APScheduler |
| 前端    | Vue/React   |
| AI接口  | OpenAI兼容协议  |
| 本地模型  | LM Studio（优先）；Ollama 可选 |

---

# 4. 功能需求

# 4.1 AI模型配置

支持两类模型：

## 在线模型

例如：

```
OpenAI
Claude
DeepSeek
通义千问
```

配置：

```yaml
provider: openai

api_key:
model:
```

---

## 本地模型

优先：

```
LM Studio（OpenAI 兼容本地服务）
默认地址: http://127.0.0.1:1234/v1
```

配置：

```yaml
provider: lmstudio

url: http://127.0.0.1:1234/v1
model: # 与 LM Studio 当前加载模型一致
```

备选（可选）：

```
Ollama

qwen2.5
llama3
deepseek
```

```yaml
provider: ollama

url:
model: qwen2.5
```

---

# 4.2 每日分析任务

每天执行一次。

流程：

```
获取当天热点

↓

热点聚类

↓

AI分类

↓

生成摘要

↓

生成日报

↓

保存结果
```

---

# 4.3 热点分类

支持规则配置。

分类：

```
新闻
├── 国内
├── 国际

科技
├── AI
├── 软件
├── 硬件

财经
├── 股票
├── 公司

社会

娱乐

体育

军事

其他

```

规则示例：

```yaml
category:
  name: 科技

  keywords:
    - AI
    - 大模型
    - 芯片
```

---

# 4.4 AI热点处理

输入：

```
标题:
某公司发布AI模型

来源:
微博

讨论:
100000
```

输出：

```json
{
"title":"某公司发布AI模型",

"category":"科技",

"summary":
"该公司推出新的AI模型，
主要提升代码能力",

"importance":8,

"tags":[
"人工智能",
"大模型"
]
}
```

---

# 4.5 每日总结

自动生成：

```
2026年8月11日热点日报

今日热点数量:
256条


重点事件：

1.
AI行业出现重大更新

影响：
★★★★★


2.
某政策发布

影响：
★★★★


今日趋势：

人工智能、消费市场、
国际新闻关注度上涨。


```

---

# 5. 数据库设计

## hot_analysis

```sql
CREATE TABLE hot_analysis
(
id INTEGER PRIMARY KEY,

hot_id INTEGER,

category TEXT,

summary TEXT,

tags TEXT,

importance INTEGER,

analyze_time DATETIME
);
```

---

## daily_report

```sql
CREATE TABLE daily_report
(
id INTEGER PRIMARY KEY,

report_date DATE,

summary TEXT,

content TEXT,

create_time DATETIME
);
```

---

## ai_config

```sql
CREATE TABLE ai_config
(
id INTEGER PRIMARY KEY,

provider TEXT,

model TEXT,

api_url TEXT,

api_key TEXT,

enabled INTEGER
);
```

---

# 6. Web展示需求

## 首页

展示：

* 今日热点总览
* 分类统计
* 热点排行榜
* AI日报

---

## 分类页面

例如：

```
科技

---------------
AI模型发布

摘要：

影响：

来源：
微博/知乎

```

---

## 历史查询

支持：

* 日期查询
* 分类查询
* 关键词搜索

例如：

```
查询：
2026-08-01

分类：
科技

关键词：
AI
```

---

# 7. API需求

## 查询日报

GET

```
/api/report/{date}
```

返回：

```json
{
"date":"2026-08-11",

"summary":"今日热点主要集中在AI和财经",

"items":[]
}
```

---

## 查询分类热点

GET

```
/api/hot/category
```

参数：

```
category=科技
date=2026-08-11
```

---

# 8. 非功能需求

## 可扩展

未来支持：

* 更多模型
* 更多数据源
* 用户自定义分类

## AI成本控制

支持：

* 本地模型优先
* Token统计
* 最大调用次数限制

## 数据安全

要求：

* API Key加密保存
* 模型调用日志记录

---

# 两个项目之间接口约定

项目一：

```
hot-collector
```

提供：

```
GET /api/hot/list
```

项目二：

```
ai-analyzer
```

每日：

```
调用采集接口

↓

AI处理

↓

生成报告

↓

展示
```

最终形成：

```
多个热点源
      |
      v
Rust采集服务
      |
      v
SQLite原始数据
      |
      v
Python AI分析服务
      |
      v
热点日报平台
```

这个拆分方式后续也方便将 Rust 采集服务独立部署成边缘采集节点，而 Python AI 服务作为中心分析服务运行。
