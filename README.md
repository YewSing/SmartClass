# SmartClass

A classroom management system featuring face recognition attendance, quiz management, and participation analytics — built for Universiti Malaya FYP1.

## Apps

| App | Description | Directory |
|-----|-------------|-----------|
| Admin Dashboard | Web UI for managing users, enrollment, and face data | `frontend/admin/` |
| Student App | Mobile-sized UI for attendance and participation | `frontend/student/` |
| Lecturer App | Mobile-sized UI for sessions, quizzes, and analytics | `frontend/lecturer/` |

## Tech Stack

**Frontend:** React 18 + Vite 5, Tailwind CSS 3, React Context API

**Backend:** FastAPI + SQLAlchemy 2 (async) + PostgreSQL + pgvector, InsightFace, JWT auth, Docker Compose

---

## How to Run

### Prerequisites

- [Node.js](https://nodejs.org/) (v18+)
- [Python](https://www.python.org/) 3.10+
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (for PostgreSQL)

---

### 1. Start the Database

```bash
cd backend
docker compose up -d
```

Starts PostgreSQL + pgvector in the background.

---

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` if you need to change the database URL or secret key. Skip this step if `.env` already exists.

---

### 3. Install Backend Dependencies & Run Migrations

```bash
cd backend
pip install -r requirements.txt
alembic upgrade head
python scripts/seed.py
```

`seed.py` creates demo admin, lecturer, and student accounts.

---

### 4. Start the API Server

```bash
cd backend
uvicorn app.main:app --reload
```

API runs at **http://localhost:8000**. Docs at **http://localhost:8000/docs**.

---

### 5. Start the Face Recognition Worker

Open a **separate terminal**:

```bash
cd backend/face_worker
pip install -r requirements.txt
python worker.py
```

The worker handles real-time face matching during attendance sessions.

---

### 6. Start the Frontend Apps

Each app runs independently. Open a new terminal for each:

```bash
# Admin dashboard → http://localhost:5173
cd frontend/admin
npm install
npm run dev

# Student app → http://localhost:5174
cd frontend/student
npm install
npm run dev

# Lecturer app → http://localhost:5175
cd frontend/lecturer
npm install
npm run dev
```

> All three frontends can run simultaneously on their respective ports.

---

## Project Structure

```
SmartClass/
├── backend/
│   ├── app/            # FastAPI application
│   ├── alembic/        # DB migrations
│   ├── face_worker/    # Face recognition worker process
│   ├── scripts/        # Seed scripts
│   └── docker-compose.yml
└── frontend/
    ├── admin/
    │   └── src/
    │       ├── components/   # UI primitives and layout
    │       ├── context/      # AdminContext (global state)
    │       ├── data/         # Mock data
    │       ├── services/     # API layer
    │       └── views/        # Page components
    ├── student/
    │   └── src/
    │       ├── components/
    │       ├── context/      # StudentContext
    │       ├── data/
    │       ├── services/     # API layer
    │       └── views/
    └── lecturer/
        └── src/
            ├── components/
            ├── context/      # LecturerContext
            ├── data/
            ├── services/     # API layer
            └── views/
```

## Features

- **Attendance** — Face recognition-based check-in, session management
- **Quizzes** — Create quizzes, live results, breakdowns
- **Analytics** — Participation tracking, classroom environment monitoring
- **Admin** — User management, face data enrollment, audit logs
