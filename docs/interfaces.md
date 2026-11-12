# Interfaces Yew Sing's modules give Shino's modules

This page lists the Python functions Shino's modules may call to read data Yew Sing's modules
own. It is plain English on purpose: the code is the source of truth, this page says what to
expect from it. Fields may be added; names are not changed without a note in
`docs/requests-for-shino.md`.

One interface so far:

- **Attendance read interface for Module 7 (FR-313)** — below.
- A retrieval interface for Module 6 (T88) will be added later.

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
