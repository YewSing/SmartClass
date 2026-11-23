# PLAN — Shino's modules (M2, M5, M6, M7)

Fresh start (2026-11-21): earlier M2/M5/M6/M7 code is not trusted and is not built on. Every module is rebuilt here, test first. Yew Sing's plan for M1/M3/M4/M8 is [PLAN.md](PLAN.md); never edit it.

Spec: `docs/requirements/functional-requirements.md` (FR-2xx, FR-5xx, FR-6xx, FR-7xx), `docs/requirements/non-functional-requirements.md`. Interfaces from Yew Sing's modules: `docs/interfaces.md`. Rules: `CLAUDE.md` → "Task Loop Rules" (read `PLAN.md` as this file and `PROGRESS.md` as [progress-shino.md](progress-shino.md)).

Run the loop with `/shino-run-plan [rounds]` (or `bash scripts/shino/run-tasks.sh <rounds>`). One task per fresh session (`/shino-next-task`), reviewed by the `shino-reviewer` agent.

**Legend:** `[ ]` todo · `[x]` done · `[~]` done but needs a manual check (see progress-shino.md) · `[!]` blocked

**Tags:** `[API]` backend · `[UI]` mobile/web, done only when its E2E flow passes (Playwright for lecturer web, Maestro for mobile) · `[INFRA]` tooling · `[HUMAN]` the loop skips it; Shino does it · `[OPUS]` in the hybrid loop, Claude Opus builds it fully (hard design, timers, websockets, LLM prompts)

**Picking rule:** the first `[ ]` task, top to bottom, whose `Depends on` tasks are all `[x]` or `[~]` and which isn't `[HUMAN]`. **A `[HUMAN] Checkpoint` stops the loop:** no task below an unticked checkpoint may start. Other `[HUMAN]` tasks are simply skipped.

## Guardrails

- **Ownership.** Never change M1/M3/M4/M8 code (auth, Moodle sync, attendance, sessions, face, KB/assistant) except an additive hook the task names. Consume only their documented interfaces: `app/services/notify.py::emit` (FR-205 hook, R1), `app/services/attendance_read.py` (FR-313, R2), `app/services/kb/retrieval_api.py::search` (FR-814), `app.core.deps.ensure_teaches_occurrence`. If an interface is missing something, write a request in progress-shino.md `## Next` ("Requests for Yew Sing") and stub your side.
- **One class session.** M3's `AttendanceSession` is the only class session. M5 interaction is keyed to `attendance_session_id`, is open only while that session is `open`, and never opens, extends or closes it.
- **Privacy.** Anonymous questions and confusion presses never show identity (FR-504, FR-515, FR-713). Graded quiz results are private and never ranked (FR-605, FR-613). Unreleased marks/answers stay hidden (FR-618). Students never receive correct answers before they are revealed. Every lecturer endpoint checks the lecturer teaches the class (NFR-04); students reach only enrolled courses and their own data.
- **Tests.** Normal tests never call Moodle, the LLM, Expo Push or SMTP: mocks (respx, fakes) or recorded fixtures. New LLM prompts get `@pytest.mark.live` cases in `backend/tests/live/` on the synthetic test course plus fixtures in `backend/tests/fixtures/llm/`. Never weaken or skip a test (`scripts/test_guard.py` accepts a `TEST-CHANGE:` line in progress-shino.md).
- **Real time.** Websocket events go out only after the DB commit (`app.core.database.after_commit`).
- **Migrations.** Every model change has a new Alembic migration on the current head; one head only. Shino's tables are prefixed `m2_`, `m5_`, `m6_`, `m7_`.
- **UI.** Use the apps' existing components (`src/components/ui/`), theme and navigation. Clean, light, consistent: white cards with subtle borders, one primary blue, soft status badges, regular/medium text weights. Lecturer screens work at 1280 px in the browser and at phone width.

---

## 0. Foundation

- [x] **S01 [INFRA] Shino task loop.** Depends on: —.
  Done when: `scripts/shino/run-tasks.sh`, `/shino-run-plan`, `/shino-next-task`, `/shino-plan-task`, the `shino-reviewer` agent, `scripts/shino/opencode/*.md`, this file and progress-shino.md exist; `backend/tests/test_shino_loop_script.py` passes; test_guard accepts `TEST-CHANGE:` in progress-shino.md.
- [x] **S02 [OPUS] [INFRA] Clean slate for M2/M5/M6/M7.** Depends on: S01.
  Done when: no pre-plan M2/M5/M6/M7 implementation remains: the legacy `routers/analytics.py` and any notification/dashboard/interaction/quiz routers, services, models, schemas and their tests are removed (each removed test has a `TEST-CHANGE:` line), except what an M1/M3/M4/M8 app screen or test still calls (list each kept endpoint in progress-shino.md with its caller); `notify.emit` is the logging-only T44 hook again; the mock screens and mock data for Shino's areas (lecturer `QuizList`, `CreateQuiz`, `LiveResults`, `ResultsClosed`, `Breakdown`, `Analytics`, and any interaction/notification screens; student `Participation`, `PartSessionPerf`, quiz/live-class/notification screens) are replaced by one shared "Coming soon" placeholder per app, with navigation still working; if a removed migration was applied to the dev DB, progress-shino.md gives the exact `alembic downgrade` command for Shino (the loop does not downgrade the dev DB); one Alembic head; `bash scripts/check.sh` passes; Yew Sing's E2E flows (`login`, `live-session`, `assistant`) are unchanged.
- [x] **S03 [INFRA] Test helpers for Shino's modules.** Depends on: S02.
  Done when: `backend/tests/shino_helpers.py` (or conftest fixtures) builds a course with one lecturer, ≥4 enrolled students, a non-enrolled student, a second lecturer who doesn't teach it, and an open `AttendanceSession` (using M3's service, not raw SQL that bypasses it); a fake Expo Push server (respx) and a fake SMTP sink; an LLM fixture helper for Shino's prompts (`tests/fixtures/llm/m6/`, replay by default, record with a flag); `scripts/check.sh` also triggers the live suite when `backend/app/services/quiz/` changes (same once-per-state rule as `app/services/kb`). A sample test per helper passes.
- [x] **S04 [HUMAN] Checkpoint: review S01–S03.** Shino (or a Claude review session) reads the S02 removal list and the helpers, then ticks `[x]`.

## 1. Module 2 — Dashboard and Notifications

- [x] **S10 [API] Notification store and event interface (FR-205, FR-206, FR-207, FR-216).** Depends on: S04.
  Done when: `m2_notifications` (recipient user, event, priority, title, message, link, subject key, read_at, created_at) with migration; `app/services/notifications/` has an event registry mapping every FR-206 event to its priority, default title/message and app-relative link; `notify.emit(event, user_ids, payload)` persists through it (an additive change to `notify.py` as agreed in R1; existing callers unchanged); unknown events are logged, not raised; duplicates by (event, recipient, subject, window) are dropped; unsafe/external links are rejected. Tests: each FR-206 event maps to a priority, dedup within/after the window, `attendance.recorded` from M3 lands without editing M3, payload never stored raw.
- [x] **S11 [API] Feed and read state (FR-208, FR-209).** Depends on: S10.
  Done when: `GET /notifications` (newest first, cursor pagination, unread count), `GET /notifications/priority` (unread urgent+important for the dashboard), `POST /notifications/{id}/read`, `POST /notifications/read-all`; a user never sees or marks another user's notification (404). Tests for ordering, pagination, counts, isolation.
- [x] **S12 [OPUS] [API] Live notifications over websocket (FR-213).** Depends on: S11.
  Done when: `WS /notifications/ws?token=` authenticates with the access token, rejects bad/expired tokens (1008), and sends `{type:"notification", ...}` plus the new unread count to every open connection of the recipient after commit. Tests: delivery to the right user only, not before commit, reconnect gets nothing stale.
- [x] **S13 [API] Push tokens and Expo push (FR-210, FR-212).** Depends on: S10.
  Done when: `POST /me/push-tokens` / `DELETE /me/push-tokens/{token}` (validated Expo token format, one row per device); urgent and important notifications are sent through the Expo Push API in a background task (batching, `DeviceNotRegistered` deletes the token, network failure doesn't fail the request); general ones are not pushed. Tests with respx only.
- [x] **S14 [API] Email for urgent/important (FR-211).** Depends on: S10.
  Done when: SMTP settings in config (off when unset); urgent/important notifications are emailed to the user's email in the background, general never; failures are logged and retried at most N times; no secrets in logs. Tests with the fake SMTP sink.
- [x] **S15 [API] Preferences and retention (FR-214, FR-218).** Depends on: S13, S14.
  Done when: `GET/PUT /me/notification-preferences` turns push/email off for general only (urgent/important can't be turned off: 422); a daily job deletes notifications older than `NOTIFICATION_RETENTION_DAYS` (default 90). Tests for both, clock monkeypatched.
- [~] **S16 [OPUS] [API] Moodle announcements and deadlines on login (FR-203).** Depends on: S10.
  Done when: on successful Moodle login the user's course news-forum posts and upcoming assignment/calendar events are fetched with the user's own transient token and saved as a per-user read-only snapshot (`m2_moodle_snapshot`, with refreshed_at); the token is never stored or logged; a Moodle failure keeps the previous snapshot and never fails login. The only M1 change is one additive call in the login route, noted in progress-shino.md and `docs/requests-for-shino.md`. Tests with respx; one `moodle` test against the local Moodle.
- [~] **S17 [API] Lecturer announcements (FR-217).** Depends on: S10, S16.
  Done when: `POST /lecturer/classes/{occurrence_id}/announcements {title, message, post_to_moodle}` (teaching lecturer only) notifies the class's students as *important*; with `post_to_moodle` it is posted to the course news forum, failures retried with backoff, status visible in `GET .../announcements`. Tests with respx; a `moodle` test for the forum post.
- [x] **S18 [API] Dashboard reads (FR-201, FR-202).** Depends on: S11, S16.
  Done when: `GET /student/me/dashboard` returns today's classes with the student's attendance status, attendance rate per course (via `attendance_read`), Moodle deadlines and announcements with refreshed_at, and unread urgent/important notifications; `GET /lecturer/dashboard` returns today's classes, the current/latest session's attendance counts (via `attendance_read`), and unread urgent/important notifications. Fields from M5/M6/M7 are present and `null` until S80 fills them. Tests for both roles and isolation.
- [x] **S19 [UI] Notification centre and push registration (both apps).** Depends on: S12, S13, S15.
  Done when: both apps show a bell with the unread count on the home screen, a feed screen (pull to refresh, mark one/all read, tap opens the deep link), live updates through the websocket, a preferences screen; the phone apps register the Expo push token after login and remove it on logout. Maestro `notifications.yaml` (student) and Playwright `notifications.spec.js` (lecturer) pass.
- [~] **S20 [UI] Student and lecturer dashboards.** Depends on: S18, S19.
  Done when: the student Home and lecturer Dashboard show the S18 data with loading, empty and error states, Moodle items open the Moodle link, priority notifications sit at the top until read (FR-208). Maestro `dashboard.yaml` and Playwright `dashboard.spec.js` pass at phone width and 1280 px.
- [x] **S21 [HUMAN] Checkpoint: notifications on a real phone.** Shino logs in on Android, checks a push arrives and the dashboard is right, then ticks `[x]`.

## 2. Module 5 — Classroom Interaction

- [x] **S30 [OPUS] [API] Interaction session tied to the class session (FR-501, FR-502).** Depends on: S21.
  Done when: `m5_interaction_sessions` keyed to `attendance_session_id`; the interaction is open/close  only follow the attendance session; it is treated as closed the moment the attendance session is not `open` (checked on every write, under a row lock), and a background sweep closes it within 30 s for clients; only enrolled students and the teaching lecturer can join (403 otherwise). No M3 code changes. Tests: lifecycle, closing class closes interaction, access matrix.
- [x] **S31 [API] Live questions (FR-503–FR-506).** Depends on: S30.
  Done when: students ask (optionally anonymous), upvote once, list by votes then time; the lecturer marks answered, pins, hides (hide audited, NFR-06); anonymous identity appears in no response, event or audit value. Tests including the anonymity check on every response shape.
- [x] **S32 [API] Polls (FR-507–FR-509).** Depends on: S30.
  Done when: lecturer creates (2–6 options, single/multiple), starts, closes; students vote once and may change until close; live results to the lecturer; lecturer chooses whether students see results; `poll.started` notification. Tests.
- [x] **S33 [API] Quick answers, reactions and confusion (FR-510–FR-512, FR-514, FR-515).** Depends on: S30.
  Done when: quick questions with length-limited text answers (lecturer sees the list, anonymous to the class); reactions with a per-student cooldown; "I don't understand" with optional topic tag, configurable cooldown (default 2 min), lecturer sees count and timeline only; `confusion.spike` to the lecturer when presses in the window reach the configured share (defaults 2 min / 25%), once per spike. Tests with the clock monkeypatched.
- [x] **S34 [API] Event log and M7 read interface (FR-513, FR-517, FR-713).** Depends on: S31, S32, S33.
  Done when: every interaction event is stored (type, student, session, time); `app/services/interaction_read.py` gives per-student counts (polls answered, questions excluding anonymous ones, reactions, confusion) and class totals (including anonymous questions without identity), documented in `docs/interfaces.md`; nothing is graded. Tests.
- [x] **S35 [OPUS] [API] Interaction websocket (FR-516).** Depends on: S34.
  Done when: `WS /interaction/{attendance_session_id}/ws?token=` with role-separated payloads (students never get identities or hidden items), after-commit invalidation events for questions, polls, quick answers, reactions, confusion, and a `closed` event when the class ends. Tests.
- [x] **S36 [API] After class: summary, CSV, my questions (FR-518–FR-520).** Depends on: S34.
  Done when: lecturer summary (questions asked/answered, poll results, reactions, confusion timeline), CSV export without anonymous identities (cells starting with `= + - @` escaped), students list their own past questions with answered status. Tests.
- [x] **S37 [UI] Lecturer live interaction.** Depends on: S35, S36, S20.
  Done when: from the dashboard's current class the lecturer opens interaction, moderates questions, runs polls and quick questions, sees reactions and the confusion timeline live, and opens the after-class summary/CSV. Playwright `interaction.spec.js` passes at 1280 px and phone width.
- [~] **S38 [UI] Student live class.** Depends on: S35, S36, S20.
  Done when: during an open class a student joins from Home, asks (anonymous option), upvotes, votes, answers quick questions, reacts, presses "I don't understand", sees updates live and a closed state when class ends, and sees their past questions. Maestro `interaction.yaml` passes.
- [ ] **S39 [HUMAN] Checkpoint: interaction in a real class.** Shino runs one class with a few phones, then ticks `[x]`.

## 3. Module 6 — AI Quiz and Assessment

- [ ] **S40 [API] Quiz model and lecturer CRUD (FR-605, FR-606 settings).** Depends on: S39.
  Done when: `m6_quizzes`, `m6_questions` (type mcq/short, text, options, answer, suggested answer, topic, source file + page, origin `from_material`/`extended`, explanation, order, approved), `m6_attempts`, `m6_answers` with migration and pydantic schemas; the teaching lecturer creates/reads/updates/deletes draft quizzes and their settings (title, type, timer mode, timer seconds, open/close, shuffle, release, speed bonus); a game quiz forces per-question timers. Tests: validation and access matrix.
- [ ] **S41 [OPUS] [API] AI draft from a prompt (FR-601–FR-603).** Depends on: S40.
  Done when: `POST /lecturer/quizzes/draft {course_id, prompt, material_ids?}` reads settings from the prompt, retrieves passages only through `retrieval_api.search`, and asks the LLM (existing `app/services/kb/llm.py` adapter) for JSON questions that are validated (counts, option indexes, required fields) before saving as an unapproved draft; each question is tagged topic + source + origin with an explanation citing the source; "only the material" mode produces no `extended` questions; LLM failures give a clear 502/503 and save nothing. Code in `app/services/quiz/`. Replay-fixture tests and `live` tests on the synthetic course (structure and grounding). `scripts/check.sh`'s live trigger runs only Shino's M6 live tests (`tests/live/test_live_quiz*.py`) when only `app/services/quiz/` changed, and the whole live suite only when `app/services/kb/` changed, so Yew Sing's flaky M8 live test can't fail an M6 round.
- [ ] **S42 [API] Draft review and refinement (FR-604).** Depends on: S41.
  Done when: edit, delete, reorder, add, approve/unapprove questions; regenerate one question and refine the draft with a further prompt (LLM, validated, fixtures + live cases); questions can't change once the quiz has attempts (409). Tests.
- [ ] **S43 [API] Publish and student quiz cards (FR-606, FR-607).** Depends on: S42.
  Done when: publish needs ≥1 approved question and only approved ones are published; unpublish/close; `quiz.published` to enrolled students; `GET /student/me/quizzes` lists cards for enrolled courses with state (upcoming, open, attempted, closed) and never includes answers. Tests.
- [ ] **S44 [OPUS] [API] Graded attempts and server timers (FR-607, FR-608).** Depends on: S43.
  Done when: one graded attempt per student; answers autosave; whole-quiz or per-question timers are enforced on the server (late answers rejected, expired attempts auto-submitted on next touch and by a background sweep); resuming after a disconnect never extends time; shuffle is stable per attempt. Tests with the clock monkeypatched, including concurrent submits.
- [ ] **S45 [API] Grading (FR-616, FR-617).** Depends on: S44.
  Done when: MCQ graded on submit; short answers graded by the LLM against the suggested answer with score, reason and confidence (validated JSON, fixtures + live cases); low-confidence scores are flagged; the lecturer can change a short-answer score with feedback, audited with old/new score; `quiz.graded` sent when results are released. Tests.
- [ ] **S46 [API] Results release and lecturer results (FR-618, FR-619).** Depends on: S45.
  Done when: the lecturer releases marks, answers, both or neither; students see only released parts; lecturer results show submissions, score distribution, average, per-question correct rate and most-missed questions. Tests including hidden parts never leaking.
- [ ] **S47 [API] Read interfaces for M7 and M8 (FR-609, FR-620, FR-621).** Depends on: S46.
  Done when: `app/services/quiz_read.py` provides `has_active_graded_attempt(student_id, course_id)`, per-student answers with topic/source/quiz type, graded scores with dates and game participation by topic; documented in `docs/interfaces.md`; a line added to `docs/requests-for-shino.md` telling Yew Sing FR-820–FR-824 can now use it. Tests.
- [ ] **S48 [OPUS] [API] Live game engine (FR-610–FR-612).** Depends on: S43.
  Done when: the lecturer starts a game quiz (`game.started`), releases one question at a time with a server countdown, can pause, skip, end; students answer once per question; late joiners enter at the current question; after each question the correct answer, class answer split and explanation are revealed; scoring is base points plus an optional speed bonus; a game websocket pushes state after commit and never sends the correct answer early. Tests with the clock monkeypatched.
- [ ] **S49 [API] Leaderboards (FR-613, FR-614).** Depends on: S48.
  Done when: per-question and final game leaderboard (top five + own rank), nickname or opt-out per student, a course leaderboard summing game points; graded quizzes have no leaderboard endpoint (404). Tests.
- [ ] **S50 [UI] Lecturer quiz authoring and review.** Depends on: S42, S43, S20.
  Done when: the lecturer writes a prompt, sees the filled settings and draft questions with topic/source/origin labels, edits/reorders/regenerates/refines/approves, and publishes. Playwright `quiz-authoring.spec.js` passes with `LLM_FAKE=1`.
- [ ] **S51 [UI] Student graded quiz and results.** Depends on: S44, S46, S20.
  Done when: quiz cards on the student app, a timed attempt with autosave and resume, auto-submit at time up, and the released result view. Maestro `quiz-graded.yaml` passes.
- [ ] **S52 [UI] Live game (lecturer host and student play, FR-615).** Depends on: S48, S49, S50.
  Done when: the lecturer hosts from the browser (question, live answer counts, pause/skip/end, reveal, leaderboard); students play on the phone with countdown, correct/wrong feedback, streak indicator and a final podium. Playwright `quiz-game.spec.js` and Maestro `quiz-game.yaml` pass.
- [ ] **S53 [UI] Lecturer results and short-answer review.** Depends on: S46, S50.
  Done when: results screen (distribution, averages, per-question correct rate, most-missed) and flagged short answers the lecturer can re-score with feedback; release controls. Playwright `quiz-results.spec.js` passes.
- [ ] **S54 [HUMAN] Checkpoint: quizzes in class.** Shino runs a game quiz and a graded quiz with a few phones, then ticks `[x]`.

## 4. Module 7 — Learning Analytics and Early Warning

- [ ] **S60 [API] Indicators (FR-701, FR-702, FR-706, FR-713).** Depends on: S54.
  Done when: `app/services/analytics/indicators.py` computes per student per course every FR-702 figure, reading only `attendance_read`, `interaction_read` and `quiz_read` (Late counts as attended, Excused is not an absence); "not enough data" below configurable minimums; anonymous questions only in class totals. Tests per indicator with built fixtures.
- [ ] **S61 [API] Lecturer class and student views (FR-703, FR-704, FR-707, FR-714, FR-716).** Depends on: S60.
  Done when: class dashboard (attendance trend by session, participation trend, quiz performance by quiz and topic, at-risk count, most-missed topics, lowest-engagement sessions), student-level view, CSV export; lecturers who don't teach the class get 403 via `ensure_teaches_occurrence`, admins see all. Tests including cross-lecturer denial.
- [ ] **S62 [API] Student's own insights (FR-705).** Depends on: S60.
  Done when: `GET /student/me/insights?course_id=` returns only the caller's attendance, engagement, quiz performance and topic mastery (graded and game separately); any attempt to read another student's data is impossible by construction. Tests.
- [ ] **S63 [API] At-risk rules and thresholds (FR-708, FR-709, FR-715).** Depends on: S60.
  Done when: rules (a)–(d) with defaults in config and per-course overrides in `m7_rule_settings` (teaching lecturer only, each change audited); each rule can be turned off; rules skip "not enough data". Tests for every rule at, below and above the threshold.
- [ ] **S64 [OPUS] [API] Evaluation and alerts (FR-710, FR-711).** Depends on: S63, S47.
  Done when: rules are evaluated after an attendance session is finalised (by observing M3 state or an additive hook named in the task notes, no M3 behaviour change), after a quiz is graded, and daily; `m7_alerts` stores rule + evidence; `at_risk.alert` goes to the lecturer the first time a rule fires and not again until it clears and recurs. Tests with the clock monkeypatched.
- [ ] **S65 [API] Alert list and follow-up (FR-712, FR-715).** Depends on: S64.
  Done when: per-course at-risk list with rules and evidence; acknowledge / followed up / dismissed with optional note, audited. Tests.
- [ ] **S66 [UI] Lecturer analytics.** Depends on: S61, S65, S20.
  Done when: class dashboard charts, student drill-down, at-risk list with actions, threshold settings, CSV export. Playwright `analytics.spec.js` passes at 1280 px and phone width.
- [ ] **S67 [UI] Student insights.** Depends on: S62, S20.
  Done when: the student sees their own attendance, engagement, quiz performance and topic mastery per course, with "not enough data" states. Maestro `insights.yaml` passes.
- [ ] **S68 [HUMAN] Checkpoint: analytics with real data.** Shino checks the numbers against a class she ran, then ticks `[x]`.

## 5. Integration and wrap-up

- [ ] **S80 [API] [UI] Dashboards complete (FR-201, FR-202).** Depends on: S36, S49, S65.
  Done when: the S18 `null` fields are filled: student sees running classroom activity (live poll/question, open quiz); lecturer sees the participation summary, running and recent quizzes and at-risk alerts; both dashboards show them. Backend tests plus the S20 E2E flows extended.
- [ ] **S81 [OPUS] [API] Deadline and quiz reminders (FR-215).** Depends on: S16, S43.
  Done when: reminders before a Moodle deadline and before an open quiz closes (configurable, default 24 h and 1 h) via `quiz.deadline_reminder` / Moodle deadline events, each sent once per user per window (FR-216). Tests with the clock monkeypatched.
- [ ] **S90 [INFRA] Docs refresh.** Depends on: S80, S81.
  Done when: `docs/interfaces.md` covers every Shino interface, `README.md` has M2/M5/M6/M7 setup (SMTP, push), `docs/requests-for-shino.md` replies are current, and progress-shino.md lists known limitations.
- [ ] **S91 [HUMAN] Final checkpoint and merge.** Shino runs everything end to end, then says "prepare the merge" (`/prepare-merge`).
