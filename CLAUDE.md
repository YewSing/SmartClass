# SmartClass — Claude Code Guide

## Project Overview
SmartClass is a classroom management system for UM (Universiti Malaya) with face recognition-based attendance tracking, quiz management, and participation analytics. It has three separate React frontends — admin, student, and lecturer.

## Repo Structure
```
SmartClass/
└── frontend/
    ├── admin/      # Web dashboard for administrators
    ├── student/    # Mobile-sized UI for students
    └── lecturer/   # Mobile-sized UI for lecturers
```

Each app is fully independent with its own `package.json`, `node_modules`, and `vite.config.js`.

## Tech Stack
- **Framework:** React 18 + Vite 5
- **Styling:** Tailwind CSS 3
- **State:** React Context API (no Redux)
- **No backend yet** — all data is mocked via `src/data/mockData.js` and `src/services/api.js`

## Running Each App
Each app must be run independently from its own directory:
```bash
cd frontend/admin    && npm install && npm run dev
cd frontend/student  && npm install && npm run dev
cd frontend/lecturer && npm install && npm run dev
```
Default Vite ports: admin → 5173, student → 5174, lecturer → 5175 (may vary).

## App-Specific Notes

### Admin (`frontend/admin/`)
- Full web dashboard (not mobile-constrained)
- Views: Dashboard, Users, Students, Lecturers, Enrollment, FaceData, AuditLog, Login
- State managed in `src/context/AdminContext.jsx`
- Mock users in `src/data/users.js`

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

## Key Prototype Files
- `frontend/lecturer_app_prototype_v3_5_1.html` — standalone HTML prototype for lecturer app
- `frontend/student_app_prototype_v2.html` — standalone HTML prototype for student app

These are reference prototypes; the actual apps are in the subdirectories above.
