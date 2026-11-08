# PLAN — Yew Sing's modules (M1, M3, M4, M8)

Spec: `docs/requirements/*.md`, `docs/use-cases/UC-M*.md`. Rules: `CLAUDE.md` → "Task Loop Rules".

**Legend:** `[ ]` todo · `[x]` done · `[~]` done but needs a manual check (see PROGRESS.md) · `[!]` blocked

**Tags:** `[API]` backend · `[UI]` mobile/web, done only when its E2E flow passes · `[INFRA]` tooling · `[HUMAN]` the loop skips it; Yew Sing does it

**Picking rule:** the first `[ ]` task, top to bottom, whose `Depends on` tasks are all `[x]` or `[~]` and which isn't `[HUMAN]`.

---

## 0. Foundation

- [x] **T01 [INFRA] Test + lint baseline.** Depends on: —.
  Done when: `backend/pytest.ini` defines markers `db`, `live`, `moodle`, `e2e` and `asyncio_default_fixture_loop_scope`; `backend/tests/conftest.py` gives `db` tests a separate `smartclass_test` database on the docker postgres (created + migrated with alembic per test session, cleaned between tests) and an authenticated `httpx.AsyncClient` fixture per role; the 15 existing ruff errors are fixed (unused imports; `app/core/config.py` re-saved as UTF-8 without changing its content) so `ruff check .` in `backend/` passes with the existing `ruff.toml`; `requirements-dev.txt` (pytest, pytest-asyncio, respx, ruff); one sample `db` test (login with seeded admin) passes; `bash scripts/check.sh` passes.
- [x] **T02 [API] Characterisation tests for existing behaviour.** Depends on: T01.
  Done when: `db` tests cover the current auth (login/refresh/me), session open/close, attendance list/override and CSV export, and face-review endpoints — at least 12 tests, all passing against the unchanged code. No production code changes except real bugs, each noted in PROGRESS.md.
- [ ] **T03 [INFRA] Mobile + web E2E harness.** Depends on: T01.
  Done when: `scripts/e2e-mobile.sh <app> <flow>` boots AVD `Pixel_4_API_35` (headless if possible), adds `$LOCALAPPDATA/Android/Sdk/platform-tools` to PATH, starts the backend and Expo (`EXPO_PUBLIC_API_URL=http://10.0.2.2:8000`), opens the app in Expo Go and runs `mobile/<app>/e2e/<flow>.yaml` with Maestro (install the Maestro CLI if missing; Java 21 is present). `smoke.yaml` for both apps (login screen visible) passes. The script cleans up on exit (trap): it stops the uvicorn and Expo processes it started and the emulator if it booted it, so the next round doesn't find ports 8000/8081 taken. The lecturer app gets its Expo web dependencies (`react-native-web`, `react-dom`, `@expo/metro-runtime`), and `mobile/lecturer/e2e-web/` has a Playwright smoke test (the login page renders in the browser) runnable via `npm run e2e:web`. If Maestro can't be installed or Expo Go can't be automated, write the exact error under Blocked.
- [ ] **T04 [HUMAN] Checkpoint: review T01–T03.** The loop stops here (all feature tasks depend on T04). Yew Sing (or a Claude review session) checks the T01–T03 diffs and PROGRESS.md, then ticks `[x]` to let the loop continue.

## 0b. Week 7 demo — AI chat first

These M8 tasks run before everything else after the T04 checkpoint, so the student chat screen is ready for the Week 7 monitoring demo. The rest of M8 stays in section 4.

- [ ] **T80 [API] Characterisation tests for KB + assistant.** Depends on: T01, T04.
  Done when: `db` tests cover materials list, sync (Moodle mocked), chat session CRUD and message answer (LLM mocked through the adapter), course access control (not-enrolled → 403), at least 10 tests.
- [ ] **T93 [API] Phone-friendly answer format.** Depends on: T80.
  Done when: the system prompt forbids LaTeX and asks for plain-text formulas; a backend cleanup step runs on every answer before it is saved and converts any remaining LaTeX (`$$…$$`, `\frac{a}{b}`, `\text{}`, `\times`, `\%`) to readable text; citations are renumbered 1, 2, 3… by first appearance in both the answer text and the citation list; unit tests cover each conversion and the renumbering, including an answer citing [1], [2], [4].
- [ ] **T84 [API] Open cited source (FR-809).** Depends on: T80.
  Done when: `GET /student/assistant/materials/{id}/file` streams the material (proxied from Moodle, enrolled students only) and citations carry page/slide numbers the app can open; tests.
- [ ] **T89 [UI] Student app: assistant chat with citations.** Depends on: T84, T93, T03.
  Done when: new Assistant tab: course picker, sessions list, chat with citation chips that open the source; general-knowledge label shown; Maestro flow asks a question with the backend's LLM mocked (`LLM_FAKE=1` env flag added for E2E) and sees a citation.

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
  Done when: both login screens ask for SPeCTRUM username + password and call `/auth/moodle-login`; error messages for 401 and 503; Maestro flows `login.yaml` log in `student1` / `lecturer1` and reach the home screen.
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

## 2. Module 3 — Attendance Management

- [ ] **T30 [API] Present/Absent only (FR-304).** Depends on: T02, T04.
  Done when: attendance status is limited to `present | absent` (data migration: existing `unidentified` records → `absent`, and unidentified faces live only in the face-review table); the API, seed and tests are updated; CHECK constraint in the DB.
- [ ] **T31 [API] Override with mandatory reason + full audit (FR-305, NFR-06).** Depends on: T30.
  Done when: both override endpoints require a non-empty reason (422 otherwise) and audit actor, old, new, reason, time; only the course's lecturer may override (403 test).
- [ ] **T32 [API] Attendance rate + history (FR-307–FR-309).** Depends on: T30.
  Done when: rate = present ÷ closed sessions per student per course; student endpoint returns per-course rate + session history; lecturer endpoint returns per-student rates for a course; tests including zero closed sessions.
- [ ] **T33 [API] Reports + CSV export for course/date range (FR-310).** Depends on: T32.
  Done when: CSV for a session and for a course over `from`/`to` (students × sessions + rate); tests check headers and rows.
- [ ] **T34 [INFRA] Moodle Attendance plugin in the simulated SPeCTRUM.** Depends on: T01, T04.
  Done when: `backend/moodle/scripts/setup.sh` installs `mod_attendance` (version matching Moodle 4.5) idempotently, adds its web-service functions (`mod_attendance_add_session`, `mod_attendance_get_sessions`, `mod_attendance_update_user_status`, …) to the `smartclass` service, and `seed.sh` adds an Attendance activity to each seeded course; a `moodle` test calls `mod_attendance_get_sessions` successfully.
- [ ] **T35 [API] Sync closed sessions to Moodle Attendance (FR-311, NFR-20, NFR-22).** Depends on: T34, T30.
  Done when: closing a session queues a sync that finds or creates the matching Moodle attendance session and sets each student's status (Present/Absent mapped to the plugin's status ids); the sync status (`pending | synced | failed`) is stored on the session; failures retry with backoff; idempotent; unit tests with respx + one `moodle` test end-to-end.
- [ ] **T36 [API] Re-sync after override + retry endpoint (FR-312).** Depends on: T35, T31.
  Done when: an override on a synced session sets it back to `pending` and re-syncs; `POST /lecturer/sessions/{id}/moodle-sync` retries now; sync status in the session API; tests.
- [ ] **T37 [API] Read interface for Module 7 (FR-313).** Depends on: T32.
  Done when: `app/services/attendance_read.py` exposes documented functions (records per course/student, rates, consecutive absences); `docs/interfaces.md` describes them for Shino; tests.
- [ ] **T38 [UI] Lecturer app: live session, override with reason, sync status.** Depends on: T31, T36, T03.
  Done when: the session screen updates live over the websocket, override asks for a reason, sync status is shown with a Retry button; Maestro flow opens a session, overrides a student with a reason and closes it.
- [ ] **T39 [UI] Student app: attendance rate + history per course.** Depends on: T32, T03.
  Done when: the Attendance screen shows per-course rate and session list from the real API; Maestro flow checks a seeded rate.

## 3. Module 4 — Face Recognition Verification

- [ ] **T40 [API] Camera device registry + per-device keys + heartbeat (FR-408, NFR-07, NFR-23).** Depends on: T02, T04.
  Done when: admins can register a device (name, room) and get its key once (stored hashed), regenerate a key (old one revoked); device endpoints authenticate with `X-Device-Key` instead of the shared internal key; `POST /device/heartbeat`; online = heartbeat within 60 s; tests.
- [ ] **T41 [API] Server-side recognition from face crops (FR-402–FR-405, NFR-10, NFR-22).** Depends on: T40, T30.
  Done when: `POST /device/faces` (multipart crop(s)) embeds on the server, matches only students enrolled in the open session's course above the threshold, keeps per-device consecutive-match votes (default 3) and records Present through the attendance service; non-enrolled matches are logged, not recorded; tests with InsightFace sample images (match, below threshold, not enrolled, vote counting, duplicate).
- [ ] **T42 [API] Device client for Pi and webcam (FR-401, FR-409, FR-411).** Depends on: T41.
  Done when: `device_client/` (replaces `face_worker/`'s role) polls for an open session for its room, detects faces locally (light model suitable for a Pi), POSTs crops with its key, sends heartbeats, optionally buffers while offline; runs on the laptop with a USB webcam via `python -m device_client --camera 0`; unit tests for the detection → crop → post logic with a fake camera.
- [ ] **T43 [API] Unrecognised faces → lecturer review (FR-407, FR-410, NFR-02).** Depends on: T41.
  Done when: unmatched crops are stored per session; the session's lecturer lists them, assigns one to an enrolled, not-yet-present student (Present, source `face_review`, audited) or dismisses; crops are deleted on resolution, with a retention job after 7 days; admin keeps access as a fallback; tests.
- [ ] **T44 [API] Recognition feedback events (FR-406, NFR-12).** Depends on: T41.
  Done when: on Present, a websocket event goes to the lecturer's session channel and to the student's channel, and `app/services/notify.py` exposes `emit(event, user_ids, payload)` as the M2 hook (logs only for now, documented in `docs/interfaces.md`); tests.
- [ ] **T45 [UI] Lecturer unrecognised-faces screen + student "attendance recorded" banner.** Depends on: T43, T44, T03.
  Done when: Maestro flows: lecturer assigns a seeded unrecognised face; the student app shows the banner after a simulated recognition.
- [ ] **T46 [UI] Admin area: device management page.** Depends on: T40, T22.
  Done when: page lists devices with online status, registers a device and shows the key once, regenerates a key; Playwright test.
- [ ] **T47 [HUMAN] Run the device client on the Raspberry Pi** with the Pi camera at the door; measure NFR-11 (fps) and NFR-10; record results in PROGRESS.md.

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
  Done when: each student question is tagged with a topic (from the cited materials/sections or a cheap LLM label); the lecturer endpoint returns topics with ≥3 distinct students only and no names or text; tests prove that k<3 topics are hidden and that no endpoint exposes another student's chat.
- [ ] **T88 [API] Retrieval interface for Module 6 (FR-814).** Depends on: T80.
  Done when: `app/services/kb/retrieval_api.py` (`search(course_id, query, k)` → passages with source) is documented in `docs/interfaces.md`; tests.
- [ ] **T90 [UI] Student app: summaries + flashcards/practice.** Depends on: T85, T86, T89.
  Done when: screens for generate summary, flip flashcards, answer practice questions; Maestro flow with the fake LLM.
- [ ] **T91 [UI] Lecturer app: materials status + sync button + question trends.** Depends on: T81, T87, T03.
  Done when: Maestro flow triggers a sync and sees the statuses and the trends list.
- [ ] **T92 [API] YouTube suggestions (FR-812, Could Have).** Depends on: T85.
  Done when: YouTube Data API search behind config (`YOUTUBE_API_KEY`; feature off when empty); mocked tests. Needs Yew Sing to add the key to `.env`.

## 5. Wrap-up

- [ ] **T95 [HUMAN] Confirm with Shino that `frontend/admin` can go.** Check that none of her modules (M2, M5, M6, M7) still rely on it or plan to build on it.
- [ ] **T96 [INFRA] Retire `frontend/admin`.** Depends on: T22, T46, T95.
  Done when: PROGRESS.md lists every old admin view and where it went (Users → accounts; FaceData, FaceReviewQueue → verification fallback; AuditLog → audit log; Students, Lecturers, Enrollment, ClassManagement → replaced by Moodle sync; Dashboard → removed); `frontend/admin/` is deleted; `scripts/check.sh`, README and CLAUDE.md no longer refer to it; no backend endpoint is removed unless a test shows nothing uses it; `bash scripts/check.sh` and the admin-area Playwright flows pass.
- [ ] **T98 [INFRA] Docs refresh.** Depends on: all API tasks of M1/M3/M4/M8.
  Done when: README and CLAUDE.md run instructions match reality (device client, Moodle plugin, E2E); `docs/interfaces.md` is complete.
- [ ] **T99 [HUMAN] UAT preparation** (VPS deploy, test accounts, consent forms).

**Deferred (not in this plan, waiting on M6):** FR-820–FR-824.
