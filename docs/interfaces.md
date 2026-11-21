# Interfaces Yew Sing's modules give Shino's modules

This page lists the Python functions Shino's modules may call to read data Yew Sing's modules
own. It is plain English on purpose: the code is the source of truth, this page says what to
expect from it. Fields may be added; names are not changed without a note in
`docs/requests-for-shino.md`.

Three interfaces so far:

- **Attendance read interface for Module 7 (FR-313)** — below.
- **Course knowledge base retrieval for Module 6 (FR-814, T88)** — below.
- **Notification hook for Module 2 (FR-406, T44)** — below.

---

## Attendance read interface for Module 7 (FR-313)

`app/services/attendance_read.py` gives M7 attendance records, attendance rates and
consecutive absences, so M7 does not have to count `AttendanceRecord` rows itself.

### How to call it

```python
from app.services.attendance_read import course_rates, consecutive_absences

@router.get("/lecturer/analytics/...")
async def handler(course_id: int, db: AsyncSession = Depends(get_db),
                  actor: User = Depends(require_role("lecturer"))):
    # check access first (NFR-04): ensure_teaches_occurrence / your own course check
    rates = await course_rates(db, course_id)
```

The functions take an `AsyncSession` and read only; they never commit.

### Rules

These are the same rules the student app and the lecturer reports use (FR-308):

- Only **closed** sessions count. Open, scheduled, cancelled and `needs_confirmation` sessions
  are left out.
- A student enrolled in a class with no record in one of its closed sessions is **absent**.
- **Late** counts as attended. **Excused** is left out of the rate.
- The rate is `(present + late) ÷ (closed − excused)` as a percentage with one decimal.
  When nothing counts (`closed − excused` is 0) the rate is `None`, not 0.
- Enrolment is per class (occurrence), so a tutorial session lists only that group's students.
  A course result joins all its classes (lecture and tutorials) together, the same way the
  student app groups a course.
- Dates are the MYT date of the class. Date ranges are inclusive.

### Functions

| Function | Arguments | Returns | Order |
|---|---|---|---|
| `course_records` | `db, course_id, from_date=None, to_date=None` | `list[AttendanceRow]` — every enrolled student in every closed session of the course | oldest session first, then matric no |
| `student_records` | `db, student_id, course_id=None, from_date=None, to_date=None` | `list[AttendanceRow]` — one student in every closed session of their classes | oldest first |
| `course_rates` | `db, course_id, from_date=None, to_date=None` | `list[AttendanceRate]` — one row per enrolled student | matric no |
| `student_rates` | `db, student_id, from_date=None, to_date=None` | `list[AttendanceRate]` — one row per course | course code |
| `consecutive_absences` | `db, course_id, min_current=0` | `list[AbsenceStreak]` — one row per enrolled student with `current >= min_current` | highest `current` first, then matric no |
| `absence_streak` | `statuses: list[str]` (oldest first) | `tuple[int, int]` — `(current, longest)` | pure helper, no DB |

A date range whose `from_date` is after `to_date` raises `ValueError`. Unknown course or
student ids return an empty list.

### Returned fields

`AttendanceRow` — one student's status in one closed session:

| Field | Meaning |
|---|---|
| `session_id` | attendance session id |
| `occurrence_id` | class (occurrence) id |
| `class_type` | `LECTURE` or `TUTORIAL` |
| `class_label` | the class's label, or `None` |
| `course_id`, `course_code` | the course |
| `student_id`, `matric_no`, `name` | the student (`students.id`, matric no, full name) |
| `date` | MYT date of the class |
| `starts_at` | session start time (`starts_at`, else `opened_at`) |
| `status` | `present`, `late`, `excused` or `absent` |
| `detected_at` | when the record was detected, or `None` |
| `overridden` | `True` when a lecturer changed the status |

`AttendanceRate` — one student's counts and rate for one course:

| Field | Meaning |
|---|---|
| `student_id`, `matric_no`, `name` | the student |
| `course_id`, `course_code`, `course_name` | the course |
| `present`, `late`, `excused`, `absent` | session counts |
| `closed_sessions` | all four counts added together |
| `counted_sessions` | `closed_sessions - excused` |
| `rate` | percentage 0–100 with one decimal, or `None` when nothing counts |

`AbsenceStreak` — consecutive absences of one student in one course:

| Field | Meaning |
|---|---|
| `student_id`, `matric_no`, `name` | the student |
| `course_id`, `course_code` | the course |
| `current` | absences in a row up to the latest closed session (0 if they last attended) |
| `longest` | longest run of absences so far |
| `last_attended` | date of the latest present/late session, or `None` if never |

### Statuses

The four statuses are `present | late | excused | absent` (`ATTENDANCE_STATUSES` in
`app/models/attendance.py`). `ATTENDED_STATUSES` is `("present", "late")`. The old
`unidentified` status no longer exists.

### No permission checks

The interface does not check who is asking. Callers must check the user may see the course
(NFR-04) before calling it, because it returns names and matric numbers.

### Stability

Fields may be added, but never renamed or removed without a note in
`docs/requests-for-shino.md`.

### Why switch

`app/routers/analytics.py` (M7) counts only `present` (around lines 75–76, 151–152 and 206) and
still treats the removed `unidentified` status as absent. Since T30, Late counts as attended
(FR-308), so in M7 Late students look absent and its rate disagrees with the student app's
`/student/me/attendance/courses`. Suggested fix: build the counts from `student_rates`,
`course_rates` or `course_records` instead of counting `AttendanceRecord` rows directly.
Yew Sing did not edit `analytics.py` because M7 belongs to Shino.
(2026-11-21: `analytics.py` was removed in plan-shino.md S02; the rebuilt M7 reads `attendance_read`.)

---

## Module 8 → Module 6 — course knowledge base retrieval (FR-814)

**File:** `backend/app/services/kb/retrieval_api.py`

```python
async def search(course_id: int, query: str, k: int = 8) -> list[Passage]
```

Returns the top-k passages for `query` within one course. Module 6 (AI quiz generation)
uses this to draft questions from a course's materials without parsing them itself.

Each `Passage` (from `app.services.kb.search`) carries its source so citations and quiz
question references can point at the material:

| Field | Meaning |
|---|---|
| `material_id`, `title` | the source file |
| `section_name` | the Moodle section (e.g. "Week 3") |
| `location_type` | `page`, `slide` or `section` |
| `location_start`, `location_end` | the page/slide/section number(s) |
| `heading`, `text` | the passage itself |
| `score`, `vector_similarity` | retrieval confidence (RRF score, cosine similarity) |

The search is hybrid (vector + keyword) and is scoped to `course_id`, so Module 6 gets
only the materials of the course it is generating for. The function owns its own
database session; the caller passes no session.

---

## Notification hook for Module 2 (FR-406, T44)

**File:** `backend/app/services/notify.py`

```python
async def emit(event: str, user_ids: Iterable[int], payload: dict) -> None
```

Yew Sing's modules raise a notification event here and Module 2 delivers it (push, in-app or
email). Since S10 it **stores an in-app notification** per recipient (`m2_notifications`, see
"Module 2 notification events" below); push/email follow in S13/S14. It **never raises**, so a
notification can never fail the request that raised it. `user_ids` are `users.id`, not
`students.id` or `lecturers.id`. The payload is never logged: it holds names and matric numbers
(NFR-02 / PDPA).

### Events currently raised

| Event | To | Payload fields |
|---|---|---|
| `attendance.recorded` | the student | `session_id`, `course_code`, `course_name`, `status` (`present` \| `late`), `detected_at`, `source` (`recognition` \| `student_flag`), `message` |

`attendance.flagged` and `face_enrolment.pending_review` / `face_enrolment.result` (R1 in
`docs/requests-for-shino.md`) are not raised through `emit` yet.

### Module 2 notification events (S10, Shino)

`emit` calls `app/services/notifications/store.py::deliver`, which opens its **own** DB session, so
call `emit` after your commit (an `after_commit` callback). The event registry is
`app/services/notifications/registry.py`:

- The **priority** comes from the event type only (FR-207); a `priority` in the payload is ignored.
- `title`, `message`, `link` in the payload override the defaults (FR-205). Otherwise they are
  filled from the payload fields below; a missing field falls back to fixed text (link: none).
- `link` must be an app-relative path (`/quizzes/7`); external URLs, `//`, `..`, schemes or odd
  characters are rejected and **nothing is stored** (logged as `UnsafeLink`).
- **De-duplication (FR-216):** same event + recipient + subject inside the event's window is
  dropped. Without the subject fields, identical title/message/link count as the same subject.
- Unknown events and unknown recipients are logged and skipped. Only the rendered title,
  message and link are stored, never the payload.

| Event | Priority | Payload fields used | Subject | Window |
|---|---|---|---|---|
| `attendance.recorded` | general | `session_id`, `course_code`, `status` | `session_id` | 24 h |
| `attendance.flagged` | important | `session_id`, `course_code`, `flag_id` | `flag_id` | 24 h |
| `face_enrolment.pending_review` | important | `enrolment_id` | `enrolment_id` | 24 h |
| `face_enrolment.result` | important | `enrolment_id`, `status` | `enrolment_id` + `status` | 24 h |
| `quiz.published` | important | `quiz_id`, `quiz_title`, `course_code` | `quiz_id` | 24 h |
| `quiz.deadline_reminder` | urgent | `quiz_id`, `quiz_title`, `remaining`, `reminder` | `quiz_id` + `reminder` | 3 d |
| `quiz.graded` | important | `quiz_id`, `quiz_title` | `quiz_id` | 24 h |
| `game.started` | urgent | `game_id`, `quiz_title`, `course_code` | `game_id` | 6 h |
| `poll.started` | general | `poll_id`, `attendance_session_id`, `course_code` | `poll_id` | 6 h |
| `confusion.spike` | urgent | `attendance_session_id`, `spike_id`, `course_code` | session + `spike_id` | 6 h |
| `at_risk.alert` | important | `alert_id`, `course_id`, `course_code` | `alert_id` | 30 d |
| `moodle.deadline_reminder` | important | `moodle_event_id`, `title`, `course_code`, `remaining`, `reminder` | event + `reminder` | 3 d |
| `announcement.posted` | important | `announcement_id`, `title`, `message` | `announcement_id` | 24 h |

### Notification feed API (S11, Shino)

Any signed-in active user (student, lecturer, admin); only the caller's own notifications. Someone
else's (or a missing) id → 404. Item: `{id, event, priority, title, message, link, read, read_at, created_at}`.

| Endpoint | Returns |
|---|---|
| `GET /notifications?limit=20&cursor=` | `{items, next_cursor, unread_count}`: newest first (`created_at`, then `id`); `limit` 1–100; pass `next_cursor` back for older items, `null` = last page; bad cursor → 422 |
| `GET /notifications/priority` | `{items, unread_count}`: unread urgent first, then important, newest first within each, at most 50 (FR-208) |
| `POST /notifications/{id}/read` | `{notification, unread_count}`; idempotent, keeps the first `read_at` |
| `POST /notifications/read-all` | `{marked, unread_count}` |

### Live channels (until M2)

The apps can also listen on WebSockets directly:

- Lecturers: `/ws/sessions/{id}?token=<access JWT>` — the session's live feed (`attendance_update`,
  `attendance_flagged`, `attendance_flag_resolved`, `session_closed`, ...). Only the lecturer who
  teaches the class may connect.
- Students: `/ws/me?token=<access JWT>` — the student's own events (`connected`,
  `attendance_recorded`, `attendance_flag_resolved`). Only an active student may connect; anyone
  else is closed with code 1008.
