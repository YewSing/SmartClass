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

**Status / reply:** open

---

## R2 — Use the attendance read interface in M7 (M7) — opened 2026-11-12

**Why:** since T30 attendance has four statuses (present, late, excused, absent) and Late counts as
attended (FR-308). `routers/analytics.py` still counts only `present` and the old `unidentified`, so
M7's rates disagree with the student app.

**What Yew Sing's side provides:** `app/services/attendance_read.py` (FR-313): records per course or
student, rates, and consecutive absences, described in `docs/interfaces.md`.

**Needed from M7:** read attendance through those functions instead of counting `AttendanceRecord`
rows directly. Tell Yew Sing if M7 needs anything the interface doesn't give.

**Status / reply:** accepted (Shino, 2026-11-21). The old `routers/analytics.py` was removed in
plan-shino.md S02; the rebuilt M7 (S60) reads attendance only through `attendance_read`.

---

## Note for Yew Sing — M2 hook in Moodle login (FR-203) — 2026-11-22

Shino's S16 adds two small, additive changes to M1 so the dashboard can show Moodle announcements
and deadlines (FR-203): `MoodleProfile.moodle_token` (the user's own token, hidden from `repr`, set
in `moodle_auth.authenticate`) and one call in `POST /auth/moodle-login` after its commit,
`moodle_snapshot.refresh_on_login(user.id, profile)`, which clears the token and never raises. Login
behaviour is unchanged (your `test_moodle_login.py` passes unchanged). `configure_moodle.php` also
allows `mod_forum_get_forums_by_courses`, `mod_forum_get_forum_discussions` and
`core_calendar_get_calendar_events` in the `smartclass` service. Details in `docs/interfaces.md`.

**Status / reply:** open (for information)

---

## Note for Yew Sing — End class / +15 min moved to the lecturer Dashboard — 2026-11-22

On Shino's instruction, the live session screen (`AttendanceDetail.jsx`, your T38) no longer has End class / +15 min: they are on the lecturer Dashboard's session card (`home-session-end`, `home-session-end-confirm`, `home-session-extend`), calling the same `doCloseSession` / `doExtendSession`. The card also drops its Live session button once a class is open; the Attendance card on Home opens the live screen. Your `e2e-web/live-session.spec.js`, `e2e/live-session.yaml` and `e2e/flag-alert.yaml` now press the Home buttons with the same checks (details in progress-shino.md TEST-CHANGE lines). FR-315 behaviour is unchanged.

**Status / reply:** open (for information)

---

## Note for Yew Sing — one class slot = one session (M3 change) — 2026-11-23

On Shino's instruction (plan-shino.md S38a), M3 now treats one timetable slot as one class session:

- `session_schedule.start_now`: inside today's slot (from the early-open time until the scheduled end, or the session's `ends_at` if later), Start now on an ended session of that slot (`closed` / `needs_confirmation`; the `schedule` row first, else the newest `manual` row started in the slot) **reopens it** instead of adding a `manual` row: same id, `closed_at` cleared, records kept, `starts_at` kept (Late still counts from the class start), `ends_at` = the later of its current value and the scheduled end (or now + duration), audit `SESSION_REOPEN`. The Moodle sync state is cleared while it runs (`moodle_session_id` kept); the next close marks Absent again and queues the sync once, so Moodle gets the changed marks in the same Moodle session. Outside the slot, on another day, or for a class without a schedule nothing changes.
- `attendance_service.mark_present`: in an open session, the Absent a close wrote (no detection, no override, no flag, same test as `attendance_flags._absent_from_close`) becomes Present/Late on recognition and returns `was_new=True` (so the usual broadcasts fire). Overrides and flags are never changed. `recognition_service.recognise_frame` no longer counts such an Absent as "already recorded", and `attendance_flags.create_flag` lets that student flag (`confirm_flag` already accepted it).
- `start_now` checks again for an open session after locking the slot's rows, so two Start now calls at once can't open two sessions.
- Tests: new `tests/test_session_reopen.py`. Three of your tests needed a *second* session the same day (`test_char_sessions::test_closed_occurrence_can_be_reopened`, `test_char_attendance::test_occurrence_csv_export_with_date_range`, `test_attendance_statuses::test_occurrence_export_letters_and_rate`); on a Monday 07:45–10:00 they would now get the reopened one, so they pin Start now to 23:00 today. Expectations are unchanged (TEST-CHANGE lines in progress-shino.md).

**Status / reply:** open (for information)

---

## Note for Yew Sing — quiz read interface for Module 8 (FR-820–FR-824) — 2026-11-26

**FR-820–FR-824 can now use Module 6:** `app/services/quiz_read.py` (S47; `docs/interfaces.md` "Quiz read interface for Modules 7 and 8"). M8 is unchanged; the stub `kb/integrations.get_active_attempt` is yours to replace.

- FR-820: `await quiz_read.has_active_graded_attempt(db, student_id, course_id)` → bool. Your stub has no `db` parameter, but both its callers (`assistant.py`, `chat_tools.py`) only test it for None. It is false from the deadline on; game quizzes never count.
- FR-821–FR-823: `quiz_read.student_answers(db, student_id, course_id, audience="student")`: the student's answers with topic, source (file + page/slide), quiz type, the correct answer and the explanation. `audience="student"` leaves out what the lecturer hasn't released (FR-618, NFR-41), so anything a student will see must use it.
- FR-824: `quiz_read.course_answers(db, course_id)`: the whole class, for lecturers only.
- They check no permissions (NFR-04): check the caller first, as with `attendance_read`.

**Status / reply:** open

---

## Open issue already raised

- `GET /lecturer/analytics` (M7) lets any lecturer read any class's analytics (NFR-04). Details
  and the suggested fix are under Module 7 in `docs/requirements/functional-requirements.md`.
  Reply (Shino, 2026-11-21): the endpoint was removed in plan-shino.md S02; the rebuilt class
  views (S61) check `ensure_teaches_occurrence` (FR-714).
