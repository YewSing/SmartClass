"""Server-side recognition from device face crops (FR-402–FR-405).

A camera device sends the face crops of one frame to `POST /device/faces`. Each crop is embedded
here with InsightFace, matched only against students enrolled in the open session's class
(FR-403), and a student is recorded after FACE_VOTE_THRESHOLD consecutive frames (FR-404).

Votes are kept in memory per device, so the API must run as one process (the dev/demo setup
does). A frame missing a student resets that student's count, as does a gap longer than
FACE_VOTE_MAX_GAP_SECONDS or a change of session.

A backup laptop webcam (FR-409) runs with the room's own device key, so it is the same device
to the server. Nothing is written to disk: crops live in memory for this request only (NFR-01).
"""
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np
from sqlalchemy import and_, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.attendance import AttendanceRecord
from app.models.camera import Camera
from app.models.class_ import ClassOccurrence
from app.models.session import AttendanceSession
from app.models.user import Student
from app.services import attendance_service, session_schedule

logger = logging.getLogger(__name__)


def embed_crop(face_app, data: bytes) -> np.ndarray | None:
    """One normalised 512-d embedding from a device face crop, or None when no face is found.

    Synchronous and CPU-heavy: call it through `asyncio.to_thread`. Device crops are small, so a
    crop whose longer side is under 320 px is upscaled (the detector's det_size is 640); a tight
    crop with no surrounding context gets a black border before a second detection try.
    The bytes are never written anywhere (NFR-01).
    """
    import cv2

    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return None

    h, w = img.shape[:2]
    if max(h, w) < 320:
        scale = 320 / max(h, w)
        img = cv2.resize(img, (max(1, round(w * scale)), max(1, round(h * scale))),
                         interpolation=cv2.INTER_LINEAR)
        h, w = img.shape[:2]

    faces = [f for f in face_app.get(img) if f.normed_embedding is not None]
    if not faces:
        pad = max(h, w) // 2
        padded = cv2.copyMakeBorder(img, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=(0, 0, 0))
        faces = [f for f in face_app.get(padded) if f.normed_embedding is not None]
    if not faces:
        return None

    largest = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
    return largest.normed_embedding


async def find_open_session(db: AsyncSession, camera: Camera) -> AttendanceSession | None:
    """The open session this device should record into, or None.

    It is the open session assigned to the device's camera. When a session was opened before the
    room's device was registered its `camera_id` is NULL, so an open camera-less session in the
    device's room is used too. A camera-less session in another room never is.
    """
    q = (select(AttendanceSession)
         .outerjoin(ClassOccurrence, AttendanceSession.occurrence_id == ClassOccurrence.id)
         .where(AttendanceSession.status == "open",
                or_(AttendanceSession.camera_id == camera.id,
                    and_(AttendanceSession.camera_id.is_(None), ClassOccurrence.room == camera.room)))
         .order_by(AttendanceSession.opened_at.desc().nullslast(), AttendanceSession.id.desc())
         .limit(1))
    return (await db.execute(q)).scalar_one_or_none()


@dataclass
class Match:
    outcome: str            # matched | not_enrolled | below_threshold
    student_id: int | None
    similarity: float | None


_ENROLLED_BEST = text(
    "SELECT fe.student_id, (1 - (fe.embedding <=> CAST(:vec AS vector))) AS similarity "
    "FROM face_embeddings fe "
    "JOIN enrollments e ON e.student_id = fe.student_id AND e.occurrence_id = :occ "
    "ORDER BY fe.embedding <=> CAST(:vec AS vector) "
    "LIMIT 1"
)

_GLOBAL_BEST = text(
    "SELECT fe.student_id, (1 - (fe.embedding <=> CAST(:vec AS vector))) AS similarity "
    "FROM face_embeddings fe "
    "ORDER BY fe.embedding <=> CAST(:vec AS vector) "
    "LIMIT 1"
)


async def match_embedding(db: AsyncSession, embedding: np.ndarray, occurrence_id: int | None) -> Match:
    """Best enrolled student for an embedding; otherwise the best global one (FR-403).

    Only students enrolled in the session's class can be matched. A global nearest face that
    reaches the threshold is someone who is not in this class — the caller logs it, never records
    it.
    """
    vec = str([float(x) for x in embedding])

    enrolled_row = None
    if occurrence_id is not None:
        enrolled_row = (await db.execute(
            _ENROLLED_BEST, {"vec": vec, "occ": occurrence_id}
        )).fetchone()
    if enrolled_row is not None and float(enrolled_row.similarity) >= settings.FACE_MATCH_THRESHOLD:
        return Match("matched", enrolled_row.student_id, float(enrolled_row.similarity))

    global_row = (await db.execute(_GLOBAL_BEST, {"vec": vec})).fetchone()
    if global_row is not None and float(global_row.similarity) >= settings.FACE_MATCH_THRESHOLD:
        return Match("not_enrolled", global_row.student_id, float(global_row.similarity))

    return Match("below_threshold", None,
                 float(enrolled_row.similarity) if enrolled_row is not None else None)


@dataclass
class _DeviceVotes:
    session_id: int
    last_at: datetime
    counts: dict[int, int] = field(default_factory=dict)   # students.id → consecutive frames


_votes: dict[int, _DeviceVotes] = {}   # camera.id → state


def reset_votes() -> None:
    _votes.clear()


def vote(camera_id: int, session_id: int, student_ids: set[int], now: datetime) -> dict[int, int]:
    """Count one frame. Returns votes per student in `student_ids` after this frame.

    A student missing from a frame starts again from 0; so does everyone when the session
    changes or when the last frame is more than FACE_VOTE_MAX_GAP_SECONDS old.
    A student who reaches FACE_VOTE_THRESHOLD is removed from the state (the caller records them).
    No await inside: two requests can't interleave inside this function.
    """
    state = _votes.get(camera_id)
    if (state is None or state.session_id != session_id
            or now - state.last_at > timedelta(seconds=settings.FACE_VOTE_MAX_GAP_SECONDS)):
        state = _DeviceVotes(session_id, now)

    new_counts = {sid: state.counts.get(sid, 0) + 1 for sid in student_ids}
    result = dict(new_counts)
    for sid in [sid for sid, count in new_counts.items() if count >= settings.FACE_VOTE_THRESHOLD]:
        del new_counts[sid]
    state.counts = new_counts
    state.last_at = now
    _votes[camera_id] = state
    return result


async def recognise_frame(
    db: AsyncSession,
    face_app,
    camera: Camera,
    session: AttendanceSession,
    crops: list[bytes],
) -> list[dict]:
    """Embed every crop of one frame, vote, and record the students that reached the threshold."""
    embeddings = await asyncio.to_thread(lambda: [embed_crop(face_app, crop) for crop in crops])
    now = session_schedule.clock()
    recorded = {student_id: status for student_id, status in (await db.execute(
        select(AttendanceRecord.student_id, AttendanceRecord.status)
        .where(AttendanceRecord.session_id == session.id)
    )).all()}

    results: dict[int, dict] = {}
    candidates: list[tuple[int, int, float | None]] = []
    for index, embedding in enumerate(embeddings):
        if embedding is None:
            results[index] = {"index": index, "outcome": "no_face"}
            continue
        found = await match_embedding(db, embedding, session.occurrence_id)
        if found.outcome == "not_enrolled":
            logger.info(
                "Face matched student %s, who is not enrolled in session %s's class "
                "(device %s, similarity %.3f); not recorded",
                found.student_id, session.id, camera.device_id, found.similarity or 0.0,
            )
            results[index] = {"index": index, "outcome": "not_enrolled",
                              "similarity": found.similarity}
        elif found.outcome == "below_threshold":
            results[index] = {"index": index, "outcome": "below_threshold",
                              "similarity": found.similarity}
        elif found.student_id in recorded:
            results[index] = {"index": index, "outcome": "already_recorded",
                              "student_id": found.student_id, "similarity": found.similarity,
                              "status": recorded[found.student_id]}
        else:
            candidates.append((index, found.student_id, found.similarity))

    counts: dict[int, int] = {}
    if any(embedding is not None for embedding in embeddings):
        # A frame where every crop is empty is ignored: it must not reset anyone's count.
        counts = vote(camera.id, session.id, {student_id for _, student_id, _ in candidates}, now)

    done: dict[int, str] = {}
    for index, student_id, similarity in candidates:
        if student_id in done:   # the same student in a second crop of this frame
            results[index] = {"index": index, "outcome": "already_recorded",
                              "student_id": student_id, "similarity": similarity,
                              "status": done[student_id]}
            continue

        votes = counts.get(student_id, 0)
        if votes < settings.FACE_VOTE_THRESHOLD:
            results[index] = {"index": index, "outcome": "voting", "student_id": student_id,
                              "similarity": similarity, "votes": votes}
            continue

        try:
            async with db.begin_nested():
                record, was_new = await attendance_service.mark_present(
                    session.id, student_id, db, now=now, camera_id=camera.id)
        except IntegrityError:   # NFR-22: another path recorded them at the same moment
            record = (await db.execute(select(AttendanceRecord).where(
                AttendanceRecord.session_id == session.id,
                AttendanceRecord.student_id == student_id,
            ))).scalar_one()
            was_new = False

        if was_new:
            student = (await db.execute(
                select(Student).options(selectinload(Student.user)).where(Student.id == student_id)
            )).scalar_one()
            await attendance_service.broadcast_attendance_update(
                session.id, record, student.user.name, student.matric_no, db)
            done[student_id] = record.status
            results[index] = {"index": index, "outcome": "recorded", "student_id": student_id,
                              "similarity": similarity, "votes": votes, "status": record.status}
        else:
            done[student_id] = record.status
            results[index] = {"index": index, "outcome": "already_recorded",
                              "student_id": student_id, "similarity": similarity,
                              "status": record.status}

    return [results[index] for index in sorted(results)]
