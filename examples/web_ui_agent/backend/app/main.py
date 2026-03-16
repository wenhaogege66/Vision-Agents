"""FastAPI 应用入口：注册 CORS 中间件、全局异常处理器和路由"""

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.models.schemas import ErrorResponse

logger = logging.getLogger(__name__)

app = FastAPI(
    title="中国大学生创新大赛AI评委系统",
    description="基于多模态AI的智能评审与路演模拟系统",
    version="0.1.0",
)

# 注册 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 全局异常处理器 ────────────────────────────────────────────


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    """处理所有 HTTPException，统一返回 ErrorResponse 格式"""
    body = ErrorResponse(
        error=f"http_{exc.status_code}",
        message=str(exc.detail),
    )
    return JSONResponse(status_code=exc.status_code, content=body.model_dump())


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    """处理请求参数验证错误，返回 422 + 字段级错误信息"""
    body = ErrorResponse(
        error="validation_error",
        message="请求参数验证失败",
        details={"errors": exc.errors()},
    )
    return JSONResponse(status_code=422, content=body.model_dump())


@app.exception_handler(Exception)
async def generic_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    """兜底处理未预期的异常，避免泄露内部细节"""
    logger.exception("未处理的服务器异常: %s", exc)
    body = ErrorResponse(
        error="internal_error",
        message="服务器内部错误，请稍后重试",
    )
    return JSONResponse(status_code=500, content=body.model_dump())


# ── 路由 ──────────────────────────────────────────────────────


from app.routes.auth import router as auth_router
from app.routes.competitions import router as competitions_router
from app.routes.projects import router as projects_router

app.include_router(auth_router)
app.include_router(competitions_router)
app.include_router(projects_router)


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "ok"}
