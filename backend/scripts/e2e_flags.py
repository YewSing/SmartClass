"""
Test data for the "I'm here" flag E2E flows (T45): two local courses, a test camera and a made-up
face vector.

    python scripts/e2e_flags.py seed
    python scripts/e2e_flags.py actor --mode student --api http://127.0.0.1:8000
    python scripts/e2e_flags.py actor --mode lecturer --api http://127.0.0.1:8000
    python scripts/e2e_flags.py clean

`seed` gives student4 two open classes (E2E045 for the flag, E2E046 for a simulated recognition),
a camera `CAM-E2E045` with no key, and one face embedding of the first face in InsightFace's bundled
sample photo `t1.jpg` (no real student's face, NFR-01/PDPA; nothing is written to disk). The sessions have no Moodle course, so neither sync
touches them.

`actor --mode student` waits for the student's flag, confirms it as lecturer1, then (10 s later)
issues the camera a key and posts that sample face to `POST /device/faces` for E2E046 (as many
frames as FACE_VOTE_THRESHOLD), which records Present and tells the student's phone. `actor --mode lecturer` waits for the lecturer's
"+15 min" tap, then flags E2E045 as the student. Tokens and the device key stay in memory.

`clean` stops a running actor and removes everything `seed` created, leaving the dev database as
before: only the two E2E courses, the test camera and the sample-face embedding.

Run from backend/ against the dev database (DATABASE_URL in .env).
"""
import argparse
import asyncio
import json
import os
import signal
import sys
import tempfile
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from sqlalchemy import delete, select, text

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.core.security import create_access_token
from app.models.attendance import AttendanceRecord
from app.models.attendance_flag import AttendanceFlag, UnmatchedFace
from app.models.camera import Camera
from app.models.class_ import ClassOccurrence, Course, Enrollment
from app.models.face import FaceEmbedding
from app.models.session import AttendanceSession
from app.models.user import Lecturer, Student, User
from app.services import device_service, session_schedule

FLAG_CODE = "E2E045"
FLAG_NAME = "E2E Flag Test"
FLAG_ROOM = "E2E Room 45"
REC_CODE = "E2E046"
REC_NAME = "E2E Recognition Test"
REC_ROOM = "E2E Room 46"
DEVICE_ID = "CAM-E2E045"
CAMERA_LABEL = "E2E test camera"
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DEADLINE_SECONDS = 300
MARKER = os.path.join(tempfile.gettempdir(), "smartclass-e2e-flags.json")


_SAMPLE: tuple[bytes, list[float]] | None = None


def sample_face() -> tuple[bytes, list[float]]:
    """(PNG crop, embedding) of the largest face in InsightFace's bundled `t1.jpg`, made in memory.

    T46b: recognition now runs on the server from a face crop, so the E2E needs a real face; this
    sample photo ships with InsightFace and is nobody enrolled at UM. The embedding is computed the
    way the server computes it, so the crop matches it.
    """
    global _SAMPLE
    if _SAMPLE is None:
        from insightface.app import FaceAnalysis

        from app.core.config import settings
        from app.services import recognition_service
        from tests import card_images

        fa = FaceAnalysis(name=settings.INSIGHTFACE_MODEL, providers=["CPUExecutionProvider"])
        fa.prepare(ctx_id=-1, det_size=(640, 640))
        crop = card_images._png(card_images.people(fa)[0])
        embedding = recognition_service.embed_crop(fa, crop)
        if embedding is None:
            sys.exit("InsightFace found no face in its own sample photo.")
        _SAMPLE = (crop, [float(x) for x in embedding])
    return _SAMPLE


# ── Lookups ──────────────────────────────────────────────────────────────────

async def _student_by_email(db, email: str) -> Student | None:
    return (await db.execute(
        select(Student).join(User, User.id == Student.user_id).where(User.email == email)
    )).scalar_one_or_none()


async def _lecturer_by_email(db, email: str) -> Lecturer | None:
    return (await db.execute(
        select(Lecturer).join(User, User.id == Lecturer.user_id).where(User.email == email)
    )).scalar_one_or_none()


# ── seed ─────────────────────────────────────────────────────────────────────

async def seed(db, student_email: str, lecturer_email: str) -> None:
    await clean(db, student_email)

    student = await _student_by_email(db, student_email)
    if student is None:
        sys.exit(f"No SmartClass student with email {student_email}. Sign them in once first.")
    lecturer = await _lecturer_by_email(db, lecturer_email)
    if lecturer is None:
        sys.exit(f"No SmartClass lecturer with email {lecturer_email}. Sign them in once first.")

    now = session_schedule.clock()
    today = now.date()
    day = DAYS[now.weekday()]
    starts_at = now - timedelta(minutes=5)
    ends_at = now + timedelta(hours=2)

    student_id, student_user_id = student.id, student.user_id
    lecturer_id, lecturer_user_id = lecturer.id, lecturer.user_id
    course_ids, occurrence_ids, session_ids = {}, {}, {}
    for code, name, room in ((FLAG_CODE, FLAG_NAME, FLAG_ROOM), (REC_CODE, REC_NAME, REC_ROOM)):
        course = Course(code=code, name=name)
        db.add(course)
        await db.flush()
        occurrence = ClassOccurrence(
            course_id=course.id, type="LECTURE", day_of_week=day,
            start_time=starts_at.strftime("%H:%M"), end_time=ends_at.strftime("%H:%M"),
            room=room, lecturer_id=lecturer_id,
        )
        db.add(occurrence)
        await db.flush()
        db.add(Enrollment(student_id=student_id, occurrence_id=occurrence.id))
        session = AttendanceSession(
            occurrence_id=occurrence.id, lecturer_id=lecturer_id, status="open", source="manual",
            class_date=today, opened_at=starts_at, starts_at=starts_at, ends_at=ends_at, camera_id=None,
        )
        db.add(session)
        await db.flush()
        course_ids[code] = course.id
        occurrence_ids[code] = occurrence.id
        session_ids[code] = session.id

    camera = Camera(label=CAMERA_LABEL, room=REC_ROOM, device_id=DEVICE_ID)
    db.add(camera)
    await db.flush()
    embedding = FaceEmbedding(student_id=student_id, embedding=sample_face()[1])
    db.add(embedding)
    await db.flush()

    # Read the ids and times before the commit: a committed object would need a fresh SELECT
    camera_id, embedding_id = camera.id, embedding.id
    ends_at_iso = ends_at.isoformat()
    await db.commit()

    marker = {
        "course_ids": course_ids,
        "occurrence_ids": occurrence_ids,
        "flag_session_id": session_ids[FLAG_CODE],
        "rec_session_id": session_ids[REC_CODE],
        "camera_id": camera_id,
        "embedding_id": embedding_id,
        "student_id": student_id,
        "student_user_id": student_user_id,
        "lecturer_user_id": lecturer_user_id,
        "ends_at": ends_at_iso,
    }
    with open(MARKER, "w") as f:
        json.dump(marker, f)
    print(f"seeded {FLAG_CODE} (session {session_ids[FLAG_CODE]}) and {REC_CODE} "
          f"(session {session_ids[REC_CODE]}) for {student_email}; camera {DEVICE_ID}")


# ── clean ────────────────────────────────────────────────────────────────────

def _stop_actor() -> None:
    if not os.path.exists(MARKER):
        return
    try:
        with open(MARKER) as f:
            marker = json.load(f)
    except (OSError, ValueError):
        return
    pid = marker.get("actor_pid")
    if not pid:
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except (OSError, ProcessLookupError):
        pass


async def clean(db, student_email: str | None) -> None:
    _stop_actor()
    marker = {}
    if os.path.exists(MARKER):
        try:
            with open(MARKER) as f:
                marker = json.load(f)
        except (OSError, ValueError):
            marker = {}

    removed = dict.fromkeys(
        ("flags", "unmatched", "records", "sessions", "enrolments", "occurrences", "courses",
         "cameras", "embeddings"), 0)

    course_ids = (await db.execute(
        select(Course.id).where(Course.code.in_((FLAG_CODE, REC_CODE)))
    )).scalars().all()
    if course_ids:
        occurrence_ids = (await db.execute(
            select(ClassOccurrence.id).where(ClassOccurrence.course_id.in_(course_ids))
        )).scalars().all()
        if occurrence_ids:
            session_ids = (await db.execute(
                select(AttendanceSession.id).where(AttendanceSession.occurrence_id.in_(occurrence_ids))
            )).scalars().all()
            if session_ids:
                for key, model in (("flags", AttendanceFlag), ("unmatched", UnmatchedFace),
                                   ("records", AttendanceRecord)):
                    result = await db.execute(delete(model).where(model.session_id.in_(session_ids)))
                    removed[key] = result.rowcount or 0
                result = await db.execute(
                    delete(AttendanceSession).where(AttendanceSession.id.in_(session_ids)))
                removed["sessions"] = result.rowcount or 0
            result = await db.execute(
                delete(Enrollment).where(Enrollment.occurrence_id.in_(occurrence_ids)))
            removed["enrolments"] = result.rowcount or 0
            result = await db.execute(
                delete(ClassOccurrence).where(ClassOccurrence.id.in_(occurrence_ids)))
            removed["occurrences"] = result.rowcount or 0
        result = await db.execute(delete(Course).where(Course.id.in_(course_ids)))
        removed["courses"] = result.rowcount or 0

    result = await db.execute(delete(Camera).where(Camera.device_id == DEVICE_ID))
    removed["cameras"] = result.rowcount or 0

    # Only the sample-face embedding: the student's real enrolled faces stay (NFR-02)
    if marker.get("embedding_id") is not None:
        result = await db.execute(delete(FaceEmbedding).where(FaceEmbedding.id == marker["embedding_id"]))
        removed["embeddings"] = result.rowcount or 0
    else:
        student_id = marker.get("student_id")
        if student_id is None and student_email:
            student = await _student_by_email(db, student_email)
            student_id = student.id if student is not None else None
        if student_id is not None:
            result = await db.execute(
                text("DELETE FROM face_embeddings WHERE student_id = :sid AND embedding = CAST(:vec AS vector)"),
                {"sid": student_id, "vec": str(sample_face()[1])},
            )
            removed["embeddings"] = result.rowcount or 0

    await db.commit()
    if os.path.exists(MARKER):
        os.remove(MARKER)
    print("removed " + ", ".join(f"{k} {v}" for k, v in removed.items()))


# ── actor ────────────────────────────────────────────────────────────────────

async def _wait_pending_flag(marker: dict, deadline: float) -> int | None:
    while time.monotonic() < deadline:
        async with AsyncSessionLocal() as db:
            flag_id = await db.scalar(select(AttendanceFlag.id).where(
                AttendanceFlag.session_id == marker["flag_session_id"],
                AttendanceFlag.student_id == marker["student_id"],
                AttendanceFlag.status == "pending",
            ))
        if flag_id is not None:
            return flag_id
        await asyncio.sleep(1)
    return None


async def _wait_extended(marker: dict, deadline: float) -> bool:
    original = datetime.fromisoformat(marker["ends_at"])
    while time.monotonic() < deadline:
        async with AsyncSessionLocal() as db:
            ends_at = await db.scalar(select(AttendanceSession.ends_at).where(
                AttendanceSession.id == marker["flag_session_id"]))
        if ends_at is not None and ends_at > original:
            return True
        await asyncio.sleep(1)
    return False


async def _issue_camera_key(camera_id: int) -> str:
    async with AsyncSessionLocal() as db:
        camera = await db.get(Camera, camera_id)
        if camera is None:
            sys.exit(f"No camera {camera_id}; run seed again.")
        key = device_service.issue_key(camera)   # in memory only; never printed
        await db.commit()
    return key


def _post(client: httpx.Client, api: str, path: str, token: str | None = None,
          body: dict | None = None, headers: dict | None = None) -> httpx.Response:
    h = dict(headers or {})
    if token:
        h["Authorization"] = f"Bearer {token}"
    res = client.post(f"{api}{path}", json=body, headers=h)
    if res.status_code >= 300:
        sys.exit(f"POST {path} failed: {res.status_code} {res.text}")
    return res


async def actor(mode: str, api: str) -> None:
    if not os.path.exists(MARKER):
        sys.exit("No marker: run `python scripts/e2e_flags.py seed` first.")
    with open(MARKER) as f:
        marker = json.load(f)
    marker["actor_pid"] = os.getpid()
    with open(MARKER, "w") as f:
        json.dump(marker, f)

    deadline = time.monotonic() + DEADLINE_SECONDS
    lecturer_token = create_access_token(marker["lecturer_user_id"], "lecturer")
    student_token = create_access_token(marker["student_user_id"], "student")

    with httpx.Client(timeout=10) as client:
        if mode == "student":
            flag_id = await _wait_pending_flag(marker, deadline)
            if flag_id is None:
                sys.exit(f"Timed out after {DEADLINE_SECONDS}s waiting for the student's flag.")
            await asyncio.sleep(6)    # the phone shows "Waiting for your lecturer"
            _post(client, api, f"/lecturer/flags/{flag_id}/confirm", lecturer_token)
            await asyncio.sleep(10)   # the phone shows the confirmed flag first
            key = await _issue_camera_key(marker["camera_id"])
            crop = sample_face()[0]
            outcome = {}
            for _ in range(settings.FACE_VOTE_THRESHOLD):   # FR-404: consecutive frames agree
                res = client.post(f"{api}/device/faces", headers={"X-Device-Key": key},
                                  files=[("crops", ("face.png", crop, "image/png"))])
                res.raise_for_status()
                [outcome] = res.json()["results"]
                await asyncio.sleep(1)
            if outcome.get("outcome") not in ("recorded", "already_recorded"):
                sys.exit(f"/device/faces did not record the student: {res.text}")
            print("flag confirmed; recognition recorded")
        else:
            if not await _wait_extended(marker, deadline):
                sys.exit(f"Timed out after {DEADLINE_SECONDS}s waiting for the class to be extended.")
            await asyncio.sleep(3)
            res = _post(client, api, f"/student/me/sessions/{marker['flag_session_id']}/flag",
                        student_token)
            if res.status_code != 201:
                sys.exit(f"student flag failed: {res.status_code} {res.text}")
            print("student flag sent")


# ── entry point ──────────────────────────────────────────────────────────────

async def _main(args) -> None:
    try:
        if args.action == "actor":
            await actor(args.mode, args.api)
            return
        async with AsyncSessionLocal() as db:
            if args.action == "seed":
                await seed(db, args.student, args.lecturer)
            else:
                await clean(db, args.student)
    finally:
        await engine.dispose()   # before the loop closes, or Windows prints "Event loop is closed"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("action", choices=["seed", "actor", "clean"])
    parser.add_argument("--student", default="student4@example.com", help="the student's SmartClass email")
    parser.add_argument("--lecturer", default="lecturer1@example.com", help="the lecturer's SmartClass email")
    parser.add_argument("--mode", choices=["student", "lecturer"], default="student")
    parser.add_argument("--api", default=os.environ.get("E2E_API_URL", "http://127.0.0.1:8000"))
    asyncio.run(_main(parser.parse_args()))
