"""S45: grading short answers with the real LLM (FR-616, NFR-49), on questions of the synthetic test course.

Run and record:  cd backend && python -m pytest -m live -q --record-llm tests/live/test_live_quiz_grading.py
"""
import pytest

from tests import quiz_grading_cases as cases

pytestmark = pytest.mark.live


async def test_right_answers_in_other_words_or_another_language(shino_llm):
    shino_llm.use("grade_right")
    cases.check_right(await cases.run(cases.RIGHT))


async def test_wrong_answers_and_a_repeated_question(shino_llm):
    shino_llm.use("grade_wrong")
    cases.check_wrong(await cases.run(cases.WRONG))


async def test_answers_are_graded_one_by_one(shino_llm):
    shino_llm.use("grade_mixed")
    cases.check_mixed(await cases.run(cases.MIXED))


async def test_instructions_inside_an_answer_are_not_followed(shino_llm):
    shino_llm.use("grade_injection")
    cases.check_injected(await cases.run(cases.INJECTED))
