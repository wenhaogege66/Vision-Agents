"""FastAPI 应用入口：注册 CORS 中间件、全局异常处理器和路由"""

import asyncio
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.models.schemas import ErrorResponse
from app.utils.timing_middleware import TimingMiddleware

# 配置日志级别，确保 INFO 日志可见
logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s - %(message)s")

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

# 注册 API 耗时监控中间件
app.add_middleware(TimingMiddleware)


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
from app.routes.defense import router as defense_router
from app.routes.competitions import name_mappings_router, router as competitions_router
from app.routes.judge_styles import router as judge_styles_router
from app.routes.live_presentation import router as live_presentation_router
from app.routes.live_presentation import share_join_router
from app.routes.materials import router as materials_router
from app.routes.projects import router as projects_router
from app.routes.reviews import router as reviews_router
from app.routes.tags import tag_router, project_tag_router
from app.routes.voices import router as voices_router

app.include_router(auth_router)
app.include_router(defense_router)
app.include_router(competitions_router)
app.include_router(name_mappings_router)
app.include_router(judge_styles_router)
app.include_router(live_presentation_router)
app.include_router(share_join_router)
app.include_router(materials_router)
app.include_router(projects_router)
app.include_router(reviews_router)
app.include_router(voices_router)
app.include_router(tag_router)
app.include_router(project_tag_router)


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "ok"}


# ── 启动扫描：自动补全缺失的简介和问题 ──────────────────────


async def _scan_and_fill_missing():
    """扫描所有项目，对已有 BP+文本PPT 但缺少简介或问题的项目自动生成。"""
    from app.models.database import get_supabase
    from app.services.profile_service import ProfileService
    from app.services.defense_service import DefenseService

    try:
        sb = get_supabase()
    except Exception as exc:
        logger.warning("扫描任务无法获取 Supabase 客户端: %s", exc)
        return

    try:
        # 获取所有项目
        projects = sb.table("projects").select("id").execute().data or []
    except Exception as exc:
        logger.warning("扫描任务查询项目列表失败: %s", exc)
        return

    profile_svc = ProfileService(sb)
    defense_svc = DefenseService(sb)

    for proj in projects:
        pid = proj["id"]
        try:
            # 检查是否有 BP 和文本 PPT
            bp = sb.table("project_materials").select("id").eq("project_id", pid).eq("material_type", "bp").eq("is_latest", True).limit(1).execute()
            text_ppt = sb.table("project_materials").select("id").eq("project_id", pid).eq("material_type", "text_ppt").eq("is_latest", True).limit(1).execute()

            has_bp = bool(bp.data)
            has_text_ppt = bool(text_ppt.data)

            if not (has_bp and has_text_ppt):
                continue

            # 检查简介
            profile_result = sb.table("project_profiles").select("id, team_intro, domain").eq("project_id", pid).limit(1).execute()
            has_profile = bool(profile_result.data) and any(
                profile_result.data[0].get(f) for f in ["team_intro", "domain"]
            )

            # 检查问题
            questions = sb.table("defense_questions").select("id").eq("project_id", pid).limit(1).execute()
            has_questions = bool(questions.data)

            if not has_profile:
                logger.info("扫描：项目 %s 缺少简介，自动生成中…", pid)
                await profile_svc.extract_profile(pid)
                logger.info("扫描：项目 %s 简介和问题生成完成", pid)
            elif not has_questions:
                # 有简介但没问题，单独生成问题
                logger.info("扫描：项目 %s 缺少问题，自动生成中…", pid)
                profile_data = profile_result.data[0]
                await defense_svc.generate_questions(pid, profile_data)
                logger.info("扫描：项目 %s 问题生成完成", pid)

        except Exception as exc:
            logger.warning("扫描：项目 %s 自动生成失败: %s", pid, exc)
            continue


@app.on_event("startup")
async def startup_scan():
    """应用启动时异步执行扫描任务。"""
    asyncio.create_task(_scan_and_fill_missing())
