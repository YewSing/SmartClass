# SmartClass

A classroom management system for Universiti Malaya (FYP). It covers Moodle-based sign-in, face
recognition attendance from a camera at the classroom door, attendance management synced to
Moodle, and an AI learning assistant that answers from the course materials. A local Moodle
stands in for UM SPeCTRUM.

## Apps

| App | Type | Description | Directory |
|-----|------|-------------|-----------|
| Student App | Mobile (React Native + Expo) | Attendance, face enrolment, participation, AI Assistant (chat, summaries, flashcards, practice). Runs on a real phone | `mobile/student/` |
| Lecturer App | Mobile + web (React Native + Expo) | Classes, attendance, quizzes, analytics, AI Assistant (materials, most-asked topics, ask my materials, before next class). Also runs in a browser, where administrators get the admin area (accounts, Moodle sync, devices, audit log) | `mobile/lecturer/` |
| Camera device client | Python | Runs on a Raspberry Pi or a laptop webcam at the door: detects faces and sends crops to the server | `backend/device_client/` |

## Modules and owners

Each person builds and is graded on their own modules. Requests between the two are in
`docs/requests-for-shino.md`, and the interfaces Yew Sing's modules offer are in `docs/interfaces.md`.

| Module | Owner | State |
|---|---|---|
| 1 User management (Moodle sign-in, face enrolment, admin) | Yew Sing | Built |
| 2 Dashboard and notifications | Shino | Notification hook `emit()` ready for M2 (`docs/interfaces.md`) |
| 3 Attendance management (sessions, statuses, Moodle sync) | Yew Sing | Built |
| 4 Face recognition (door camera) | Yew Sing | Built; Raspberry Pi hardware test still to do |
| 5 Classroom interaction | Shino | |
| 6 AI quiz | Shino | Lecturer quiz screens are UI mock-ups only; M8 offers a materials retrieval interface |
| 7 Learning analytics | Shino | Attendance read interface ready (`docs/interfaces.md`) |
| 8 AI learning assistant | Yew Sing | Built; answer-quality review (T83) still to do |

## Tech Stack

**Mobile apps:** React Native + Expo SDK 54, React Navigation 6, AsyncStorage

**Backend:** FastAPI + SQLAlchemy 2 (async) + PostgreSQL + pgvector, InsightFace (`buffalo_sc`, CPU), JWT auth, Docker Compose

**AI assistant:** any OpenAI-compatible chat API (DeepSeek or Gemini), local embeddings (fastembed), optional YouTube Data API

---

## How to Run

### Prerequisites

- [Node.js](https://nodejs.org/) (v18+)
- [Python](https://www.python.org/) 3.10+
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (PostgreSQL and the local Moodle)
- [Expo Go](https://expo.dev/go) on your phone (for the mobile apps)
- Git Bash on Windows (the scripts are bash)

---

### 1. Start the Database

```bash
cd backend
docker compose up -d
```

PostgreSQL with pgvector listens on **localhost:5433** (not the usual 5432).

---

### 2. Start the Local Moodle (SPeCTRUM)

People, courses, enrolments and course materials all come from Moodle. The first time:

```bash
cd backend/moodle
docker compose up -d      # first boot takes 3-5 minutes
./scripts/setup.sh        # installs the Moodle Attendance plugin, writes the web-service token to backend/moodle/.env.moodle
./scripts/seed.sh         # users, courses, enrolments, materials
```

`setup.sh` downloads the Attendance plugin (`mod_attendance`) inside the container, so the first
run needs internet. Closed SmartClass sessions are written into that plugin, which is how
attendance reaches "SPeCTRUM". Details and accounts are in `backend/moodle/README.md`. After the
first time, `docker compose up -d` is enough.

---

### 3. Configure Environment

```bash
cd backend
cp .env.example .env
```

Then edit `backend/.env`:

| Setting | What to put | Without it |
|---|---|---|
| `MOODLE_URL`, `MOODLE_TOKEN` | Copy both from `backend/moodle/.env.moodle` | No Moodle sign-in, sync or materials |
| `LLM_API_KEY` (+ `LLM_BASE_URL`, `LLM_MODEL`) | A DeepSeek or Gemini key, see the comments in the file | The AI assistant answers "unavailable" (503) |
| `YOUTUBE_API_KEY` | Optional YouTube Data API key | "Find related videos" shows search keywords only |

The backend starts without any of these. Never commit `.env`.

---

### 4. Install Backend Dependencies & Run Migrations

```bash
cd backend
pip install -r requirements.txt
alembic upgrade head
python scripts/seed.py
```

`seed.py` creates what Moodle can't provide: the admin account, the timetable, and an always-open test class (WIA0000, `devlecturer`). It is safe to run again.

**Test accounts (local dev only):**

| Role | Where to sign in | Sign in with | Password |
|---|---|---|---|
| Administrator | Lecturer app in a browser (http://localhost:8082) → "Administrator sign-in" | `admin@um.edu.my` | `Admin@1234` |
| Test lecturer | Lecturer app (phone or browser), SPeCTRUM sign-in | `devlecturer` | `DevTest@1234` |
| Students / other lecturers | Student or lecturer app, SPeCTRUM sign-in | `student1`..`student8`, `lecturer1`, `lecturer2` (see `backend/moodle/README.md`) | same table |
| Moodle (SPeCTRUM) admin | Local Moodle at http://localhost:8080 | `admin` | `Admin123!` |

An existing database with the old demo data: back up (`bash scripts/backup-data.sh`), then run `python scripts/reset_to_moodle.py` from `backend/` to preview and `--yes` to apply. It keeps AI materials and face enrolments.

---

### 5. Start the API Server

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0
```

API at **http://localhost:8000** · Docs at **http://localhost:8000/docs**

> `--host 0.0.0.0` is required so the mobile apps on a physical device can reach the backend over WiFi.
> On Windows, `--reload` sometimes misses changes after a `git pull`. If the app behaves like old code, stop and restart the server.

The API runs these background jobs itself (intervals are settings in `backend/.env`; the Moodle
ones are off while `MOODLE_TOKEN` is empty):

| Job | Every | Setting |
|---|---|---|
| Open and close attendance sessions from the timetable (opens 15 min early) | 1 min | `SESSION_SCHEDULER_INTERVAL_SECONDS` |
| Send closed sessions to Moodle Attendance, retrying with backoff | 30 s | `MOODLE_ATTENDANCE_SYNC_INTERVAL_SECONDS` |
| Check synced sessions still match Moodle | 3 h | `MOODLE_ATTENDANCE_CHECK_INTERVAL_SECONDS` |
| Courses and enrolments from Moodle | 15 min | `MOODLE_SYNC_INTERVAL_SECONDS` |
| Course materials indexed for the AI assistant | 5 min | `KB_SYNC_INTERVAL_SECONDS` |
| Low-attendance alert to the lecturer's live session screen (below 70 %) | 30 s | — |
| Delete unrecognised face crops older than 7 days | 1 h | `FACE_UNMATCHED_CLEANUP_INTERVAL_SECONDS` |

A lecturer can also sync a course's materials straight away (a course's AI Assistant → Sync
materials), and an admin can run the Moodle sync from the admin area.

---

### 6. Start the Camera Device Client (optional)

Only needed to test face attendance. Open a **separate terminal**:

```bash
cd backend
python scripts/device_key.py CAM-TEST     # prints the seeded room's new key (copy it)
DEVICE_KEY=<key> python -m device_client --camera 0
```

The client detects faces locally and sends crops to `POST /device/faces`; the server recognises them.
It opens the camera only while a session is open for its room. Running it on a Raspberry Pi, and
all its flags, are in `backend/device_client/README.md`. Other devices get their keys on the admin
area's Devices page.

---

### 7. Run the Mobile Apps

```bash
cd mobile/lecturer   # or mobile/student
cp .env.example .env
# Edit .env → set EXPO_PUBLIC_API_URL=http://<your-laptop-ip>:8000
# Find your IP with: ipconfig (Windows) or ifconfig (Mac/Linux)

npm install --legacy-peer-deps
npm start
```

Scan the QR code with **Expo Go** on your phone. Both phone and laptop must be on the same WiFi.

The lecturer app also runs in a browser (press `w` in its Expo terminal). Administrators sign in there to reach the admin area.

---

## Tests

```bash
bash scripts/check.sh                         # fast checks: lint, backend tests, app unit tests
cd backend && python -m pytest -q             # backend tests (needs the docker database)
cd backend && python -m pytest -m live -q     # real AI calls (uses your LLM key, rate-limited)
bash scripts/e2e-mobile.sh student assistant  # phone app E2E on an Android emulator (Maestro)
cd mobile/lecturer && npm run e2e:web         # lecturer web E2E (Playwright)
```

Normal tests never call Moodle or the AI; they use recorded responses and mocks. Backend test
markers: `db` needs the docker database, `live` calls the real AI, `moodle` needs the local Moodle
(the last two skip themselves when their key or token is missing).

**Phone E2E (Maestro):** flows are in `mobile/<app>/e2e/*.yaml`. Needs the Android SDK
(`ANDROID_HOME`, or the default `%LOCALAPPDATA%\Android\Sdk`) with an emulator image named
`Pixel_4_API_35` (or set `AVD=`) and Java. Maestro installs itself into the git-ignored `.tools/` on
the first run. The script boots the emulator headless, starts the backend and Expo, and stops all of
them when it ends.

**Lecturer web E2E (Playwright):** tests are in `mobile/lecturer/e2e-web/`. It starts its own backend
on :8001 (fake AI answers, no schedule or Moodle sync jobs) and Expo web on :8092, so it never
touches your dev servers. Needs the docker database, the seed data and the local Moodle.

---

## Project Structure

```
SmartClass/
├── backend/
│   ├── app/            # FastAPI application (routers, models, schemas, services)
│   ├── alembic/        # DB migrations
│   ├── device_client/  # Camera device client (Pi / webcam): detect faces, send crops
│   ├── moodle/         # Local Moodle 4.5 simulating SPeCTRUM (own docker-compose)
│   ├── scripts/        # seed.py, device_key.py, reset_to_moodle.py, kb_sync.py, e2e_*.py helpers
│   ├── eval/           # AI assistant evaluation question set
│   ├── tests/          # pytest suite (tests/live = real-AI suite)
│   └── docker-compose.yml
├── mobile/
│   ├── lecturer/       # React Native lecturer app (Expo, also web); e2e/ Maestro, e2e-web/ Playwright
│   └── student/        # React Native student app (Expo); e2e/ Maestro
├── scripts/            # check.sh, e2e-mobile.sh, eval_assistant.py, backup-data.sh / restore-data.sh
└── docs/
    ├── requirements/       # functional and non-functional requirements
    ├── use-cases/
    ├── interfaces.md       # what Yew Sing's modules offer Shino's
    ├── requests-for-shino.md
    └── product-walkthrough.md
```

## Features

- **Sign-in:** UM SPeCTRUM (Moodle) accounts; courses and enrolments sync from Moodle.
- **Face enrolment:** students enrol their face in the app; an admin or lecturer reviews unclear ones.
- **Attendance:** the door camera records Present or Late, students can flag "I'm here" when not recognised, lecturers confirm, excuse or edit, and attendance syncs to Moodle.
- **AI Assistant:** students ask about their course materials with cited answers that open the source file, and generate summaries, flashcards and practice questions. Lecturers see their materials' status and the most-asked topics, ask their own materials, and get a "before next class" note.
- **Quizzes and analytics:** Shino's modules (5, 6, 7).
- **Admin (browser):** accounts, Moodle sync, door cameras, audit log.
