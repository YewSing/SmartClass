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

_records: dict[str, dict] = {}   # kept: answers whose test passed
_pending: dict[str, dict] = {}   # test nodeid -> answers saved while that test runs


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Report a live test that hit the provider's daily quota as skipped (LLM_QUOTA), and
    keep a test's recorded answers only if the test passed (a wrong answer must never
    become a replay fixture)."""
    outcome = yield
    report = outcome.get_result()
    if report.outcome == "failed" and call.excinfo and isinstance(call.excinfo.value, LLMQuotaExhausted):
        report.outcome = "skipped"
        report.longrepr = (item.path, item.location[1], "LLM_QUOTA")
    if call.when == "call":
        saved = _pending.pop(item.nodeid, {})
        if report.outcome == "passed":
            _records.update(saved)


@pytest.fixture
def record(request):
    """Returns a `save(question, raw, passages, source, kind=None)` callable, active only with --record-llm.

    Saved answers are held until the test finishes and kept only if it passed."""
    enabled = request.config.getoption("--record-llm")
    nodeid = request.node.nodeid

    def save(question: str, raw: str, passages: list, source: str, kind: str | None = None) -> None:
        if not enabled:
            return
        from tests.fixtures.synthetic import passage_to_dict

        _pending.setdefault(nodeid, {})[question] = {
            "raw": raw, "source": source, "kind": kind,
            "passages": [passage_to_dict(p) for p in passages],
        }

    return save


def pytest_sessionfinish(session, exitstatus):
    if _records and session.config.getoption("--record-llm"):
        from tests.fixtures.synthetic import merge_recordings

        existing = RECORDING_PATH.read_text(encoding="utf-8") if RECORDING_PATH.exists() else None
        merged = merge_recordings(existing, _records)
        RECORDING_PATH.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
