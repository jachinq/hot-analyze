"""OpenAI 兼容 HTTP 客户端（含 LM Studio / DeepSeek / 通义等）。"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx
from openai import APITimeoutError, AsyncOpenAI, AuthenticationError

logger = logging.getLogger(__name__)


def extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        raise ValueError(f"no JSON object in response: {text[:200]}")
    data = json.loads(m.group(0))
    if not isinstance(data, dict):
        raise ValueError("JSON root is not object")
    return data


class OpenAICompatProvider:
    def __init__(
        self,
        *,
        name: str,
        provider: str,
        api_url: str,
        model: str,
        api_key: str = "lm-studio",
        timeout: float = 120.0,
    ) -> None:
        self.name = name
        self.provider = provider
        self.model = model
        self.api_url = api_url.rstrip("/")
        self.timeout = float(timeout)
        # connect 短、read 长：本地大模型生成阶段可能很慢
        http_timeout = httpx.Timeout(self.timeout, connect=min(30.0, self.timeout))
        self._client = AsyncOpenAI(
            api_key=api_key or "lm-studio",
            base_url=self.api_url,
            timeout=http_timeout,
        )
        self.last_usage: dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0}

    async def chat_text(self, system: str, user: str, **kw: Any) -> str:
        temperature = kw.get("temperature", 0.3)
        max_tokens = kw.get("max_tokens", 1024)
        req_timeout = kw.get("timeout")
        create_kw: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if req_timeout is not None:
            create_kw["timeout"] = float(req_timeout)
        resp = await self._client.chat.completions.create(**create_kw)
        usage = getattr(resp, "usage", None)
        if usage:
            self.last_usage = {
                "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
                "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
            }
        else:
            self.last_usage = {"prompt_tokens": 0, "completion_tokens": 0}
        content = resp.choices[0].message.content or ""
        return content

    async def chat_json(self, system: str, user: str, **kw: Any) -> dict[str, Any]:
        text = await self.chat_text(system, user, **kw)
        try:
            return extract_json(text)
        except (APITimeoutError, TimeoutError, AuthenticationError, httpx.TimeoutException):
            raise
        except Exception:
            # 仅对 JSON 解析失败重试一次；超时/鉴权不再重试以免双倍等待
            logger.warning("JSON parse failed for %s, retrying once", self.name)
            retry_user = user + "\n\n上一次输出不是合法 JSON，请严格只输出 JSON 对象。"
            text2 = await self.chat_text(system, retry_user, **kw)
            return extract_json(text2)
