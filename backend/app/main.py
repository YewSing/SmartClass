import asyncio
import mimetypes
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routers import auth, admin_users, admin_students, admin_courses, admin_moodle, classes, sessions, attendance, internal, analytics, audit, face_review, assistant, student_face, face_verification
from app.services.attendance_service import low_attendance_monitor
from app.services.kb.sync import kb_sync_loop
from app.services.moodle_sync import moodle_sync_loop
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

    try:
        from app.services.kb.embedder import warm_up
        await asyncio.to_thread(warm_up)
        print("Knowledge base embedding model loaded.")
    except Exception as exc:
        print(f"WARNING: embedding model not loaded ({exc}) - assistant search will load it on first use.")

    tasks = [asyncio.create_task(low_attendance_monitor()), asyncio.create_task(kb_sync_loop()),
             asyncio.create_task(moodle_sync_loop())]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass


app = FastAPI(title="SmartClass API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:8081",
        "http://localhost:8082",
        "http://localhost:8092",  # lecturer app on Expo web in the Playwright E2E
        "http://localhost:19006",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admin_users.router)
app.include_router(admin_students.router)
app.include_router(admin_courses.router)
app.include_router(admin_moodle.router)
app.include_router(classes.router)
app.include_router(sessions.router)
app.include_router(attendance.router)
app.include_router(internal.router)
app.include_router(analytics.router)
app.include_router(ws_router.router)
app.include_router(audit.router)
app.include_router(face_review.router)
app.include_router(assistant.router)
app.include_router(student_face.router)
app.include_router(face_verification.router)

# pdf.js for the student app's in-app PDF viewer (FR-809). It's a public library with no course data.
mimetypes.add_type("text/javascript", ".js")   # Windows can map .js to text/plain, which blocks the worker
app.mount("/static/pdfjs", StaticFiles(directory=Path(__file__).parent / "static" / "pdfjs"), name="pdfjs")


@app.get("/health")
async def health():
    return {"status": "ok"}
