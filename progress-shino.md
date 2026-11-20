# PROGRESS — Shino's modules (M2, M5, M6, M7)

Companion to [plan-shino.md](plan-shino.md). It follows the structure and evidence standard of [PROGRESS.md](PROGRESS.md), but does not alter Yew Sing's log.

## Current baseline — 2026-11-20

- M2, M5, and M6 backend implementations do not yet exist. Existing lecturer quiz, student participation, and parts of analytics are legacy mock UI and must be replaced, not extended as production state.
- M7 has a partial legacy endpoint/UI. It currently risks exposing another lecturer's analytics and calculates attendance incorrectly because it does not use the shared attendance read interface.
- M3 is complete and owns `AttendanceSession`, session open/extend/close, attendance finalisation, Moodle sync, and the attendance websocket. These are stable integration points, not Shino rewrite targets.
- Current lecturer UI places `+15 min` and `End class` in `AttendanceDetail`; the required S01 move places them in Dashboard's top session card. `AttendanceDetail` will retain roster, override, history, confirmation, and SPeCTRUM sync responsibilities.

## S01 — dashboard shared-session controls — 2026-11-20 [~]

- Changed: Dashboard's top session card now owns `+15 min` and End class (with the existing finalisation confirmation); AttendanceDetail no longer exposes class lifecycle controls. The dashboard derives class identity from the actual open session, avoiding controls for one class appearing under another class title.
- Decision: until M5 exists, the dashboard explicitly says interaction will use the same session when available; it does not claim interaction is live or already being closed.
- Interface/schema changes: none. Existing `LecturerContext` session actions and M3 APIs are reused unchanged.
- Tests: lecturer unit tests passed (`npm.cmd test`: 35/35); Expo web export passed; `npm.cmd run e2e:web` passed against its isolated backend and Expo web server.
- Visual QA: external review found no remaining source-level critical issue after copy/identity corrections. Browser E2E now passes; an optional manual phone/Maestro confirmation remains useful but does not block S02.

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

- Run S01's Playwright/Maestro and browser visual verification, then mark it complete.
- Record every additive API/schema/websocket contract here before another module relies on it.
- Add a dated entry after each completed S-task with files changed, decisions, interface/schema changes, tests/E2E evidence, and follow-ups.

## Blocked

None. M2/M5/M6/M7 work can start from S01; later tasks have explicit dependencies in `plan-shino.md`.
