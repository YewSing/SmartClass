"""T82 replay: run the parsing/citation code against *real* Gemini answers, at zero API cost.

`pytest -m live --record-llm` saves each real answer (raw text + the passages it cited)
to `tests/fixtures/llm/qa.json`. These tests replay that file through `parse_answer` +
`clean_latex`, so the citation mapping, renumbering and LaTeX cleanup are exercised every
round against real provider output without calling the LLM. Hand-written mocks stay only
for the error cases Gemini rarely produces.
"""
import json
from pathlib import Path

import pytest

from app.services.kb.answer_format import clean_latex
from app.services.kb.assistant import SOURCE_COURSE, parse_answer
from tests.fixtures.synthetic import passage_from_dict

RECORDING = Path(__file__).resolve().parent / "fixtures" / "llm" / "qa.json"


def _cases():
    if not RECORDING.exists():
        return []
    try:
        return list(json.loads(RECORDING.read_text(encoding="utf-8")).items())
    except (OSError, json.JSONDecodeError):
        return []


def _check(question, case):
    raw = case["raw"]
    passages = [passage_from_dict(p) for p in case["passages"]]
    content, citations, source = parse_answer(clean_latex(raw), passages)

    assert case["source"] == source, f"{question!r}: expected {case['source']}, got {source}"
    if case["source"] == SOURCE_COURSE:
        assert citations, f"{question!r}: a course answer must keep at least one citation"
        assert all(1 <= c["n"] <= len(passages) for c in citations), f"{question!r}: citation out of range"
    else:
        assert citations == [], f"{question!r}: a general answer must not carry citations"
    # the stored answer is plain text the phone can render (T93)
    assert "$$" not in content and "\\frac" not in content, f"{question!r}: LaTeX leaked through"


def test_recorded_answers_replay():
    cases = _cases()
    if not cases:
        pytest.skip("no recorded LLM fixtures yet (run: pytest -m live --record-llm)")
    for question, case in cases:
        _check(question, case)
