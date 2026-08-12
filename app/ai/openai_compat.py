"""OpenAI 兼容 HTTP 客户端（含 LM Studio / DeepSeek / 通义等）。"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx
from openai import APITimeoutError, AsyncOpenAI, AuthenticationError

from app.ai.errors import InvalidAIJsonError

logger = logging.getLogger(__name__)


def extract_json(text: str) -> dict[str, Any]:
    raw = text
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
        raise ValueError(f"JSON root is not object: {type(data).__name__}")
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        raise ValueError(f"no JSON object in response: {raw[:200]}")
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise ValueError(f"embedded JSON decode failed: {e}") from e
    if not isinstance(data, dict):
        raise ValueError("JSON root is not object")
    return data


def _clip(text: str, limit: int = 1500) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    return text[:limit] + f"…(truncated, total={len(text)})"


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
        except Exception as first_err:
            # 仅对 JSON 解析失败重试一次；超时/鉴权不再重试以免双倍等待
            logger.warning(
                "JSON parse failed for provider=%s model=%s err=%s; raw_response=%s",
                self.name,
                self.model,
                first_err,
                _clip(text),
            )
            retry_user = (
                user
                + "\n\n上一次输出不是合法 JSON，请严格只输出一个 JSON 对象，"
                + "不要 Markdown 代码块，不要解释文字。"
            )
            try:
                text2 = await self.chat_text(system, retry_user, **kw)
            except (APITimeoutError, TimeoutError, AuthenticationError, httpx.TimeoutException):
                raise
            except Exception as retry_call_err:
                logger.error(
                    "JSON retry request failed for provider=%s: %s",
                    self.name,
                    retry_call_err,
                )
                raise InvalidAIJsonError(
                    f"JSON retry request failed: {retry_call_err}",
                    raw=text,
                ) from retry_call_err

            try:
                return extract_json(text2)
            except Exception as second_err:
                logger.error(
                    "JSON parse retry still failed for provider=%s model=%s err=%s; "
                    "first_raw=%s; retry_raw=%s",
                    self.name,
                    self.model,
                    second_err,
                    _clip(text),
                    _clip(text2),
                )
                raise InvalidAIJsonError(
                    f"invalid AI JSON after retry: {second_err}",
                    raw=text2 or text,
                ) from second_err
