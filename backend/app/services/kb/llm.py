"""Chat LLM client for any OpenAI-compatible provider.

Switching provider is a .env change only, e.g.
    DeepSeek:  LLM_BASE_URL=https://api.deepseek.com
    Gemini:    LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
    OpenCode:  LLM_BASE_URL=https://opencode.ai/inference/openai/v1

Resilience (NFR-21, T82):
- a client-side rate limiter caps requests at `LLM_RPM` per minute, so the free
  tier is never tripped by a burst;
- transient 429/5xx errors retry with backoff, at most `LLM_MAX_RETRIES` times;
- daily-quota exhaustion is a distinct `LLMQuotaExhausted` error (no point retrying),
  so the live test suite can skip with `LLM_QUOTA` instead of failing.
"""
import asyncio
import json as _json
import time
from collections import deque

from app.core.config import settings

# Module-level indirection so tests can inject a fake clock/sleep.
_monotonic = time.monotonic
_sleep = asyncio.sleep


class LLMUnavailable(Exception):
    """No key configured, provider down, or timed out. Routers turn this into a 503."""


class LLMQuotaExhausted(LLMUnavailable):
    """The provider's daily quota is used up. Retrying won't help (it is still a 503)."""


_client = None
_client_loop = None


async def _get_client():
    """The shared OpenAI client, recreated when the running event loop changes.

    Tests run each case on its own event loop, and httpx binds its connection pool to the
    loop it is first used on. Reusing a client across loops raises "Event loop is closed".
    """
    global _client, _client_loop
    if not settings.LLM_API_KEY:
        raise LLMUnavailable("The AI assistant is not configured (LLM_API_KEY is empty).")
    loop = asyncio.get_running_loop()
    if _client is not None and _client_loop is not loop:
        old, _client = _client, None
        try:
            await old.close()
        except Exception:  # noqa: BLE001 — best effort; the old loop may already be gone
            pass
    if _client is None:
        from openai import AsyncOpenAI

        _client = AsyncOpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
            timeout=settings.LLM_TIMEOUT_SECONDS,
            max_retries=0,  # we retry ourselves, with backoff and quota awareness
            default_headers={"User-Agent": "smartclass-backend/1.0"},
        )
        _client_loop = loop
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


# ── client-side rate limiter ──────────────────────────────────────────────────
# One shared sliding window for the whole process. Requests wait for a free slot so
# that, e.g., the live suite can't burst past the provider's free tier.

_rate_times: deque[float] = deque()
_rate_lock = asyncio.Lock()


async def _throttle() -> None:
    """Wait until a request may be sent without exceeding `LLM_RPM` in the last 60 s."""
    if settings.LLM_RPM <= 0:
        return
    async with _rate_lock:
        now = _monotonic()
        while _rate_times and now - _rate_times[0] >= 60.0:
            _rate_times.popleft()
        if len(_rate_times) >= settings.LLM_RPM:
            await _sleep(60.0 - (now - _rate_times[0]))
            now = _monotonic()
            while _rate_times and now - _rate_times[0] >= 60.0:
                _rate_times.popleft()
        _rate_times.append(now)


# ── error classification ──────────────────────────────────────────────────────

def _error_kind(exc: Exception) -> str:
    """'quota' | 'retryable' | 'fatal' for an openai client exception."""
    status = getattr(exc, "status_code", None)
    body = getattr(exc, "body", None)
    message = str(getattr(exc, "message", "") or "")
    # Gemini's OpenAI-compatible endpoint wraps the error in a one-element list:
    #   [{"error": {"code": 429, "message": "...quota...", "status": "RESOURCE_EXHAUSTED"}}]
    if isinstance(body, dict):
        body = [body]
    if isinstance(body, list):
        for item in body:
            if isinstance(item, dict):
                err = item.get("error") or {}
                for field in ("message", "status", "code"):
                    v = err.get(field)
                    if isinstance(v, str):
                        message += " " + v
    text = message.lower()
    if any(k in text for k in ("quota", "resource_exhausted", "daily limit", "exceeded your current quota")):
        return "quota"
    if status is not None and (status == 429 or status >= 500):
        return "retryable"
    return "fatal"


async def chat(messages: list[dict], max_tokens: int | None = None, temperature: float = 0.2) -> str:
    if settings.LLM_FAKE:
        return fake_chat(messages)
    client = await _get_client()
    # Thinking models (Gemini 3.x) can spend tens of seconds reasoning; "low" keeps chat snappy
    extra = {"reasoning_effort": settings.LLM_REASONING_EFFORT} if settings.LLM_REASONING_EFFORT else {}
    attempts = settings.LLM_MAX_RETRIES + 1
    for attempt in range(attempts):
        await _throttle()
        try:
            resp = await client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=messages,
                max_tokens=max_tokens or settings.LLM_MAX_OUTPUT_TOKENS,
                temperature=temperature,
                **extra,
            )
        except Exception as exc:  # noqa: BLE001 — callers only need "unavailable"/"quota"
            kind = _error_kind(exc)
            if kind == "quota":
                raise LLMQuotaExhausted("The AI provider's daily quota is exhausted.") from exc
            if kind == "retryable" and attempt < attempts - 1:
                await asyncio.sleep(settings.LLM_RETRY_BASE_SECONDS * (2 ** attempt))
                continue
            raise LLMUnavailable(f"AI provider error: {type(exc).__name__}") from exc
        return (resp.choices[0].message.content or "").strip()
    raise LLMUnavailable("AI provider error: retries exhausted")  # pragma: no cover


def _extract_json(text: str) -> str:
    """Pull the JSON object out of a reply that may be wrapped in markdown fences."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]  # drop the opening fence
        if text.rstrip().endswith("```"):
            text = text.rsplit("```", 1)[0]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no JSON object found")
    return text[start:end + 1]


async def chat_json(messages: list[dict], *, max_tokens: int | None = None,
                    temperature: float = 0.2, retries: int = 1, validator=None) -> object:
    """Ask the LLM for a JSON object. Malformed output is retried once, then fails.

    `validator` (optional) is applied to the parsed object; a `ValueError` from it (e.g. a
    pydantic `ValidationError`) counts as malformed too. Raises `LLMUnavailable` when the
    provider errors or the JSON stays malformed (routers turn that into a 502).
    `LLMQuotaExhausted` propagates unchanged.
    """
    for attempt in range(retries + 1):
        raw = await chat(messages, max_tokens=max_tokens, temperature=temperature)
        try:
            data = _json.loads(_extract_json(raw))
            return validator(data) if validator else data
        except ValueError:
            if attempt >= retries:
                raise LLMUnavailable("The AI returned malformed JSON.") from None
            messages = messages + [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": "That was not valid JSON. Reply with a single valid JSON object only."},
            ]
    raise LLMUnavailable("The AI returned malformed JSON.")  # pragma: no cover
