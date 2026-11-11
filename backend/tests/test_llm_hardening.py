"""T82: LLM adapter hardening — retry on 429/5xx, quota detection, rate limiter."""
import pytest

from app.core.config import settings
from app.services.kb import llm
from app.services.kb.llm import LLMQuotaExhausted, LLMUnavailable


def _api_error(status_code, message="", error_body=None):
    """A minimal stand-in for an openai APIStatusError with the fields the adapter reads."""
    err = RuntimeError(message or "boom")
    err.status_code = status_code
    err.body = error_body or {}
    err.message = message
    return err


def _ok(content="answer"):
    class _Message:
        def __init__(self):
            self.content = content
    class _Choice:
        def __init__(self):
            self.message = _Message()
    class _Resp:
        def __init__(self):
            self.choices = [_Choice()]
    return _Resp()


class FakeCompletions:
    def __init__(self, results):
        self.results = list(results)
        self.calls = 0

    async def create(self, **kwargs):
        self.calls += 1
        item = self.results.pop(0) if self.results else RuntimeError("no more results")
        if isinstance(item, Exception):
            raise item
        return item


class FakeClient:
    def __init__(self, results):
        self.chat = type("_Chat", (), {"completions": FakeCompletions(results)})()


@pytest.fixture
def fake_client(monkeypatch):
    def install(results):
        client = FakeClient(results)

        async def fake_get_client():
            return client

        monkeypatch.setattr(llm, "_get_client", fake_get_client)
        monkeypatch.setattr(settings, "LLM_API_KEY", "test-key")
        monkeypatch.setattr(settings, "LLM_RPM", 0)              # no rate limiting here
        monkeypatch.setattr(settings, "LLM_MAX_RETRIES", 3)
        monkeypatch.setattr(settings, "LLM_RETRY_BASE_SECONDS", 0)  # no real sleep
        return client.chat.completions
    return install


# ── retry + error mapping ─────────────────────────────────────────────────────

async def test_success_returns_content(fake_client):
    fake_client([_ok("  the answer  ")])
    assert await llm.chat([{"role": "user", "content": "hi"}]) == "the answer"


async def test_retries_on_429_then_succeeds(fake_client):
    c = fake_client([_api_error(429), _api_error(429), _ok("recovered")])
    assert await llm.chat([{"role": "user", "content": "hi"}]) == "recovered"
    assert c.calls == 3


async def test_retries_on_5xx_then_succeeds(fake_client):
    c = fake_client([_api_error(500), _api_error(503), _api_error(502), _ok("recovered")])
    assert await llm.chat([{"role": "user", "content": "hi"}]) == "recovered"
    assert c.calls == 4  # 1 initial + 3 retries


async def test_gives_up_after_max_retries(fake_client):
    c = fake_client([_api_error(429)] * 4)
    with pytest.raises(LLMUnavailable):
        await llm.chat([{"role": "user", "content": "hi"}])
    assert c.calls == 4  # never more than 1 + LLM_MAX_RETRIES


async def test_quota_error_is_distinct_and_not_retried(fake_client):
    body = {"error": {"message": "You have exceeded your daily quota", "status": "RESOURCE_EXHAUSTED"}}
    c = fake_client([_api_error(429, "quota exhausted", body)])
    with pytest.raises(LLMQuotaExhausted):
        await llm.chat([{"role": "user", "content": "hi"}])
    assert c.calls == 1  # retrying a quota error is pointless


async def test_fatal_4xx_is_not_retried(fake_client):
    c = fake_client([_api_error(400, "bad request")])
    with pytest.raises(LLMUnavailable):
        await llm.chat([{"role": "user", "content": "hi"}])
    assert c.calls == 1


async def test_llm_quota_exhausted_is_an_llm_unavailable():
    assert issubclass(LLMQuotaExhausted, LLMUnavailable)


# ── rate limiter ──────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _clear_rate_times():
    llm._rate_times.clear()
    yield
    llm._rate_times.clear()


async def test_throttle_waits_when_at_cap(monkeypatch):
    monkeypatch.setattr(settings, "LLM_RPM", 2)
    clock = {"now": 0.0}
    sleeps = []
    monkeypatch.setattr(llm, "_monotonic", lambda: clock["now"])

    async def fake_sleep(delay):
        sleeps.append(delay)
        clock["now"] += delay

    monkeypatch.setattr(llm, "_sleep", fake_sleep)

    await llm._throttle()  # slot 1 at t=0
    await llm._throttle()  # slot 2 at t=0
    await llm._throttle()  # at the cap: waits out the 60 s window
    assert sleeps == [60.0]


async def test_throttle_no_wait_under_cap(monkeypatch):
    monkeypatch.setattr(settings, "LLM_RPM", 5)
    monkeypatch.setattr(llm, "_monotonic", lambda: 0.0)
    sleeps = []

    async def fake_sleep(delay):
        sleeps.append(delay)

    monkeypatch.setattr(llm, "_sleep", fake_sleep)
    for _ in range(5):
        await llm._throttle()
    assert sleeps == []


async def test_throttle_disabled_when_rpm_is_zero(monkeypatch):
    monkeypatch.setattr(settings, "LLM_RPM", 0)
    monkeypatch.setattr(llm, "_monotonic", lambda: 0.0)
    monkeypatch.setattr(llm, "_sleep", lambda d: pytest.fail("must not sleep"))
    await llm._throttle()  # no-op
