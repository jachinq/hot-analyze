"""Ollama 备选：走 OpenAI 兼容端点。"""

from __future__ import annotations

from app.ai.openai_compat import OpenAICompatProvider


class OllamaProvider(OpenAICompatProvider):
    """Ollama OpenAI 兼容 `/v1` 端点。"""

    def __init__(
        self,
        *,
        name: str = "ollama",
        api_url: str = "http://127.0.0.1:11434/v1",
        model: str = "qwen2.5",
        api_key: str = "ollama",
        timeout: float = 120.0,
        **_: object,
    ) -> None:
        super().__init__(
            name=name,
            provider="ollama",
            api_url=api_url,
            model=model,
            api_key=api_key or "ollama",
            timeout=timeout,
        )
