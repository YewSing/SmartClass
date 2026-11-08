# PROGRESS

Short log, newest entry at the bottom of "Log". Each entry is at most 5 lines:
`### Txx — <title> — <date>` then: Changed · Decisions · Interface/schema changes · Tests · Next.

## Blocked
<!-- Format: - Txx: <problem>, what was tried, what is needed. Remove the line when it's resolved. -->

## Next
<!-- Follow-up ideas found during tasks that are out of the current task's scope. -->
- (T00f) `GET /lecturer/analytics` (`routers/analytics.py`, M7, Shino) lets any lecturer read any class's analytics (NFR-04). Not changed because it's her module; the issue and fix are written up for her under Module 7 in `docs/requirements/functional-requirements.md`.

## Log

### T00 — Setup — 2026-11-08
- Changed: FR/NFR/UC docs rewritten for M1/M3/M4/M8 (commit 646f1c0); CLAUDE.md loop rules; PLAN.md; hooks, reviewer agent, /next-task, scripts/run-tasks.sh.
- Decisions: Moodle login + auto-create accounts, local admin; face self-enrolment verified against the matric card (local OCR); Present/Absent only; mod_attendance sync; Pi does detection, server does recognition; M8 quiz-based features deferred.
- Tests: 12 KB unit tests passing at start.
- Next: T01.

### T00b — Web and admin decision — 2026-11-09
- Decisions: lecturer app also runs in a browser (Expo web); small admin role with web-only screens inside it; `frontend/admin` retired after T22, T46, T96, once Shino confirms (T95).
- Changed: PLAN.md adds T05, T22, T93, T95, T96 and edits T03, T46, T89; CLAUDE.md gets the web direction and "Merging to main"; new `/prepare-merge` command.
- Next: T01.

### T00c — Week 7 priority — 2026-11-09
- Decisions: the student AI chat screen must be ready for the Week 7 demo, so T80, T93, T84, T89 now run right after the T04 checkpoint (PLAN.md section 0b). Dependencies are unchanged.
- Next: T01.

### T01 — Test + lint baseline — 2026-11-09
- Changed: `backend/pytest.ini` (markers, `asyncio_mode=auto`, `pythonpath=.`), `requirements-dev.txt`, `tests/conftest.py`, `tests/test_db_baseline.py`; unused imports removed (10 files); `app/core/config.py` comments re-saved as UTF-8.
- Decisions: `db` tests use `smartclass_test` (from DATABASE_URL, or TEST_DATABASE_URL; name must end `_test`), dropped/recreated + `alembic upgrade head` once per session, TRUNCATE after each test; role clients use `create_access_token` directly; `live`/`moodle` auto-skip in conftest when LLM_API_KEY / MOODLE_TOKEN empty.
- Interface/schema changes: none. Tests: 17 passing (12 KB + 5 db); `ruff check .` clean; check.sh passes (needs docker postgres up).
- Next: T02, T03.

### T02 — Characterisation tests — 2026-11-09
- Changed: `tests/conftest.py` adds `classroom` (CS101 + 3 enrolled students, CS202 for another lecturer) and `other_lecturer_client`; new `tests/test_char_{auth,sessions,attendance,face_review}.py` (28 tests).
- Decisions: tests pin current behaviour as-is (e.g. session CSV exports missing records as "absent"; face-review closest match stores users.id). No production code changed; 2 pre-existing bugs logged under Next.
- Interface/schema changes: none. Tests: 33 `db` passing, check.sh 45 passing; reviewer PASS.
- Next: T03.

### T00d — Plan corrections while the loop runs — 2026-11-09
- Decisions (Yew Sing): four attendance statuses, replacing Present/Absent only. Defaults: Late after 15 min from session open; Late counts as attended; Excused is lecturer-only and left out of the rate. Admins use the browser only.
- Changed: FR-103, FR-302–FR-304, FR-306, FR-308, UC-M3/M4; PLAN.md T13, T30–T33, T35, T38, T39, T41, T43, T44, T99; new checkpoints T94, T23, T48 that stop the loop.
- Next: continue the plan.

### T03 — Mobile + web E2E harness — 2026-11-09
- Changed: `scripts/e2e-mobile.sh` (emulator/backend/Expo/Expo Go/Maestro, trap cleanup), `mobile/{student,lecturer}/e2e/smoke.yaml`, lecturer `playwright.config.js` + `e2e-web/smoke.spec.js` + `npm run e2e:web` (`@playwright/test` dev dep); `.gitignore` (`.tools/`, Playwright output); CLAUDE.md commands.
- Decisions: Maestro installs into git-ignored `.tools/maestro` (sandbox blocks `~/.maestro`); on Windows the script runs Maestro's Java main class directly because `maestro.bat` breaks on the space in "UM Documents"; Expo Go opens `exp://127.0.0.1:8081` via `adb reverse`; web test runs Expo web on :8082. Web deps were already present.
- Interface/schema changes: none. Tests: student + lecturer Maestro smoke PASS (fresh emulator each run; ports 8000/8081 free after), `npm run e2e:web` PASS, check.sh 45 passing; reviewer PASS.
- Next: T04 checkpoint (human).

### T00e — Attendance flow decisions — 2026-11-09
- Decisions (Yew Sing): sessions open from the class schedule, and the lecturer can change the time for one class; students flag "not recognised" and the lecturer confirms in the room, replacing assigning unknown faces; Moodle mismatches are never overwritten silently; a third trends list for topics the materials don't cover; no OCR for now; Shino confirmed she doesn't need `frontend/admin`.
- Changed: FR-301, FR-302, FR-407, FR-813, new FR-315–FR-320; UC-301, UC-304, UC-404; PLAN.md adds T29 and changes T30, T31, T34–T36, T38, T43, T45, T48, T87, T91, T95. The REVIEW items on ownership checks (NFR-04) and T31's test update are now in T31.
- Loop: `run-tasks.sh` refuses a second run through a lock file and stops at "no runnable task", fixing both Loop REVIEW items.
- Interface: M2 event `face.unrecognised` becomes `attendance.flagged`.

### T00f — Lecturer access fix (from the T01–T03 review) — 2026-11-09
- Changed: `core/deps.py` adds `ensure_teaches_occurrence`; `routers/sessions.py`, `attendance.py`, `classes.py` and `websocket/router.py` enforce it; new `tests/test_lecturer_access.py` (22 tests). T31 no longer lists this work.
- Decisions (Yew Sing): running a session is the lecturer's job only, so admins can't open sessions. "Teaches" means assigned to that class (`class_occurrences.lecturer_id`). Admins can still list sessions.
- Interface: open, close, roster, both overrides and both exports now return 403 to admins and to lecturers not assigned to the class; `/ws/sessions/{id}` closes (1008) for them too. `GET /classes/{id}/students` is 403 for students and other lecturers (admins keep it). Session override on an unknown session is now 404, not a 500.

### T00g — Lecturer AI — 2026-11-09
- Decisions (Yew Sing): lecturers get "ask my materials" and a "before next class" summary, both in M8, built after the student study tools. Quiz drafting stays in M6 and at-risk alerts in M7.
- Changed: FR-815, FR-816, UC-810, UC-811, walkthrough; PLAN.md adds T100, T101, T102.

### T80 — Characterisation tests for KB + assistant — 2026-11-09
- Changed: new `backend/tests/test_char_assistant.py` (18 `db` tests): student courses, chat CRUD + ownership, answers with citations/general/no materials/follow-up rewrite/LLM down, staff materials list, Moodle sync (add, error retry, delete, 502s), access control incl. not-enrolled → 403.
- Decisions: LLM mocked by patching `llm.chat`; embeddings patched to a fixed vector so real hybrid search runs on seeded `kb_chunks`; `MoodleClient` replaced in the router. No production code changed.
- Interface/schema changes: none. Tests: check.sh 85 passing; reviewer PASS. One early run flaked (users vanished mid-test), likely another process sharing `smartclass_test`; 3 later runs clean.
- Next: T93, T84.

### T93 — Phone-friendly answer format — 2026-11-09
- Changed: new `services/kb/answer_format.py` (`clean_latex`: `$$`/`\[ \]`/`\( \)`/maths-looking `$…$`, `\frac`, `\sqrt`, `\text`-family, `\times`/relations/Greek, `\%`, `^{}`/`_{}`; code spans untouched); `assistant.py` adds prompt rule 6 (no LaTeX), cleans every answer before `parse_answer` and the save, and renumbers citations 1, 2, 3… by first appearance.
- Decisions: `$…$` is only stripped when the inside looks like maths (or is a single letter), so "$5 or $10" stays; display formulas go on their own line; unknown `\cmd` loses its backslash only inside maths, so `\n` in prose stays.
- Interface: `citations[].n` is now the display number (1..k), not the retrieval passage index. Tests: new `test_answer_format.py` (23) + 1 `db` test; `test_kb` renumbering assertion updated to [1, 2] (intended change); check.sh 107 passing; reviewer PASS.
- Next: T84.
