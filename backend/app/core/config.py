from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    DATABASE_URL: str = "postgresql+asyncpg://smartclass:smartclass_dev@localhost:5432/smartclass"
    SECRET_KEY: str = "dev-secret-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    INTERNAL_API_KEY: str = "worker-shared-secret"   # unused since T40 (devices have their own keys); kept so old .env files load
    DEVICE_ONLINE_SECONDS: int = 60   # FR-408/NFR-23: a device is online if it sent a heartbeat this recently

    FACE_MATCH_THRESHOLD: float = 0.40
    INSIGHTFACE_MODEL: str = "buffalo_sc"
    FACE_VOTE_THRESHOLD: int = 3
    FACE_VOTE_MAX_GAP_SECONDS: int = 10   # FR-404: frames further apart than this aren't "consecutive"
    DEVICE_MAX_CROPS: int = 10            # crops per POST /device/faces (one frame)
    DEVICE_MAX_CROP_BYTES: int = 2 * 1024 * 1024
    FACE_COOLDOWN_SECONDS: int = 30   # unused since T46b (old face_worker); kept so old .env files still load
    # Unmatched face crops kept as evidence for "not recognised" flags (FR-407, FR-410, NFR-02)
    FACE_UNMATCHED_RETENTION_DAYS: int = 7
    FACE_UNMATCHED_CLEANUP_INTERVAL_SECONDS: int = 3600   # <= 0 disables the retention job
    FACE_UNMATCHED_SAME_PERSON: float = 0.5   # cosine: a new crop this close to a kept one is not stored again
    FACE_UNMATCHED_MAX_PER_SESSION: int = 200
    # PDPA face-data notice the student app shows (FR-109). Bump it when the wording changes.
    FACE_CONSENT_VERSION: str = "2026-11-v1"

    # Matric card verification for face self-enrolment (FR-111). Tune on real photos (T21).
    CARD_MAX_SIDE_PX: int = 1600                # photos are downscaled to this before any check
    CARD_FACE_MATCH_THRESHOLD: float = 0.30     # cosine, selfies vs the small card photo
    CARD_MATRIC_REGEX: str = r"\d{8}|[A-Z]{1,3}\d{6,7}"   # UM matric formats, after OCR clean-up
    CARD_OCR_MIN_CONFIDENCE: float = 0.85       # matric read at least this sure overrides quality warnings
    CARD_NAME_MIN_MATCH: float = 0.6            # share of the account's name words found on the card
    CARD_MIN_AREA_FRACTION: float = 0.15        # card must cover this share of the photo
    CARD_MAX_TILT_DEGREES: float = 15.0
    CARD_MAX_SKEW_RATIO: float = 0.25           # opposite card edges may differ by this much
    CARD_BLUR_MIN_VARIANCE: float = 40.0        # Laplacian variance of the card (long side shrunk to 856 px)
    CARD_GLARE_MAX_FRACTION: float = 0.06       # largest blown-out patch, share of the card area
    CARD_DARK_MAX_MEAN: float = 60.0            # mean brightness (0-255) at or below this is too dark
    CARD_MIN_SATURATION: int = 40               # colour finder: card pixels are at least this saturated
    # UM card text: any of these words, in any order, allowing small OCR misreads (T23a)
    CARD_UM_KEYWORDS: str = "UNIVERSITI,MALAYA,MYSISWA"
    # Optional extra pattern, matched on the OCR letters joined without spaces; empty = off
    CARD_UM_TEXT_REGEX: str = ""
    FACE_SELFIE_CONSISTENCY_THRESHOLD: float = 0.45   # cosine every pair of selfies must reach

    # Face self-enrolment uploads (FR-110)
    FACE_ENROL_MAX_IMAGE_BYTES: int = 10 * 1024 * 1024   # per photo
    FACE_ENROL_BLOCKS_BEFORE_SUBMIT_ANYWAY: int = 2      # blocked card photos before "submit anyway"

    DEV_BYPASS_TIME_CHECK: bool = False

    # ── Module 8: AI Learning Assistant ─────────────────────────────────────
    # LLM (DeepSeek, OpenAI-compatible API). Empty key → LLM endpoints return 503.
    LLM_BASE_URL: str = "https://api.deepseek.com"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "deepseek-chat"
    LLM_TIMEOUT_SECONDS: float = 45.0
    LLM_MAX_OUTPUT_TOKENS: int = 1200
    # Summaries, study guides, flashcards, practice and "before next class" write much more,
    # and thinking models spend part of the budget on hidden reasoning first.
    LLM_LONG_OUTPUT_TOKENS: int = 6000
    LLM_REASONING_EFFORT: str = ""   # e.g. "low" for Gemini thinking models; empty = not sent
    LLM_FAKE: bool = False           # E2E only: canned answers, no provider call (see llm.fake_chat)
    LLM_RPM: int = 10                # client-side requests-per-minute cap (provider free tier)
    LLM_MAX_RETRIES: int = 3         # retries on 429/5xx before giving up (NFR-21)
    LLM_RETRY_BASE_SECONDS: float = 1.0   # backoff base; doubles each retry
    ASSISTANT_HISTORY_TURNS: int = 3          # previous Q/A pairs sent for follow-ups
    ASSISTANT_REWRITE_FOLLOWUPS: bool = True  # rewrite follow-ups into standalone retrieval queries
    ASSISTANT_TOP_K: int = 8

    # YouTube suggestions (FR-812, Could Have). Empty key → the feature is off.
    YOUTUBE_API_KEY: str = ""
    YOUTUBE_MAX_RESULTS: int = 5

    # Local embeddings (fastembed / ONNX). Dimension must match kb_chunks.embedding.
    KB_EMBED_MODEL: str = "BAAI/bge-small-en-v1.5"
    KB_EMBED_CACHE_DIR: str = ""              # empty → ~/.cache/smartclass/fastembed
    KB_CHUNK_TARGET_TOKENS: int = 400
    KB_CHUNK_MAX_TOKENS: int = 500
    KB_CHUNK_OVERLAP_TOKENS: int = 50

    # Class sessions from the timetable (FR-301, FR-315–FR-317)
    SESSION_EARLY_OPEN_MINUTES: int = 15          # FR-301: sessions open this long before the scheduled start
    SESSION_SCHEDULER_INTERVAL_SECONDS: int = 60  # 0 disables the schedule job (the E2E backends turn it off)
    SESSION_DEFAULT_MINUTES: int = 120            # length of a "start now" class that has no schedule
    ATTENDANCE_LATE_AFTER_MINUTES: int = 15       # FR-302: a first recognition later than this after the effective start is Late

    # Moodle (UM SPeCTRUM simulation) – source of courses and materials
    MOODLE_URL: str = "http://localhost:8080"
    MOODLE_TOKEN: str = ""
    KB_SYNC_INTERVAL_SECONDS: int = 300       # 0 disables; also disabled when MOODLE_TOKEN is empty
    MOODLE_SYNC_INTERVAL_SECONDS: int = 900   # courses + enrolments (FR-104); same rules as above
    # Closed sessions -> Moodle Attendance (FR-311, NFR-20); same rules as above
    MOODLE_ATTENDANCE_SYNC_INTERVAL_SECONDS: int = 30
    MOODLE_ATTENDANCE_RETRY_BASE_SECONDS: int = 60     # first retry after a failure; doubles each time
    MOODLE_ATTENDANCE_RETRY_MAX_SECONDS: int = 3600    # backoff cap; retries never stop
    MOODLE_ATTENDANCE_CHECK_INTERVAL_SECONDS: int = 10800  # re-read synced sessions in Moodle this often (FR-320)
    MOODLE_ATTENDANCE_CHECK_DAYS: int = 30             # ...for sessions closed within this many days


settings = Settings()
