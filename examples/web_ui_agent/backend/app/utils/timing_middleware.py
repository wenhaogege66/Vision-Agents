"""FastAPI 中间件：记录每个 API 请求的总耗时。"""

from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class TimingMiddleware(BaseHTTPMiddleware):
    """API 调用耗时监控中间件。"""

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        start = time.perf_counter()
        response: Response = await call_next(request)
        total_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "api_timing",
            extra={
                "api_path": request.url.path,
                "method": request.method,
                "total_ms": round(total_ms, 2),
                "status_code": response.status_code,
            },
        )
        return response
