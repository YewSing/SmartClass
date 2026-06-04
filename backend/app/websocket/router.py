from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.core.security import decode_token
from app.models.session import AttendanceSession
from app.models.attendance import AttendanceRecord
from app.models.user import Student
from app.models.class_ import Enrollment
from app.services.session_service import get_session_counts
from app.websocket.manager import manager

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/sessions/{session_id}")
async def attendance_ws(
    session_id: int,
    websocket: WebSocket,
    token: str = Query(...),
):
    """
    Real-time attendance feed for a session.
    Authenticate via ?token=<JWT>. Lecturer role required.
    Pushes attendance_update / attendance_override / session_closed events.
    """
    payload = decode_token(token)
    user_id = payload.get("sub")
    role = payload.get("role")
    token_type = payload.get("type")

    if not user_id or token_type != "access" or role not in ("lecturer", "admin"):
        await websocket.close(code=1008)
        return

    async with AsyncSessionLocal() as db:
        session_result = await db.execute(
            select(AttendanceSession).where(AttendanceSession.id == session_id)
        )
        session = session_result.scalar_one_or_none()
        if not session:
            await websocket.close(code=1008)
            return

        await manager.connect(session_id, websocket)

        try:
            # Send initial state so the frontend populates immediately on connect
            counts = await get_session_counts(session_id, db)

            enrolled = await db.execute(
                select(Student)
                .options(selectinload(Student.user))
                .join(Enrollment, Enrollment.student_id == Student.id)
                .where(Enrollment.occurrence_id == session.occurrence_id)
                .order_by(Student.matric_no)
            )
            students = enrolled.scalars().all()

            records_result = await db.execute(
                select(AttendanceRecord).where(AttendanceRecord.session_id == session_id)
            )
            records_by_student = {r.student_id: r for r in records_result.scalars().all()}

            student_list = []
            for stu in students:
                rec = records_by_student.get(stu.id)
                student_list.append({
                    "id": stu.id,
                    "name": stu.user.name,
                    "matric_no": stu.matric_no,
                    "status": rec.status if rec else "not_recorded",
                    "record_id": rec.id if rec else None,
                })

            await websocket.send_json({
                "event": "session_state",
                "session_id": session_id,
                "counts": counts,
                "students": student_list,
            })

            # Keep connection alive; server drives all pushes
            while True:
                await websocket.receive_text()

        except WebSocketDisconnect:
            pass
        finally:
            manager.disconnect(session_id, websocket)
