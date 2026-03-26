"""认证路由：注册、登录、获取当前用户信息。"""

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client

from app.models.database import get_supabase
from app.models.schemas import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    UserInfo,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Bearer token 提取器
_bearer_scheme = HTTPBearer()


def _get_auth_service(supabase: Client = Depends(get_supabase)) -> AuthService:
    return AuthService(supabase)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    auth_service: AuthService = Depends(_get_auth_service),
) -> UserInfo:
    """FastAPI 依赖项：从 Authorization 头提取 Bearer token 并验证。

    用法::

        @router.get("/protected")
        async def protected(user: UserInfo = Depends(get_current_user)):
            ...
    """
    data = await auth_service.get_current_user(credentials.credentials)
    return UserInfo(**data)


# ── 端点 ──────────────────────────────────────────────────────


@router.post("/register", response_model=AuthResponse)
async def register(
    body: RegisterRequest,
    auth_service: AuthService = Depends(_get_auth_service),
):
    """用户注册"""
    result = await auth_service.register(body.email, body.password, body.display_name)
    return AuthResponse(
        access_token=result["access_token"],
        user=UserInfo(**result["user"]),
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    body: LoginRequest,
    auth_service: AuthService = Depends(_get_auth_service),
):
    """用户登录"""
    result = await auth_service.login(body.email, body.password)
    return AuthResponse(
        access_token=result["access_token"],
        user=UserInfo(**result["user"]),
    )


@router.get("/me", response_model=UserInfo)
async def me(user: UserInfo = Depends(get_current_user)):
    """获取当前登录用户信息"""
    return user
