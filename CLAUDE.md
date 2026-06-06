# SmartClass — Claude Code Guide

## Project Overview
SmartClass is a classroom management system for UM (Universiti Malaya) with face recognition-based attendance tracking, quiz management, and participation analytics. It has one React web frontend (admin) and two React Native mobile apps (lecturer, student).

## Repo Structure
```
SmartClass/
├── backend/
│   ├── app/            # FastAPI application (routers, models, schemas, services)
│   ├── alembic/        # DB migrations
│   ├── face_worker/    # Standalone face recognition worker process
│   ├── scripts/        # seed.py — populates demo data
│   └── docker-compose.yml
├── frontend/
│   └── admin/      # Web dashboard for administrators
└── mobile/
    ├── lecturer/   # React Native (Expo) app for lecturers
    └── student/    # React Native (Expo) app for students
```

The web frontend is independent with its own `package.json`, `node_modules`, and `vite.config.js`. The mobile apps use Expo SDK 54.

## Tech Stack
- **Web frontend (admin):** React 18 + Vite 5, Tailwind CSS 3, React Context API
- **Mobile apps:** React Native + Expo SDK 54, React Navigation 6, AsyncStorage
- **Backend:** FastAPI + SQLAlchemy 2 async + asyncpg + PostgreSQL + pgvector
- **Auth:** JWT (python-jose) + bcrypt (passlib)
- **Face recognition:** InsightFace `buffalo_sc` (CPU)
- **Infra:** Docker Compose (postgres+pgvector)

## Running the Project

### Backend
```bash
cd backend
docker compose up -d                              # start postgres+pgvector
pip install -r requirements.txt
alembic upgrade head
python scripts/seed.py                            # demo data
uvicorn app.main:app --reload --host 0.0.0.0     # API at localhost:8000, also reachable from phone
```

> Use `--host 0.0.0.0` so the React Native app on a physical device can reach the backend over WiFi.

### Face Worker (separate terminal)
```bash
cd backend/face_worker
pip install -r requirements.txt
python worker.py
```

### Admin Web App
```bash
cd frontend/admin && npm install && npm run dev  # → localhost:5173
```

### Mobile Apps (React Native / Expo)
```bash
cd mobile/lecturer   # or mobile/student
cp .env.example .env          # then set EXPO_PUBLIC_API_URL=http://<your-laptop-ip>:8000
npm install --legacy-peer-deps
npm start                     # scan QR with Expo Go on your phone
```

Both phone and laptop must be on the same WiFi network.

## App-Specific Notes

### Admin (`frontend/admin/`)
- Full web dashboard (not mobile-constrained)
- Views: Dashboard, Users, Students, Lecturers, Enrollment, FaceData, FaceReviewQueue, ClassManagement, AuditLog, Login
- State managed in `src/context/AdminContext.jsx`
- API layer in `src/services/api.js` + `src/services/client.js` (real HTTP calls to backend)

### Student (`mobile/student/`)
- React Native app (Expo SDK 54), runs on physical Android/iOS via Expo Go
- Screens: Login, Home, Attendance, AttSessionDetail, AttReportStatus, Participation, PartSessionPerf, Profile
- Navigation: React Navigation 6 — bottom tabs + native stack per tab
- API base URL set via `EXPO_PUBLIC_API_URL` in `.env`

### Lecturer (`mobile/lecturer/`)
- React Native app (Expo SDK 54), runs on physical Android/iOS via Expo Go
- Screens: Dashboard, AttendanceSessions, AttendanceDetail, QuizList, CreateQuiz, LiveResults, ResultsClosed, Breakdown, Analytics, Environment, Profile, Login
- Navigation: React Navigation 6 — bottom tabs + native stack per tab
- State in `src/context/LecturerContext.jsx`
- API base URL set via `EXPO_PUBLIC_API_URL` in `.env`

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
- No known gaps at this time.
