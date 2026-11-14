# PLAN-SHINO — Shino's modules (M2, M5, M6, M7)

Spec: `docs/requirements/functional-requirements.md` (Module 2 = FR-2xx, Module 5 = FR-5xx, Module 6 = FR-6xx, Module 7 = FR-7xx). Rules: `CLAUDE.md` → "Task Loop Rules". Counterpart of Yew Sing's `PLAN.md`; log in `PROGRESS-SHINO.md`.

**Legend:** `[ ]` todo · `[x]` done · `[~]` done but needs a manual check (see PROGRESS-SHINO.md) · `[!]` blocked

**Tags:** `[API]` backend · `[UI]` mobile/web, done only when its E2E flow passes · `[INFRA]` tooling · `[HUMAN]` the loop skips it; Shino does it

**Picking rule:** the first `[ ]` task, top to bottom, whose `Depends on` tasks are all `[x]` or `[~]` and which isn't `[HUMAN]`. **A `[HUMAN] Checkpoint` stops the loop:** no task below an unticked checkpoint may start.

**Starting conditions (2026-11-13):**
- Yew Sing's modules are far along; read `docs/interfaces.md` (attendance read interface FR-313, KB retrieval FR-814) and `docs/requests-for-shino.md` (R1, R2 — both open, reply in the Status line).
- `backend/app/routers/analytics.py` is old FYP1 code: it counts only `present` (Late now counts as attended, FR-308) and lets any lecturer read any class's analytics (NFR-04 hole). S02 pins it with characterisation tests before anything rebuilds it.
- M6 reads the course KB through `app/services/kb/retrieval_api.search(course_id, query, k)` (T88, done) — never parse materials yourself.
- LLM rules (CLAUDE.md): normal tests replay recorded responses in `backend/tests/fixtures/llm/`; anything touching the LLM adds cases to the `live` suite and records fixtures. The `llm.py` adapter already has rate limiting, retries and `llm.chat_json`.
- Every schema change needs an Alembic migration chained after the current single head (run `alembic heads` first; never branch a second head).
- Lecturer app runs on phone (Maestro) and browser (Playwright, `npm run e2e:web`); student app is phone-only (Maestro). Quiz screens in the lecturer app and Participation screens in the student app are UI mocks today.
- Deferred, not in this plan: FR-820–FR-824 (M8, Yew Sing) — unlocked only after S34 exists.

---

## 0. Setup

- [x] **S01 [INFRA] Shino's own loop, separate from Yew Sing's.** Depends on: —.
  Done when: Yew Sing's `scripts/run-tasks.sh`, `scripts/test_guard.py` and everything they read (`PLAN.md`, `PROGRESS.md`) are untouched — `git status` shows no change to them; Shino's loop lives in its own copies under `scripts/shino/` (`run-tasks.sh`, `test_guard.py`), edited to read `PLAN-SHINO.md` / `PROGRESS-SHINO.md` and verified with the fake-`claude` throwaway-repo pattern from `backend/tests/test_run_tasks_script.py` (it picks S02 as the first task and stops cleanly after it); the work branch is `shino-new`; `bash scripts/check.sh` passes on it. If the copies turn out unnecessary (tasks run manually, one per fresh session), delete them and say so in PROGRESS-SHINO.md instead. The original files must remain untouched. All Shino loop tests must run in an isolated temporary repository and must clean up after completion.
- [x] **S02 [API] Characterisation tests for the existing analytics endpoints.** Depends on: S01.
  Done when: `db` tests pin the current behaviour of `GET /lecturer/analytics`, `GET /student/me/attendance/summary` and `GET /student/me/attendance` (including their known quirks: only `present` counts, `unidentified` treated as absent, any lecturer passes the occurrence check) — at least 8 tests, all passing against unchanged code. Note in PROGRESS-SHINO.md that the two student endpoints are dead code since T39 (the app uses `GET /student/me/attendance/courses`); their removal happens in S40 with a `TEST-CHANGE:` line.

## 1. Module 2 — Notifications (dashboards come in section 5, after the data exists)

- [ ] **S10 [API] Notification store + in-app feed + the emit hook (FR-205, FR-206).** Depends on: S02, T44 (Yew Sing's `notify.emit`; if T44 is still unticked when S10 starts, create `app/services/notify.py` to the T44 spec yourself and say so in PROGRESS-SHINO.md).
  Done when: migration adds a `notifications` table (user, event name, priority `urgent|important|general` with a CHECK, payload JSON, created_at, read_at, delivered flags); `notify.emit(event, user_ids, payload, priority=...)` becomes the single entry point M1/M3/M4 call sites already use (additive change — callers without a priority default to `general`, so Yew Sing's T44 call sites keep working); feed endpoint `GET /me/notifications` ordered by priority (urgent, important, general) then newest first, with unread count, mark-read (one and all); tests for ordering, priority values, unread, and that a `general` event never triggers a channel send (S11). Reply to R1 in `docs/requests-for-shino.md` describing the final emit shape (it now carries priority).
- [ ] **S11 [API] Delivery channels: push + email, urgent and important only (FR-207, FR-208).** Depends on: S10.
  Done when: a delivery worker (background loop, interval config) sends every urgent and important notification within the configurable window (default 60 s) of the event, and leaves general ones feed-only; Android gets a push via Expo Push API (config-gated, off without credentials); iOS and push-less devices get in-app (already) + email (SMTP config-gated); failures retry with backoff and are visible in the delivery flags; senders are mocked in tests (no real push/email in the suite); config documented.
- [ ] **S12 [API] Wire the producer events from M1/M3/M4 (FR-209, FR-212, R1).** Depends on: S10.
  Done when: the routers that produce the events call `notify.emit`: `attendance.recorded` → the student (FR-406 site, `recognition_service`/`mark_present`), `attendance.flagged` → the lecturer (FR-318/T43 site — if T43 isn't built yet, leave that one call site for T45 and say so), `face_enrolment.result` → the student on approve/reject (T17 `close_pending`), `face_enrolment.pending_review` → the lecturers of the student's courses on a pending submission (T16). Priorities per the FR table (`attendance.recorded` general; `face_enrolment.result` important; `pending_review` important). These are a few lines in Yew Sing's files — coordination noted in PROGRESS-SHINO.md and a reply line in `docs/requests-for-shino.md` (R1). Tests fire each event and assert one notification row per target user with the right priority and payload.

## 2. Module 5 — Classroom Interaction (non-graded)

- [x] **S20 [API] Interaction session lifecycle (FR-501).** Depends on: S02.
  Done when: migration adds `interaction_sessions` (occurrence, status `open|closed`, opened/closed by/at); `POST /lecturer/interactions` (open for a class they teach — reuse `ensure_teaches_occurrence`), `POST .../{id}/close`, `GET /lecturer/interactions?occurrence_id=` (newest first) and `GET /lecturer/interactions/open` (all open sessions across the lecturer's classes — the Home-card query); reopening a closed session creates a new row (history kept for FR-509); students can act only while open and only if enrolled (403/409 otherwise); a websocket room per interaction session (`/ws/interactions/{id}`) broadcasts open/close and later questions/votes/reactions, after commit via `after_commit`; tests for lifecycle, both list shapes, enrolment + access control, and events.
- [x] **S21 [API] Questions with anonymous option (FR-502, FR-503, FR-509 part).** Depends on: S20.
  Done when: `POST /student/interactions/{id}/questions {text, anonymous}`; the student's identity is always stored (for FR-509 counting) but never exposed when anonymous (response objects strip it; a test proves the lecturer view and the feed contain no identity for an anonymous question); the lecturer's question list arrives live over the websocket and `POST .../questions/{id}/answered` marks it answered; tests for both roles.
- [x] **S22 [API] Live polls (FR-504, FR-505, FR-509 part).** Depends on: S20.
  Done when: `POST /lecturer/interactions/{id}/polls {question, options[2+]}` (422 with fewer), `POST /lecturer/interactions/{id}/polls/{poll_id}/close` (close voting, FR-504; 409 when already closed); `POST /student/polls/{id}/vote` — one vote per enrolled student per poll (second vote 409), only while open; live results (per-option counts) to the lecturer over the websocket and on `GET .../polls`; tests.
- [x] **S23 [API] Live question, reactions, "I Don't Understand" (FR-506, FR-507, FR-508, FR-509 part).** Depends on: S20.
  Done when: the lecturer can post a live question to the class and see responses arrive in real time; students send one of a predefined reaction set and the lecturer sees live counts; an IDU button records at most one signal per student per session and the lecturer sees the number of distinct students (not the number of clicks), live; all writes carry session, student and timestamp (FR-509); tests.
- [x] **S24 [API] Participation read interface for Module 7 (FR-509).** Depends on: S21, S22, S23.
  Done when: `app/services/participation_read.py` exposes documented functions (per student per course/session: questions submitted, votes cast, responses, reactions, IDU signals; class-level counts per session), no permission checks inside (callers check NFR-04), described in `docs/interfaces.md`; tests. This is the FR-509→FR-701 handover.
- [x] **S25 [UI] Student app: interaction entered from Home (FR-501–FR-508, UC-502/505–508).** Depends on: S21, S22, S23, T03.
  Done when: the Home screen shows a live interaction card for any open session of the student's enrolled courses (hidden when none), tapping it opens the rebuilt Participation screen with the session pre-selected; the Participation screen carries the full interaction UI on the real endpoints — question box with anonymous toggle, live poll voting, reaction buttons with my-reaction state, IDU button locking after one signal; live-question responses post to the response endpoint (not the question endpoint); live updates over the websocket without a manual refresh; screen is inert outside an open session; Maestro flow: seeded open session → Home card → ask a question → vote in a poll → react → press IDU.
- [x] **S26 [UI] Lecturer app: open/close from Home + live control screen (FR-501–FR-508, UC-501/503/504/506–508).** Depends on: S21, S22, S23, T03.
  Done when: opening and closing an interaction session happen from the lecturer Home header card (per UC-501 — the class card already opens/closes the attendance session there): the card shows "Live" via `GET /lecturer/interactions/open` and toggles into the rebuilt InteractionControl screen, which is the live view only — questions arrive live with Mark answered, create/open/close a poll with live per-option results (a close-poll button that does NOT close the session), post a live question and see responses, reaction counts, the IDU counter, plus a Close-session action; the Interaction tab survives as a fallback list of open sessions; Maestro + Playwright flows cover Home → open → question → answered → poll → results → close poll → close session.
- [ ] **S27 [HUMAN] Checkpoint: interaction in a real (or seeded) class.** Shino runs one session end to end on a phone (or the browser app) with a second device as student; fixes found become S27b-style follow-up tasks.

## 3. Module 6 — AI-Powered Quiz and Assessment

- [x] **S30 [API] Quiz model + LLM question generation (FR-601, FR-602, FR-603).** Depends on: S02.
  Done when: migration adds quizzes/quiz_questions (type `mcq|short_answer`, options + correct answer or suggested answer, level, source material + topic, status `draft|approved|deleted`); `POST /lecturer/courses/{id}/quizzes/generate {material_ids, type, level, count}` drafts questions by calling `retrieval_api.search` per selected material (FR-814 — never parse materials) and the LLM (adapter's `chat_json`, malformed output retried once then 502, like T86); every question carries its source material and topic (from the Passage source, like T87); only the course's lecturer (NFR-04); replay/mock tests + ≥3 live cases recorded in the T82 suite (generation per type + a material with no retrievable text); fixture recorded.
- [x] **S31 [API] Review, edit, approve, publish (FR-604, FR-605).** Depends on: S30.
  Done when: the lecturer can list/edit/approve/delete each draft question; only approved questions can go into a quiz (server-enforced, tested); `POST /lecturer/quizzes {question_ids, time_limit_minutes, opens_at, closes_at}` publishes with a status `published|closed`; publish emits the M2 `quiz.published`/deadline notifications (FR-211 — important priority, calls `notify.emit`, tested without real channels); tests for the status machine and access control.
- [x] **S32 [API] Taking quizzes + auto-grade (FR-606, FR-607, FR-608).** Depends on: S31.
  Done when: students see published quizzes of enrolled courses only (FR-607's one attempt: second attempt 409, outside the open window 403); an attempt has a server-side deadline (started_at + time limit) — submission after expiry is rejected and the attempt auto-submits at expiry (background check); MCQ answers auto-graded on submission; short answers left unscored; tests for window, one-attempt, expiry auto-submit, and MCQ grading.
- [x] **S33 [API] Short-answer scoring + AI suggestion (FR-609, FR-610, FR-611).** Depends on: S32.
  Done when: the lecturer lists unscored short answers per quiz and scores them; FR-610 (Could): `POST .../suggest-score` returns an AI-suggested score via the LLM (record/replay + 1 live case, fixtures); a quiz becomes "grading complete" when no short answer is unscored, and only then can the student see their score and per-question results (FR-611 — tested: not visible before completion); student result endpoint with per-question correctness; tests.
- [x] **S34 [API] Results, hard questions, and the M7/M8 interface (FR-612, FR-613, FR-614).** Depends on: S33.
  Done when: the lecturer sees each student's score and the class average per quiz; questions answered incorrectly by more than the configurable percentage (default 50) are listed; `app/services/quiz_read.py` exposes the internal interface (per student per question: correct/score, question topic + source material, and whether the student has an active graded attempt in the course — the data FR-820–FR-824 need), described in `docs/interfaces.md`, no permission checks inside; tests. When this is done, tell Yew Sing — it unlocks his deferred FR-820–FR-824.
- [ ] **S35 [UI] Lecturer app: real quiz screens.** Depends on: S31, S32, S33, S34, .
  Done when: the mock screens QuizList, CreateQuiz, LiveResults, ResultsClosed, Breakdown are rebuilt on the real API (generate → review/approve → publish → live progress → score short answers → results + hard questions); Maestro + Playwright flows with the LLM faked (`LLM_FAKE=1`) cover generate → publish → a seeded student attempt → grade → results.
- [ ] **S36 [UI] Student app: quiz tab.** Depends on: S32, S33, .
  Done when: a Quiz section (in an existing tab or a new one, per navigation conventions): quiz list with open/closed state, take-quiz screen with countdown and auto-submit, result screen with per-question results after grading; Maestro flow with a seeded published quiz: answer, submit, see the MCQ result.
- [ ] **S37 [HUMAN] Checkpoint: quiz cycle on real devices.** Shino generates from real material, publishes, takes it as a student, grades, and reads the results. Fix list becomes follow-up tasks.

## 4. Module 7 — Learning Analytics and Early Warning

- [x] **S40 [API] Rebuild analytics.py on the attendance read interface (R2, NFR-04).** Depends on: S02.
  Done when: `GET /lecturer/analytics` counts through `app/services/attendance_read.py` (`course_rates`/`course_records` — Late counts as attended, Excused left out, FR-308), the ownership hole is closed (`ensure_teaches_occurrence` after the 404 check, per the fix note under Module 7 in the FR doc); the dead student endpoints `/student/me/attendance[/summary]` are removed (the app uses T32's `/student/me/attendance/courses` since T39) with a `TEST-CHANGE:` line for the S02 characterisation tests; R2's Status line gets Shino's reply; tests prove parity with the student app's rate and a 403 for a lecturer who doesn't teach the class.
- [x] **S41 [API] Per-student engagement indicators (FR-701, FR-702, FR-703).** Depends on: S24, S34, S40.
  Done when: a service computes per student per course: attendance rate + absence frequency (from `attendance_read`), participation frequency, questions submitted, IDU signals (from `participation_read`), quiz scores + trend across quizzes (from `quiz_read`); lecturer endpoint returns it for the students of a class they teach (NFR-04 enforced); tests cover each indicator with seeded data and the access rule.
- [x] **S42 [API] Class-level trends + assessment by topic/session (FR-704, FR-705).** Depends on: S41.
  Done when: the lecturer sees the class engagement trend across sessions (per-session participation + attendance series) and the class assessment performance by topic and by session (from `quiz_read`'s topic/source tags); tests.
- [x] **S43 [API] Student self view (FR-706).** Depends on: S41.
  Done when: `GET /student/me/analytics` returns the student's own attendance status, engagement summary and performance indicators, and nothing about other students (a test proves a student cannot read another student's indicators, and the lecturer endpoints reject students).
- [ ] **S44 [API] Early warning (FR-707, FR-708, FR-709).** Depends on: S41, S10.
  Done when: the four conditions (configurable: minimum attendance %, consecutive absences, quiz decline over N quizzes, participation drop % vs previous period) are evaluated by a service after each attendance session closes (hook the close path) and after each quiz finishes grading (hook the grading-complete path); a flag generates an alert (student, course, condition met) and calls `notify.emit(..., priority="important")` to the lecturer (FR-210); re-flagging the same unresolved condition doesn't spam duplicates (a test); thresholds in config with defaults; tests per condition + the hooks.
- [ ] **S45 [API] At-risk list (FR-710).** Depends on: S44.
  Done when: `GET /lecturer/classes/{id}/at-risk` lists the flagged students of a class with the triggering condition (only the class's lecturer, NFR-04); alerts appear in the notification feed (FR-210/FR-206); tests.
- [ ] **S46 [UI] Analytics screens on the real API.** Depends on: S41, S42, S43, S45, .
  Done when: the lecturer Analytics screen is rebuilt on the real endpoints (per-student indicators, class trend, assessment by topic/session, at-risk list); the student app gets a self-view screen (own indicators only); Maestro (both apps) + Playwright flows with seeded indicator data.
- [ ] **S47 [HUMAN] Checkpoint: analytics review.** Shino reviews the numbers against the source screens (attendance rates must match the student app's `66.7%`-style numbers) and the alert flow end to end.

## 5. Module 2 (rest) — Dashboards, built last because they aggregate everything

- [ ] **S60 [API] Dashboard aggregate endpoints (FR-201, FR-202, FR-203).** Depends on: S12, S25, S34, S45 (or their equivalents marked `[x]`).
  Done when: `GET /me/dashboard` (role-shaped): student — attendance status, upcoming quiz deadlines (published, not yet closed), deadlines(assignment/quiz in moodle)notifications (top urgent/important first, FR-204), ongoing interaction sessions; lecturer — per-class attendance overview, participation summary, assessment activities, notifications; the response only ever contains the user's own courses (FR-203, tested per role); decided with Yew Sing: the source of "latest announcements" (no FR defines a producer — simplest is Moodle's announcements forum via the existing sync, noted as a decision in PROGRESS-SHINO.md); tests.
- [ ] **S61 [UI] Student dashboard rebuild (FR-201, FR-204).** Depends on: S60, .
  Done when: the student Home screen is rebuilt on the dashboard endpoint: urgent/important notifications at the top, above general ones (test in the flow), attendance status, deadlines(quiz in app or assignment/quiz in moodle), ongoing activities with tap-through to the existing screens; Maestro flow with seeded data of all three priorities.
- [ ] **S62 [UI] Lecturer dashboard rebuild (FR-202, FR-204).** Depends on: S60, .
  Done when: the lecturer Dashboard screen is rebuilt on the dashboard endpoint (phone + browser layout per T05 conventions); Maestro + Playwright flows with seeded data.
- [ ] **S63 [HUMAN] Checkpoint: all four modules on real devices.** Shino walks M2 → M5 → M6 → M7 end to end on a phone and the browser; Yew Sing joins to check the cross-module seams (notifications his events trigger, the FR-313/614 interfaces, the at-risk alerts he sees as a lecturer).

## 6. Wrap-up

- [ ] **S70 [HUMAN] Merge preparation.** Depends on: S63.
  When Shino says "prepare the merge": Yew Sing runs `.claude/commands/prepare-merge.md` against the `shino-new` branch — checks, conflict resolution against `main`, a note for Shino with anything from `docs/requests-for-shino.md` still open.
- [ ] **S71 [INFRA] Docs refresh for Shino's modules.** Depends on: all S-API tasks.
  Done when: README/CLAUDE.md run instructions cover anything new (push credentials config, email SMTP, quiz E2E seeds); `docs/interfaces.md` holds all three internal interfaces (attendance read, KB retrieval, participation read + quiz read).

**Deferred (not in this plan, waiting on S34):** FR-820–FR-824 — Module 8, owned by Yew Sing.
