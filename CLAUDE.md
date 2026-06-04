# SmartClass — Claude Code Guide

## Project Overview
SmartClass is a classroom management system for UM (Universiti Malaya) with face recognition-based attendance tracking, quiz management, and participation analytics. It has three separate React frontends — admin, student, and lecturer.

## Repo Structure
```
SmartClass/
├── backend/
│   ├── app/            # FastAPI application (routers, models, schemas, services)
│   ├── alembic/        # DB migrations
│   ├── face_worker/    # Standalone face recognition worker process
│   ├── scripts/        # seed.py — populates demo data
│   └── docker-compose.yml
└── frontend/
    ├── admin/      # Web dashboard for administrators
    ├── student/    # Mobile-sized UI for students
    └── lecturer/   # Mobile-sized UI for lecturers
```

Each frontend app is fully independent with its own `package.json`, `node_modules`, and `vite.config.js`.

## Tech Stack
- **Frontend:** React 18 + Vite 5, Tailwind CSS 3, React Context API
- **Backend:** FastAPI + SQLAlchemy 2 async + asyncpg + PostgreSQL + pgvector
- **Auth:** JWT (python-jose) + bcrypt (passlib)
- **Face recognition:** InsightFace `buffalo_sc` (CPU)
- **Infra:** Docker Compose (postgres+pgvector)

## Running the Project

### Backend
```bash
cd backend
docker compose up -d          # start postgres+pgvector
pip install -r requirements.txt
alembic upgrade head
python scripts/seed.py        # demo data
uvicorn app.main:app --reload # API at localhost:8000
```

### Face Worker (separate terminal)
```bash
cd backend/face_worker
pip install -r requirements.txt
python worker.py
```

### Frontend Apps
```bash
cd frontend/admin    && npm install && npm run dev  # → localhost:5173
cd frontend/student  && npm install && npm run dev  # → localhost:5174
cd frontend/lecturer && npm install && npm run dev  # → localhost:5175
```

## App-Specific Notes

### Admin (`frontend/admin/`)
- Full web dashboard (not mobile-constrained)
- Views: Dashboard, Users, Students, Lecturers, Enrollment, FaceData, FaceReviewQueue, ClassManagement, AuditLog, Login
- State managed in `src/context/AdminContext.jsx`
- API layer in `src/services/api.js` + `src/services/client.js` (real HTTP calls to backend)

### Student (`frontend/student/`)
- Phone-frame UI (844px height, simulated mobile)
- Views: Login, Home, Attendance, AttSessionDetail, AttReportStatus, Participation, PartSessionPerf, Profile
- Bottom nav for navigation
- State in `src/context/StudentContext.jsx`

### Lecturer (`frontend/lecturer/`)
- Phone-frame UI (same mobile simulation as student)
- Views: Dashboard, AttendanceSessions, AttendanceDetail, QuizList, CreateQuiz, LiveResults, ResultsClosed, Breakdown, Analytics, Environment, Profile, Login
- State in `src/context/LecturerContext.jsx`

## Component Conventions
- `src/components/ui/` — reusable primitives (Button, Modal, Toast, Badge, etc.)
- `src/components/layout/` — structural wrappers (Sidebar, Topbar, BottomNav, PhoneFrame, StatusBar)
- `src/views/` — page-level components, one file per route/screen

## Project Documentation

All requirements and use case specs live in `docs/`. Reference these before designing APIs, schemas, or backend logic.

```
docs/
├── requirements/
│   ├── functional-requirements.md      # FR-001–FR-062, grouped by module
│   └── non-functional-requirements.md  # NFR-01–NFR-39, grouped by category
└── use-cases/
    ├── UC-01-08-face-detection-attendance.md
    ├── UC-09-13-environmental-sensing.md
    ├── UC-14-23-desk-projection-quiz.md
    └── UC-24-32-analytics-user-management.md
```

**Module ownership:**
- Modules 1, 2, 5, 6 → Yew Sing
- Modules 3, 4, 7, 8 → Shino

**Diagrams still to be created:** System Architecture, Module Diagram, Class Diagram, ERD, Activity Diagrams, Navigation Diagram, Wireframes.

## WIP / Known Gaps
- Face review queue frontend: entries load on login but the count badge and table do not auto-refresh — requires re-login or a manual refresh call to see new entries from the worker.
