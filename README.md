# SmartClass

A classroom management system featuring face recognition attendance, quiz management, and participation analytics — built for Universiti Malaya FYP1.

## Apps

| App | Type | Description | Directory |
|-----|------|-------------|-----------|
| Admin Dashboard | Web (React + Vite) | Manage users, enrollment, face data, audit logs | `frontend/admin/` |
| Student App | Mobile (React Native + Expo) | Attendance and participation — runs on real phone | `mobile/student/` |
| Lecturer App | Mobile (React Native + Expo) | Sessions, quizzes, analytics — runs on real phone | `mobile/lecturer/` |

## Tech Stack

**Admin web:** React 18 + Vite 5, Tailwind CSS 3, React Context API

**Mobile apps:** React Native + Expo SDK 54, React Navigation 6, AsyncStorage

**Backend:** FastAPI + SQLAlchemy 2 (async) + PostgreSQL + pgvector, InsightFace, JWT auth, Docker Compose

---

## How to Run

### Prerequisites

- [Node.js](https://nodejs.org/) (v18+)
- [Python](https://www.python.org/) 3.10+
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (for PostgreSQL)
- [Expo Go](https://expo.dev/go) on your phone (for the mobile apps)

---

### 1. Start the Database

```bash
cd backend
docker compose up -d
```

---

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` if needed. Skip if `.env` already exists.

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
uvicorn app.main:app --reload --host 0.0.0.0
```

API at **http://localhost:8000** · Docs at **http://localhost:8000/docs**

> `--host 0.0.0.0` is required so the mobile apps on a physical device can reach the backend over WiFi.

---

### 5. Start the Face Recognition Worker

Open a **separate terminal**:

```bash
cd backend/face_worker
pip install -r requirements.txt
python worker.py
```

---

### 6. Start the Admin Web App

```bash
cd frontend/admin
npm install && npm run dev
# → http://localhost:5173
```

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
├── frontend/
│   └── admin/          # Web admin dashboard
├── mobile/
│   ├── lecturer/       # React Native lecturer app (Expo)
│   └── student/        # React Native student app (Expo)
└── docs/
    ├── requirements/
    └── use-cases/
```

## Features

- **Attendance** — Face recognition-based check-in, live session management
- **Quizzes** — Create and push quizzes, live results, per-student breakdown
- **Analytics** — Attendance rates, at-risk students, participation tracking
- **Environment** — Live classroom sensor readings, actuator control
- **Admin** — User management, face data enrollment, face review queue, audit logs
