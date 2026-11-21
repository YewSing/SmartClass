"""Module 6 authoring, delivery and results. Server state, not clients, owns attempts."""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db, after_commit
from app.core.deps import get_current_user
from app.core.timezone import now_myt
from app.models.class_ import ClassOccurrence, Enrollment
from app.models.quiz import Quiz, QuizAttempt
from app.models.user import Lecturer, Student, User
from app.services import notify
from app.services.kb import retrieval_api

router = APIRouter(prefix="/quizzes", tags=["quizzes"])

async def _student(db, actor):
    return await db.scalar(select(Student).where(Student.user_id == actor.id))
async def _lecturer(db, actor):
    return await db.scalar(select(Lecturer).where(Lecturer.user_id == actor.id))
async def _can_course(db, student_id, course_id):
    return await db.scalar(select(Enrollment.id).join(ClassOccurrence).where(Enrollment.student_id == student_id, ClassOccurrence.course_id == course_id))
async def _owned(db, actor, quiz):
    lec = await _lecturer(db, actor)
    if not lec or quiz.lecturer_id != lec.id: raise HTTPException(403, "Quiz is not yours")
    return lec


async def _require_teaches_course(db, actor, course_id):
    lec = await _lecturer(db, actor)
    teaches = await db.scalar(select(ClassOccurrence.id).where(
        ClassOccurrence.course_id == course_id, ClassOccurrence.lecturer_id == getattr(lec, "id", None)
    ))
    if not teaches:
        raise HTTPException(403, "You do not teach this course")
    return lec
def _out(q, attempt=None, include_answers=False):
    out = {"id": q.id, "course_id": q.course_id, "title": q.title, "type": q.quiz_type, "status": q.status,
           "timer_mode": q.timer_mode, "timer_seconds": q.timer_seconds, "opens_at": q.opens_at, "closes_at": q.closes_at,
           "current_question": q.current_question, "question_count": len(q.questions), "release_marks": q.release_marks,
           "release_answers": q.release_answers}
    if include_answers: out["questions"] = q.questions
    else: out["questions"] = [{k:v for k,v in x.items() if k not in ("answer", "suggested_answer")} for x in q.questions]
    if attempt: out["attempt"] = {"id": attempt.id, "status": attempt.status, "answers": attempt.answers, "score": attempt.score, "deadline_at": attempt.deadline_at}
    return out


def _student_out(q, attempt=None, *, include_result=False):
    """Never leak an unreleased graded result or future live-game questions."""
    out = _out(q, attempt, include_answers=False)
    if q.quiz_type == "game" and q.status == "open":
        index = q.current_question
        out["questions"] = [out["questions"][index]] if index is not None and index < len(q.questions) else []
        out["current_question"] = 0
    elif q.quiz_type == "game" and q.status == "published":
        out["questions"] = []
    if attempt and (q.quiz_type == "graded" and not q.release_marks and not include_result):
        out["attempt"] = {**out["attempt"], "score": None}
    if q.quiz_type == "graded" and not q.release_answers:
        out["questions"] = [{k: v for k, v in item.items() if k != "explanation"} for item in out["questions"]]
    return out
async def _get(db, quiz_id):
    q = await db.get(Quiz, quiz_id)
    if not q: raise HTTPException(404, "Quiz not found")
    return q


def _expire_if_due(q, attempt):
    if attempt and attempt.status == "in_progress" and attempt.deadline_at and now_myt() >= attempt.deadline_at:
        _grade(q, attempt)

@router.get("")
async def list_quizzes(db: AsyncSession = Depends(get_db), actor: User = Depends(get_current_user)):
    if actor.role == "lecturer":
        lec = await _lecturer(db, actor); rows = (await db.scalars(select(Quiz).where(Quiz.lecturer_id == lec.id).order_by(Quiz.created_at.desc()))).all() if lec else []
        return [_out(q, include_answers=True) for q in rows]
    stu = await _student(db, actor)
    rows = (await db.scalars(select(Quiz).where(Quiz.status.in_(("published", "open", "closed"))).order_by(Quiz.created_at.desc()))).all()
    result=[]
    for q in rows:
        if stu and await _can_course(db, stu.id, q.course_id):
            attempt = await db.scalar(select(QuizAttempt).where(QuizAttempt.quiz_id==q.id, QuizAttempt.student_id==stu.id))
            _expire_if_due(q, attempt)
            result.append(_student_out(q, attempt))
    return result

@router.post("", status_code=201)
async def create_quiz(body: dict, db: AsyncSession = Depends(get_db), actor: User = Depends(get_current_user)):
    if actor.role != "lecturer": raise HTTPException(403, "Lecturer only")
    course_id=int(body.get("course_id", 0)); lec = await _require_teaches_course(db, actor, course_id)
    typ=body.get("type", "graded")
    if typ not in ("graded","game"): raise HTTPException(422, "Invalid quiz type")
    q=Quiz(course_id=course_id, lecturer_id=lec.id, title=str(body.get("title", "Untitled quiz"))[:255], quiz_type=typ,
           timer_mode="per_question" if typ=="game" else body.get("timer_mode", "whole"), timer_seconds=body.get("timer_seconds"),
           shuffle=bool(body.get("shuffle",False)), questions=body.get("questions", []))
    db.add(q); await db.flush(); return _out(q, include_answers=True)

@router.post("/draft")
async def draft_quiz(body: dict, db: AsyncSession = Depends(get_db), actor: User = Depends(get_current_user)):
    # Retrieval is deliberately the sole Module-8 dependency for generation.
    course_id = int(body["course_id"])
    if actor.role != "lecturer":
        raise HTTPException(403, "Lecturer only")
    await _require_teaches_course(db, actor, course_id)
    passages = await retrieval_api.search(course_id, str(body.get("prompt", "")), k=4)
    source = passages[0] if passages else None
    question={"id":"q1", "type":"mcq", "text": str(body.get("prompt", "Draft question")), "options":["Option A","Option B"], "answer":0,
              "topic": source.heading if source else "General", "source": (f"{source.title}, {source.location_label}" if source else None), "origin":"from_material" if source else "extended", "explanation":"Review this generated draft before publishing."}
    copy=dict(body); copy["questions"]=[question]; return await create_quiz(copy, db, actor)

@router.patch("/{quiz_id}")
async def edit_quiz(quiz_id:int, body:dict, db:AsyncSession=Depends(get_db), actor:User=Depends(get_current_user)):
    q=await _get(db,quiz_id); await _owned(db,actor,q)
    if await db.scalar(select(QuizAttempt.id).where(QuizAttempt.quiz_id==q.id)): raise HTTPException(409,"Questions cannot change after attempts")
    for name in ("title","timer_mode","timer_seconds","shuffle","release_marks","release_answers","speed_bonus","questions"):
        if name in body: setattr(q,name,body[name])
    return _out(q,include_answers=True)

@router.post("/{quiz_id}/publish")
async def publish(quiz_id:int, db:AsyncSession=Depends(get_db), actor:User=Depends(get_current_user)):
    q=await _get(db,quiz_id); await _owned(db,actor,q)
    if not q.questions: raise HTTPException(422,"Add an approved question first")
    q.status="published"
    recipients=(await db.scalars(select(Student.user_id).join(Enrollment).join(ClassOccurrence).where(ClassOccurrence.course_id==q.course_id))).all()
    after_commit(db, lambda: notify.emit("quiz.published", recipients, {"quiz_id":q.id,"message":q.title,"link":f"/quizzes/{q.id}"}))
    return _out(q,include_answers=True)

@router.post("/{quiz_id}/start")
async def start(quiz_id:int, db:AsyncSession=Depends(get_db), actor:User=Depends(get_current_user)):
    q=await _get(db,quiz_id); await _owned(db,actor,q)
    if q.quiz_type!="game": raise HTTPException(409,"Only game quizzes start live")
    q.status="open"; q.current_question=0; return _out(q,include_answers=True)
@router.post("/{quiz_id}/next")
async def next_question(quiz_id:int, db:AsyncSession=Depends(get_db), actor:User=Depends(get_current_user)):
    q=await _get(db,quiz_id); await _owned(db,actor,q)
    if q.status!="open": raise HTTPException(409,"Game is not open")
    q.current_question=(q.current_question or 0)+1
    if q.current_question>=len(q.questions):
        q.status="closed"
        for attempt in (await db.scalars(select(QuizAttempt).where(QuizAttempt.quiz_id == q.id, QuizAttempt.status == "in_progress"))).all():
            _grade(q, attempt)
    return _out(q,include_answers=True)
@router.post("/{quiz_id}/close")
async def close(quiz_id:int, db:AsyncSession=Depends(get_db), actor:User=Depends(get_current_user)):
    q=await _get(db,quiz_id); await _owned(db,actor,q); q.status="closed"
    for attempt in (await db.scalars(select(QuizAttempt).where(QuizAttempt.quiz_id == q.id, QuizAttempt.status == "in_progress"))).all():
        _grade(q, attempt)
    return _out(q,include_answers=True)

@router.post("/{quiz_id}/attempts", status_code=201)
async def start_attempt(quiz_id:int, db:AsyncSession=Depends(get_db), actor:User=Depends(get_current_user)):
    q=await _get(db,quiz_id); stu=await _student(db,actor)
    if not stu or not await _can_course(db,stu.id,q.course_id): raise HTTPException(403,"Not enrolled")
    if q.status not in ("published","open"): raise HTTPException(409,"Quiz is unavailable")
    old=await db.scalar(select(QuizAttempt).where(QuizAttempt.quiz_id==q.id,QuizAttempt.student_id==stu.id))
    if old:
        _expire_if_due(q, old)
        return _student_out(q,old)
    deadline=now_myt()+timedelta(seconds=q.timer_seconds) if q.timer_seconds and q.timer_mode=="whole" else None
    a=QuizAttempt(quiz_id=q.id,student_id=stu.id,deadline_at=deadline); db.add(a); await db.flush(); return _student_out(q,a)

def _grade(q,a):
    total=max(len(q.questions),1); correct=0
    for i,item in enumerate(q.questions):
        answer=a.answers.get(str(i)); expected=item.get("answer", item.get("suggested_answer",""))
        if item.get("type")=="mcq": correct += int(answer==expected)
        else: correct += int(str(answer or "").strip().lower()==str(expected).strip().lower())
    a.score=round(100*correct/total,2); a.status="submitted"; a.submitted_at=now_myt()

@router.put("/{quiz_id}/attempts/{attempt_id}/answers/{index}")
async def save_answer(quiz_id:int,attempt_id:int,index:int,body:dict,db:AsyncSession=Depends(get_db),actor:User=Depends(get_current_user)):
    q=await _get(db,quiz_id); a=await db.get(QuizAttempt,attempt_id); stu=await _student(db,actor)
    if not a or a.quiz_id!=q.id or not stu or a.student_id!=stu.id: raise HTTPException(404,"Attempt not found")
    _expire_if_due(q, a)
    if a.status!="in_progress": raise HTTPException(409,"Attempt is locked")
    if index<0 or index>=len(q.questions): raise HTTPException(404,"Question not found")
    # A live game accepts only the currently released question; clients cannot preload answers.
    if q.quiz_type == "game" and (q.status != "open" or index != q.current_question):
        raise HTTPException(409, "This game question is not open")
    answers=dict(a.answers); answers[str(index)]=body.get("answer"); a.answers=answers; return _student_out(q,a)
@router.post("/{quiz_id}/attempts/{attempt_id}/submit")
async def submit(quiz_id:int,attempt_id:int,db:AsyncSession=Depends(get_db),actor:User=Depends(get_current_user)):
    q=await _get(db,quiz_id); a=await db.get(QuizAttempt,attempt_id); stu=await _student(db,actor)
    if not a or a.quiz_id!=q.id or not stu or a.student_id!=stu.id: raise HTTPException(404,"Attempt not found")
    _expire_if_due(q, a)
    if a.status=="in_progress": _grade(q,a)
    return _student_out(q,a)
@router.get("/{quiz_id}/results/me")
async def result(quiz_id:int,db:AsyncSession=Depends(get_db),actor:User=Depends(get_current_user)):
    q=await _get(db,quiz_id); stu=await _student(db,actor); a=await db.scalar(select(QuizAttempt).where(QuizAttempt.quiz_id==q.id,QuizAttempt.student_id==getattr(stu,"id",None)))
    if not a: raise HTTPException(404,"No attempt")
    _expire_if_due(q, a)
    return _student_out(q,a)


@router.get("/{quiz_id}/results")
async def lecturer_results(quiz_id: int, db: AsyncSession = Depends(get_db), actor: User = Depends(get_current_user)):
    q = await _get(db, quiz_id)
    await _owned(db, actor, q)
    attempts = (await db.scalars(select(QuizAttempt).where(QuizAttempt.quiz_id == q.id))).all()
    submitted = [a for a in attempts if a.status == "submitted"]
    scores = [a.score for a in submitted if a.score is not None]
    question_correct = []
    for index, question in enumerate(q.questions):
        expected = question.get("answer", question.get("suggested_answer", ""))
        correct = sum(1 for attempt in submitted if attempt.answers.get(str(index)) == expected)
        question_correct.append({"index": index, "correct": correct, "answered": sum(str(index) in a.answers for a in submitted)})
    return {"quiz_id": q.id, "submissions": len(submitted), "average": round(sum(scores) / len(scores), 2) if scores else None,
            "score_distribution": scores, "questions": question_correct}
@router.get("/{quiz_id}/leaderboard")
async def leaderboard(quiz_id:int,db:AsyncSession=Depends(get_db),actor:User=Depends(get_current_user)):
    q=await _get(db,quiz_id)
    if q.quiz_type!="game": raise HTTPException(404,"Graded quizzes never have a leaderboard")
    rows=(await db.scalars(select(QuizAttempt).where(QuizAttempt.quiz_id==q.id,QuizAttempt.status=="submitted").order_by(QuizAttempt.score.desc()))).all()
    return [{"rank":i+1,"score":a.score,"attempt_id":a.id} for i,a in enumerate(rows[:5])]
