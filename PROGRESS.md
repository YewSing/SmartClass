# PROGRESS

Short log, newest entry at the bottom of "Log". Each entry is at most 5 lines:
`### Txx — <title> — <date>` then: Changed · Decisions · Interface/schema changes · Tests · Next.

## Blocked
<!-- Format: - Txx: <problem>, what was tried, what is needed. Remove the line when it's resolved. -->

## Next
<!-- Follow-up ideas found during tasks that are out of the current task's scope. -->
- (T00f) `GET /lecturer/analytics` (`routers/analytics.py`, M7, Shino) lets any lecturer read any class's analytics (NFR-04). Not changed because it's her module; the issue and fix are written up for her under Module 7 in `docs/requirements/functional-requirements.md`.
- T94 (2026-11-09): the approved overnight run past T94 (T05, T10, T11, T12, T13) is finished and the checkpoint wording is back in PLAN.md. The chat to test is at tag `t94-chat-ready` (T89).
- REVIEW: T81 - NFR-08: a failed Moodle download can return the Moodle token to the caller. `MoodleClient.download` uses `raise_for_status()`, whose message includes the full URL with `?token=`; `sync.py:76` puts that text in `report.failed`, which the sync API returns (`schemas/assistant.py:93`) and `scripts/kb_sync.py` prints. Older code, found in this review. T84's `open_file` already avoids it, so reuse that error handling and add a test that the token is never in `failed`. Fix before merging to main.
- REVIEW: T84/T89 - FR-809 and UC step 6 say the source opens in the app at the cited page or slide. It actually opens in another app from the start, and the screen tells the student which page to go to (on web it uses `#page=N`). Yew Sing decides: change the FR/UC to match, or build an in-app viewer.
- REVIEW: T89 - FR-808 (Must Have) lets students rename chats. `PATCH /student/assistant/sessions/{id}` exists, but the app has no rename and no later task covers it.
- REVIEW: T93/T89 - answers show in a plain `<Text>`, and the prompt asks for bullet points without banning markdown. T93 only cleans LaTeX, so `**bold**` or `* ` from Gemini would probably show as typed. Not confirmed with a real answer; check during T94.
- REVIEW: T82 - no `live` tests or `tests/fixtures/llm/` exist yet, so T93's no-LaTeX prompt rule and the renumbered citations have never been checked against real Gemini in a test. Add both to the T82 live suite.
- LOOP (T10): the reviewer subagent and the Stop hook's check.sh both drop and recreate `smartclass_test`, so if they run at the same time both get random "relation does not exist" / FK / 401 failures (seen 3 times in T10; a clean solo run passed). Fix: a per-process test DB name (e.g. suffix the PID) or a lock in conftest.
- REVIEW: T89 - `e2e-mobile.sh` only warns if a backend is already running on the port, so the flow could use one without `LLM_FAKE` and call real Gemini; it should stop instead. `assistant.yaml` also needs indexed WIA2005 in the dev DB, which seed data alone doesn't provide, leaves one chat per run, and never taps "Open file".
- REVIEW: T13 - both apps still offer Change Password, but Moodle accounts have no local password: `PUT /auth/me/password` (`auth.py:196`) always answers "Current password is incorrect". Hide it for Moodle accounts and point to SPeCTRUM.
- REVIEW: T12 - `PUT /admin/users/{id}/password` (`admin_users.py:286`) also works on Moodle accounts and gives them a local password, so they could use `/auth/login` without Moodle (lecturers through the browser sign-in). FR-103 keeps local sign-in for administrators. Refuse it when `moodle_user_id` is set.
- REVIEW: T13 - for the merge note: the phone apps now sign in only through Moodle, so seeded accounts (`23004002@siswa...`, `devlecturer`) no longer work on a phone, and login gives 503 unless `backend/moodle` is running. Shino needs the local Moodle up and its accounts (`backend/moodle/README.md`).
- REVIEW: T11/T29 - a full sync only manages students who have already logged in (`unlinked_users` are only counted). Students who never logged in have no enrolment, so M3 can't mark them Absent. Decide before T29/T30 whether the sync creates these accounts (already raised in the T11 log).
- REVIEW: T10 - a Moodle idnumber that matches another student's matric number gives a 500 at login (noted in the T10 log, no task covers it).

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
- Interface: `citations[].n` is now the display number (1..k), not the retrieval passage index. Tests: new `test_answer_format.py` (21) + 1 `db` test; `test_kb` renumbering assertion updated to [1, 2] (intended change); check.sh 107 passing; reviewer PASS.
- Next: T84.

### T84 — Open cited source — 2026-11-09
- Changed: `moodle_client.py` adds `open_file` (streamed GET with token; Moodle's JSON errors, HTTP ≥400 and connection errors become `MoodleError` before any bytes); `routers/assistant.py` adds `GET /student/assistant/materials/{id}/file`; `Citation` gets `file_url` and `open_page`.
- Decisions: student only, enrolled in the material's course (403), unknown id 404, local dev materials without a Moodle file 404, Moodle failure 502; served `inline` with a UTF-8 filename and `Cache-Control: private`; `open_page` = `location_start` (page or slide, per `location_type`); both fields are computed, so citations stored earlier carry them too.
- Interface: new endpoint above; `citations[]` gain `file_url` (API path) and `open_page`. No schema change. Tests: new `test_assistant_open_source.py` (11: 7 `db` + 4 respx); check.sh 118 passing; reviewer PASS.
- Next: T89 (the app opens `file_url` with the token and jumps to `open_page`; slides need a viewer that can, or show "slide N").

### T89 — Student app: assistant chat with citations — 2026-11-09
- Changed: student app Assistant tab (`Assistant`, `AssistantChat`, `AssistantSource` screens, `services/openSource.js`, assistant calls in `api.js`); course chips (the first course with materials is preselected and scrolled into view), chat list (long-press deletes), chat with an orange "General knowledge" label and `[n] title · slide N` chips that open a source screen with the passage and "Open file at …". Backend `LLM_FAKE` setting → `llm.fake_chat` canned replies; `e2e-mobile.sh` starts uvicorn with `LLM_FAKE=1`.
- Decisions: the chat is created on the first question, not on "New chat"; the file is downloaded with the token (expo-file-system) and opened in a viewer via an Android VIEW intent, or the share sheet as a fallback/on iOS. Phone viewers can't jump to a page, so the screen tells the student which page/slide to go to (on web it opens the PDF at `#page=N`). New deps: expo-file-system, expo-sharing, expo-intent-launcher.
- Interface: new env flag `LLM_FAKE` (E2E only). Login's email clear button gets `accessibilityLabel="Clear email"`. No API/schema change. Tests: `test_llm_fake.py` (6, 2 `db`); Maestro `student assistant` PASS (uses the dev DB's indexed WIA2005 and student 23004002; each run leaves one chat), `student smoke` PASS; check.sh 124 passing; reviewer PASS.
- Next: T94 checkpoint (human): ask real questions on a phone and tap "Open file" on a real Moodle PDF/PPTX, which E2E doesn't cover.

### T05 — Lecturer app runs in the browser — 2026-11-09
- Changed: `useWideLayout` (web and ≥900 px) → `SideNav` (232 px) replaces the bottom tabs, content is a centred 960 px column, sheets become centred dialogs and toasts move bottom-right; login card max 440 px; CSV export split into `saveCsv.js` (share sheet) and `saveCsv.web.js` (Blob download); AsyncStorage calls catch errors; `check.sh` runs `expo export --platform web` when lecturer sources change.
- Decisions: the phone layout is unchanged below 900 px or off web. The Playwright config starts its own backend on :8001 (`LLM_FAKE=1`, dev DB) and Expo web on :8092 with `reuseExistingServer: false`, because :8082 was running the student app and the old config would have tested that app. Logs in as the seeded devlecturer.
- Interface: CORS adds `localhost:8092`. No API/schema change. Tests: `test_cors.py` (5); new `e2e-web/desktop.spec.js` (3: 1280 px login + no sideways overflow, every screen and dialog with no page error, phone width keeps the bottom tabs) + smoke all pass; web + android exports pass; Maestro lecturer smoke PASS (the first run lost the emulator's Metro connection, the rerun passed); check.sh 129 passing; reviewer PASS.
- Next: T10.

### T10 — Moodle login + account auto-creation — 2026-11-09
- Changed: new `services/moodle_auth.py` (token.php with service `smartclass`, then with the user's own token: site info, `core_user_get_users_by_field`, courses + enrolled users for the role); `POST /auth/moodle-login`; `verify_password` is False for no hash; `UserOut` shows only the profile matching `role`.
- Decisions: find by `moodle_user_id`, else link by email (case-insensitive); admin or inactive → 401; teacher = `editingteacher`/`teacher` in any course; matric/staff no = Moodle idnumber, username only when creating; old profile row kept on a role change; audit `MOODLE_ACCOUNT_CREATE`/`MOODLE_ROLE_CHANGE` with the user as actor; Moodle errors `invalidlogin`/`suspended`/… → 401, network/5xx/bad JSON/WS misconfigured → 503.
- Interface/schema: new endpoint; migration `c3d4e5f6a7b8` adds `users.moodle_user_id` (unique) and makes `password_hash` nullable (applied to the dev DB). Tests: `test_moodle_login.py` 20 respx/db + 3 `moodle` (student1, lecturer1, wrong password) pass; check.sh 149 passing.
- Next: T11 (the courses read here can feed the sync); a Moodle idnumber clashing with another student's matric would give a 500, not handled.

### T11 — Course + enrolment sync from Moodle — 2026-11-09
- Changed: new `services/moodle_sync.py` (fetch all from Moodle first, then apply in one transaction), `routers/admin_moodle.py` (`POST /admin/moodle/sync`, `GET` = last result), login sync in `/auth/moodle-login` (user's own courses read with their token), `moodle_sync_loop` in main.py, `MOODLE_SYNC_INTERVAL_SECONDS` (3600).
- Decisions (mapping): Moodle course = `Course` by `moodle_course_id`, else `code == shortname`; unknown Moodle courses are created, names follow Moodle. Occurrences (timetable) stay SmartClass data; a Moodle student gets every LECTURE occurrence + the tutorial if there is only one (several groups: admin picks). Only Moodle-linked accounts are managed, so seed/local accounts are never touched; the full sync creates no accounts (counted as `unlinked_users`). Linked lecturers no longer teaching are unassigned; empty occurrences get the first linked teacher. Manual sync is admin-only, though UC-103 also lists lecturers.
- Interface: new endpoints above; `MOODLE_SYNC` audit entry per manual sync. No schema change. Tests: `test_moodle_sync.py` 13 (add, remove, course gone, idempotent, Moodle down + mid-fetch failure unchanged, local accounts untouched, login scope, admin-only, 1 `moodle`); check.sh 161 passing; reviewer PASS.
- Next: map Moodle groups to tutorial occurrences; decide whether the sync should pre-create accounts so rosters include students who never logged in (matters for M3 absences); the last-sync status is in memory only (T22 may want it stored).

### T12 — Admin accounts: deactivate/reactivate, create admin, audit — 2026-11-09
- Changed: `routers/admin_users.py` adds `_set_status` (the only place status changes: blocks self-deactivation, audits `USER_DEACTIVATE`/`USER_REACTIVATE` with the real old status, no entry for a no-op), used by `DELETE /admin/users/{id}`, new `POST /admin/users/{id}/reactivate` and `PUT {status}`; `USER_UPDATE` is now logged only when other fields change.
- Decisions: login, Moodle login, refresh and `get_current_user` already rejected inactive accounts, so no auth code changed; "create admin" is the existing `POST /admin/users` with `role=admin` (bcrypt, audited `USER_CREATE`). `frontend/admin` keeps working (DELETE + PUT status).
- Interface: new endpoint above; `PUT /admin/users/{id}` returns 422 for a status other than active/inactive and 400 for deactivating yourself. No schema change. Tests: `test_admin_accounts.py` (12 `db`); check.sh 173 passing; reviewer PASS.
- Next: T13.

### T13 — resume note — 2026-11-09
- The first T13 round hit the Claude session limit at 06:12 before committing. Its unfinished work is in the git stash "T13 partial work (session limit, 2026-11-09)". Start T13 with `git stash pop`, check that work, finish it, and run the Done-when flows. Do not redo it from scratch unless the pop fails.
- Changed: `scripts/run-tasks.sh` missed the "session limit" message, so the loop stopped instead of waiting. It now matches that message, and its stash leaves PDFs alone.

### T13 — Mobile login uses Moodle credentials (both apps) — 2026-11-09
- Changed: both `Login.jsx` ask for SPeCTRUM username + password (nothing prefilled) → `POST /auth/moodle-login`; `api.js` maps 401 → "Wrong SPeCTRUM username or password.", 503 → SPeCTRUM unreachable, no response → server unreachable; `client.js` tags errors with `status` and no longer treats a 401 from either login path as an expired session. Each app refuses the other app's role.
- Decisions: the lecturer app shows "Administrator sign-in" (email + `/auth/login`, lecturer or admin) only on web, so phones have none; the seeded local `devlecturer` signs in that way in the Playwright specs. Finished from the stash after the session limit.
- Interface: no API/schema change. Tests: Maestro `login.yaml` (student1, lecturer1, incl. 401 and wrong-role) and `student assistant` (now student2 via Moodle) PASS; Playwright `login.spec.js` + updated desktop/smoke (6 passed); check.sh passes; reviewer PASS. The 503 message is not covered by an E2E flow.
- Next: the 5-task overnight run is done; T94's checkpoint wording is back in PLAN.md, so the loop stops there.
