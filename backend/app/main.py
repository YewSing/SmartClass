import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, admin_users, admin_students, admin_courses, classes, sessions, attendance, internal, analytics, audit, face_review
from app.services.attendance_service import low_attendance_monitor
from app.websocket import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        from insightface.app import FaceAnalysis
        from app.core.config import settings
        fa = FaceAnalysis(name=settings.INSIGHTFACE_MODEL, providers=["CPUExecutionProvider"])
        fa.prepare(ctx_id=-1, det_size=(640, 640))
        app.state.face_app = fa
        print(f"InsightFace model '{settings.INSIGHTFACE_MODEL}' loaded.")
    except ImportError:
        app.state.face_app = None
        print("WARNING: insightface not installed — face endpoints will return 503.")

    monitor_task = asyncio.create_task(low_attendance_monitor())
    try:
        yield
    finally:
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="SmartClass API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admin_users.router)
app.include_router(admin_students.router)
app.include_router(admin_courses.router)
app.include_router(classes.router)
app.include_router(sessions.router)
app.include_router(attendance.router)
app.include_router(internal.router)
app.include_router(analytics.router)
app.include_router(ws_router.router)
app.include_router(audit.router)
app.include_router(face_review.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
