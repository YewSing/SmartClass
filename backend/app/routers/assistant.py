"""AI Learning Assistant (Module 8): student chat API and lecturer knowledge-base status."""
from dataclasses import asdict
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_role
from app.models.ai_chat import ChatMessage, ChatSession
from app.models.class_ import ClassOccurrence, Course, Enrollment
from app.models.knowledge import MAT_INDEXED, KbMaterial
from app.models.user import Lecturer, Student, User
from app.schemas.assistant import (
    AssistantCourseOut, MaterialOut, MessageCreate, MessageOut, SessionCreate, SessionOut,
    SessionRename, StudyToolsCreate, StudyToolsOut, SummaryCreate, SummaryOut, SyncOut,
    TrendsOut,
)
from app.services.kb import trends
from app.services.kb.assistant import answer_question
from app.services.kb.llm import LLMMalformedOutput, LLMUnavailable
from app.services.kb.moodle_client import MoodleClient, MoodleError
from app.services.kb.study_tools import generate_study_tools
from app.services.kb.summarize import summarize
from app.services.kb.sync import sync_course

router = APIRouter(tags=["assistant"])

_student_only = require_role("student")
_lecturer_only = require_role("lecturer")
_lecturer_or_admin = require_role("lecturer", "admin")


# ── helpers ───────────────────────────────────────────────────────────────────

async def _student(db: AsyncSession, user: User) -> Student:
    student = (await db.execute(select(Student).where(Student.user_id == user.id))).scalar_one_or_none()
    if not student:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Student profile not found")
    return student


def _enrolled_courses_query(student_id: int):
    return (
        select(Course).distinct()
        .join(ClassOccurrence, ClassOccurrence.course_id == Course.id)
        .join(Enrollment, Enrollment.occurrence_id == ClassOccurrence.id)
        .where(Enrollment.student_id == student_id)
    )


async def _enrolled_course(db: AsyncSession, student_id: int, course_id: int) -> Course:
    """Only courses the student is enrolled in are searchable (mirrors SPeCTRUM access)."""
    course = (await db.execute(_enrolled_courses_query(student_id).where(Course.id == course_id))).scalar_one_or_none()
    if not course:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You are not enrolled in this course")
    return course


async def _own_session(db: AsyncSession, student_id: int, session_id: int) -> ChatSession:
    session = (await db.execute(select(ChatSession).where(
        ChatSession.id == session_id, ChatSession.student_id == student_id
    ))).scalar_one_or_none()
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chat not found")
    return session


# ── student: chats ────────────────────────────────────────────────────────────

@router.get("/student/assistant/courses", response_model=list[AssistantCourseOut])
async def list_assistant_courses(db: AsyncSession = Depends(get_db), user: User = Depends(_student_only)):
    student = await _student(db, user)
    courses = (await db.execute(_enrolled_courses_query(student.id).order_by(Course.code))).scalars().all()
    counts = dict((await db.execute(
        select(KbMaterial.course_id, func.count()).where(
            KbMaterial.course_id.in_([c.id for c in courses]), KbMaterial.status == MAT_INDEXED
        ).group_by(KbMaterial.course_id)
    )).all()) if courses else {}
    return [AssistantCourseOut(course_id=c.id, code=c.code, name=c.name, indexed_materials=counts.get(c.id, 0))
            for c in courses]


@router.get("/student/assistant/sessions", response_model=list[SessionOut])
async def list_sessions(course_id: int | None = None, db: AsyncSession = Depends(get_db),
                        user: User = Depends(_student_only)):
    student = await _student(db, user)
    q = select(ChatSession).where(ChatSession.student_id == student.id)
    if course_id is not None:
        q = q.where(ChatSession.course_id == course_id)
    return (await db.execute(q.order_by(ChatSession.updated_at.desc()))).scalars().all()


@router.post("/student/assistant/sessions", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
async def create_session(body: SessionCreate, db: AsyncSession = Depends(get_db), user: User = Depends(_student_only)):
    student = await _student(db, user)
    await _enrolled_course(db, student.id, body.course_id)
    session = ChatSession(student_id=student.id, course_id=body.course_id, title=body.title)
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return session


@router.patch("/student/assistant/sessions/{session_id}", response_model=SessionOut)
async def rename_session(session_id: int, body: SessionRename, db: AsyncSession = Depends(get_db),
                         user: User = Depends(_student_only)):
    student = await _student(db, user)
    session = await _own_session(db, student.id, session_id)
    session.title = body.title
    await db.flush()
    await db.refresh(session)
    return session


@router.delete("/student/assistant/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(_student_only)):
    student = await _student(db, user)
    await db.delete(await _own_session(db, student.id, session_id))


@router.get("/student/assistant/sessions/{session_id}/messages", response_model=list[MessageOut])
async def list_messages(session_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(_student_only)):
    student = await _student(db, user)
    session = await _own_session(db, student.id, session_id)
    rows = (await db.execute(select(ChatMessage).where(ChatMessage.session_id == session.id)
                             .order_by(ChatMessage.id))).scalars().all()
    return [MessageOut(id=m.id, role=m.role, content=m.content, citations=m.citations or [],
                       source_type=m.source_type, created_at=m.created_at) for m in rows]


@router.post("/student/assistant/sessions/{session_id}/messages", response_model=MessageOut)
async def send_message(session_id: int, body: MessageCreate, db: AsyncSession = Depends(get_db),
                       user: User = Depends(_student_only)):
    student = await _student(db, user)
    session = await _own_session(db, student.id, session_id)
    course = await _enrolled_course(db, student.id, session.course_id)  # enrolment may have changed
    try:
        reply = await answer_question(db, session, course, body.content.strip())
    except LLMUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))
    await db.refresh(reply)
    return MessageOut(id=reply.id, role=reply.role, content=reply.content, citations=reply.citations or [],
                      source_type=reply.source_type, created_at=reply.created_at)


# ── lecturer: ask my materials (FR-815) ───────────────────────────────────────

async def _lecturer(db: AsyncSession, user: User) -> Lecturer:
    lecturer = (await db.execute(select(Lecturer).where(Lecturer.user_id == user.id))).scalar_one_or_none()
    if not lecturer:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lecturer profile not found")
    return lecturer


def _taught_courses_query(lecturer_id: int):
    return (
        select(Course).distinct()
        .join(ClassOccurrence, ClassOccurrence.course_id == Course.id)
        .where(ClassOccurrence.lecturer_id == lecturer_id)
    )


async def _taught_course(db: AsyncSession, lecturer_id: int, course_id: int) -> Course:
    course = (await db.execute(_taught_courses_query(lecturer_id).where(Course.id == course_id))).scalar_one_or_none()
    if not course:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not teach this course")
    return course


async def _own_lecturer_session(db: AsyncSession, lecturer_id: int, session_id: int) -> ChatSession:
    session = (await db.execute(select(ChatSession).where(
        ChatSession.id == session_id, ChatSession.lecturer_id == lecturer_id
    ))).scalar_one_or_none()
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chat not found")
    return session


@router.get("/lecturer/assistant/courses", response_model=list[AssistantCourseOut])
async def list_lecturer_courses(db: AsyncSession = Depends(get_db), user: User = Depends(_lecturer_only)):
    lecturer = await _lecturer(db, user)
    courses = (await db.execute(_taught_courses_query(lecturer.id).order_by(Course.code))).scalars().all()
    counts = dict((await db.execute(
        select(KbMaterial.course_id, func.count()).where(
            KbMaterial.course_id.in_([c.id for c in courses]), KbMaterial.status == MAT_INDEXED
        ).group_by(KbMaterial.course_id)
    )).all()) if courses else {}
    return [AssistantCourseOut(course_id=c.id, code=c.code, name=c.name, indexed_materials=counts.get(c.id, 0))
            for c in courses]


@router.get("/lecturer/assistant/sessions", response_model=list[SessionOut])
async def list_lecturer_sessions(course_id: int | None = None, db: AsyncSession = Depends(get_db),
                                 user: User = Depends(_lecturer_only)):
    lecturer = await _lecturer(db, user)
    q = select(ChatSession).where(ChatSession.lecturer_id == lecturer.id)
    if course_id is not None:
        q = q.where(ChatSession.course_id == course_id)
    return (await db.execute(q.order_by(ChatSession.updated_at.desc()))).scalars().all()


@router.post("/lecturer/assistant/sessions", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
async def create_lecturer_session(body: SessionCreate, db: AsyncSession = Depends(get_db),
                                  user: User = Depends(_lecturer_only)):
    lecturer = await _lecturer(db, user)
    await _taught_course(db, lecturer.id, body.course_id)
    session = ChatSession(lecturer_id=lecturer.id, course_id=body.course_id, title=body.title)
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return session


@router.patch("/lecturer/assistant/sessions/{session_id}", response_model=SessionOut)
async def rename_lecturer_session(session_id: int, body: SessionRename, db: AsyncSession = Depends(get_db),
                                  user: User = Depends(_lecturer_only)):
    lecturer = await _lecturer(db, user)
    session = await _own_lecturer_session(db, lecturer.id, session_id)
    session.title = body.title
    await db.flush()
    await db.refresh(session)
    return session


@router.delete("/lecturer/assistant/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lecturer_session(session_id: int, db: AsyncSession = Depends(get_db),
                                  user: User = Depends(_lecturer_only)):
    lecturer = await _lecturer(db, user)
    await db.delete(await _own_lecturer_session(db, lecturer.id, session_id))


@router.get("/lecturer/assistant/sessions/{session_id}/messages", response_model=list[MessageOut])
async def list_lecturer_messages(session_id: int, db: AsyncSession = Depends(get_db),
                                 user: User = Depends(_lecturer_only)):
    lecturer = await _lecturer(db, user)
    session = await _own_lecturer_session(db, lecturer.id, session_id)
    rows = (await db.execute(select(ChatMessage).where(ChatMessage.session_id == session.id)
                             .order_by(ChatMessage.id))).scalars().all()
    return [MessageOut(id=m.id, role=m.role, content=m.content, citations=m.citations or [],
                       source_type=m.source_type, created_at=m.created_at) for m in rows]


@router.post("/lecturer/assistant/sessions/{session_id}/messages", response_model=MessageOut)
async def send_lecturer_message(session_id: int, body: MessageCreate, db: AsyncSession = Depends(get_db),
                                user: User = Depends(_lecturer_only)):
    lecturer = await _lecturer(db, user)
    session = await _own_lecturer_session(db, lecturer.id, session_id)
    course = await _taught_course(db, lecturer.id, session.course_id)  # teaching may have changed
    try:
        reply = await answer_question(db, session, course, body.content.strip())
    except LLMUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))
    await db.refresh(reply)
    return MessageOut(id=reply.id, role=reply.role, content=reply.content, citations=reply.citations or [],
                      source_type=reply.source_type, created_at=reply.created_at)


# ── student: open a cited source (FR-809) ─────────────────────────────────────

@router.get("/student/assistant/materials/{material_id}/file")
async def open_material_file(material_id: int, db: AsyncSession = Depends(get_db),
                             user: User = Depends(_student_only)):
    """Stream a course file from Moodle, so the app can show it at the cited page or slide."""
    student = await _student(db, user)
    material = (await db.execute(select(KbMaterial).where(KbMaterial.id == material_id))).scalar_one_or_none()
    if not material:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Material not found")
    await _enrolled_course(db, student.id, material.course_id)
    if material.source != "moodle" or not material.file_url:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This material has no file to open")

    # Not `async with`: the client must stay open until the response body has been sent
    client = None
    try:
        client = MoodleClient()
        stream = await client.open_file(material.file_url)
    except MoodleError as exc:
        if client:
            await client.__aexit__(None, None, None)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Could not fetch the file from Moodle: {exc}")

    async def body():
        try:
            async for chunk in stream.aiter_bytes():
                yield chunk
        finally:
            await stream.aclose()
            await client.__aexit__(None, None, None)

    media_type = material.mimetype or stream.content_type or "application/octet-stream"
    return StreamingResponse(body(), media_type=media_type, headers={
        "Content-Disposition": f"inline; filename*=UTF-8''{quote(material.file_name)}",
        "Cache-Control": "private, max-age=300",
    })


@router.post("/student/assistant/summaries", response_model=SummaryOut)
async def generate_summary(body: SummaryCreate, db: AsyncSession = Depends(get_db),
                           user: User = Depends(_student_only)):
    """Generate a summary or study guide for a material or topic (FR-810)."""
    student = await _student(db, user)
    course = await _enrolled_course(db, student.id, body.course_id)
    if (body.material_id is None) == (body.topic is None):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Provide exactly one of material_id or topic")
    if body.material_id is not None:
        material = (await db.execute(select(KbMaterial).where(KbMaterial.id == body.material_id))).scalar_one_or_none()
        if not material or material.course_id != course.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Material not found")
    try:
        content, citations, source = await summarize(
            db, course, material_id=body.material_id, topic=body.topic, kind=body.kind)
    except LLMUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))
    return SummaryOut(content=content, citations=citations, source_type=source,
                      kind=body.kind, material_id=body.material_id, topic=body.topic)


@router.post("/student/assistant/study-tools", response_model=StudyToolsOut)
async def study_tools(body: StudyToolsCreate, db: AsyncSession = Depends(get_db),
                      user: User = Depends(_student_only)):
    """Generate flashcards or practice questions for a material or topic (FR-811)."""
    student = await _student(db, user)
    course = await _enrolled_course(db, student.id, body.course_id)
    if (body.material_id is None) == (body.topic is None):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Provide exactly one of material_id or topic")
    if body.material_id is not None:
        material = (await db.execute(select(KbMaterial).where(KbMaterial.id == body.material_id))).scalar_one_or_none()
        if not material or material.course_id != course.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Material not found")
    try:
        cards, questions, source = await generate_study_tools(
            db, course, material_id=body.material_id, topic=body.topic, kind=body.kind)
    except LLMMalformedOutput as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))
    except LLMUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))
    return StudyToolsOut(kind=body.kind, source_type=source, cards=cards, questions=questions)


# ── lecturer / admin: knowledge base status and sync ──────────────────────────

async def _course_for_staff(db: AsyncSession, user: User, course_id: int) -> Course:
    course = (await db.execute(select(Course).where(Course.id == course_id))).scalar_one_or_none()
    if not course:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")
    if user.role == "lecturer":
        teaches = (await db.execute(
            select(ClassOccurrence.id).join(Lecturer, Lecturer.id == ClassOccurrence.lecturer_id)
            .where(Lecturer.user_id == user.id, ClassOccurrence.course_id == course_id).limit(1)
        )).first()
        if not teaches:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not teach this course")
    return course


@router.get("/kb/courses/{course_id}/materials", response_model=list[MaterialOut])
async def list_materials(course_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(_lecturer_or_admin)):
    await _course_for_staff(db, user, course_id)
    return (await db.execute(select(KbMaterial).where(KbMaterial.course_id == course_id)
                             .order_by(KbMaterial.section_name, KbMaterial.title))).scalars().all()


@router.post("/kb/courses/{course_id}/sync", response_model=SyncOut)
async def sync_now(course_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(_lecturer_or_admin)):
    """The "Sync now" button: pull changes from Moodle immediately instead of waiting for the timer."""
    course = await _course_for_staff(db, user, course_id)
    try:
        async with MoodleClient() as client:
            report = await sync_course(db, course, client)
    except MoodleError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Moodle sync failed: {exc}")
    return SyncOut(**asdict(report))


@router.get("/lecturer/assistant/trends/{course_id}", response_model=TrendsOut)
async def question_trends(course_id: int, db: AsyncSession = Depends(get_db),
                          user: User = Depends(_lecturer_or_admin)):
    """Anonymised question trends for the course's lecturer (FR-813, NFR-09)."""
    course = await _course_for_staff(db, user, course_id)
    return await trends.question_trends(db, course.id)
