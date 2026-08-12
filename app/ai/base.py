"""AI Provider 抽象。"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class AIProvider(Protocol):
    name: str
    provider: str
    model: str

    async def chat_json(self, system: str, user: str, **kw: Any) -> dict[str, Any]: ...

    async def chat_text(self, system: str, user: str, **kw: Any) -> str: ...
