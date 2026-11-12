"""Anonymised question trends for lecturers (FR-813, NFR-09).

Aggregates the assistant answers of a course into three lists, each showing only topics
asked by at least `MIN_STUDENTS` distinct students, with no student names and no question
text:
  - most-asked topics (course answers, grouped by the cited material title)
  - most-cited materials (course answers, grouped by the cited material id)
  - most-asked topics the materials don't cover (general-knowledge answers, grouped by
    the short LLM label stored at answer time)
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

MIN_STUDENTS = 3

_MOST_ASKED_SQL = text("""
    SELECT m.topic AS topic, COUNT(DISTINCT s.student_id) AS students
    FROM ai_chat_messages m
    JOIN ai_chat_sessions s ON s.id = m.session_id
    WHERE s.course_id = :course_id AND m.role = 'assistant' AND m.source_type = 'course'
      AND m.topic IS NOT NULL AND s.student_id IS NOT NULL
    GROUP BY m.topic
    HAVING COUNT(DISTINCT s.student_id) >= :min_students
    ORDER BY students DESC, topic
""")

_MOST_CITED_SQL = text("""
    SELECT (c.value->>'material_id')::int AS material_id,
           c.value->>'title' AS title,
           COUNT(DISTINCT s.student_id) AS students
    FROM ai_chat_messages m
    JOIN ai_chat_sessions s ON s.id = m.session_id
    CROSS JOIN LATERAL jsonb_array_elements(m.citations) AS c(value)
    WHERE s.course_id = :course_id AND m.role = 'assistant' AND m.source_type = 'course'
      AND s.student_id IS NOT NULL
    GROUP BY (c.value->>'material_id')::int, c.value->>'title'
    HAVING COUNT(DISTINCT s.student_id) >= :min_students
    ORDER BY students DESC, title
""")

_UNCOVERED_SQL = text("""
    SELECT m.topic AS topic, COUNT(DISTINCT s.student_id) AS students
    FROM ai_chat_messages m
    JOIN ai_chat_sessions s ON s.id = m.session_id
    WHERE s.course_id = :course_id AND m.role = 'assistant' AND m.source_type = 'general'
      AND m.topic IS NOT NULL AND s.student_id IS NOT NULL
    GROUP BY m.topic
    HAVING COUNT(DISTINCT s.student_id) >= :min_students
    ORDER BY students DESC, topic
""")


async def question_trends(db: AsyncSession, course_id: int, min_students: int = MIN_STUDENTS) -> dict:
    """Three anonymised lists for a course's lecturer."""
    params = {"course_id": course_id, "min_students": min_students}

    most_asked = (await db.execute(_MOST_ASKED_SQL, params)).all()
    most_cited = (await db.execute(_MOST_CITED_SQL, params)).all()
    uncovered = (await db.execute(_UNCOVERED_SQL, params)).all()

    return {
        "most_asked_topics": [{"topic": r.topic, "students": r.students} for r in most_asked],
        "most_cited_materials": [
            {"material_id": r.material_id, "title": r.title, "students": r.students}
            for r in most_cited
        ],
        "topics_materials_dont_cover": [
            {"topic": r.topic, "students": r.students} for r in uncovered
        ],
    }
