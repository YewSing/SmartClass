"""Chat LLM client for any OpenAI-compatible provider.

Switching provider is a .env change only, e.g.
    DeepSeek:  LLM_BASE_URL=https://api.deepseek.com
    Gemini:    LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
    OpenCode:  LLM_BASE_URL=https://opencode.ai/inference/openai/v1
"""
from app.core.config import settings


class LLMUnavailable(Exception):
    """No key configured, provider down, or timed out. Routers turn this into a 503."""


_client = None


def _get_client():
    global _client
    if not settings.LLM_API_KEY:
        raise LLMUnavailable("The AI assistant is not configured (LLM_API_KEY is empty).")
    if _client is None:
        from openai import AsyncOpenAI

        _client = AsyncOpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
            timeout=settings.LLM_TIMEOUT_SECONDS,
            max_retries=1,
            default_headers={"User-Agent": "smartclass-backend/1.0"},
        )
    return _client


FAKE_COURSE_ANSWER = "This is a test answer from your course materials [1]."
FAKE_GENERAL_ANSWER = (
    "This isn't covered in your course materials, so here's a general explanation: this is a test answer."
)


def fake_chat(messages: list[dict]) -> str:
    """Deterministic reply for E2E runs (LLM_FAKE=1), shaped like the real prompts' answers.

    A follow-up rewrite gets the latest question back; an answer cites passage [1] when the
    prompt carries course passages, otherwise it is a general-knowledge answer.
    """
    last = messages[-1]["content"]
    if "standalone search query" in messages[0]["content"]:
        return last.rsplit("Latest question:", 1)[-1].strip()
    if "\n[1] " in last:
        return FAKE_COURSE_ANSWER
    return FAKE_GENERAL_ANSWER


async def chat(messages: list[dict], max_tokens: int | None = None, temperature: float = 0.2) -> str:
    if settings.LLM_FAKE:
        return fake_chat(messages)
    client = _get_client()
    # Thinking models (Gemini 3.x) can spend tens of seconds reasoning; "low" keeps chat snappy
    extra = {"reasoning_effort": settings.LLM_REASONING_EFFORT} if settings.LLM_REASONING_EFFORT else {}
    try:
        resp = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=messages,
            max_tokens=max_tokens or settings.LLM_MAX_OUTPUT_TOKENS,
            temperature=temperature,
            **extra,
        )
    except Exception as exc:  # openai raises typed errors; callers only need "unavailable"
        raise LLMUnavailable(f"AI provider error: {type(exc).__name__}") from exc
    return (resp.choices[0].message.content or "").strip()
