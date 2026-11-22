"""After class: session summary, CSV export and a student's own questions (FR-518–FR-520) — S36.

- `build` gives the teaching lecturer the summary of one class session's interaction: question
  counts and the questions (the lecturer's view, so anonymous ones have no author), the polls that
  ran (drafts left out) with their results, the quick questions with their answers (no names),
  reaction counts and the confusion timeline/topics/spikes. It reuses the role-shaped loaders of
  S31–S33, so nothing here can show more than the lecturer's live screens. It works while the class
  runs too (a running total), not only after it.
- `to_csv` turns the summary into one flat table. Anonymous questions are written as "Anonymous"
  (FR-519), quick answers and confusion have no author column value at all, and every text cell that
  a spreadsheet would read as a formula (starting with = + - @, tab or CR) gets a leading `'`.
- `my_questions` lists a student's own questions across every class session, newest first, with the
  lecturer's answered status (FR-520). Hidden questions stay hidden from their asker (as in S31).

Read only: no writes, no events, nothing graded (FR-513).
"""
from __future__ import annotations

import csv
import io
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.class_ import ClassOccurrence, Course
from app.models.interaction import Question, QuestionVote
from app.models.session import AttendanceSession
from app.schemas.interaction import (
    InteractionSummaryOut,
    MyQuestionListOut,
    MyQuestionOut,
    SummaryConfusion,
    SummaryQuestionCounts,
    SummaryQuickQuestion,
)
from app.services.interaction import polls, questions, quick, sessions, signals
from app.services.interaction.sessions import Member

MY_QUESTIONS_DEFAULT_LIMIT = 50
MY_QUESTIONS_MAX_LIMIT = 200
ANONYMOUS_LABEL = "Anonymous"
CSV_HEADER = ["Section", "Time", "Text", "Author", "Status", "Count"]
_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def class_date(session: AttendanceSession) -> date | None:
    """The MYT date of the class: class_date, else the opened/starts date."""
    if session.class_date:
        return session.class_date
    when = session.opened_at or session.starts_at
    return when.date() if when else None


# ── summary (FR-518) ─────────────────────────────────────────────────────────

async def build(db: AsyncSession, member: Member, session: AttendanceSession) -> InteractionSummaryOut:
    sessions.require_lecturer(member)
    st = await sessions.state(db, session)
    qs = await questions.list_questions(db, member, session.id)
    ps = [p for p in await polls.list_polls(db, member, session.id, interaction_open=st.is_open)
          if p.status != "draft"]
    quicks = await quick.list_quick(db, member, session.id, interaction_open=st.is_open)
    reactions = await signals.reaction_counts(db, member, session.id, st.status)
    confusion = await signals.confusion_view(db, member, session, st.status)
    d = class_date(session)
    return InteractionSummaryOut(
        attendance_session_id=session.id, course_code=st.course_code, course_name=st.course_name,
        class_date=d.isoformat() if d else None, class_status=st.class_status, status=st.status,
        question_counts=SummaryQuestionCounts(
            asked=len(qs), answered=sum(q.answered for q in qs),
            anonymous=sum(q.anonymous for q in qs), hidden=sum(q.hidden for q in qs),
            upvotes=sum(q.upvotes for q in qs)),
        questions=qs, polls=ps,
        quick_questions=[SummaryQuickQuestion(
            id=q.id, prompt=q.prompt, status=q.status, answer_count=q.answer_count or 0,
            answers=q.answers or [], created_at=q.created_at) for q in quicks],
        reactions=reactions.counts, reactions_total=reactions.total,
        confusion=SummaryConfusion(total=confusion.total, spikes=confusion.spikes,
                                   timeline=confusion.timeline, topics=confusion.topics))


# ── CSV (FR-519) ─────────────────────────────────────────────────────────────

def safe_cell(value):
    """Neutralise spreadsheet formulas: text starting with = + - @ (or tab/CR) gets a leading '."""
    if isinstance(value, str) and value.startswith(_FORMULA_START):
        return "'" + value
    return value


def _time(t: datetime | None) -> str:
    return t.isoformat(timespec="seconds") if t else ""


def _question_status(q) -> str:
    parts = ["answered" if q.answered else "unanswered"]
    if q.pinned:
        parts.append("pinned")
    if q.hidden:
        parts.append("hidden")
    return ", ".join(parts)


def csv_rows(s: InteractionSummaryOut) -> list[list]:
    rows: list[list] = [
        ["Class", "", f"{s.course_code or ''} {s.course_name or ''}".strip(), "", s.class_status,
         s.class_date or ""],
        ["Questions asked", "", "", "", "", s.question_counts.asked],
        ["Questions answered", "", "", "", "", s.question_counts.answered],
        ["Anonymous questions", "", "", "", "", s.question_counts.anonymous],
    ]
    for q in sorted(s.questions, key=lambda q: (q.created_at, q.id)):
        author = ANONYMOUS_LABEL if q.anonymous else (q.author_name or "")
        rows.append(["Question", _time(q.created_at), q.text, author, _question_status(q), q.upvotes])
    for p in sorted(s.polls, key=lambda p: (p.started_at or p.created_at, p.id)):
        kind = "multiple choice" if p.multiple else "single choice"
        rows.append(["Poll", _time(p.started_at), p.question, "", f"{p.status}, {kind}", p.total_voters or 0])
        for o in p.options:
            rows.append(["Poll option", "", o.text, "", "", o.votes or 0])
    for q in sorted(s.quick_questions, key=lambda q: (q.created_at, q.id)):
        rows.append(["Quick question", _time(q.created_at), q.prompt, "", q.status, q.answer_count])
        for a in q.answers:
            rows.append(["Quick answer", _time(a.created_at), a.text, "", "", ""])
    for kind, n in s.reactions.items():
        rows.append(["Reaction", "", kind, "", "", n])
    rows.append(["Confusion presses", "", "", "", "", s.confusion.total])
    rows.append(["Confusion spikes", "", "", "", "", s.confusion.spikes])
    for b in s.confusion.timeline:
        rows.append(["Confusion", _time(b.start), "", "", "", b.count])
    for t in s.confusion.topics:
        rows.append(["Confusion topic", "", t.topic, "", "", t.count])
    return rows


def to_csv(s: InteractionSummaryOut) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(CSV_HEADER)
    for row in csv_rows(s):
        writer.writerow([safe_cell(v) for v in row])
    return out.getvalue()


def csv_filename(s: InteractionSummaryOut) -> str:
    code = "".join(ch for ch in (s.course_code or "class") if ch.isalnum() or ch in "-_") or "class"
    day = (s.class_date or "").replace("-", "")
    return f"interaction_{code}_{day or s.attendance_session_id}_{s.attendance_session_id}.csv"


# ── a student's own questions (FR-520) ───────────────────────────────────────

async def my_questions(db: AsyncSession, student_id: int, *, attendance_session_id: int | None = None,
                       limit: int = MY_QUESTIONS_DEFAULT_LIMIT, before: int | None = None) -> MyQuestionListOut:
    limit = max(1, min(limit, MY_QUESTIONS_MAX_LIMIT))
    votes = (select(QuestionVote.question_id, func.count().label("n"))
             .group_by(QuestionVote.question_id).subquery())
    stmt = (select(Question, func.coalesce(votes.c.n, 0), AttendanceSession, Course.code, Course.name)
            .join(AttendanceSession, AttendanceSession.id == Question.attendance_session_id)
            .outerjoin(ClassOccurrence, ClassOccurrence.id == AttendanceSession.occurrence_id)
            .outerjoin(Course, Course.id == ClassOccurrence.course_id)
            .outerjoin(votes, votes.c.question_id == Question.id)
            .where(Question.student_id == student_id, Question.hidden.is_(False)))
    if attendance_session_id is not None:
        stmt = stmt.where(Question.attendance_session_id == attendance_session_id)
    if before is not None:
        stmt = stmt.where(Question.id < before)
    rows = (await db.execute(stmt.order_by(Question.id.desc()).limit(limit + 1))).all()
    more = len(rows) > limit
    rows = rows[:limit]
    out = []
    for q, n, sess, code, name in rows:
        d = class_date(sess)
        out.append(MyQuestionOut(
            id=q.id, attendance_session_id=q.attendance_session_id, occurrence_id=sess.occurrence_id,
            course_code=code, course_name=name, class_date=d.isoformat() if d else None,
            text=q.text, anonymous=q.anonymous, upvotes=int(n), answered=q.answered_at is not None,
            answered_at=q.answered_at, created_at=q.created_at))
    return MyQuestionListOut(questions=out, next_before=out[-1].id if more and out else None)
