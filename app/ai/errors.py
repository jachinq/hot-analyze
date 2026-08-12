"""AI 相关异常。"""

from __future__ import annotations


class InvalidAIJsonError(ValueError):
    """模型返回无法解析为 JSON 对象（已按策略重试仍失败）。"""

    def __init__(self, message: str, *, raw: str = "") -> None:
        super().__init__(message)
        self.raw = raw
