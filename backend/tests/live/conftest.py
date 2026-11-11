"""Shared setup for the live AI suite (tests/live/).

Live tests make real LLM calls, so they only run under `pytest -m live` (check.sh
triggers that when the KB or a prompt changed; see T82). Two safety nets:

- `LLMQuotaExhausted` becomes `pytest.skip("LLM_QUOTA")` (handled in the test helpers,
  since a generator fixture cannot catch an async test's exception under pytest-asyncio),
  so a used-up daily quota skips the suite instead of failing the round.
- `--record-llm` saves each first-question answer + retrieved passages to
  `tests/fixtures/llm/qa.json`, which the non-live replay tests read at zero cost.
"""
import json
from pathlib import Path

import pytest

LLM_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "llm"
LLM_FIXTURES.mkdir(parents=True, exist_ok=True)
RECORDING_PATH = LLM_FIXTURES / "qa.json"

_records: dict[str, dict] = {}


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
