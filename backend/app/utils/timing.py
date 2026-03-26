"""外部服务调用耗时记录工具。"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Generator


class TimingContext:
    """记录外部服务调用耗时的上下文管理器。

    用法::

        tc = TimingContext()
        with tc.track("qwen_long"):
            result = await call_qwen_long(...)
        with tc.track("qwen_vl"):
            result = await call_qwen_vl(...)
        print(tc.summary())
    """

    def __init__(self) -> None:
        self.stages: list[dict] = []

    @contextmanager
    def track(self, stage_name: str) -> Generator[None, None, None]:
        """记录一个阶段的耗时。"""
        start = time.perf_counter()
        yield
        elapsed_ms = (time.perf_counter() - start) * 1000
        self.stages.append({"stage": stage_name, "ms": round(elapsed_ms, 2)})

    def summary(self) -> dict:
        """返回所有阶段的耗时汇总。"""
        return {
            "stages": self.stages,
            "total_ms": round(sum(s["ms"] for s in self.stages), 2),
        }
