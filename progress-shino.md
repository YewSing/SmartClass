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

## S03 — role dashboards and notification centre — 2026-11-21 [x]

- Rebuilt the student dashboard against `/student/me/dashboard`: priority notices, today's classes and personal attendance state, attendance rates, login-refreshed SPeCTRUM deadlines/announcements, enrolled-class navigation, loading/empty/stale/error states, and safe validated HTTPS Moodle links.
- Kept the lecturer's shared-session command card as the first dashboard card. Start, extend and end still operate the single attendance/interaction session, and live attendance uses the existing normalized five-count view. Per the final product clarification, the lecturer dashboard does not show a separate Today list or closed-session attendance summary; closed history remains in Attendance.
- Added student and lecturer notification centres with recipient-scoped pagination, whole-feed unread counts, mark-one/read-all, initial-error versus empty states, cursor-specific retry, pull-to-refresh, focus-refreshed dashboard badges, and allowlisted app-relative deep links. Unsafe/unknown links remain non-navigable.
- Preserved existing M1/M3/M4/M8 flows and S01 test IDs. No additional backend contract or schema change was needed for S03.
- Verification: independent frontend evaluation reached PASS after refinement; student unit suite 65/65; lecturer unit suite 55/55; student and lecturer Expo web exports pass; focused Playwright dashboard/notification/phone-width tests 5/5 and the shared live-session start/override/end flow 1/1 pass. The repository `scripts/check.sh` passed with test guard, Ruff, 709 backend tests (43 external/E2E deselected), both mobile suites, and lecturer web export.
- Full Playwright run reached 28/30 before two stale assertions failed: one expected the removed Today heading and one assumed no other scheduled session could be open after closing the test session. Those assertions were corrected to match the clarified UI and to verify the exact close response; all affected focused specs then passed. Maestro was not run because no emulator/Expo Go session was available.
- Next task: S04 M5 interaction API tied to `attendance_session_id`. No S04 implementation was started in this session.

## S04 — shared-session interaction API — 2026-11-21 [x]

- Added additive M5 persistence for questions, polls/current ballots, quick prompts/answers, and an append-only participation event stream. Migration `f5a6b7c8d9e0` follows the current M2 head and uses `m5_*` tables so it does not overwrite or delete legacy unversioned `interaction_*` tables already present in the development database; no M3 table or lifecycle field was changed.
- Every live mutation locks and rechecks the canonical `AttendanceSession`, then enforces the assigned lecturer or exact occurrence enrolment. Any non-open attendance status rejects new questions, votes, answers, reactions, and confusion presses.
- Anonymous question authors and confusion pressers remain stored for private accounting but are removed from lecturer/student projections, live events, notification payloads, and audit values. Question hide changes are audited.
- Added poll start/close/result visibility, mutable ballots until close, quick answers, configurable reaction/confusion cooldowns, distinct-student confusion spike detection, M2 `poll.started` / `confusion.spike` delivery, lecturer aggregates and post-class summaries.
- Added a role-separated interaction websocket. It emits only after-commit invalidations and a minimal class-status projection; manual close and scheduler close/needs-confirmation both end interaction without changing M3 close semantics.
- Added `interaction_read.student_counts` / `class_totals` for future M7. Individual figures exclude anonymous questions; class totals may include them without author identity.
- Final verification: 15 focused migration-backed interaction tests and 81 interaction/session/schedule/notification/access regression tests pass. Post-fix `scripts/check.sh` exited 0: test guard, Ruff, 724 backend tests (43 external/E2E deselected), and both mobile unit suites. Development database is at migration `f5a6b7c8d9e0`.
- Review findings resolved and follow-up reviewer PASS: anonymous-only submissions no longer reveal authors through changes in individual M7 rows; spike counts and recipients follow current enrolment/lecturer assignment; unpublished polls remain private; websocket roles use current database authority; subscription and locked bootstrap handle concurrent close; both manual and scheduled opening transitions publish status.
- Next: S05 lecturer moderation and student live participation UI. S04 introduces the API; app interaction screens and their browser/mobile E2E belong to S05.

## S05 — classroom interaction screens — 2026-11-21 [x]

- The lecturer enters interaction from the dashboard session card and can moderate questions, run polls, collect quick answers, and see aggregate feedback. A closed attendance record links to the read-only interaction summary.
- Students can enter an open enrolled class from Home or a supported notification and participate in questions, polls, quick answers, reactions, and confusion feedback. Both apps subscribe to the shared session's state and disable writes when it ends.
- The student dashboard adds scoped `live_sessions` and M5 questions add a viewer-only `upvoted_by_me` indicator. These additions use the existing schema and are recorded in `docs/interfaces.md`.
- Final verification: 22 focused backend tests, 70 student unit tests, 55 lecturer unit tests, both Expo web exports, and the seeded lecturer Playwright flow passed. Independent review passed after fixing student refresh handling. The lecturer tabs now announce selected state. The full repository check exited 0 with Ruff, test guard, 724 backend tests (43 external/E2E deselected), both app suites, and lecturer web export.
- Shino subsequently waived emulator testing. The Android attempt stopped during Maestro driver installation with an integrity verification timeout before app assertions ran. The test emulator was shut down and the runner performed fixture cleanup. Native execution remains unverified. Completion uses the browser flow, unit suites, web exports, responsive review, and repository check.
- Responsive screenshots at 375, 768, and 1440 pixels were reviewed using synthetic classroom data. Review artifacts are in `C:/Users/User/AppData/Local/Temp/smartclass-s05-gguyaglf.vtb`. The frontend-design review identified and resolved student request starvation during bursts of invalidations and stale lifecycle handling after reconnect.
- S06 quiz authoring and assessment APIs are the next task.

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

### S02 complete — 2026-11-20

- Required `scripts/check.sh` passed: test guard, repository Ruff, 709 backend tests (43 external/E2E tests deselected by the standard script), and student/lecturer unit suites. The dedicated live Moodle snapshot test passed separately. Follow-up reviewer PASS; no unresolved review findings.
- Both migrations are applied to the development database. Moodle forum/calendar/group read functions are enabled. Moodle cache ownership was repaired and configuration rerun as daemon; the former demo-login blocker is resolved. Earlier pending/blocker entries below are historical and superseded by this completion entry and the login-only refresh decision.
- S02 provides notification persistence/feed/read APIs, event policies and deduplication, role-scoped dashboard reads, student attendance status, lecturer counts, and read-only Moodle snapshots with current membership/group filtering. Future modules supply their own producers and aggregates; push/email and frontend consumption are outside this foundation task.
- Next task: S03 role dashboards and notification centre. No second task was started in this session.

### S02 review fixes and live verification — 2026-11-20

- Diagnosed the live-login error as Moodle `invaliddatarootpermissions`, not bad credentials. The earlier root-run Moodle configuration generated root-owned cache entries. Repaired ownership only within the verified Moodle cache/localcache directories and reran configuration as `daemon` with secret-bearing output suppressed. Documented demo login works again; no account passwords changed.
- Live `test_live_moodle_login_populates_dashboard_snapshot` passed: real Moodle login and dashboard snapshot availability verified. Development DB is at `e4f5a6b7c8d9`.
- Reviewer found four issues, now fixed: bounded occurrence keys for recurring notices, validated custom titles, today's off-timetable classes, and group-scoped calendar reads. Added regression coverage. Follow-up reviewer PASS for S02 foundation scope.
- Full `scripts/check.sh` is running with Git Bash and a process-local Git safe-directory setting. No global Git configuration was changed. S02 stays unchecked until it completes.

### S02 approved Moodle login integration — 2026-11-20

- User approved the additive M1 login hook. `MoodleProfile.dashboard_token` is transient, excluded from repr, and cleared in the login route's finally block. It is never returned in the auth response or persisted. M2 uses the user's own Moodle client to fetch news forums and future calendar events, including assignment events supplied by Moodle.
- Added migration `e4f5a6b7c8d9` after `e3f4a5b6c7d8` for a per-user read-only dashboard snapshot. Refresh uses a savepoint; errors preserve the previous snapshot and do not prevent login. Dashboard reads filter snapshots against current course memberships.
- Added Moodle read functions to the simulation's service allowlist. Existing installations must rerun `configure_moodle.php` and apply `alembic upgrade head`; these runtime setup changes have not been executed here.
- Verification: notification/dashboard/Moodle-login tests: 30 passed, 3 Moodle-marker tests deselected; repository Ruff clean; single Alembic head. Additional cache write test added for credentials not appearing in stored data.
- S02 remains in progress: this refresh runs on Moodle login. Manual/scheduled sync refresh, group-specific deadline coverage, live Moodle validation and the required final review/check script remain. No M3 attendance producers or lifecycle code were changed.

### S02 implementation in progress — 2026-11-20

- Added recipient-scoped notification persistence, migration `e3f4a5b6c7d8` (after updated head `b5c6d7e8f9a0`), priority policy, subject-based duplicate suppression, paginated feed and read-one/read-all endpoints. T44's existing hook now calls the M2 adapter; producer call sites are unchanged. No raw payload is stored or logged.
- Added role-scoped `/student/me/dashboard` and `/lecturer/dashboard` reads: today's timetable, current/latest attendance session, student attendance rates via the read interface, and unread important/urgent notices. M5–M7 fields are null while unavailable. Moodle availability is explicitly false until its read-only sync lands.
- Verification: initial notification + recognition-feedback suite 12 passed; expanded notification/dashboard suite 4 passed; targeted Ruff passed; Alembic reports one head. Test database migration succeeds through the pytest fixture. Development database migration has not been applied.
- Remaining S02 work: Moodle announcement/deadline sync with visibility-safe course/user scoping, student current-session attendance status, default deep links/event identity policy for recurring reminders, full check script and reviewer. S02 remains unchecked.

### S02 follow-up — student attendance status and validation

- Student dashboard now includes the student's own attendance status for the current/latest session and today's scheduled classes. Open sessions without a record show `not_recorded`; closed sessions without a record show `absent`. Lecturer counts remain lecturer-only. Existing M3 `session_date` defines the class date fallback.
- Added app-relative default destinations for attendance, face enrolment and quiz events, with external/protocol-relative links rejected. Recurring reminder producers still need explicit event/window keys.
- Broad backend run: 693 passed, 8 failed because the Windows PATH selected WSL Bash and returned Access denied. Reran those eight tests with Git Bash first on the process PATH alongside the then-current notification tests: 13 passed; repository Ruff passed. No tests were skipped, weakened, or removed.
- Moodle integration decision pending: the existing M1 authentication adapter discards the user's Moodle token after profile reads. Refreshing M2 data with user-specific Moodle permissions requires an additive hook at that login boundary. That touches Yew Sing's module and needs agreement under the user's ownership constraint. No token/password was read from disk, logged, or persisted.

- Run S01's Playwright/Maestro and browser visual verification, then mark it complete.
- Record every additive API/schema/websocket contract here before another module relies on it.
- Add a dated entry after each completed S-task with files changed, decisions, interface/schema changes, tests/E2E evidence, and follow-ups.

## Blocked

### S02 runtime verification — 2026-11-20

- Applied `alembic upgrade head` to the development database and reran the Moodle service configuration successfully. Configuration stdout was suppressed because it contains a service token.
- Added a live Moodle test that logs in the documented `student1` account and requires a populated dashboard snapshot. It currently fails at login with HTTP 401 using the documented demo credentials; no password was reset and the test remains failing.
- Incomplete Moodle responses carrying warnings now preserve the previous snapshot rather than replacing it with partial data.
- Resolved by Shino: refresh remains login-only. Manual/scheduled snapshot refresh is out of scope; Moodle tokens are not persisted. FR-203, PLAN-SHINO.md and the interface contract now reflect this decision. Earlier log entries listing scheduled refresh as pending are superseded.

None. M2/M5/M6/M7 work can start from S01; later tasks have explicit dependencies in `plan-shino.md`.
