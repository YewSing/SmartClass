from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    DATABASE_URL: str = "postgresql+asyncpg://smartclass:smartclass_dev@localhost:5432/smartclass"
    SECRET_KEY: str = "dev-secret-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    INTERNAL_API_KEY: str = "worker-shared-secret"

    FACE_MATCH_THRESHOLD: float = 0.40
    INSIGHTFACE_MODEL: str = "buffalo_sc"
    FACE_VOTE_THRESHOLD: int = 3
    FACE_COOLDOWN_SECONDS: int = 30

    DEV_BYPASS_TIME_CHECK: bool = False

    # ©¤©¤ Module 8: AI Learning Assistant ©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤
    # LLM (DeepSeek, OpenAI-compatible API). Empty key ¡ú LLM endpoints return 503.
    LLM_BASE_URL: str = "https://api.deepseek.com"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "deepseek-chat"
    LLM_TIMEOUT_SECONDS: float = 45.0
    LLM_MAX_OUTPUT_TOKENS: int = 1200
    LLM_REASONING_EFFORT: str = ""   # e.g. "low" for Gemini thinking models; empty = not sent
    ASSISTANT_HISTORY_TURNS: int = 3          # previous Q/A pairs sent for follow-ups
    ASSISTANT_REWRITE_FOLLOWUPS: bool = True  # rewrite follow-ups into standalone retrieval queries
    ASSISTANT_TOP_K: int = 8

    # Local embeddings (fastembed / ONNX). Dimension must match kb_chunks.embedding.
    KB_EMBED_MODEL: str = "BAAI/bge-small-en-v1.5"
    KB_EMBED_CACHE_DIR: str = ""              # empty ¡ú ~/.cache/smartclass/fastembed
    KB_CHUNK_TARGET_TOKENS: int = 400
    KB_CHUNK_MAX_TOKENS: int = 500
    KB_CHUNK_OVERLAP_TOKENS: int = 50

    # Moodle (UM SPeCTRUM simulation) ¨C source of courses and materials
    MOODLE_URL: str = "http://localhost:8080"
    MOODLE_TOKEN: str = ""
    KB_SYNC_INTERVAL_SECONDS: int = 300       # 0 disables; also disabled when MOODLE_TOKEN is empty


settings = Settings()
