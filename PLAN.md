# PLAN — Yew Sing's modules (M1, M3, M4, M8)

Spec: `docs/requirements/*.md`, `docs/use-cases/UC-M*.md`. Rules: `CLAUDE.md` → "Task Loop Rules".

**Legend:** `[ ]` todo · `[x]` done · `[~]` done but needs a manual check (see PROGRESS.md) · `[!]` blocked

**Tags:** `[API]` backend · `[UI]` mobile/web, done only when its E2E flow passes · `[INFRA]` tooling · `[HUMAN]` the loop skips it; Yew Sing does it

**Picking rule:** the first `[ ]` task, top to bottom, whose `Depends on` tasks are all `[x]` or `[~]` and which isn't `[HUMAN]`. **A `[HUMAN] Checkpoint` stops the loop:** no task below an unticked checkpoint may start. Other `[HUMAN]` tasks are simply skipped.

---

## 0. Foundation

- [x] **T01 [INFRA] Test + lint baseline.** Depends on: —.
  Done when: `backend/pytest.ini` defines markers `db`, `live`, `moodle`, `e2e` and `asyncio_default_fixture_loop_scope`; `backend/tests/conftest.py` gives `db` tests a separate `smartclass_test` database on the docker postgres (created + migrated with alembic per test session, cleaned between tests) and an authenticated `httpx.AsyncClient` fixture per role; the 15 existing ruff errors are fixed (unused imports; `app/core/config.py` re-saved as UTF-8 without changing its content) so `ruff check .` in `backend/` passes with the existing `ruff.toml`; `requirements-dev.txt` (pytest, pytest-asyncio, respx, ruff); one sample `db` test (login with seeded admin) passes; `bash scripts/check.sh` passes.
- [x] **T02 [API] Characterisation tests for existing behaviour.** Depends on: T01.
  Done when: `db` tests cover the current auth (login/refresh/me), session open/close, attendance list/override and CSV export, and face-review endpoints — at least 12 tests, all passing against the unchanged code. No production code changes except real bugs, each noted in PROGRESS.md.
- [x] **T03 [INFRA] Mobile + web E2E harness.** Depends on: T01.
  Done when: `scripts/e2e-mobile.sh <app> <flow>` boots AVD `Pixel_4_API_35` (headless if possible), adds `$LOCALAPPDATA/Android/Sdk/platform-tools` to PATH, starts the backend and Expo (`EXPO_PUBLIC_API_URL=http://10.0.2.2:8000`), opens the app in Expo Go and runs `mobile/<app>/e2e/<flow>.yaml` with Maestro (install the Maestro CLI if missing; Java 21 is present). `smoke.yaml` for both apps (login screen visible) passes. The script cleans up on exit (trap): it stops the uvicorn and Expo processes it started and the emulator if it booted it, so the next round doesn't find ports 8000/8081 taken. The lecturer app gets its Expo web dependencies (`react-native-web`, `react-dom`, `@expo/metro-runtime`), and `mobile/lecturer/e2e-web/` has a Playwright smoke test (the login page renders in the browser) runnable via `npm run e2e:web`. If Maestro can't be installed or Expo Go can't be automated, write the exact error under Blocked.
- [x] **T04 [HUMAN] Checkpoint: review T01–T03.** The loop stops here (all feature tasks depend on T04). Yew Sing (or a Claude review session) checks the T01–T03 diffs and PROGRESS.md, then ticks `[x]` to let the loop continue.

## 0b. Week 7 demo — AI chat first

These M8 tasks run before everything else after the T04 checkpoint, so the student chat screen is ready for the Week 7 monitoring demo. The rest of M8 stays in section 4.

- [x] **T80 [API] Characterisation tests for KB + assistant.** Depends on: T01, T04.
  Done when: `db` tests cover materials list, sync (Moodle mocked), chat session CRUD and message answer (LLM mocked through the adapter), course access control (not-enrolled → 403), at least 10 tests.
- [x] **T93 [API] Phone-friendly answer format.** Depends on: T80.
  Done when: the system prompt forbids LaTeX and asks for plain-text formulas; a backend cleanup step runs on every answer before it is saved and converts any remaining LaTeX (`$$…$$`, `\frac{a}{b}`, `\text{}`, `\times`, `\%`) to readable text; citations are renumbered 1, 2, 3… by first appearance in both the answer text and the citation list; unit tests cover each conversion and the renumbering, including an answer citing [1], [2], [4].
- [x] **T84 [API] Open cited source (FR-809).** Depends on: T80.
  Done when: `GET /student/assistant/materials/{id}/file` streams the material (proxied from Moodle, enrolled students only) and citations carry page/slide numbers the app can open; tests.
- [x] **T89 [UI] Student app: assistant chat with citations.** Depends on: T84, T93, T03.
  Done when: new Assistant tab: course picker, sessions list, chat with citation chips that open the source; general-knowledge label shown; Maestro flow asks a question with the backend's LLM mocked (`LLM_FAKE=1` env flag added for E2E) and sees a citation.
- [ ] **T94 [HUMAN] Checkpoint: try the AI chat before Week 7.** Yew Sing asks real questions on a phone and taps citations. A Claude session reviews the work so far, then Yew Sing can say "prepare the merge".

## 0c. Lecturer web

- [ ] **T05 [UI] Lecturer app runs in the browser.** Depends on: T03, T04.
  Done when: the existing lecturer app (same code, Expo web) works in a desktop browser: every current screen opens without a runtime error; phone-only modules have web fallbacks (e.g. token storage); layouts use wide screens through a side navigation and a sensible content width instead of a stretched phone column, while the phone layout stays unchanged; `npx expo export --platform web` and the Android export both pass; `scripts/check.sh` runs the web export when `mobile/lecturer/src` changes; a Playwright flow logs a lecturer in at 1280 px and reaches the dashboard with no horizontal scrolling, and the existing Maestro `smoke.yaml` still passes.

## 1. Module 1 — User Management

- [ ] **T10 [API] Moodle login + account auto-creation (FR-101, FR-102, FR-106).** Depends on: T02, T04.
  Done when: `POST /auth/moodle-login {username, password}` gets a token from Moodle `login/token.php` (service `smartclass`), reads the profile via `core_webservice_get_site_info`, creates or updates the SmartClass user (lecturer if they teach any course in Moodle, else student) and returns the same token shape as `/auth/login`; the password is never stored or logged; wrong credentials → 401 with a generic message; Moodle down → 503. Unit tests mock Moodle with respx (≥6 cases); one `moodle` test logs in `student1` against the local Moodle.
- [ ] **T11 [API] Course + enrolment sync from Moodle (FR-104).** Depends on: T10.
  Done when: a sync service maps Moodle courses → SmartClass courses/occurrences (record the mapping decision in PROGRESS.md), adds and removes enrolments and lecturer assignments to match Moodle, runs for the user on login, on `POST /admin/moodle/sync`, and on a schedule (interval from config); idempotent (running twice changes nothing). Tests: add, remove, idempotency, Moodle failure leaves data unchanged.
- [ ] **T12 [API] Admin accounts: deactivate/reactivate, create admin, audit (FR-103, FR-108, FR-118).** Depends on: T02, T04.
  Done when: a deactivated user can't log in (local or Moodle) and can't refresh tokens; an admin can't deactivate themselves; each change writes an audit entry; tests for each rule.
- [ ] **T13 [UI] Mobile login uses Moodle credentials (both apps).** Depends on: T10, T03.
  Done when: both login screens ask for SPeCTRUM username + password and call `/auth/moodle-login`; error messages for 401 and 503; the phone apps have no administrator sign-in, because admins use the browser only; Maestro flows `login.yaml` log in `student1` / `lecturer1` and reach the home screen.
- [ ] **T14 [API] PDPA consent + withdrawal (FR-109, FR-116, NFR-03).** Depends on: T02, T04.
  Done when: migration adds a consent record (student, version, accepted_at, withdrawn_at); `POST /student/me/face-consent`, `DELETE /student/me/face-consent` (deletes embeddings at once, audited); enrolment endpoints refuse without active consent; tests.
- [ ] **T15 [API] Card verification service (FR-111).** Depends on: T01, T04.
  Done when: `app/services/face_verification.py` provides (a) a selfie ↔ card face similarity check using InsightFace, and (b) matric number + name extraction from a card image with a **local** OCR library (card images must not leave the server — PDPA; e.g. `rapidocr-onnxruntime`), with thresholds in config. Tests use generated card images (PIL: rendered matric number/name/faculty text + an InsightFace sample face pasted in) for: match, wrong face, wrong matric number, unreadable card.
  Also (c) a **photo quality check** that returns specific, fixable reasons: `no_card_found`, `blurry` (Laplacian variance), `glare` (share of near-white saturated pixels inside the card area), `too_dark`, `card_too_small`/`angled`, `no_face_on_card`. To avoid rejecting good photos: thresholds live in config, and the quality check only **blocks** when OCR *also* fails to read a valid matric number. If OCR reads the matric number with high confidence, the photo is accepted even if the glare score is high. Tests: generated glare (white ellipse overlay), blur (Gaussian), dark and clean cards, including "glare present but text readable → accepted".
- [ ] **T16 [API] Face self-enrolment endpoint (FR-110, FR-112, FR-115, NFR-01).** Depends on: T14, T15.
  Done when: `POST /student/me/face-enrolment` (multipart: 3–5 selfies + card) → auto-approves (embeddings stored, status `active`) when both checks pass, else status `pending_review`; `GET /student/me/face-enrolment` returns the status and any rejection reason; images are deleted after the decision (pending ones are kept only until review, and NFR-01 applies); tests for both paths and for image deletion. Before saving anything, the card photo goes through the T15 quality check: a blocking quality failure returns 422 with the reason codes and a user-facing message (e.g. "Glare is covering your card details. Tilt the card away from the light and retake."), and nothing is stored. After 2 blocked attempts, the student may choose "submit anyway", which sends it to lecturer review instead of blocking a third time.
- [ ] **T17 [API] Lecturer verification queue + admin fallback (FR-113, FR-114, FR-117).** Depends on: T16.
  Done when: lecturers of any of the student's courses can list pending submissions (selfie + card images, OCR result, account matric/name, score) and approve or reject with a reason; admins can do the same and reset face data; other lecturers get 403; each decision is audited and the images deleted; tests.
- [ ] **T18 [UI] Student app: consent + guided selfie + card capture + status.** Depends on: T16, T03.
  Done when: Profile → "Face enrolment" walks through consent → 3 selfies → card photo (card-outline guide on the camera screen; on a 422 the specific retake message is shown with a Retake button, and "submit anyway" after 2 tries) → result/status screen; Maestro flow runs up to the consent and status screens (camera steps may use the emulator's virtual camera; if they can't be automated, mark `[~]`).
- [ ] **T21 [HUMAN] Calibrate card checks on real photos.** Depends on: T16. Yew Sing takes ~10 photos of his own matric card (clean, glare, blur, angled, dim) into a local, git-ignored folder `backend/eval/cards/` and runs `python scripts/eval_card_quality.py` (written in T16), which prints the quality scores + OCR result per photo. Adjust the thresholds in `.env` until good photos pass and bad ones get the right message.
- [ ] **T19 [UI] Lecturer app: face verification queue.** Depends on: T17, T03.
  Done when: a lecturer screen lists pending submissions with side-by-side images and approve/reject (reason required); Maestro flow approves a seeded pending submission.
- [ ] **T20 [API] Profile fields (FR-107).** Depends on: T11.
  Done when: `/auth/me` returns name, matric/staff number, email, faculty, courses, face status (students); test.
- [ ] **T22 [UI] Admin area inside the lecturer web app (FR-103, FR-108, FR-117).** Depends on: T05, T11, T12, T17.
  Done when: the browser login offers administrator sign-in with local email + password; admin-role logins land on an admin area, available on web only, with these screens: accounts (view, deactivate/reactivate, create admin), verification fallback + face data reset, audit log, and Moodle sync status with a sync button. Lecturer logins never see these screens and the server still returns 403 to them. Playwright flows: an admin deactivates and reactivates an account; a lecturer sees no admin navigation and gets 403 from an admin endpoint.
- [ ] **T23 [HUMAN] Checkpoint: M1 and admin screens on real devices.** Yew Sing tries Moodle login, face enrolment and lecturer review on a phone, and the admin area in a browser. A Claude session reviews the work so far.

## 2. Module 3 — Attendance Management

- [ ] **T29 [API] Sessions open from the class schedule (FR-301, FR-315–FR-317).** Depends on: T02, T04.
  Done when: a background job opens each class's session `SESSION_EARLY_OPEN_MINUTES` (config, default 15) before its scheduled start and closes it at the scheduled end, once per class date, in Malaysia time; sessions store their effective start and end; a lecturer can set the weekly schedule (day, time, room) of classes they teach, which Moodle sync never overwrites; for one class a lecturer can change the time (before or during it), start now, end early, extend or cancel, each audited and without changing the weekly schedule; a class with no schedule never opens by itself but can be started manually; a session reaching its end with no recognitions and no lecturer action becomes `needs_confirmation`, with no Absent marks and no Moodle sync until the lecturer confirms it was held or not held; tests use a controlled clock for each case.
- [ ] **T30 [API] Four attendance statuses (FR-302–FR-304).** Depends on: T29.
  Done when: attendance status is limited to `present | late | excused | absent`; a first recognition more than `ATTENDANCE_LATE_AFTER_MINUTES` (config, default 15) after the session's effective start records `late`; `excused` is only ever set by a lecturer override (data migration: existing `unidentified` records → `absent`, and unidentified faces live only in the face-review table); the API, seed and tests are updated; CHECK constraint in the DB.
- [ ] **T31 [API] Override with mandatory reason + full audit (FR-305, NFR-06).** Depends on: T30.
  Done when: both override endpoints require a non-empty reason (422 otherwise) and audit actor, old, new, reason, time; only the class's lecturer may override (already enforced, with the NFR-04 checks on open, close, roster and exports, in `tests/test_lecturer_access.py`; keep those tests passing). The T02 tests that override without a reason are updated to send one, with a `TEST-CHANGE:` line.
- [ ] **T32 [API] Attendance rate + history (FR-307–FR-309).** Depends on: T30.
  Done when: rate = (present + late) ÷ (closed sessions − excused) per student per course, with status counts returned too; student endpoint returns per-course rate + session history; lecturer endpoint returns per-student rates for a course; tests including zero closed sessions and every session excused.
- [ ] **T33 [API] Reports + CSV export for course/date range (FR-310).** Depends on: T32.
  Done when: CSV for a session and for a course over `from`/`to` (students × sessions showing all four statuses + rate); tests check headers and rows.
- [ ] **T34 [INFRA] Moodle Attendance plugin in the simulated SPeCTRUM.** Depends on: T01, T04.
  Done when: `backend/moodle/scripts/setup.sh` installs `mod_attendance` (version matching Moodle 4.5) idempotently, adds its web-service functions (`mod_attendance_add_session`, `mod_attendance_get_sessions`, `mod_attendance_update_user_status`, …) to the `smartclass` service, and `seed.sh` adds an Attendance activity to each seeded course; the plugin's student self-marking stays off for these sessions; a `moodle` test calls `mod_attendance_get_sessions` successfully.
- [ ] **T35 [API] Sync closed sessions to Moodle Attendance (FR-311, NFR-20, NFR-22).** Depends on: T34, T30.
  Done when: closing a session queues a sync that finds or creates the matching Moodle attendance session and sets each student's status (all four statuses mapped one-to-one to the plugin's status ids); the last status sent for each student is stored; the sync status (`pending | synced | failed | conflict`) is stored on the session; failures retry with backoff; idempotent; unit tests with respx + one `moodle` test end-to-end.
- [ ] **T36 [API] Re-sync after override, Moodle mismatch check + retry endpoint (FR-312, FR-320).** Depends on: T35, T31.
  Done when: an override on a synced session sets it back to `pending` and re-syncs; before changing a session already in Moodle, and on each scheduled check of synced sessions, the sync reads Moodle's statuses; a student whose Moodle status differs from the last one sent is never overwritten, and the session becomes `conflict` with both values; the lecturer keeps SmartClass's value or takes Moodle's through an endpoint (audited, then re-synced); `POST /lecturer/sessions/{id}/moodle-sync` retries now; sync status in the session API; tests.
- [ ] **T37 [API] Read interface for Module 7 (FR-313).** Depends on: T32.
  Done when: `app/services/attendance_read.py` exposes documented functions (records per course/student, rates, consecutive absences); `docs/interfaces.md` describes them for Shino; tests.
- [ ] **T38 [UI] Lecturer app: live session, class controls, override with reason, sync status.** Depends on: T29, T31, T36, T03.
  Done when: lecturers can set a class's weekly schedule, and for one class change the time, start now, end early, extend, cancel, or confirm a `needs_confirmation` session; the session screen updates live over the websocket, late students are shown separately, override offers all four statuses and asks for a reason, sync status is shown with a Retry button, and a conflict shows both values with a choice; Maestro flow starts a session now, overrides a student to Excused with a reason and ends it.
- [ ] **T39 [UI] Student app: attendance rate + history per course.** Depends on: T32, T03.
  Done when: the Attendance screen shows per-course rate, status counts and session list (all four statuses) from the real API; Maestro flow checks a seeded rate.

## 3. Module 4 — Face Recognition Verification

- [ ] **T40 [API] Camera device registry + per-device keys + heartbeat (FR-408, NFR-07, NFR-23).** Depends on: T02, T04.
  Done when: admins can register a device (name, room) and get its key once (stored hashed), regenerate a key (old one revoked); device endpoints authenticate with `X-Device-Key` instead of the shared internal key; `POST /device/heartbeat`; online = heartbeat within 60 s; tests.
- [ ] **T41 [API] Server-side recognition from face crops (FR-402–FR-405, NFR-10, NFR-22).** Depends on: T40, T30.
  Done when: `POST /device/faces` (multipart crop(s)) embeds on the server, matches only students enrolled in the open session's course above the threshold, keeps per-device consecutive-match votes (default 3) and records Present or Late through the attendance service; non-enrolled matches are logged, not recorded; tests with InsightFace sample images (match, late arrival, below threshold, not enrolled, vote counting, duplicate).
- [ ] **T42 [API] Device client for Pi and webcam (FR-401, FR-409, FR-411).** Depends on: T41.
  Done when: `device_client/` (replaces `face_worker/`'s role) polls for an open session for its room, detects faces locally (light model suitable for a Pi), POSTs crops with its key, sends heartbeats, optionally buffers while offline; runs on the laptop with a USB webcam via `python -m device_client --camera 0`; unit tests for the detection → crop → post logic with a fake camera.
- [ ] **T43 [API] Student flags "not recognised"; lecturer resolves (FR-318, FR-319, FR-407, FR-410, NFR-02).** Depends on: T41, T31.
  Done when: while a session is open, an enrolled student with no record can flag it once, and the lecturer's live channel gets an event; the lecturer lists flags with the student's name and matric number, plus the closest unmatched crop if any, with its similarity; the lecturer confirms (Present or Late from the flag time, source `student_flag`, audited, re-synced if already synced) or rejects with a reason, and the student sees the result; flags unresolved at close leave the student Absent and stay in the lecturer's list; no screen asks a lecturer to identify an unclaimed face; unmatched crops are stored per session and deleted on resolution, with a retention job after 7 days; admin keeps access as a fallback; tests include flagging outside an open session, not enrolled, already recorded, and another lecturer's 403.
- [ ] **T44 [API] Recognition feedback events (FR-406, NFR-12).** Depends on: T41.
  Done when: on Present or Late, a websocket event goes to the lecturer's session channel and to the student's channel, and `app/services/notify.py` exposes `emit(event, user_ids, payload)` as the M2 hook (logs only for now, documented in `docs/interfaces.md`); tests.
- [ ] **T45 [UI] Student "I'm here" flag, lecturer flag alerts, "attendance recorded" banner.** Depends on: T43, T44, T03.
  Done when: the student app's flag button appears only during an open session with no record, and the old mock report screen (`AttReportStatus`) shows the real flag status; Maestro flows: a student flags and sees pending then the result; the lecturer sees the alert and confirms it; the student app shows the banner after a simulated recognition.
- [ ] **T46 [UI] Admin area: device management page.** Depends on: T40, T22.
  Done when: page lists devices with online status, registers a device and shows the key once, regenerates a key; Playwright test.
- [ ] **T47 [HUMAN] Run the device client on the Raspberry Pi** with the Pi camera at the door; measure NFR-11 (fps) and NFR-10; record results in PROGRESS.md.
- [ ] **T48 [HUMAN] Checkpoint: full attendance run.** Yew Sing runs one class end to end with the camera: a scheduled session opens by itself, Present and Late recognition, a student flags and the lecturer confirms, override to Excused, close, and check the statuses in Moodle. A Claude session reviews the work so far.

## 4. Module 8 — AI Learning Assistant

- [ ] **T81 [API] Scheduled material sync + lecturer materials status (FR-803, FR-804).** Depends on: T80.
  Done when: sync runs on a configurable schedule for all courses; only the course's lecturer (or admin) can trigger a sync or list status; tests.
- [ ] **T82 [INFRA] Live Gemini test suite + record/replay + Q&A evaluation harness (NFR-18, NFR-19, NFR-21).** Depends on: T80.
  Done when:
  - **Synthetic test course:** `backend/tests/fixtures/course/` holds 3 short teaching documents written for testing (e.g. software-testing notes; no real course material), indexed into the test DB by a fixture. Live tests use only this, so they are stable and copyright-free.
  - **LLM adapter hardening (production code):** client-side rate limiter (`LLM_RPM`, default 10), retry with backoff on 429/5xx (max 3), and a distinct `LLMQuotaExhausted` error for daily-quota exhaustion.
  - **Live suite** `backend/tests/live/` (`@pytest.mark.live`, about 30–40 calls per run). It checks *structure and grounding*, never exact wording: ≥8 in-syllabus questions (answer parses; ≥1 citation; every citation points to a passage that was actually retrieved; cited passage contains the key term); ≥4 off-syllabus questions (labelled general knowledge, no fake citations); 2 follow-up conversations (the stand-alone query keeps the topic); prompt-injection text inside a document doesn't change the answer format; an empty-course question → general-knowledge answer. Each case may retry once for nondeterminism; a case failing twice fails the suite.
  - **Record/replay:** `pytest -m live --record-llm` saves the real responses to `backend/tests/fixtures/llm/*.json`. Normal (non-live) tests replay them, so the parsing/citation code is tested every round against *real* Gemini output at zero cost. Hand-written mocks stay only for error cases Gemini rarely produces (malformed output, timeout, 429).
  - **Automatic trigger:** `scripts/check.sh` runs `pytest -m live` itself when the round changed `app/services/kb/` or any prompt file (diff vs `SMARTCLASS_BASE`). It runs **at most once per code state**: a hash of `app/services/kb/` + prompts is stored in `.claude/.live-pass` (git-ignored) after a pass, and check.sh skips the live suite when the hash is unchanged. Otherwise the Stop hook and the loop script calling check.sh several times per round would burn the daily quota. If Gemini's daily quota is exhausted, the live tests skip with reason `LLM_QUOTA` and check.sh prints `LIVE TESTS PENDING (quota)`; the task is then marked `[~]` with "re-run live tests" instead of blocking the loop.
  - **Eval harness:** `backend/eval/qa_set.jsonl` (draft ~20 in-syllabus + 5 off-syllabus questions over the seeded courses, `draft: true`) and `scripts/eval_assistant.py`, which runs them throttled and reports citation-support, off-syllabus labelling, latency (NFR-14) and an LLM-judged correctness score, for the report.
- [ ] **T83 [HUMAN] Review and finalise the Q&A evaluation set** (correct answers, remove `draft`).
- [ ] **T85 [API] Summary / study guide (FR-810).** Depends on: T82.
  Done when: `POST /student/assistant/summaries {course_id, material_id | topic, kind: summary|study_guide}` returns structured markdown with citations; replay/mock tests + live cases added to the T82 suite (≥3: material summary, topic study guide, topic not in materials) with recorded fixtures.
- [ ] **T86 [API] Flashcards + practice questions (FR-811).** Depends on: T82.
  Done when: endpoint returns validated JSON (cards: front/back/citation; questions: stem/options/answer/explanation/citation); malformed LLM output is retried once, then 502; replay/mock tests + live cases in the T82 suite (≥4: flashcards and practice questions for 2 materials each, JSON schema-valid, every citation real) with recorded fixtures.
- [ ] **T87 [API] Anonymised question trends for lecturers (FR-813, NFR-09).** Depends on: T80.
  Done when: each student question is tagged with a topic (from the cited materials/sections or a cheap LLM label); the lecturer endpoint returns three lists, most-asked topics, most-cited materials, and most-asked topics the materials don't cover (answers labelled general knowledge), each with ≥3 distinct students only and no names or text; tests prove that k<3 topics are hidden and that no endpoint exposes another student's chat.
- [ ] **T88 [API] Retrieval interface for Module 6 (FR-814).** Depends on: T80.
  Done when: `app/services/kb/retrieval_api.py` (`search(course_id, query, k)` → passages with source) is documented in `docs/interfaces.md`; tests.
- [ ] **T90 [UI] Student app: summaries + flashcards/practice.** Depends on: T85, T86, T89.
  Done when: screens for generate summary, flip flashcards, answer practice questions; Maestro flow with the fake LLM.
- [ ] **T91 [UI] Lecturer app: materials status + sync button + question trends.** Depends on: T81, T87, T03.
  Done when: Maestro flow triggers a sync and sees the statuses and all three trends lists.
- [ ] **T100 [API] Lecturer asks their own materials (FR-815).** Depends on: T82, T87.
  Done when: a lecturer can create, list, rename and delete chats and ask questions for courses they teach (other lecturers and students get 403), through the same answer code as students, with the same citations and labels; chats have one owner, a student or a lecturer (migration); a lecturer's chats are visible only to that lecturer and are never counted in question trends (test); replay/mock tests + live cases in the T82 suite with recorded fixtures.
- [ ] **T101 [API] "Before next class" summary (FR-816, NFR-09).** Depends on: T82, T87.
  Done when: `GET` for a course returns a short summary built only from the T87 aggregates, with what to revisit (citing material sections that exist) and what the materials don't cover; a test proves the LLM prompt holds no names, chat text or topics below the 3-student minimum; with too little data it returns "not enough questions yet" and makes no LLM call; the result is cached until the trends change; only the course's lecturer can read it; replay/mock tests + live cases in the T82 suite with recorded fixtures.
- [ ] **T102 [UI] Lecturer app: ask my materials + before next class summary.** Depends on: T05, T91, T100, T101.
  Done when: the lecturer app has both screens on phone and in the browser; citations open the source; Maestro and Playwright flows with the fake LLM ask a question and see a citation, and read a seeded summary.
- [ ] **T92 [API] YouTube suggestions (FR-812, Could Have).** Depends on: T85.
  Done when: YouTube Data API search behind config (`YOUTUBE_API_KEY`; feature off when empty); mocked tests. Needs Yew Sing to add the key to `.env`.

## 5. Wrap-up

- [x] **T95 [HUMAN] Confirm with Shino that `frontend/admin` can go.** Shino confirmed on 2026-11-09 that her modules won't use it.
- [ ] **T96 [INFRA] Retire `frontend/admin`.** Depends on: T22, T46, T95.
  Done when: PROGRESS.md lists every old admin view and where it went (Users → accounts; FaceData, FaceReviewQueue → verification fallback; AuditLog → audit log; Students, Lecturers, Enrollment, ClassManagement → replaced by Moodle sync; Dashboard → removed); `frontend/admin/` is deleted; `scripts/check.sh`, README and CLAUDE.md no longer refer to it; no backend endpoint is removed unless a test shows nothing uses it; `bash scripts/check.sh` and the admin-area Playwright flows pass.
- [ ] **T98 [INFRA] Docs refresh.** Depends on: all API tasks of M1/M3/M4/M8.
  Done when: README and CLAUDE.md run instructions match reality (device client, Moodle plugin, E2E); `docs/interfaces.md` is complete.
- [ ] **T99 [HUMAN] UAT preparation** (VPS deploy, test accounts, consent forms, and installable Android APKs of the student and lecturer apps pointed at the server, e.g. with EAS Build, because Expo Go needs the laptop's dev server).

**Deferred (not in this plan, waiting on M6):** FR-820–FR-824.
