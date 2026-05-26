# SmartClass

A classroom management system featuring face recognition attendance, quiz management, and participation analytics — built for Universiti Malaya FYP1.

## Apps

| App | Description | Directory |
|-----|-------------|-----------|
| Admin Dashboard | Web UI for managing users, enrollment, and face data | `frontend/admin/` |
| Student App | Mobile-sized UI for attendance and participation | `frontend/student/` |
| Lecturer App | Mobile-sized UI for sessions, quizzes, and analytics | `frontend/lecturer/` |

## Tech Stack

- React 18 + Vite 5
- Tailwind CSS 3
- React Context API

## Getting Started

Each app runs independently. From the repo root:

```bash
# Admin dashboard
cd frontend/admin
npm install
npm run dev

# Student app
cd frontend/student
npm install
npm run dev

# Lecturer app
cd frontend/lecturer
npm install
npm run dev
```

> Note: All three can run simultaneously on different ports (default: 5173, 5174, 5175).

## Project Structure

```
SmartClass/
└── frontend/
    ├── admin/
    │   └── src/
    │       ├── components/   # UI primitives and layout
    │       ├── context/      # AdminContext (global state)
    │       ├── data/         # Mock data
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
