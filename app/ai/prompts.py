"""Prompt 模板。"""

from __future__ import annotations

CATEGORY_OPTIONS = "新闻/科技/财经/社会/娱乐/体育/军事/其他"

ANALYZE_SYSTEM = (
    "你是热点分析助手，只输出合法 JSON，不要 Markdown，不要代码块。"
)

ANALYZE_USER_TMPL = """标题: {title}
来源: {source}
讨论热度: {heat}
可选分类: {categories}

请输出:
{{
  "title": "...",
  "category": "...",
  "sub_category": "...",
  "summary": "一句话摘要，不超过80字",
  "importance": 1-10,
  "tags": ["...", "..."]
}}
"""

REPORT_SYSTEM = (
    "你是资深媒体编辑，根据当日热点分析结果写日报。"
    "只输出合法 JSON，不要 Markdown 代码块包裹。"
)

REPORT_USER_TMPL = """日期: {date}
热点条目（JSON 数组，已按重要性排序）:
{items_json}

请输出:
{{
  "summary": "一句话总览今日热点",
  "highlights": [
    {{"title": "...", "impact": 5, "summary": "...", "url": "原条目url，没有则空字符串"}}
  ],
  "trends": ["趋势词1", "趋势词2"],
  "markdown": "可读的 Markdown 日报正文"
}}
highlights 最多 8 条，trends 3-6 个。
markdown 中「重点事件」标题必须使用 Markdown 链接：`- **[标题](url)**：摘要`（无 url 时写纯标题）。
"""


def build_analyze_user(title: str, source: str, heat: int) -> str:
    return ANALYZE_USER_TMPL.format(
        title=title,
        source=source or "未知",
        heat=heat,
        categories=CATEGORY_OPTIONS,
    )


def build_report_user(date: str, items_json: str) -> str:
    return REPORT_USER_TMPL.format(date=date, items_json=items_json)
