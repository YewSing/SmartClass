# PROGRESS

Short log, newest entry at the bottom of "Log". Each entry is at most 5 lines:
`### Txx — <title> — <date>` then: Changed · Decisions · Interface/schema changes · Tests · Next.

## Blocked
<!-- Format: - Txx: <problem>, what was tried, what is needed. Remove the line when it's resolved. -->

## Next
<!-- Follow-up ideas found during tasks that are out of the current task's scope. -->
- (T00f) `GET /lecturer/analytics` (`routers/analytics.py`, M7, Shino) lets any lecturer read any class's analytics (NFR-04). Not changed because it's her module; the issue and fix are written up for her under Module 7 in `docs/requirements/functional-requirements.md`.
- T94 (2026-11-09): the approved overnight run past T94 (T05, T10, T11, T12, T13) is finished and the checkpoint wording is back in PLAN.md. The chat to test is at tag `t94-chat-ready` (T89).
- REVIEW: T82 - no `live` tests or `tests/fixtures/llm/` exist yet, so T93's no-LaTeX prompt rule and the renumbered citations have never been checked against real Gemini in a test. Add both to the T82 live suite.
- LOOP (T10): the reviewer subagent and the Stop hook's check.sh both drop and recreate `smartclass_test`, so if they run at the same time both get random "relation does not exist" / FK / 401 failures (seen 3 times in T10; a clean solo run passed). Fix: a per-process test DB name (e.g. suffix the PID) or a lock in conftest.
- REVIEW: T13 - for the merge note: the phone apps now sign in only through Moodle, and login gives 503 unless `backend/moodle` is running. Shino needs the local Moodle up and its accounts (`backend/moodle/README.md`).
- ACCOUNTS: Yew Sing's direction is that Moodle owns accounts. `frontend/admin` still has "Add Student/Lecturer" (`POST /admin/users` accepts those roles) and edits names that the next Moodle login overwrites. FR-108 only needs creating admins, so limit this in T12's follow-up or T22.
- REVIEW: T10 - a Moodle idnumber that matches another student's matric number gives a 500 at login (noted in the T10 log, no task covers it).
- REVIEW: lecturer app - toasts show behind an open dialog (RN `Modal`). The export dialog now closes first; other dialogs may hide their error toasts the same way.
- (AI fixes) Text extracted from PDFs garbles maths fonts (e.g. `n = s.length` is stored as `n D s:length`). Students see this in "Cited passage", and the LLM reads it too. A parser issue; look at it with the T82 evaluation.
- (AI fixes) `assistant.yaml` still needs WIA2005 indexed in the dev DB (a Moodle sync). The PDF viewer draws pages at 2x at most, so text is slightly soft on sharper phones.

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

### Fix — Lecturer CSV export saves on Android, confirmed in the browser — 2026-11-09
- Changed: `saveCsv.js` on Android saves straight into a folder picked once (StorageAccessFramework, remembered in AsyncStorage, asks again if access is lost); iPhone keeps the share sheet. `saveCsv.web.js` was already right (T05). `ExportModal` shows the folder with a Change link, and always closes so the toast is visible. A toast now says where the file went.
- Decisions: Android refuses the Download root, so the dialog tells the lecturer to create a folder inside it. Expo Go asks for access as "Expo Go"; a real build would show the app's name.
- Interface: no API/schema change; `exportSessionCsv`/`exportOccurrenceCsv` now return a message. Tests: Maestro `lecturer export` PASS (first save, remembered folder, Change, cancel) on a throwaway DB copy, see Next; Playwright `export.spec.js` + `desktop.spec.js` 4 passed; check.sh passes. iPhone not tested. The reviewer agent was not run.
- E2E traps: `adb` can hang after `e2e-mobile.sh` (end adb.exe); stopping a background Expo can leave its node child on :8081 serving old code, and the script's Expo then logs "Skipping dev server".

### AI chat fixes from T94 testing + review — 2026-11-09
- Changed: `MarkdownText` + `services/markdown.js`; chat input stays above the keyboard on Android; floating "Drafting answer…"; rename in the chat list (FR-808); in-app PDF viewer `AssistantPdf` + `pdfViewerHtml.js` (FR-809, reworded with its UC step: PowerPoint and Word still open in another app); `MoodleClient.download` errors never carry the token (NFR-08); `e2e-mobile.sh` stops if a backend is already running, `E2E_LLM_FAKE=0` for the by-hand `assistant-look` flow; `seed.py` gives every student WIA2005; check.sh runs the student unit tests (`npm test`).
- Decisions (Yew Sing): PDF in the app, PPTX later, since real materials are mostly PDF. pdf.js 3.11.174 is served from `backend/app/static/pdfjs`, not a CDN, so no third-party script sees the token and demos need no outside internet. "Page X of Y" only shows once the cited page is drawn, so the E2E flow proves it rendered.
- Interface: new public `GET /static/pdfjs/*`; new dep `react-native-webview` 13.15.0. No API or schema change. T94 stays unticked: Yew Sing tests on a real phone.
- Tests: `test_moodle_token_privacy.py`, `test_pdfjs_static.py`, `test_seed_courses.py`, 11 student unit tests; check.sh 184 passing; Maestro `student assistant` PASS; `assistant-look` run with real Gemini, screenshots checked (keyboard, drafting pill, bold/bullets, general label, PDF at cited page). Reviewer agent not run on this.

### Fix — Moodle is the only source of people and courses (Yew Sing's decision) — 2026-11-09
- Changed: `moodle_sync.py`: a full sync creates accounts for Moodle users who never logged in (clashes skip that person). `seed.py` no longer wipes, re-runs safely, and holds only the admin, the timetable of WIF3001/WIF3004/WIA2005, cameras, and devlecturer + WIA0000 (always open). `moodle/seed_config.json` adds devlecturer and WIA0000 with student1-5. New `scripts/reset_to_moodle.py` moves an old database across (preview by default, `--yes` to apply).
- Decisions (Yew Sing): keep devlecturer and the always-open class; devlecturer is also a Moodle user, so one account signs in on a phone via Moodle and in the browser with its local password. Keep AI materials and the 2 face accounts (matric 23005014, 23004444, Yew Sing's own tests; local, in WIA0000 only). Resolves the T11/T29 and T11/T13 review items.
- Interface: `POST /admin/moodle/sync` report gains `accounts_created`. No schema change. Sign-in on a phone, and all Moodle accounts, need `backend/moodle` running.
- Tests: new `test_seed.py`, 4 new cases in `test_moodle_sync.py`; `login.spec.js` wrong-role check now uses Moodle's student1. Rehearsed the reset and both devlecturer logins on a temporary database copy first.
TEST-CHANGE: tests/test_seed_courses.py (test_materials_course_exists_in_the_seed, test_every_seed_student_has_the_materials_course) - removed because the demo students and courses_for_student no longer exist; every Moodle student's courses now come from Moodle, and WIA2005 materials stay.

### Fix — T94 testing: Change Password removed for Moodle accounts, bubble clipping, audit labels — 2026-11-09
- Changed: student app has no Change Password; lecturer app shows it to admins only. `PUT /auth/me/password` and `PUT /admin/users/{id}/password` answer 400 for Moodle-linked accounts, so a local password can't bypass Moodle. Chat user bubble uses `textBreakStrategy="simple"`. Audit log labels `USER_REACTIVATE` and the `MOODLE_*` actions.
- Decisions (Yew Sing): Moodle owns accounts and passwords. Bubble cause: saved prompts are complete, so it's display only; the shrink-to-fit bubble is probably measured too narrow with the phone's system font. Not reproduced here (no phone connected).
- Interface: the two password endpoints return 400 for Moodle accounts. Tests: 4 new in `test_admin_accounts.py`; `desktop.spec.js` checks a lecturer has no Change Password, and the centred-dialog check moved to a new admin test; Playwright 6 passed. Maestro not run because Yew Sing's backend and Expo were running. Reviewer agent not run.
- Next: Yew Sing confirms the bubble on the phone. T94 stays unticked.

### Fix — loop waits through every usage-limit message and keeps partial work — 2026-11-09
- Changed: `scripts/run-tasks.sh` missed "You've hit your 5-hour limit" (newer CLI wording), so it would have quit at the limit again. It now matches any "hit your ... limit", on the log's last line only, so a round that merely mentions a Gemini rate limit doesn't sleep for hours. Partial work stays in the tree instead of a stash, and the retry is told to continue it with `--append-system-prompt`.
- Decisions: `claude -p` has no auto-continue, so this script is the loop's only protection whichever app starts it. New optional env `SMARTCLASS_LIMIT_WAIT_MIN` (default 30), used by the tests.
- Tests: new `test_run_tasks_script.py` runs the real script in a throwaway repo with fake `claude` and `docker`; the 5-hour case failed before the fix. check.sh passes (204). Not yet exercised against a real limit. Reviewer agent not run.

### Fix — T94 testing: chat bubble second attempt, deactivated login message — 2026-11-09
- Changed: `textBreakStrategy` didn't fix the hidden last word on Yew Sing's phone, so it's removed. The user bubble now measures its text once, then gives it a fixed, slightly wider width (`services/bubbleWidth.js`). Login tells a deactivated user so (403), only after the password is confirmed; a wrong password stays a generic 401. UC-M1 updated.
- Interface: `POST /auth/login` and `POST /auth/moodle-login` return 403 for a deactivated account (was 401). Tests: five existing assertions changed from 401 to 403 on purpose (Yew Sing's decision), a wrong-password check added, `bubbleWidth.test.js` added; check.sh passes (204). Bubble not confirmed on a phone: it only shows on Yew Sing's phone. Reviewer agent and Maestro not run.
- Next: Yew Sing confirms the bubble. T94 stays unticked. Yew Sing left the matric clash, toasts, garbled maths and PDF sharpness for later.

### Fix — T94 testing: class details screen, tabs return to their main page, 15-minute sync — 2026-11-09
- Changed: new lecturer `ClassDetail` screen (schedule, room, students with matric no and face status, search, pull to refresh), opened from the Home card, Home upcoming rows and Profile class cards (FR-119, new). `AppNavigator` `screenListeners`: pressing a tab goes to its main page instead of the page last left open. `getClasses`/`getLecturerAllClasses` drop a leading course code from the name, because Moodle full names repeat it. `MOODLE_SYNC_INTERVAL_SECONDS` default 3600 → 900.
- Decisions (Yew Sing): shorter sync instead of instant updates, because a Moodle plugin can't go on the real SPeCTRUM. "Sync now" stays with T22, in the admin area of the web app.
- Interface: no API/schema change (uses existing `GET /classes/{id}/students`, already lecturer-scoped). Tests: Playwright `class-detail.spec.js` (3), `tabs.spec.js` (6; 4 failed before the fix), all lecturer web specs 17 passed. Not run on a phone: Maestro needs Yew Sing's backend and Expo stopped, and `adb` saw no device. Reviewer agent not run.
- Next: Yew Sing tries both on the phone. T94, then prepare the merge.

### T14 — PDPA consent + withdrawal — 2026-11-09
- Changed: new `face_consents` table + model, `consent_service.py`, `routers/student_face.py` (`GET/POST/DELETE /student/me/face-consent`); `/admin/students/{id}/face-enroll` and `/admin/face-review/{id}/promote` now return 409 without active consent (NFR-03). Config `FACE_CONSENT_VERSION` (default `2026-11-v1`).
- Decisions: one row per acceptance; withdrawal sets `withdrawn_at` (history kept) and deletes embeddings in the same request; POST must send the current notice version (else 409), re-accepting is a 200 no-op, a newer version closes the old row. Audit actions `FACE_CONSENT_GIVE` / `FACE_CONSENT_WITHDRAW`. Admin "reset face data" needs no consent (it only deletes).
- Interface/schema changes: migration `d4e5f6a7b8c9`; new student endpoints; the two admin enrolment endpoints gain a 409. For the merge note: `frontend/admin` face upload now fails for students who haven't consented in the student app.
- Tests: new `test_face_consent.py` (12); `test_char_face_review.py` promote test records consent first (behaviour changed on purpose, no assertion weakened). check.sh 216 passed; reviewer PASS.
- Next: T15.

### T15 — Card verification service — 2026-11-09
- Changed: new `services/face_verification.py`: `match_faces` (largest card face vs averaged selfies, cosine), `run_ocr`/`read_card` (local RapidOCR; matric via `CARD_MATRIC_REGEX` with O→0/I→1 fixes, name = share of account name words found, spaces ignored), `check_quality` (reasons in message order: too_dark, no_card_found, card_too_small, angled, blurry, glare, no_face_on_card, each with a retake message), `verify_card` for T16. 12 `CARD_*` settings in config.
- Decisions: quality blocks only when no matric reaches `CARD_OCR_MIN_CONFIDENCE` (0.85); glare = largest blown-out patch after opening, so white print isn't glare; card crop only shrunk before the blur measure; auto-approve needs face + matric + name. Generated cards: genuine face 0.94, worst impostor 0.15 (threshold 0.30). OCR reads a 20%-brightness card, so dark-only photos pass if readable.
- Interface: new dep `rapidocr-onnxruntime==1.4.4`; new pytest marker `face` (conftest skips it when insightface/rapidocr/buffalo_sc are missing). No API/schema change. Tests: `test_face_verification.py` (28, `tests/card_images.py` generator); check.sh 244 passed; reviewer PASS.
- Next: T16. Real-photo thresholds are T21's job.

### T16 — Face self-enrolment endpoint — 2026-11-09
- Changed: `GET/POST /student/me/face-enrolment` in `routers/student_face.py`, new `face_enrolment_service.py`, models `FaceEnrolment` + `FaceEnrolmentImage`; `FaceMatch.selfie_embedding` (also set when the card has no face); consent withdrawal withdraws a pending submission and deletes its photos + embedding; `scripts/eval_card_quality.py` for T21 (`backend/eval/` git-ignored).
- Decisions: status is derived (embeddings → active, else latest non-blocked submission: pending_review/rejected, else not_enrolled); auto-approve stores no photos at all; pending keeps photos in the DB, OCR lines and the averaged selfie embedding so T17 approves without re-running models (T17 must call `clear_review_data`); a quality block saves only a `blocked` row (reasons + scores) as the submit-anyway counter; `submit_anyway` before 2 blocks is ignored; 409 while active or pending; no face in selfies / not an image → 422 retake, not counted.
- Interface/schema: migration `e6f7a8b9c0d1` (`face_enrolments`, `face_enrolment_images`, applied to the dev DB); 422 body is `{"detail": {reasons, message, blocked_attempts, can_submit_anyway}}`, 413 over `FACE_ENROL_MAX_IMAGE_BYTES`; audit `FACE_ENROL_AUTO_APPROVE`/`FACE_ENROL_SUBMIT`. Tests: `test_face_enrolment.py` (22, 2 with real models on generated cards), `test_eval_card_quality.py` (2); check.sh 268 passed; reviewer PASS.
- Next: T17. No M2 notification hook exists yet for `face_enrolment.pending_review`/`.result` (FR-114); NFR-01's 24 h limit relies on T17 clearing photos at decision time (no sweeper).

### T17 — Lecturer verification queue + admin fallback — 2026-11-09
- Changed: new `routers/face_verification.py`: `GET /face-verification/pending`, `GET /face-verification/{id}/images/{image_id}` (`no-store`), `POST /{id}/approve`, `POST /{id}/reject {reason}`; `face_enrolment_service.close_pending`; `DELETE /admin/students/{id}/face-data` (reset) also closes pending submissions as `reset` and deletes their photos.
- Decisions: "the student's courses" = the lecturer is assigned to any class of a course the student is enrolled in (any class of it); admins see all pending, also students in no course. Approve needs active consent (409) and copies the stored selfie embedding; reject needs a non-blank reason (≤500, trimmed). A decision clears photos, OCR lines and the pending embedding; deciding twice is 409. Audit `FACE_ENROL_APPROVE`/`FACE_ENROL_REJECT` (target = student user id); reset keeps `FACE_REMOVE` and now 404s only when there are neither embeddings nor a pending submission.
- Interface: new endpoints above; list items carry account name/matric, OCR matric + confidence + lines, face/name scores, check reasons, shared course codes and image URLs (fetch with the token). New enrolment status value `reset` (no schema change). Tests: `test_face_verification_queue.py` (22); check.sh 290 passed; reviewer PASS.
- Next: T19 (lecturer UI) can load images with `Image source={{uri, headers}}`; the M2 `face_enrolment.result` notification (FR-114) still has no hook to call.

### T18 — Student app: face enrolment UI — 2026-11-09
- Changed: student app `FaceEnrolment` (status, start/try again, withdraw consent), `FaceConsent` (PDPA notice, accepts `current_version`), `FaceCapture` (expo-camera: 3 guided selfies with an oval, card photo with an ID-1 card outline, review, 422 retake message + Retake, "Submit anyway" when the server allows it); Profile → "Face enrolment"; `services/faceEnrolment.js`; `client.js` `apiUpload` (multipart, refresh-retry) and errors now keep `err.detail` (object details give `message`).
- Decisions: retake target comes from the 422 reasons (card-quality reasons → card, `no_face_in_selfies` → selfies, `not_an_image` → all); after a selfie retake the card photo is kept. Withdraw consent added to the status screen (FR-116/UC-106, no other task had the UI).
- Interface: new dep `expo-camera ~17.0.10` + app.json plugin (camera permission text); no API/schema change. Tests: `faceEnrolment.test.js` (10); Maestro `face-enrolment.yaml` PASS end to end incl. emulator camera (virtual scene has no face → 422 selfie retake), student4, leaves no consent behind; check.sh 290 passed; reviewer PASS.
- Next: auto-approve / pending / submit-anyway on screen need a real phone with a real card (T21/T23).
