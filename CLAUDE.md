# SmartClass — Claude Code Guide

## Project Overview
SmartClass is a classroom management system for UM (Universiti Malaya): Moodle-based login, face recognition attendance (Raspberry Pi at the entrance), attendance management synced to Moodle, and an AI learning assistant over course materials. It has one React web frontend (admin) and two React Native mobile apps (lecturer, student). A local Moodle (`backend/moodle/`) simulates UM SPeCTRUM. Scope is defined by `PROJECT PROPOSAL PAPER.pdf` (8 modules); IoT environment control and desk projection were dropped.

## Repo Structure
```
SmartClass/
├── backend/
│   ├── app/            # FastAPI application (routers, models, schemas, services)
│   ├── alembic/        # DB migrations
│   ├── face_worker/    # Standalone face recognition worker process
│   ├── moodle/         # Local Moodle 4.5 simulating SPeCTRUM (own docker-compose)
│   ├── tests/          # pytest suite
│   ├── scripts/        # seed.py — populates demo data; kb_sync.py
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
- Screens: Dashboard, AttendanceSessions, AttendanceDetail, QuizList, CreateQuiz, LiveResults, ResultsClosed, Breakdown, Analytics, Profile, Login (quiz screens are UI mock only — Module 6 belongs to Shino)
- Navigation: React Navigation 6 — bottom tabs + native stack per tab
- State in `src/context/LecturerContext.jsx`
- API base URL set via `EXPO_PUBLIC_API_URL` in `.env`

## Component Conventions
- `src/components/ui/` — reusable primitives (Button, Modal, Toast, Badge, etc.)
- `src/components/layout/` — structural wrappers (Sidebar, Topbar, BottomNav, PhoneFrame, StatusBar)
- `src/views/` — page-level components, one file per route/screen

## Project Documentation

All requirements and use case specs live in `docs/`. Read the relevant FRs/UCs before designing APIs, schemas, or backend logic.

```
docs/
├── requirements/
│   ├── functional-requirements.md      # FR-1xx (M1), FR-3xx (M3), FR-4xx (M4), FR-8xx (M8); M2/5/6/7 placeholders
│   └── non-functional-requirements.md  # NFR-01–NFR-30 (M1/3/4/8 + system-wide)
├── use-cases/
│   ├── UC-M1-user-management.md
│   ├── UC-M3-M4-attendance-face-recognition.md
│   └── UC-M8-ai-learning-assistant.md
└── archive/use-cases-fyp1/             # old FYP1 use cases (IoT, projection) — outdated, do not implement
```

**Module ownership (graded per person — never build the other person's module):**
- Modules 1, 3, 4, 8 → Yew Sing (User Mgmt, Attendance Mgmt, Face Recognition, AI Learning Assistant)
- Modules 2, 5, 6, 7 → Shino (Dashboard & Notifications, Classroom Interaction, AI Quiz, Learning Analytics)
- Where Yew Sing's modules need Shino's, build only the interface/stub described in the FR doc.

**Diagrams still to be created:** System Architecture, Module Diagram, Class Diagram, ERD, Activity Diagrams, Navigation Diagram, Wireframes.

## Commands
- Fast checks (what the Stop hook runs): `bash scripts/check.sh`
- Backend tests: `cd backend && python -m pytest -q` (markers: `db` needs docker postgres, `live` calls the real LLM, `moodle` needs the local Moodle up)
- Live LLM tests (Gemini free tier, rate-limited): `cd backend && python -m pytest -m live -q`
- Lint: `cd backend && ruff check .` · format: `ruff format <file>`
- Mobile E2E (Android emulator + Maestro): `bash scripts/e2e-mobile.sh <student|lecturer> <flow>` (set up by T03)
- Admin web build: `cd frontend/admin && npm run build`

## Task Loop Rules (PLAN.md / PROGRESS.md)
Long jobs run as one task per fresh session via `/next-task` (see `scripts/run-tasks.sh`).
- **One task per session.** Pick the first unchecked task in `PLAN.md` whose dependencies are all `[x]` and which is not tagged `[HUMAN]`. Never start a second task.
- A task is **DONE** only when: code written, tests written, `bash scripts/check.sh` passes, its "Done when" line is met, and the reviewer agent found no unresolved real problems.
- `[UI]` tasks are done only when their Maestro (mobile) or Playwright (admin) flow passes. If the E2E setup is broken, mark the task `[~]` and explain in PROGRESS.md.
- **Never delete, skip or weaken a test to make it pass.** If a test looks wrong, leave it failing and write why in PROGRESS.md under "Blocked".
- If stuck after 3 genuine attempts at the same problem, write it under `## Blocked` in PROGRESS.md and stop.
- Changing a shared interface (API path/shape, DB schema, migration) must be noted in the PROGRESS.md entry. Every schema change needs an Alembic migration.
- Tests: unit tests mock Moodle and the LLM. Real-LLM tests carry `@pytest.mark.live`, stay few and small (free-tier RPM/RPD limits), and are never part of `check.sh`.
- Course materials and face/card images are never committed (copyright, PDPA). Test images are generated or use InsightFace's bundled sample images.
- Never read or print `backend/.env` or any secret. Never commit secrets.
- On Windows use the Bash tool (Git Bash) for commands, not PowerShell.
- Stay inside the task's scope; note follow-up ideas in PROGRESS.md under "Next" instead of doing them.

## WIP / Known Gaps
- See `PLAN.md` (task list) and `PROGRESS.md` (log). FRs marked Deferred depend on Module 6.
