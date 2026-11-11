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
- (done in T18b) the T14 consent-less face data, T15/T16 selfie consistency, T18 phone photo deletion, T16 content type, T17 `ocr_matric` and T14 consent version review items.
- T21: also calibrate `FACE_SELFIE_CONSISTENCY_THRESHOLD` (0.45) on real angled selfies, and `CARD_UM_TEXT_REGEX` on real card OCR output.
- REVIEW: T16/T17 - no task delivers FR-113/FR-114 events. The FR doc says that until M2 exists they appear as live updates in the app, but a student only sees a result on reopening the status screen and a lecturer only on reloading the queue. T44 creates `notify.emit` for attendance only. Add `face_enrolment.pending_review` and `.result` once T44 exists, and a live update for T19.
- (done 2026-11-10: install line added to CLAUDE.md) REVIEW: T15 - `insightface` is only in `face_worker/requirements.txt`, so a backend installed by the `CLAUDE.md` steps answers 503 on enrolment and the `face` tests skip. Put this in the merge note for Shino or document the extra install.
- (T19) Playwright `class-detail.spec.js` (2 tests) fails since WIA0000 has 11 students (Yew Sing's own account in the Moodle seed): it counts rendered `FlatList` rows, and only 10 render at first. ClassDetail was not changed by T19; the test (or `initialNumToRender`) needs a look.
- (T19) `Pillow` is used directly by `backend/scripts/e2e_face_review.py` and `tests/card_images.py` but only installed as a dependency of other packages; pin it in `requirements.txt`.
- (done in T22) audit labels for `FACE_CONSENT_*`, `FACE_ENROL_*` are in the new admin audit log screen (`adminHelpers.js`); `frontend/admin` keeps its old list until T96.
- (T22) The new admin area only creates administrators, but `POST /admin/users` still accepts student/lecturer because `frontend/admin` uses it. Restrict it to `role=admin` in T96.
- REVIEW: T19/T22 - the lecturer web E2E suite is red (2 `class-detail.spec.js` tests) since the Moodle seed gave WIA0000 11 students (4263306). Two `[UI]` tasks were ticked with the suite partly failing; fix the test or the list (`initialNumToRender`) before the next `[UI]` task so a real regression isn't hidden. Checkpoint review 4263306..f996310: no other cross-task problems (check.sh 336 + 229 db passed).
- No runnable task (2026-11-10): T21 is `[HUMAN]` (card calibration) and T23 `[HUMAN] Checkpoint` (M1 + admin screens on real devices) is unticked, which gates every task below it. Yew Sing ticks T23 to resume the loop (next would be T29).
- (fixed 2026-11-12) REVIEW: T29×T30 - the low-attendance alert counted from `opened_at`, so with T29's 15-min early open it fired before class and never during it. Now it counts from `starts_at` (fallback `opened_at`); test `test_low_attendance_alert_waits_for_class_start_not_early_open`.
- REVIEW: T30/T32 × Module 7 (Shino) - since T30 a `late` record counts as neither present nor absent in Shino's `routers/analytics.py` (lines 75-76, 151-152, 206 count only `present`; `unidentified` still listed), so `/student/me/attendance[/summary]` and lecturer analytics now disagree with T32's `/student/me/attendance/courses`. Don't edit `analytics.py`; T37's `docs/interfaces.md` should point her at `ATTENDED_STATUSES` / `attendance_stats`, and add a line to `docs/requests-for-shino.md`.
- REVIEW: T29→T38 - a missed class becomes `needs_confirmation` with `opened_at` NULL, and `GET /lecturer/sessions` hides never-opened rows, so the lecturer can't find it. T38's Done-when asks for "confirm a `needs_confirmation` session" but not for listing these; T38 must list them too.
- REVIEW: T29 - until T38, Start on the always-open WIA0000 gets 409 in the lecturer app (the scheduler already opened it). Expected interim state. (Mark Present/Absent works again since the override reason became optional, 2026-11-12.)
- REVIEW: T33 (low) - the CSV exports write student names as-is, so a Moodle name starting with `=`, `+`, `-` or `@` becomes a spreadsheet formula when a lecturer opens the file in Excel. Prefix such cells with `'` in both `export_session` and `export_occurrence`. Checkpoint review 61bcc73..45d6e2c: check.sh 457 passed, `pytest -m db` 324 passed; no finished task reopened.
- (2026-11-11) T23a's first loop session hit the 80-turn limit and left its work uncommitted; it is committed as `WIP T23a` (untested, unreviewed) and T23a is split into T23a (card checks) + T23b (lecturer web fixes). For big tasks run `bash scripts/run-tasks.sh <rounds> 150`.

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

### Fix — profile data from Moodle, seed accounts, request file for Shino — 2026-11-10
- Changed: `moodle_sync.profile_fields` reads Moodle `idnumber`, `department` and custom profile fields `programme` / `yearsem`; new accounts get them, a full sync refreshes linked accounts (empty Moodle value keeps ours; a number clash skips that person), login copies programme/year too. Moodle seed: 3 more students (student6-8), matric 23004901-08, programmes across all six FSKTM BCS specialisations, staff ids/departments; `seed_courses.php` creates the profile fields and updates existing users; `seed.sh` adds a git-ignored `seed_config.local.json` (Yew Sing's own account, 23004976).
- Decisions (Yew Sing): faculty in full English; "Year N, Semester 1 (2026/2027)"; programmes spread. Dev DB: Yew Sing's real card photos on the old pending test submission (student1) deleted, status `reset`.
- Interface: sync report gains `profiles_updated`. No schema change (columns existed). New `docs/requests-for-shino.md` (R1: face enrolment notifications), linked from CLAUDE.md; CLAUDE.md backend setup now installs `face_worker/requirements.txt` (insightface).
- Tests: 3 new (`test_moodle_login.py` programme/year; `test_moodle_sync.py` new+linked refresh, clash skip). Ran the real seed + full sync against local Moodle: 9 students and 3 lecturers have full profiles.
- Next: T18b (in PLAN.md, now also UM-card text check and the Expo Go crash details).

### T18b — Face enrolment fixes from the checkpoint review and phone test — 2026-11-10
- Changed: migration `f7a8b9c0d1e2` deletes embeddings without active consent (applied to the dev DB); `match_faces` embeds each selfie (`selfie_faces`, lowest pairwise cosine → `selfies_consistent`); `read_card` sets `um_card`; enrolment needs the current consent version (409), stores the type sniffed from the bytes, `nosniff` on review photos; `clear_review_data` clears `ocr_matric`. App: one `CameraView` switching `facing`, shutter only when ready and the last photo is saved, restart on `onMountError` or after 8 s, error boundary with "Try again", photos shrunk to 1280 px (`expo-image-manipulator`) and deleted after submit, retake and on leaving; PDPA text from `consentSummary`.
- Decisions: <3 selfies with a face → 422; ≥3 but one without a face → review `selfie_without_face`; mixed faces → `selfies_inconsistent`; not UM text → `not_um_card`. `FACE_SELFIE_CONSISTENCY_THRESHOLD` 0.45 (generated: same person 0.92, mixed ≤0.16; real angled selfies are lower, calibrate in T21), `CARD_UM_TEXT_REGEX` on OCR letters joined without spaces.
- Interface/schema: new migration (data only); new review reasons above; `POST /student/me/face-enrolment` gives 409 on an old consent version. New dep `expo-image-manipulator ~14.0.8`.
- Tests: `test_face_enrolment_checks.py` (29, incl. real-model mixed faces + non-UM card); `_result` helper in `test_face_enrolment.py` gained the new fields; 2 JS unit tests; check.sh 322 passed; Maestro `student face-enrolment` PASS (back camera shows the scene); reviewer PASS. `[~]`: Yew Sing checks (4) on his phone: card step not black, 3 quick selfies no crash.

### T19 — Lecturer app: face verification queue — 2026-11-10
- Changed: lecturer `FaceVerification` screen (selfies next to the card photo, tap to enlarge, account vs card matric, scores, reason chips, Approve with confirm, Reject with a required reason), Home banner with the pending count, Profile row; `AuthImage` fetches review photos with the token (blob URL on web, data URI on phones: Android's new-arch `Image` dropped `headers`, the server answered 403); `services/faceReview.js` helpers; lecturer `npm test` (node --test), run by check.sh.
- Decisions: nothing written to an image cache (photos held in memory, NFR-01); 409/404 on a decision removes the card and reloads. E2E data: `backend/scripts/e2e_face_review.py seed|clean --student <email>` (placeholder PNGs, current consent, dummy embedding); `e2e-mobile.sh` runs an optional `e2e/<flow>.setup.sh` (setup before Maestro, teardown on exit).
- Interface/schema: none (uses T17 endpoints). Tests: `faceReview.test.js` (6), `test_e2e_face_review_seed.py` (2, db); check.sh 324 passed; Maestro `lecturer face-verification` PASS (lecturer1 approves student8); Playwright `face-verification.spec.js` PASS (devlecturer rejects student7, photos decode in the browser); reviewer PASS.
- Next: T20. Two older Playwright class-detail tests fail on the 11-student WIA0000 (see Next).

### T20 — Profile fields (FR-107) — 2026-11-10
- Changed: `GET /auth/me` adds `courses` ({id, code, name}, distinct, by code: students' enrolled courses, lecturers' taught courses, admins none) and `face_status` (students only, from `face_enrolment_service.enrolment_status`). Name, email, matric/staff no and faculty/dept were already in `UserOut`.
- Decisions: login responses keep `courses: []` and `face_status: null` (no extra queries at login); the apps should read the profile from `/auth/me`.
- Interface: `UserOut` gains `courses` + `face_status` (additive). No schema change. Tests: `test_profile_me.py` (5); check.sh 329 passed; reviewer PASS.
- Next: the student/lecturer Profile screens can show the courses and face status from `/auth/me` (no task covers the UI yet).

### T22 — Admin area inside the lecturer web app — 2026-11-10
- Changed: admin logins (browser email sign-in) land on `AdminTabs` instead of the lecturer screens: Accounts (search, role/status filters, deactivate/reactivate with inline confirm, reset face data, new administrator, change own password), Face verification (the T19 screen, all pending), Audit log (paged, labels in `services/adminHelpers.js`), SPeCTRUM sync (last result + Sync now). On a phone an admin gets a "browser only" page with Sign out. `GET /admin/users` adds `q` + `status`.
- Decisions: confirms are inline, not dialogs (toasts hide behind RN `Modal`); only administrators are created here, since Moodle owns students and lecturers; no self-deactivate button (server rule from T12).
- Interface: `GET /admin/users?q=&status=active|inactive` (q matches name/email/matric/staff no, wildcards literal); `UserDetailOut.moodle_linked` (additive). No schema change.
- Tests: `test_admin_user_search.py` (7 db), `adminHelpers.test.js` (6); Playwright `admin.spec.js` (3: deactivate/reactivate student6 + audit + sync now, no self-deactivate, lecturer no admin nav + 403 on 3 admin endpoints); `desktop.spec.js` admin password test now starts in the admin area (admins no longer see lecturer Home); web suite 19 passed, 2 `class-detail` failing as before T22 (see Next); check.sh 336 passed; reviewer PASS.

### T23a — Card check fixes from the T21 photos — 2026-11-11 [~]
- Changed: `_find_card` looks for the card by colour (one hue at a time, convex hull, so a hand isn't merged with it) before falling back to Canny; `_best_rotation` tries 0/90/180/270 and keeps the turn with an upright face (eyes above mouth), else the best OCR; UM text = any of `CARD_UM_KEYWORDS` (UNIVERSITI, MALAYA, MYSISWA) within 1–2 edits, any order; blur default 40 measured on the card region (long side 856 px); `eval_card_quality.py` prints rotation, UM card and AUTO-APPROVE / REVIEW (reasons) / BLOCKED; student card outline is portrait 54:86 with "Hold the card upright (portrait)".
- Decisions: "UNIVERSITI TEKNOLOGI MALAYSIA" now counts as UM text; another university's card is still stopped by the matric check (test). Config: `CARD_UM_TEXT_REGEX` is now an optional extra (empty by default), new `CARD_UM_KEYWORDS`, `CARD_MIN_SATURATION`. `CardVerification.rotation` + `review_reasons()` (moved from the router). No schema change.
- Tests: portrait card on a white table, hand next to the card, turns 90/180/270, OCR runs once when upright, split UM text, transport card without matric, UM text misreads/look-alikes, blur default + measured on the card; check.sh 362 passed (run alone); Maestro `student face-enrolment` PASS (first try lost to an emulator "Bluetooth keeps stopping" dialog); reviewer PASS.
- [~] Manual: `backend/eval/cards/` is absent here, so Yew Sing re-runs `python scripts/eval_card_quality.py --matric <no> --name "<name>" eval/cards` and records the per-photo outcome (expect clear close photos AUTO-APPROVE, the 2 very blurry BLOCKED, far-away ones card_too_small).
- Next: T23b. Review note: the stored card photo stays as uploaded, so a lecturer reviewing a sideways card sees it unrotated (could store the turned image).

### T23b — Lecturer web app fixes from the T23 device test — 2026-11-12
- Changed: first hybrid round (plan Opus `.claude/plans/T23b.md`, build OpenCode deepseek-v4.1-flash, review Sonnet). The WIP T23a commit already held session restore (`services/session.js`), Accounts refresh on focus and the non-email sign-in message; DeepSeek added a no-status session test and `initialNumToRender={60}` on ClassDetail, which fixes the 2 long-failing `class-detail.spec.js` tests (11 students in WIA0000).
- Interface/schema: none. Tests: lecturer `npm test` 19 passed; Playwright `npm run e2e:web` 25/25 (reviewer ran it); check.sh 362 passed. Reviewer: code PASS (its only findings were the tick and this entry).
- Loop fixes found on this round: a crashed OpenCode left a pytest run going that clobbered the next one (test DB now has a per-run lock + 600 s test timeout); OpenCode retries on connection errors; the reviewer no longer flags the not-yet-written tick/log.

### T23 retest — 2026-11-12 (Yew Sing, phone + browser)
- T23a manual check done: `eval_card_quality.py` on the 13 real card photos: 11 AUTO-APPROVE (2 needed a 90/270 turn), the 2 very blurry ones BLOCKED (blur 8.9, 11.5); before T23a, 8 were `no_card_found` and 3 `card_too_small` (misdetections). Phone: proper card auto-approved; myrapid transport card went to review (matric unreadable, face 3%). T23a ticked `[x]`.
- T23b passed in the browser (stays signed in after refresh, Accounts refresh, sign-in message). New gap → T23c: Accounts shows "No face data" while a submission is pending review.

### T23c — Admin Accounts shows a pending face submission — 2026-11-12
- Changed: `face_enrolment_service.enrolment_statuses` + `status_word` (one query per page); `UserDetailOut.face_status`; admin Accounts shows an amber "Pending review" badge with a "Review in Face verification" link, shows "Face rejected", and offers "Reset face data" for pending submissions too.
- Decisions: status words are the existing `not_enrolled | pending_review | active | rejected` (the task said `none`; `not_enrolled` matches `/auth/me` and the student status endpoint); `null` for non-students. Interface: `GET /admin/users` items and `GET/POST/PUT /admin/users[/{id}]` responses gain `face_status` (additive); `face_enrolled` kept for `frontend/admin` until T96; no schema change, no migration.
- Tests: `test_admin_face_status.py` (7 db, incl. parity with `enrolment_status` and one-query check), `adminHelpers.test.js` face status case; Playwright `admin.spec.js` approve-then-Accounts now opens Face verification from the row's link; `npm run e2e:web` 25/25; check.sh 369 passed; reviewer PASS.
- TEST-CHANGE: admin.spec.js "admin approves a face, and Accounts shows it on return" - renamed and now expects "Pending review" (not "No face data") for the seeded pending submission and opens Face verification through the row's link; "No face data" there was the T23c bug.
- Next: nothing; `frontend/admin` keeps `face_enrolled` until T96.

### T29 — Sessions open from the class schedule — 2026-11-11 (built by OpenCode, finished by Opus)
- Changed: `services/session_schedule.py` job (`tick`, `session_scheduler_loop`, opens 15 min early, closes at end, one `source=schedule` row per class date) + lecturer ops (weekly schedule, start now, change time, cancel, extend, end early, confirm), all audited; new `routers/class_schedule.py`; E2E launchers set `SESSION_SCHEDULER_INTERVAL_SECONDS=0`; audit labels in `adminHelpers.js`. Opus fixed the audit actor (now the caller, not the row's lecturer) and the 3 tests below.
- Decisions: FR-317 lecturer action = start now, extend, or a time change during the class; overrides count via their record, unidentified faces don't. Changes/cancel ahead create a `scheduled`/`cancelled` row. Dev uvicorn now auto-opens WIA0000 all day, so the app's Start button gets 409 for it until T38. Config: `SESSION_EARLY_OPEN_MINUTES`, `SESSION_SCHEDULER_INTERVAL_SECONDS`, `SESSION_DEFAULT_MINUTES`.
- Interface/schema: migration `a7b8c9d0e1f2` (occurrence day/start/end nullable; sessions gain `class_date`, `starts_at`, `ends_at`, `source`, `lecturer_action_at`, nullable `opened_at`, status/source CHECKs, partial unique index). `SessionOut` adds those fields; `POST /lecturer/sessions` takes optional `duration_minutes`; new `PUT /lecturer/classes/{id}/schedule`, `PUT /lecturer/classes/{id}/dates/{date}`, `POST .../dates/{date}/cancel`, `POST /lecturer/sessions/{id}/extend`, `/confirm`; `GET /lecturer/sessions` hides never-opened rows; job's WS `session_closed` carries `status`.
- Tests: `test_session_schedule.py` (31 db, controlled clock); check.sh 400 passed; reviewer PASS. Audit lookups in `test_char_attendance.py` (2) and `test_char_face_review.py` (1) now filter by the action under test, since Start now writes its own `SESSION_START_NOW` row; assertions unchanged.
- Next: a `scheduled` row missed entirely (server down) becomes `needs_confirmation` with `opened_at` NULL, so `GET /lecturer/sessions` hides it and the lecturer can't find it to confirm (T38 should list it); un-cancel a class; T35 syncs only `closed` and queues on `confirm(held=true)`.


### T30 — Four attendance statuses — 2026-11-11
- Changed: `models/attendance.py` constants + CHECK; `attendance_service.status_for_recognition` + `mark_present(now=)` writes present/late; `get_session_counts` grouped (present/late/excused/absent/unid); both overrides accept the four statuses (400 otherwise); occurrence CSV letters P/L/E/A; face-match dry-run `already_present` true for late; low-attendance alerts count present + late.
- Decisions: Late is strictly more than `ATTENDANCE_LATE_AFTER_MINUTES` after the effective start (`starts_at`, falling back to `opened_at`); exactly 15:00 is Present; only the first recognition counts (existing records never changed); Excused is left out of the export rate denominator (decision T00d).
- Interface/schema: migration `b8c9d0e1f2a3` maps every unknown status (`unidentified` included) to `absent` then adds CHECK `ck_attendance_records_status`; `SessionOut`, the WS `counts` dict and close responses gain `late` + `excused` (additive); absent = enrolled − present − late − excused. Config: `ATTENDANCE_LATE_AFTER_MINUTES` (default 15).
- Tests: new `test_attendance_statuses.py` (15 db, incl. real migration test); targeted set 84 passed; check.sh 415 passed; reviewer PASS.
- TEST-CHANGE: `test_override_rejects_other_statuses` - "late" is a valid status since T30 (FR-304); it now sends "unidentified", still 400.
- Next: lecturer app (`LecturerContext.jsx`, `AttendanceDetail.jsx`) and student `api.js` still count/map `unidentified` and don't show Late/Excused → T38/T39; Shino's `analytics.py` counts only `present` as attended and still mentions `unidentified` (T37 / requests-for-shino).

### T31 — Override with mandatory reason + full audit (FR-305, NFR-06) — 2026-11-11
- Changed: both override endpoints require `reason` (stripped, 1–500 chars, else 422) and audit `new_val={"status", "reason"}`; `frontend/admin` AuditLogView shows the reason; new `tests/test_attendance_override_reason.py`; 5 existing test files now send a reason.
- Decisions: the reason lives only in the append-only audit row (actor=`actor_id`, time=`ts`), not on `attendance_records`; NFR-06 is enforced at API level (only `GET /admin/audit-logs`) and pinned by a test; the lecturer app's Mark Present/Absent gets 422 until T38 adds a reason dialog.
- Interface/schema: `PUT /attendance/{record_id}/override` and `PUT /lecturer/sessions/{id}/attendance/override` now require `reason` (string, 1–500 after trimming, 422 otherwise); the `ATTENDANCE_OVERRIDE` audit `new_val` is now `{"status", "reason"}`. No schema change, no migration. Tests: new 13-case db suite (422s for missing/empty/whitespace/too-long, audit actor/old/new/reason/time, NFR-06), targeted db set 96 passed, check.sh 428 passed, admin build passed; reviewer PASS. Next: T38 must add a reason input to `StudentModal` and pass it through `overrideAttendance`/`LecturerContext.overrideStudent`; no Maestro/Playwright flow exercises override.
- TEST-CHANGE: test_char_attendance - bodies send `reason`, and the audit `new_val` assertion now expects `{"status": "present", "reason": "Seen in class"}` (intended interface change); test_char_sessions · test_attendance_statuses · test_session_schedule · test_lecturer_access - bodies send `reason`, assertions unchanged (the 403/400 paths still test ownership/status).

### T32 — Attendance rate + history (FR-307–FR-309) — 2026-11-11
- Changed: new `services/attendance_stats.py` (`StatusCounts`, `session_date`, `student_course_history`, `class_student_rates`, `counts_out`), new `routers/attendance_stats.py` and `schemas/attendance_stats.py`; router registered in `main.py` right after `attendance.router`.
- Decisions: rate = (present + late) ÷ (closed − excused), 1 decimal, `null` when the denominator is 0 (never `0.0` or a division error); only `closed` sessions count (`open`/`scheduled`/`needs_confirmation`/`cancelled` never do, FR-317); a missing record in a closed session is absent, in an open session `not_recorded` (shown, not counted); student view is per course (lecture + tutorial combined), lecturer view per class they are assigned to (NFR-04 / T00f).
- Interface/schema (additive): new `GET /student/me/attendance/courses` (student; per-course counts + rate + session history) and `GET /lecturer/classes/{occurrence_id}/attendance/rates` (assigned lecturer only; per-student counts + rate); new service for T33/T37 to reuse. No schema change, no migration.
- Tests: new `test_attendance_rates.py` (17: formula, zero closed sessions, every session excused, only-closed counting, open-session visibility, course grouping, access control, confirm → closed); `pytest -m db` 312 passed; check.sh 445 passed; reviewer PASS.
- Next: T33 should make `export_occurrence` use `StatusCounts` (it prints `0.0%` where the API gives null); T39 should move the student app off Shino's `/student/me/attendance*`, which still counts only `present`; students enrolled mid-semester are absent for earlier sessions.

### T33 — Reports + CSV export for course/date range (FR-310) — 2026-11-11
- Changed: session CSV (`export_session`) fixes (missing record `not_recorded` unless closed, filename from the class date); class CSV (`export_occurrence`) rebuilt on new `class_report`; new `class_report`, `session_label`, `resolve_date_range` and factored `_class_students` in `services/attendance_stats.py`; new JSON `GET /lecturer/classes/{occurrence_id}/attendance/report?from=&to=` with schemas; new `tests/test_attendance_reports.py` (12 db).
- Decisions: "course" report = per class (occurrence), like T32's lecturer rates; only `closed` sessions; date range on the class's MYT date, inclusive; missing record = absent in closed sessions, `not_recorded` in the session CSV of an unfinished session.
- Interface (CSV, intended change): class header now `Matric No, Name, <YYYY-MM-DD HH:MM per session>, Present, Late, Excused, Absent, Total, Rate`; Rate is blank when nothing counts (was `0.0%`); accepts `from`/`to` (old `from_date`/`to_date` still work); 422 when from > to; filename `attendance_report_<code>_<from>_<to>.csv`. Session export: missing records in a non-closed session read `not_recorded` (was `absent`); filename date from `class_date`. New JSON report returns sessions + per-student statuses, counts, rate. No schema change, no migration.
- Tests: new 12-case db suite (headers/rows, all four statuses, inclusive + legacy ranges, closed-only, 422, JSON/CSV/rates parity, access); targeted set 74 passed; check.sh 457 passed; reviewer PASS.
- Next: the lecturer app's export/Analytics still sends `from_date`/`to_date` (works); a Reports screen using the JSON endpoint is not in any UI task yet (T38 candidate).
- TEST-CHANGE: test_char_attendance::test_session_csv_export, test_char_attendance::test_occurrence_csv_export_with_date_range, test_attendance_statuses::test_occurrence_export_letters_and_rate - T33 CSV format change (four status count columns, blank rate when nothing counts, not_recorded for open sessions); same data, expectations updated to the new format.

### T31 follow-up — override reason made optional — 2026-11-12
- Yew Sing decided the override reason should be optional (FR-305 said mandatory). Changed FR-305, UC-M3 override flow steps 2-3, PLAN T31/T38 lines; `OverrideReason` is now optional: trimmed, blank or missing → `null`, more than 500 chars → 422. Audit `new_val` stays `{"status", "reason"}` with `reason: null` when none was given; admin AuditLogView already hides an empty reason.
- Interface: `PUT /attendance/{record_id}/override` and `PUT /lecturer/sessions/{id}/attendance/override` accept `reason` as optional (was required). No schema change, no migration. The lecturer app's Mark Present/Absent (no reason) works again.
- Tests: `test_attendance_override_reason.py` - 8 new cases (both endpoints save and audit with missing/null/empty/whitespace reason); override-related set 53 passed.
- TEST-CHANGE: test_attendance_override_reason::test_record_override_requires_reason and ::test_session_override_requires_reason - renamed to `..._rejects_too_long_reason` and now cover only the 501-char case; the missing/empty/whitespace cases moved to the new `..._without_reason_is_saved_and_audited` tests, because the requirement changed (FR-305 reason optional, Yew Sing 2026-11-12).

### Loop: faster rounds + Opus coach — 2026-11-12
- Tests: db tests spent ~1.5 s each in setup hashing ~6 test passwords at bcrypt cost 12; `conftest.py` now sets cost 4 for tests only (app unchanged). check.sh pytest 9:38 → 2:53 (460 passed).
- `run-tasks.sh` (hybrid): skips the post-commit check.sh when the committed code equals the code its pre-review check.sh passed on (`code_tree`, ignores PLAN.md/PROGRESS.md/.claude). Stuck or still-failing builds get an Opus **coach** (read-only diagnosis → `scripts/opencode/coach-fix.md` → OpenCode applies it), at most 2 rounds, before the Opus takeover (Yew Sing 2026-11-11: loop must not stop). Coach notes in `<round log>.coach`.
- `/plan-task`: **Run** lists only targeted tests (no check.sh / full db suite, the loop runs check.sh); routes a task to `OPUS:` when it needs 2+ of migration on existing tables, background job/concurrency, time/timezone rules, >3 existing endpoints. `build.md`: async SQLAlchemy / clock / migration traps; don't run check.sh.
- `backup-data.sh` keeps the newest 2 backups (was 3) and drops empty ones.

### T34 — Moodle Attendance plugin in the simulated SPeCTRUM — 2026-11-12
- Changed: new `backend/moodle/scripts/install_attendance.php` (pinned `mod_attendance` download into `mod/attendance`, idempotent, plain PHP without `config.php`); `setup.sh` installs it and runs `admin/cli/upgrade.php --non-interactive` before configuring; `configure_moodle.php` adds five `mod_attendance_*` functions, a "not installed; run setup.sh" guard and `attendance/studentscanmark(_default)=0`; `seed_courses.php` adds one "Attendance" activity (section 0, via `add_moduleinfo`) per seeded course; README updated; new `tests/test_moodle_attendance.py`.
- Decisions: pin MOODLE_405_STABLE commit `7985321…` (version 2024082404, requires 4.5); the first setup run needs internet inside the container; `upgrade.php` runs on every setup run (a previous run may have installed the files and then failed the upgrade); seed idempotency is checked by `attendance.course` and a dry run skips a not-yet-created course; students never mark themselves (site setting + `add_session` never enables it); statuses stay the plugin's P/A/L/E.
- Interface (Moodle side): the `smartclass` service now also exposes `mod_attendance_add_session`, `_remove_session`, `_get_session`, `_get_sessions`, `_update_user_status`; each seeded course has one "Attendance" activity in section 0 (find it via `core_course_get_contents` → `modname == "attendance"`, `instance` = attendanceid). Shino must re-run `setup.sh` + `seed.sh` after pulling (merge note). SmartClass DB/API: no changes, no migration.
- Tests: new `moodle` suite 7 items (one activity per seeded course, get_sessions with the service token, add/get/list/remove a session with four statuses + `studentscanmark=0`, student token refused) - 11 passed with the existing moodle sync/login tests, none skipped; targeted non-moodle sync + assistant set 37 passed; `ruff check .` clean; reviewer PASS.
- Next: T35 reads the activity via `core_course_get_contents` and syncs closed sessions into it; no SmartClass sync code, mapping table or sync status here.

### T35 — Sync closed sessions to Moodle Attendance — 2026-11-12
- Changed: new `services/attendance_moodle_sync.py` (find-or-create the Moodle session: stored id → description marker `SmartClass <code> session #<id>` + start time → `add_session`; P/L/E/A mapped to the session's status set; only records whose status ≠ `moodle_status_sent` are sent) + background loop in `main.py`; `close_session` queues (`pending`) sessions tied to a class; config `MOODLE_ATTENDANCE_SYNC_INTERVAL_SECONDS` (30), `_RETRY_BASE_SECONDS` (60), `_RETRY_MAX_SECONDS` (3600).
- Decisions: failures → `failed`, backoff base·2^(n-1) capped, retries never stop (NFR-20); what was already sent is kept; students without `moodle_user_id` are skipped and counted in `moodle_sync_error` on a `synced` session; "taken by" = the lecturer's Moodle id, else the service account; sessions closed before T35 (NULL status) and `needs_confirmation` ones are never sent; `conflict` is only allowed by the constraint (T36 sets it).
- Schema (migration `c9d0e1f2a3b4`): `attendance_sessions` + `moodle_sync_status` (CHECK pending|synced|failed|conflict, indexed), `moodle_session_id`, `moodle_sync_attempts`, `moodle_sync_next_at`, `moodle_synced_at`, `moodle_sync_error`; `attendance_records` + `moodle_status_sent` (CHECK four statuses). No API change.
- Tests: new `test_attendance_moodle_sync.py` (15 db with respx + 1 `moodle` end-to-end into local WIA0000, cleans up its Moodle session); check.sh 475 passed; `-m moodle` 12 passed; reviewer PASS.
- Next: T36 (re-sync after override, conflict check, retry endpoint, sync status in the session API).

### T81 — Scheduled material sync + lecturer materials status — 2026-11-12
- Changed: `services/kb/sync.py` `sync_all` now re-fetches each course per iteration and logs a captured `code`, fixing a real bug found while testing: a failed course's `rollback()` expired every loaded `Course`, so the log line and the next course hit SQLAlchemy `MissingGreenlet` under async. The schedule (`kb_sync_loop` + `KB_SYNC_INTERVAL_SECONDS`), the manual trigger (`POST /kb/courses/{id}/sync`) and the status list (`GET /kb/courses/{id}/materials`) already existed from T80; T81 formalises and tests the scheduled path and access control.
- Decisions: no new endpoints or schema — "only the course's lecturer (or admin)" is already enforced by `_course_for_staff` in the router.
- Interface/schema changes: none.
- Tests: new `tests/test_kb_sync_schedule.py` (5 `db` tests: sync_all over every Moodle-linked course, skip non-Moodle courses, isolate a failing course, loop disabled without a token and at zero interval); check.sh 480 passed.
- Next: T82.

### T82 — Live Gemini suite + record/replay + Q&A eval harness — 2026-11-12 [~]
- Changed: `llm.py` adapter hardening — client-side `LLM_RPM` rate limiter (default 10), retry with backoff on 429/5xx (max `LLM_MAX_RETRIES`=3), a distinct `LLMQuotaExhausted` for daily-quota 429s (Gemini wraps the error in a one-element list body, handled in `_error_kind`), and a loop-aware client (tests run each case on its own event loop; reusing one httpx client across loops raised "Event loop is closed"). Config: `LLM_RPM`, `LLM_MAX_RETRIES`, `LLM_RETRY_BASE_SECONDS`.
- Decisions: the live suite runs over a synthetic, copyright-free test course (`tests/fixtures/course/` 3 original software-testing notes → PDFs, indexed by `synthetic_kb`), so it's stable and never touches real material. check.sh runs `pytest -m live` once per KB code state (hash → `.claude/.live-pass`), printing `LIVE TESTS PENDING (quota)` when quota is exhausted (detected via `-rs` skip reasons) instead of failing the round. Recording → `tests/fixtures/llm/qa.json`, replayed at zero cost by `test_qa_replay.py`.
- Interface/schema changes: none (config only). `.gitignore` allows `backend/eval/qa_set.jsonl` while still ignoring `backend/eval/cards/`.
- Tests: `test_llm_hardening.py` (10), `test_synthetic_course.py` (2), `test_qa_replay.py` (replays the 2 recorded answers), `tests/live/test_live_qa.py` (19: 10 in-syllabus + 5 off-syllabus + 2 follow-up + prompt-injection + empty course). check.sh 493 passed with the live suite skipping `LLM_QUOTA`.
- [~] Manual: Gemini's free-tier daily quota (20 requests/day for gemini-3.5-flash thinking) is exhausted, so the full ~30-call live run and recording couldn't finish. Re-run `cd backend && python -m pytest -m live --record-llm` after the quota resets to record the remaining fixtures and confirm the whole suite passes.
- Next: T85.
