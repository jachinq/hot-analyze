"""JSON 抽取与 chat_json 重试测试。"""

from __future__ import annotations

import pytest

from app.ai.errors import InvalidAIJsonError
from app.ai.openai_compat import OpenAICompatProvider, extract_json


def test_extract_plain_json():
    data = extract_json('{"category": "科技", "importance": 8}')
    assert data["category"] == "科技"


def test_extract_fenced_json():
    text = """```json
{"summary": "测试", "tags": ["a"]}
```"""
    data = extract_json(text)
    assert data["summary"] == "测试"


def test_extract_invalid_raises():
    with pytest.raises(ValueError):
        extract_json("这不是 JSON，也没有花括号对象")


@pytest.mark.asyncio
async def test_chat_json_retries_then_raises(monkeypatch):
    provider = OpenAICompatProvider(
        name="mock",
        provider="openai",
        api_url="http://127.0.0.1:9/v1",
        model="mock-model",
    )
    replies = iter(["not-json-at-all", "still broken {{{"])

    async def fake_chat_text(system: str, user: str, **kw):
        return next(replies)

    monkeypatch.setattr(provider, "chat_text", fake_chat_text)

    with pytest.raises(InvalidAIJsonError) as ei:
        await provider.chat_json("sys", "user")
    assert "still broken" in ei.value.raw or "not-json" in ei.value.raw


@pytest.mark.asyncio
async def test_chat_json_succeeds_on_retry(monkeypatch):
    provider = OpenAICompatProvider(
        name="mock",
        provider="openai",
        api_url="http://127.0.0.1:9/v1",
        model="mock-model",
    )
    replies = iter(["nonsense", '{"category": "科技", "summary": "ok", "importance": 7, "tags": []}'])

    async def fake_chat_text(system: str, user: str, **kw):
        return next(replies)

    monkeypatch.setattr(provider, "chat_text", fake_chat_text)
    data = await provider.chat_json("sys", "user")
    assert data["category"] == "科技"
    assert data["summary"] == "ok"
