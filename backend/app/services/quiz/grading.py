"""The AI's grading of short answers (FR-616) — S45.

Given questions with their suggested answers and one student's answers, the LLM replies with a score,
a short reason and its confidence for each. Nothing is read or saved here (`quiz_grading` does that),
and nothing about the student is sent but the answers. One call never mixes students, so what one
writes can't touch another's score.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.core.config import settings
from app.services.kb import llm
from app.services.quiz import prompts
from app.services.quiz.checks import Grade, check_grades
from app.services.quiz.draft import ask


@dataclass(frozen=True)
class ShortAnswer:
    question: str
    suggested_answer: str
    answer: str


async def grade(answers: Sequence[ShortAnswer]) -> list[Grade]:
    """A grade for each answer, in order. `LLMUnavailable` when the provider fails,
    `LLMMalformedOutput` when its reply stays unusable after one corrected try."""
    messages = prompts.grade_messages([(a.question, a.suggested_answer, a.answer) for a in answers])
    try:
        return await ask(messages, lambda data: check_grades(data, len(answers)),
                         max_tokens=settings.QUIZ_GRADE_OUTPUT_TOKENS)
    except ValueError as exc:
        raise llm.LLMMalformedOutput(f"grades: {exc}") from None
