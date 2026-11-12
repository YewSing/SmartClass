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

from app.schemas.assistant import LLMCards, LLMQuestions
from app.services.kb import llm
from app.services.kb.answer_format import clean_latex
from app.services.kb.assistant import SOURCE_COURSE, parse_answer
from app.services.kb.study_tools import _citation
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
    if case.get("kind"):
        _check_study_tools(question, case)
        return
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


def _check_study_tools(question, case):
    """Replay a flashcards / practice-questions recording: JSON parses, validates, cites real passages."""
    passages = [passage_from_dict(p) for p in case["passages"]]
    data = llm._json.loads(llm._extract_json(case["raw"]))
    if case["kind"] == "flashcards":
        items = LLMCards.model_validate(data).cards
    else:
        items = LLMQuestions.model_validate(data).questions
    assert items, f"{question!r}: recorded {case['kind']} output is empty"
    for item in items:
        assert _citation(item.citation, passages) is not None, \
            f"{question!r}: citation {item.citation!r} does not point at a retrieved passage"


@pytest.mark.llm_recording  # skipped by conftest.py while no recording exists
def test_recorded_answers_replay():
    cases = _cases()
    assert cases, "no recorded LLM fixtures (run: pytest -m live --record-llm)"
    for question, case in cases:
        _check(question, case)


def test_a_partial_recording_run_keeps_earlier_recordings():
    """`--record-llm` merges into qa.json: a run that records only some questions keeps the rest."""
    from tests.fixtures.synthetic import merge_recordings

    on_disk = json.dumps({"q1": {"raw": "old 1"}, "q2": {"raw": "old 2"}})
    merged = merge_recordings(on_disk, {"q2": {"raw": "new 2"}, "q3": {"raw": "new 3"}})
    assert merged == {"q1": {"raw": "old 1"}, "q2": {"raw": "new 2"}, "q3": {"raw": "new 3"}}
    assert merge_recordings(None, {"q": {"raw": "a"}}) == {"q": {"raw": "a"}}
    assert merge_recordings("not json", {"q": {"raw": "a"}}) == {"q": {"raw": "a"}}
