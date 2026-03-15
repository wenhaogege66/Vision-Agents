"""配置管理模块：使用 pydantic-settings 从环境变量加载配置"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Supabase 配置
    supabase_url: str = ""
    supabase_key: str = ""

    # 通义千问 API
    dashscope_api_key: str = ""

    # GetStream 配置
    getstream_api_key: str = ""
    getstream_api_secret: str = ""

    # 应用配置
    app_env: str = "development"
    app_debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # CORS 配置
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # 文件上传限制（单位：字节）
    max_ppt_size: int = 52428800  # 50MB
    max_video_size: int = 524288000  # 500MB

    model_config = {
        "env_file": ".env",
        "extra": "ignore",
    }


settings = Settings()
