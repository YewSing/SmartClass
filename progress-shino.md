# PROGRESS — Shino's modules (M2, M5, M6, M7)

Companion to [plan-shino.md](plan-shino.md). It follows the structure and evidence standard of [PROGRESS.md](PROGRESS.md), but does not alter Yew Sing's log.

## Current baseline — 2026-11-20

- M2, M5, and M6 backend implementations do not yet exist. Existing lecturer quiz, student participation, and parts of analytics are legacy mock UI and must be replaced, not extended as production state.
- M7 has a partial legacy endpoint/UI. It currently risks exposing another lecturer's analytics and calculates attendance incorrectly because it does not use the shared attendance read interface.
- M3 is complete and owns `AttendanceSession`, session open/extend/close, attendance finalisation, Moodle sync, and the attendance websocket. These are stable integration points, not Shino rewrite targets.
- Current lecturer UI places `+15 min` and `End class` in `AttendanceDetail`; the required S01 move places them in Dashboard's top session card. `AttendanceDetail` will retain roster, override, history, confirmation, and SPeCTRUM sync responsibilities.

## Agreed shared-session behaviour

| Lecturer action on Dashboard top card | Attendance (M3) | Interaction (M5) |
|---|---|---|
| Start now | Opens the canonical `AttendanceSession` | Becomes available for that same session; no second session is created |
| Extend | Updates the canonical session end time | Remains available for the same extended window |
| End class | Finalises attendance and starts Moodle-sync flow | Immediately closes active interaction work and rejects new events |

M5 will store a link to `attendance_session_id` and read the attendance session state. It will not modify M3 session lifecycle code.

## Interfaces consumed

- M2 event hook: `app/services/notify.py::emit(event, user_ids, payload)` (R1 pending reply).
- M7 attendance reads: `app/services/attendance_read.py` documented in `docs/interfaces.md` (R2 pending reply).
- M6 materials retrieval: `app/services/kb/retrieval_api.py::search(course_id, query, k)` documented in `docs/interfaces.md`.

## Next

- Execute S01 as the first implementation task.
- Record every additive API/schema/websocket contract here before another module relies on it.
- Add a dated entry after each completed S-task with files changed, decisions, interface/schema changes, tests/E2E evidence, and follow-ups.

## Blocked

None. M2/M5/M6/M7 work can start from S01; later tasks have explicit dependencies in `plan-shino.md`.
