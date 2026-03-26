"""Supabase 客户端初始化模块：提供数据库、认证和存储访问"""

from supabase import create_client, Client

from app.config import settings

# 初始化 Supabase 客户端（包含 Auth + Storage + DB）
supabase: Client = create_client(settings.supabase_url, settings.supabase_key)


def get_supabase() -> Client:
    """获取 Supabase 客户端实例，用于 FastAPI 依赖注入"""
    return supabase
