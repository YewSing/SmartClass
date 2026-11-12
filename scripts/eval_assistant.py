#!/usr/bin/env python
"""Evaluate the AI assistant over the Q&A evaluation set (T82; NFR-18, NFR-19, NFR-14).

Runs each question in `backend/eval/qa_set.jsonl` through the real assistant, throttled by
the LLM rate limiter, and reports:
  - citation support   — share of in-syllabus answers carrying at least one citation;
  - off-syllabus label — share of off-syllabus answers labelled general knowledge;
  - latency            — mean and p95 of the answer time (NFR-14 target: ≤ 15 s);
  - correctness        — an LLM-judged 1–5 score per answer against the reference.

Usage (from backend/):
    python ../scripts/eval_assistant.py --course WIA2005 [--limit 5] [--out eval/results.json]
"""
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from sqlalchemy import select  # noqa: E402

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.models.ai_chat import ChatSession  # noqa: E402
from app.models.class_ import ClassOccurrence, Course, Enrollment  # noqa: E402
from app.models.user import Student, User  # noqa: E402
from app.services.kb import llm  # noqa: E402
from app.services.kb.assistant import SOURCE_COURSE, SOURCE_GENERAL, answer_question  # noqa: E402

JUDGE_PROMPT = (
    "You are grading a university learning assistant. Rate how correct the assistant's "
    "answer is for the question, using the reference answer. Reply with a single integer "
    "from 1 (mostly wrong) to 5 (fully correct).\n\n"
    "Question: {question}\nReference answer: {reference}\nAssistant answer: {answer}"
)


def load_set(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


async def get_or_create_student(db, course: Course) -> int:
    """A synthetic student enrolled in `course`, so the assistant answers on their behalf."""
    email = "eval.student@siswa.um.edu.my"
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        user = User(email=email, role="student", name="Eval Student", status="active")
        db.add(user)
        await db.flush()
        db.add(Student(user_id=user.id, matric_no="EVAL0001", programme="Software Engineering"))
        await db.flush()
    student = (await db.execute(select(Student).where(Student.user_id == user.id))).scalar_one()
    occ = (await db.execute(select(ClassOccurrence).where(
        ClassOccurrence.course_id == course.id).limit(1))).scalar_one_or_none()
    if occ is not None:
        enrolled = (await db.execute(select(Enrollment).where(
            Enrollment.student_id == student.id, Enrollment.occurrence_id == occ.id))).first()
        if enrolled is None:
            db.add(Enrollment(student_id=student.id, occurrence_id=occ.id))
    await db.commit()
    return student.id


async def judge_correctness(question: str, reference: str, answer: str) -> int | None:
    if not reference or not answer:
        return None
    try:
        raw = await llm.chat([{"role": "user", "content": JUDGE_PROMPT.format(
            question=question, reference=reference, answer=answer)}], max_tokens=10, temperature=0)
        digits = [int(c) for c in raw if c.isdigit()]
        return max(1, min(5, digits[0])) if digits else None
    except llm.LLMUnavailable as exc:
        print(f"  (judge unavailable: {exc})", file=sys.stderr)
        return None


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--course", required=True, help="course code to evaluate, e.g. WIA2005")
    parser.add_argument("--set", type=Path, default=BACKEND / "eval" / "qa_set.jsonl")
    parser.add_argument("--limit", type=int, default=0, help="evaluate only the first N questions")
    parser.add_argument("--out", type=Path, default=None, help="write detailed results to this JSON file")
    args = parser.parse_args()

    items = load_set(args.set)
    if args.limit:
        items = items[: args.limit]

    async with AsyncSessionLocal() as db:
        course = (await db.execute(select(Course).where(Course.code == args.course))).scalar_one_or_none()
        if course is None:
            print(f"No course with code {args.course} (index it first, or run scripts/kb_sync.py).")
            return 1
        student_id = await get_or_create_student(db, course)

        results = []
        for item in items:
            session = ChatSession(student_id=student_id, course_id=course.id)
            db.add(session)
            await db.flush()
            start = time.perf_counter()
            reply = await answer_question(db, session, course, item["question"])
            latency = time.perf_counter() - start
            score = await judge_correctness(item["question"], item.get("reference", ""), reply.content)
            results.append({
                "question": item["question"], "kind": item["kind"], "source": reply.source_type,
                "citations": len(reply.citations or []), "latency_s": round(latency, 2),
                "correctness": score,
            })
            print(f"[{item['kind'][:3]}] {item['question'][:60]:<60} {reply.source_type:<7} "
                  f"{len(reply.citations or [])} cit  {latency:.1f}s  score={score}")

    in_syl = [r for r in results if r["kind"] == "in_syllabus"]
    off_syl = [r for r in results if r["kind"] == "off_syllabus"]
    cited = sum(1 for r in in_syl if r["source"] == SOURCE_COURSE and r["citations"] > 0)
    labelled = sum(1 for r in off_syl if r["source"] == SOURCE_GENERAL)
    lats = sorted(r["latency_s"] for r in results)
    scores = [r["correctness"] for r in results if r["correctness"] is not None]

    def pct(part, whole):
        return f"{100 * part / whole:.0f}%" if whole else "n/a"

    print("\n=== Summary ===")
    print(f"in-syllabus citation support : {pct(cited, len(in_syl))}  ({cited}/{len(in_syl)})")
    print(f"off-syllabus labelled general: {pct(labelled, len(off_syl))}  ({labelled}/{len(off_syl)})")
    if lats:
        p95 = lats[int(0.95 * (len(lats) - 1))]
        print(f"latency mean/p95             : {sum(lats)/len(lats):.1f}s / {p95:.1f}s  (NFR-14 target <= 15 s)")
    if scores:
        print(f"LLM-judged correctness (1-5) : {sum(scores)/len(scores):.2f}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"results written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
