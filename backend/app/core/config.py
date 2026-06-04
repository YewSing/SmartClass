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


settings = Settings()
