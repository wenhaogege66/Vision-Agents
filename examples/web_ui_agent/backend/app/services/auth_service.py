"""认证服务：封装 Supabase Auth（注册、登录、获取当前用户）"""

import logging

from fastapi import HTTPException
from supabase import Client

logger = logging.getLogger(__name__)


class AuthService:
    """封装 Supabase Auth 操作"""

    def __init__(self, supabase: Client) -> None:
        self._sb = supabase

    # ── 注册 ──────────────────────────────────────────────────

    async def register(
        self, email: str, password: str, display_name: str
    ) -> dict:
        """注册新用户并创建 profiles 记录。

        Returns:
            {"access_token": str, "user": {"id", "email", "display_name"}}
        """
        try:
            res = self._sb.auth.sign_up(
                {"email": email, "password": password}
            )
        except Exception as exc:
            logger.exception("Supabase Auth sign_up failed")
            raise HTTPException(status_code=400, detail=f"注册失败: {exc}") from exc

        user = res.user
        if user is None:
            raise HTTPException(status_code=400, detail="注册失败，请检查邮箱格式或密码强度")

        # 创建 profiles 记录
        try:
            self._sb.table("profiles").insert(
                {"id": user.id, "display_name": display_name}
            ).execute()
        except Exception as exc:
            logger.warning("创建 profile 失败（用户已注册但 profile 写入异常）: %s", exc)

        access_token = ""
        if res.session:
            access_token = res.session.access_token

        return {
            "access_token": access_token,
            "user": {
                "id": user.id,
                "email": user.email or email,
                "display_name": display_name,
            },
        }

    # ── 登录 ──────────────────────────────────────────────────

    async def login(self, email: str, password: str) -> dict:
        """用户登录，返回 access_token 和用户信息。

        Returns:
            {"access_token": str, "user": {"id", "email", "display_name"}}
        """
        try:
            res = self._sb.auth.sign_in_with_password(
                {"email": email, "password": password}
            )
        except Exception as exc:
            logger.exception("Supabase Auth sign_in failed")
            raise HTTPException(status_code=401, detail="邮箱或密码错误") from exc

        user = res.user
        session = res.session
        if user is None or session is None:
            raise HTTPException(status_code=401, detail="邮箱或密码错误")

        # 查询 display_name
        display_name = None
        try:
            profile = (
                self._sb.table("profiles")
                .select("display_name")
                .eq("id", user.id)
                .maybe_single()
                .execute()
            )
            if profile.data:
                display_name = profile.data.get("display_name")
        except Exception:
            logger.warning("查询 profile 失败，display_name 将为空")

        return {
            "access_token": session.access_token,
            "user": {
                "id": user.id,
                "email": user.email or email,
                "display_name": display_name,
            },
        }

    # ── 获取当前用户 ──────────────────────────────────────────

    async def get_current_user(self, token: str) -> dict:
        """通过 JWT token 验证并返回用户信息。

        Returns:
            {"id": str, "email": str, "display_name": str | None}
        """
        try:
            res = self._sb.auth.get_user(token)
        except Exception as exc:
            logger.debug("Token 验证失败: %s", exc)
            raise HTTPException(status_code=401, detail="无效或过期的认证令牌") from exc

        user = res.user
        if user is None:
            raise HTTPException(status_code=401, detail="无效或过期的认证令牌")

        # 查询 display_name
        display_name = None
        try:
            profile = (
                self._sb.table("profiles")
                .select("display_name")
                .eq("id", user.id)
                .maybe_single()
                .execute()
            )
            if profile.data:
                display_name = profile.data.get("display_name")
        except Exception:
            logger.warning("查询 profile 失败，display_name 将为空")

        return {
            "id": user.id,
            "email": user.email or "",
            "display_name": display_name,
        }
