"""Per-student engagement indicators (FR-701, FR-702, FR-703, S41).

Read-only aggregation across attendance_read, participation_read and quiz_read:
per student per course: attendance rate + absence frequency, participation frequency,
questions submitted, IDU signals, quiz scores + trend across quizzes.

No permission checks inside: callers (M7 lecturer endpoint) enforce NFR-04.
"""

from sqlalchemy import select

from app.models.class_ import ClassOccurrence, Enrollment
from app.services.attendance_read import course_rates
from app.services.participation_read import (
    get_student_participation_per_course,
    student_has_participated_in_course,
)
from app.services.quiz_read import quiz_results_per_student


async def student_engagement_indicators(
    db, course_id: int, student_id: int
) -> dict:
    """One student's engagement indicators for one course (FR-701/702/703 data).

    Returns: student_id, course_id, attendance (rate, absence_frequency),
    participation (frequency, questions, idu_signals), quizzes (scores, trend,
    average_score).
    """
    rates = await course_rates(db, course_id)
    student_rate = next((r for r in rates if r.student_id == student_id), None)
    attendance_rate = student_rate.rate if student_rate else None
    absence_frequency = None
    if student_rate is not None:
        counted = student_rate.counted_sessions or 0
        absence_frequency = counted - (student_rate.present or 0)

    participation = await get_student_participation_per_course(db, student_id, course_id)

    quiz_summary = await quiz_results_per_student(db, course_id, student_id)
    quiz_list = quiz_summary.get("quizzes", [])
    scores = [q["score"] for q in quiz_list if q["score"] is not None]
    trend = [{"quiz_id": q["quiz_id"], "title": q["title"], "score": q["score"]}
             for q in quiz_list if q["score"] is not None]

    return {
        "student_id": student_id,
        "course_id": course_id,
        "attendance": {
            "rate": attendance_rate,
            "absence_frequency": absence_frequency,
        },
        "participation": {
            "frequency": participation.get("questions", 0)
            + participation.get("votes", 0)
            + participation.get("responses", 0)
            + participation.get("reactions", 0)
            + participation.get("idu_signals", 0),
            "questions": participation.get("questions", 0),
            "votes": participation.get("votes", 0),
            "responses": participation.get("responses", 0),
            "reactions": participation.get("reactions", 0),
            "idu_signals": participation.get("idu_signals", 0),
        },
        "quizzes": {
            "scores": scores,
            "average_score": quiz_summary.get("average_score"),
            "trend": trend,
        },
        "has_data": student_has_participated_in_course(db, student_id, course_id)
        or len(quiz_list) > 0,
    }


async def student_self_view(db, student_id: int) -> dict:
    """The student's own attendance status + engagement indicators across enrolled courses.

    Returns only the requesting student's data (FR-706). Includes per-course indicators
    plus an overall attendance status summary.
    """
    occurrences = (
        await db.execute(
            select(ClassOccurrence.id, ClassOccurrence.course_id)
            .join(Enrollment, Enrollment.occurrence_id == ClassOccurrence.id)
            .where(Enrollment.student_id == student_id)
        )
    ).all()
    courses = {}
    for occurrence_id, course_id in occurrences:
        indicators = await student_engagement_indicators(db, course_id, student_id)
        courses[course_id] = indicators

    # Overall attendance status: average rate across courses that have a rate.
    rates = [
        c["attendance"]["rate"]
        for c in courses.values()
        if c["attendance"]["rate"] is not None
    ]
    overall_rate = round(sum(rates) / len(rates), 1) if rates else None

    return {
        "student_id": student_id,
        "overall_attendance_rate": overall_rate,
        "courses": [
            {
                "course_id": course_id,
                **indicators,
            }
            for course_id, indicators in sorted(courses.items())
        ],
    }
