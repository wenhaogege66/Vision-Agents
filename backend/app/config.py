"""配置管理模块：使用 pydantic-settings 从环境变量加载配置"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Supabase 配置
    supabase_url: str = ""
    supabase_key: str = ""

    # 通义千问 API
    dashscope_api_key: str = ""
    dashscope_text_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    dashscope_multimodal_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    dashscope_model: str = "qwen-vl-max"

    # Deepgram STT 配置
    deepgram_api_key: str = ""

    # GetStream 配置
    getstream_api_key: str = ""
    getstream_api_secret: str = ""

    # HeyGen 数字人配置
    heygen_api_key: str = ""
    heygen_avatar_id: str = "80d4afa941c243beb0a1116c95ea48ee"
    heygen_video_avatar_id: str = "Abigail_expressive_2024112501"
    heygen_video_voice_id: str = "de6ad44022104ac0872392d1139e9364"

    # LiveAvatar 数字人配置
    liveavatar_api_key: str = ""
    liveavatar_avatar_id: str = ""

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
