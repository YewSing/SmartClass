"""Interfaces shared with other modules (see the FYP2 plan doc, "Shared interfaces").

Functions provided BY Module 8 to others live in search.py (search_materials) and here
(list_course_topics, get_confusion_topics). Functions Module 8 needs FROM Module 6
(quiz, owned by Shino) are stubs here until the quiz backend exists.
"""
from dataclasses import dataclass
from datetime import datetime


# ── Needed from Module 6 (Quiz) ── STUB until the quiz backend exists ─────────

@dataclass
class ActiveAttempt:
    attempt_id: int
    quiz_id: int
    question_texts: list[str]


async def get_active_attempt(student_id: int, course_id: int) -> ActiveAttempt | None:
    """The student's open graded quiz attempt in this course, if any.

    While one exists, the assistant refuses to answer for that course (quiz lock).
    TODO(M6): replace with a query on quiz_attempts once Shino's tables exist.
    """
    return None


# ── Provided to Module 6 / Module 7 ── sample data until implemented ─────────

@dataclass
class CourseTopic:
    name: str
    material_ids: list[int]


@dataclass
class ConfusionTopic:
    topic: str
    distinct_students: int
    covered_by_materials: bool


async def list_course_topics(course_id: int) -> list[CourseTopic]:
    """Topics extracted from the course materials (for M6's topic picker, M7 per-topic stats).
    TODO(M8): derive from material titles/headings. Returns fixed sample data for now."""
    return [CourseTopic("Black-box testing techniques", []), CourseTopic("White-box testing and coverage", [])]


async def get_confusion_topics(course_id: int, since: datetime, min_students: int = 3) -> list[ConfusionTopic]:
    """What students ask the assistant about, grouped into topics, anonymised.
    Only topics asked by at least `min_students` distinct students are returned.
    TODO(M8, Week 10): cluster ai_chat_messages.retrieval_query. Sample data for now."""
    return [ConfusionTopic("Boundary value analysis", 5, True), ConfusionTopic("Mutation testing", 3, False)]
