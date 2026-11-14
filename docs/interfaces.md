# Interfaces Yew Sing's modules give Shino's modules

This page lists the Python functions Shino's modules may call to read data Yew Sing's modules
own. It is plain English on purpose: the code is the source of truth, this page says what to
expect from it. Fields may be added; names are not changed without a note in
`docs/requests-for-shino.md`.

Three interfaces so far:

- **Attendance read interface for Module 7 (FR-313)** — below.
- **Course knowledge base retrieval for Module 6 (FR-814, T88)** — below.
- **Notification hook for Module 2 (FR-406, T44)** — below.
- **Participation read interface for Module 7 (FR-509)** — below.

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
email). Until M2 replaces or wraps `emit`, it **logs only**. It **never raises**, so a
notification can never fail the request that raised it. `user_ids` are `users.id`, not
`students.id` or `lecturers.id`. The payload is never logged: it holds names and matric numbers
(NFR-02 / PDPA).

### Events currently raised

| Event | To | Payload fields |
|---|---|---|
| `attendance.recorded` | the student | `session_id`, `course_code`, `course_name`, `status` (`present` \| `late`), `detected_at`, `source` (`recognition` \| `student_flag`), `message` |

`attendance.flagged` and `face_enrolment.pending_review` / `face_enrolment.result` (R1 in
`docs/requests-for-shino.md`) are not raised through `emit` yet.

### Live channels (until M2)

The apps can also listen on WebSockets directly:

- Lecturers: `/ws/sessions/{id}?token=<access JWT>` — the session's live feed (`attendance_update`,
  `attendance_flagged`, `attendance_flag_resolved`, `session_closed`, ...). Only the lecturer who
  teaches the class may connect.
- Students: `/ws/me?token=<access JWT>` — the student's own events (`connected`,
  `attendance_recorded`, `attendance_flag_resolved`). Only an active student may connect; anyone
  else is closed with code 1008.
## Participation read interface for Module 7 (FR-509)

**File:** `backend/app/services/participation_read.py`

Read-only aggregation of a student's (or a class's) interaction participation across the
five interaction write tables (`interaction_questions`, `interaction_poll_votes`,
`interaction_live_question_responses`, `interaction_reactions`, `interaction_idu_signals`).
All counts are scoped through `interaction_sessions → class_occurrences → courses`, so a
course result joins all its classes (lectures and tutorials) together.

This is the FR-509 → FR-701 handover: M7's per-student engagement indicators are built from
these functions. The interface does **not** check who is asking — callers must enforce NFR-04
(the user may only see their own class's students) before calling it, because it returns
names and matric numbers.

### How to call it

```python
from app.services.participation_read import (
    get_student_participation_per_course,
    get_student_participation_per_session,
    get_class_participation_per_session,
    list_class_sessions_with_counts,
    student_has_participated_in_course,
)

summary = await get_student_participation_per_course(db, student_id, course_id)
# summary: {questions, votes, responses, reactions, idu_signals, idu_students,
#           student_id, course_id}
```

The functions take an `AsyncSession` and read only; they never commit.

### Rules

- An occurrence counts only once per interaction type per student (e.g. one vote per
  student per poll, enforced by `uq_interaction_poll_votes_poll_student`).
- `idu_signals` counts signal rows; `idu_students` counts **distinct** students, so a
  student who signals repeatedly still counts once (FR-508).
- Unknown course, student or occurrence ids return empty lists / zeros, never errors.
- Dates are not filtered here — the caller passes occurrence/course ids directly.

### Functions

| Function | Arguments | Returns | Notes |
|---|---|---|---|
| `get_student_participation_per_course` | `db, student_id, course_id` | `dict` — totals across all of the course's sessions | keys: questions, votes, responses, reactions, idu_signals, idu_students, student_id, course_id |
| `get_student_participation_per_session` | `db, student_id, occurrence_id` | `dict` — totals in one occurrence | keys as above plus occurrence_id |
| `get_class_participation_per_session` | `db, occurrence_id` | `dict` — class-level totals in one occurrence | idu_students is distinct students |
| `list_class_sessions_with_counts` | `db, course_id` | `list[dict]` — one entry per occurrence with counts and label | ordered by occurrence id |
| `student_has_participated_in_course` | `db, student_id, course_id` | `bool` — any participation record in the course | cheap existence check |

### No permission checks

The interface does not check who is asking. Callers must check the user may see the course
(NFR-04) before calling it, because it returns names and matric numbers.

### Stability

Fields may be added, but never renamed or removed without a note in
`docs/requests-for-shino.md`.


## Quiz read interface for Module 7 / Module 8 (FR-612, FR-613, FR-614)

**File:** `backend/app/services/quiz_read.py`

Read-only aggregation of quiz results: per student per question (correct/score, question
topic + source material) and whether the student has an active graded attempt in the
course — scoped through `quiz_attempts → quiz_questions → quizzes → courses`. This is the
FR-612 → FR-701 and FR-614 → FR-820–FR-824 (M8, Yew Sing) handover.

The interface does **not** check who is asking — callers must enforce NFR-04 before calling
it.

### How to call it

```python
from app.services.quiz_read import (
    quiz_result_per_student_per_question,
    quiz_results_per_student,
    student_has_active_graded_attempt_in_course,
)

per_q = await quiz_result_per_student_per_question(db, course_id, student_id)
# each entry: {quiz_id, question_id, question, type, topic, source_material_id,
#              correct, score, answered, has_active_graded_attempt_in_course, ...}
```

The functions take an `AsyncSession` and read only; they never commit.

### Rules

- Only `published` quizzes are considered.
- `correct` is populated for `mcq` questions (student's answer == `correct_answer`);
  `short_answer` questions have `correct` = null until scored.
- `score` is the stored answer score (null for unscored short answers).
- `has_active_graded_attempt_in_course` is true when the student has a `started` attempt
  on a published quiz in the course — used by M8's quiz lock.
- Unknown course or student ids return empty lists / empty dicts, never errors.

### Functions

| Function | Arguments | Returns | Notes |
|---|---|---|---|
| `quiz_result_per_student_per_question` | `db, course_id, student_id` | `list[dict]` | per attempted question: correct, score, topic, source_material_id, answered, plus `has_active_graded_attempt_in_course` |
| `quiz_results_per_student` | `db, course_id, student_id` | `dict` | per-quiz attempts with scores + `average_score` across graded quizzes |
| `student_has_active_graded_attempt_in_course` | `db, student_id, course_id` | `bool` | started attempt on a published quiz in the course (M8 quiz lock) |

### No permission checks

The interface does not check who is asking. Callers must check the user may see the course
(NFR-04) before calling it.

### Stability

Fields may be added, but never renamed or removed without a note in
`docs/requests-for-shino.md`.
