# SmartClass — Claude Code Guide

## Project Overview
SmartClass is a classroom management system for UM (Universiti Malaya): Moodle-based login, face recognition attendance (Raspberry Pi at the entrance), attendance management synced to Moodle, and an AI learning assistant over course materials. It has one React web frontend (admin) and two React Native mobile apps (lecturer, student). A local Moodle (`backend/moodle/`) simulates UM SPeCTRUM. Scope is defined by `docs/private/PROJECT PROPOSAL PAPER.pdf` (local only, git-ignored) (8 modules); IoT environment control and desk projection were dropped.

**Web direction (decided 2026-11-09):** lecturers also use the lecturer app in a browser (same Expo code via Expo web). Administrators stay as a small role with a few web-only screens inside that app. `frontend/admin` is retired once PLAN.md T22, T46 and T96 are done; keep it working until then.

## Repo Structure
```
SmartClass/
├── backend/
│   ├── app/            # FastAPI application (routers, models, schemas, services)
│   ├── alembic/        # DB migrations
│   ├── face_worker/    # Standalone face recognition worker process
│   ├── moodle/         # Local Moodle 4.5 simulating SPeCTRUM (own docker-compose)
│   ├── tests/          # pytest suite
│   ├── scripts/        # seed.py — admin, timetable, always-open test class; reset_to_moodle.py; kb_sync.py
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
pip install -r face_worker/requirements.txt       # insightface: without it face enrolment answers 503
alembic upgrade head
python scripts/seed.py                            # admin, timetable, always-open test class (safe to re-run)
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
- Screens: Dashboard, ClassDetail, AttendanceSessions, AttendanceDetail, QuizList, CreateQuiz, LiveResults, ResultsClosed, Breakdown, Analytics, Profile, Login (quiz screens are UI mock only — Module 6 belongs to Shino)
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
├── product-walkthrough.md              # plain-language picture of the finished plan; Yew Sing's expectations
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
- Requests between the two are written in `docs/requests-for-shino.md` (read it after pulling `main`; reply in its Status line).

**Diagrams still to be created:** System Architecture, Module Diagram, Class Diagram, ERD, Activity Diagrams, Navigation Diagram, Wireframes.

## Commands
- Fast checks (what the Stop hook runs): `bash scripts/check.sh`
- Backend tests: `cd backend && python -m pytest -q` (markers: `db` needs docker postgres, `live` calls the real LLM, `moodle` needs the local Moodle up)
- Live LLM tests (Gemini free tier, rate-limited): `cd backend && python -m pytest -m live -q`
- Lint: `cd backend && ruff check .` · format: `ruff format <file>`
- Mobile E2E (Android emulator + Maestro): `bash scripts/e2e-mobile.sh <student|lecturer> <flow>` runs `mobile/<app>/e2e/<flow>.yaml`; boots AVD `Pixel_4_API_35` headless, starts backend + Expo, stops them on exit. Maestro installs into git-ignored `.tools/` if missing.
- Lecturer web E2E (Playwright): `cd mobile/lecturer && npm run e2e:web` (tests in `e2e-web/`; starts its own backend on :8001 with `LLM_FAKE=1` and Expo web on :8092; needs docker postgres + seed data)
- Admin web build: `cd frontend/admin && npm run build`

## Task Loop Rules (PLAN.md / PROGRESS.md)
Long jobs run as one task per fresh session. Start everything with `/run-plan [rounds]`, 5 tasks per run at most unless Yew Sing asks for more, so the work gets checked before more is built (it runs `scripts/run-tasks.sh` in the background, one fresh Opus session per task running `/next-task`, and reports at the end). The reviewer subagent runs on Sonnet.
- **Hybrid loop** (`SMARTCLASS_BUILDER=opencode bash scripts/run-tasks.sh <rounds> [turns]`): Opus plans each task with `/plan-task` into `.claude/plans/<task>.md`, OpenCode (`SMARTCLASS_OC_MODEL`, default `opencode-go/deepseek-v4.1-flash`) builds it, the Sonnet `reviewer` checks it (2 fix rounds), OpenCode commits. `[OPUS]` tasks, a stuck builder or a failed review fall back to Opus `/next-task`. Prompts: `scripts/opencode/`.
- **One task per session.** Pick the first unchecked task in `PLAN.md` whose dependencies are all `[x]` and which is not tagged `[HUMAN]`. No task below an unticked `[HUMAN] Checkpoint` may start. Never start a second task.
- A task is **DONE** only when: code written, tests written, `bash scripts/check.sh` passes, its "Done when" line is met, and the reviewer agent found no unresolved real problems.
- `[UI]` tasks are done only when their Maestro (mobile) or Playwright (lecturer web) flow passes. If the E2E setup is broken, mark the task `[~]` and explain in PROGRESS.md.
- **Never delete, skip or weaken a test to make it pass.** If a test looks wrong, leave it failing and write why in PROGRESS.md under "Blocked".
  `scripts/test_guard.py` (part of check.sh) fails the round if a test is removed or skipped, unless PROGRESS.md gets a `TEST-CHANGE: <test> - <why>` line; the reviewer judges the reason. Put skip logic for `live`/`moodle` tests in `conftest.py`, not in test files.
- If stuck after 3 genuine attempts at the same problem, write it under `## Blocked` in PROGRESS.md and stop.
- Changing a shared interface (API path/shape, DB schema, migration) must be noted in the PROGRESS.md entry. Every schema change needs an Alembic migration.
- Tests: normal tests never call Moodle or the LLM; they replay recorded real Gemini responses (`tests/fixtures/llm/`) or use mocks for error cases. Real-LLM tests carry `@pytest.mark.live`, use only the synthetic test course, and check structure/grounding, not exact wording. check.sh runs them automatically when a round changes `app/services/kb/` or prompts (see T82). Any new AI feature adds its cases to the live suite and records fixtures.
- Course materials and face/card images are never committed (copyright, PDPA). Test images are generated or use InsightFace's bundled sample images.
- Never read or print `backend/.env` or any secret. Never commit secrets.
- On Windows use the Bash tool (Git Bash) for commands, not PowerShell.
- Stay inside the task's scope; note follow-up ideas in PROGRESS.md under "Next" instead of doing them.

## Merging to main
Shino builds on `main` or her own branches, so only finished, checked work goes there.
1. Yew Sing says "prepare the merge" or runs `/prepare-merge`, or Claude suggests it at a milestone.
2. Claude runs the checks in `.claude/commands/prepare-merge.md`, fixes problems on the work branch, and resolves conflicts there if `main` has changed.
3. Claude gives Yew Sing the GitHub link and a note for Shino. Yew Sing clicks Merge.

Claude commits and pushes work branches freely, but never pushes to `main` or force-pushes (blocked in `.claude/settings.json`).

## WIP / Known Gaps
- See `PLAN.md` (task list) and `PROGRESS.md` (log). FRs marked Deferred depend on Module 6.
