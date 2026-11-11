"""Shared setup for the live AI suite (tests/live/).

Live tests make real LLM calls, so they only run under `pytest -m live` (check.sh
triggers that when the KB or a prompt changed; see T82). Two safety nets:

- `LLMQuotaExhausted` (a used-up daily quota) turns a failed live test into a skip with
  reason `LLM_QUOTA`, via the `pytest_runtest_makereport` hook below, so the suite skips
  instead of failing the round. (A generator fixture can't catch an async test's
  exception under pytest-asyncio, so the hook is used.)
- `--record-llm` saves each first-question answer + retrieved passages to
  `tests/fixtures/llm/qa.json`, which the non-live replay tests read at zero cost.
"""
import json
from pathlib import Path

import pytest

from app.services.kb.llm import LLMQuotaExhausted

LLM_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "llm"
LLM_FIXTURES.mkdir(parents=True, exist_ok=True)
RECORDING_PATH = LLM_FIXTURES / "qa.json"

_records: dict[str, dict] = {}


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Report a live test that hit the provider's daily quota as skipped (LLM_QUOTA)."""
    outcome = yield
    report = outcome.get_result()
    if report.outcome == "failed" and call.excinfo and isinstance(call.excinfo.value, LLMQuotaExhausted):
        report.outcome = "skipped"
        report.longrepr = (item.path, item.location[1], "LLM_QUOTA")


@pytest.fixture
def record(request):
    """Returns a `save(question, raw, passages, source)` callable, active only with --record-llm."""
    enabled = request.config.getoption("--record-llm")

    def save(question: str, raw: str, passages: list, source: str) -> None:
        if not enabled:
            return
        from tests.fixtures.synthetic import passage_to_dict

        _records[question] = {
            "raw": raw, "source": source, "passages": [passage_to_dict(p) for p in passages],
        }

    return save


def pytest_sessionfinish(session, exitstatus):
    if _records and session.config.getoption("--record-llm"):
        RECORDING_PATH.write_text(json.dumps(_records, indent=2, ensure_ascii=False), encoding="utf-8")
