# Requests for Shino (Modules 2, 5, 6, 7)

Things Yew Sing's modules (1, 3, 4, 8) need from Shino's modules. Each request says what is
needed, what Yew Sing's side already provides, and its status. Shino (or her Claude session):
please read this when you pull `main`, and reply by editing the **Status / reply** line of the
request, or by message to Yew Sing.

---

## After pulling `main` (merge of 2026-11-14)

This merge brings Yew Sing's attendance device work (T42-T46b) and the Module 8 AI Assistant
(T90-T102). None of it changes Modules 2, 5, 6 or 7. To run it:

1. `cd backend && pip install -r requirements.txt` (InsightFace and onnxruntime are now in it).
2. `alembic upgrade head` (4 new migrations).
3. Check `backend/.env` against `backend/.env.example`: the database is on port **5433**,
   `INTERNAL_API_KEY` is no longer used, and `YOUTUBE_API_KEY` is new and optional. The backend
   starts without Moodle, LLM or YouTube keys; those features just stay off.
4. No new npm packages. Restart `uvicorn` after pulling (on Windows `--reload` can miss changes).

Removed: the old `frontend/admin` site (admin pages are now in the lecturer web app), the
`face_worker` service and `/internal/*` routes, and the old `/student/assistant/summaries` and
`/student/assistant/study-tools` endpoints (study tools now run inside a chat:
`POST /student/assistant/sessions/{id}/tools`). Setup steps are in `README.md`.

---

## R1 — Notifications for face enrolment (M2) — opened 2026-11-10

**Why:** a student self-enrols their face (FR-110). If the automatic checks fail, the submission
waits for a lecturer's review (FR-113). FR-114 says the student is told the result.
Notifications are Module 2.

**Needed from M2:** deliver two events (push, in-app or email, whichever M2 supports):

| Event | To | When | Payload |
|---|---|---|---|
| `face_enrolment.pending_review` | lecturers of the student's courses | a submission needs review | `{enrolment_id, student_name, matric_no, courses}` |
| `face_enrolment.result` | the student | a lecturer/admin decided | `{enrolment_id, status: "active" \| "rejected", reason}` |

**What Yew Sing's side provides:** `app/services/notify.py` with
`emit(event: str, user_ids: list[int], payload: dict)` (PLAN.md T44). Until M2 hooks in, it only
logs and the apps refresh their own screens. M2 replaces or wraps `emit` to deliver. The same
hook will carry `attendance.recorded` (student) and `attendance.flagged` (lecturer), listed in
`docs/requirements/functional-requirements.md` under Module 2.
Built in T44 (2026-11-13): `emit` exists, logs only, and raises `attendance.recorded`; see
`docs/interfaces.md`.

**Question for Shino:** is `emit(event, user_ids, payload)` a shape that works for M2? If you
prefer a different one (e.g. with a priority level: urgent / important / general), say so here
before T44 is built.

**Status / reply:** resolved — `emit(event, user_ids, payload, priority="general")` is the single
M2 entry point (in `app/services/notify.py`). `priority` is `urgent` | `important` | `general`
(default `general`), so existing T44 call sites keep working; `urgent`/`important` go through
delivery channels (S11), `general` is feed-only. It carries `attendance.recorded` → student,
`attendance.flagged` → lecturer, `face_enrolment.result` → student, `face_enrolment.pending_review`
→ lecturers, and `quiz.published` → lecturer (FR-211). Shino built `notify.emit` to the T44 spec
because T44 was still unticked when S10 started; noted in PROGRESS-SHINO.md.

---

## R2 — Use the attendance read interface in M7 (M7) — opened 2026-11-12

**Why:** since T30 attendance has four statuses (present, late, excused, absent) and Late counts as
attended (FR-308). `routers/analytics.py` still counts only `present` and the old `unidentified`, so
M7's rates disagree with the student app.

**What Yew Sing's side provides:** `app/services/attendance_read.py` (FR-313): records per course or
student, rates, and consecutive absences, described in `docs/interfaces.md`.

**Needed from M7:** read attendance through those functions instead of counting `AttendanceRecord`
rows directly. Tell Yew Sing if M7 needs anything the interface doesn't give.

**Status / reply:** resolved — `GET /lecturer/analytics` now counts through
`app/services/attendance_read.py` (`course_records`, `StatusCounts`): Late counts as attended,
Excused left out (FR-308), so M7's rates match the student app. The NFR-04 ownership hole is
closed (`ensure_teaches_occurrence` after the 404 check → 403 for a lecturer who doesn't teach
the class). The dead student endpoints `/student/me/attendance[/summary]` are removed (the app
uses T32's `/student/me/attendance/courses` since T39); see the `TEST-CHANGE:` note in
PROGRESS-SHINO.md.

---

## Open issue already raised

- `GET /lecturer/analytics` (M7) lets any lecturer read any class's analytics (NFR-04). Details
  and the suggested fix are under Module 7 in `docs/requirements/functional-requirements.md`.
