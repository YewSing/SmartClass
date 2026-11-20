# PLAN-SHINO — Shino's modules (M2, M5, M6, M7)

Spec: `docs/requirements/functional-requirements.md` (Module 2 = FR-2xx, Module 5 = FR-5xx, Module 6 = FR-6xx, Module 7 = FR-7xx) and `docs/use-cases/UC-M2/M5/M6/M7-*.md`. Rules: `CLAUDE.md` → "Task Loop Rules". Counterpart of Yew Sing's `PLAN.md`; log in `PROGRESS-SHINO.md`.

**Legend:** `[ ]` todo · `[x]` done · `[~]` done but needs a manual check (see PROGRESS-SHINO.md) · `[!]` blocked

**Tags:** `[API]` backend · `[UI]` mobile/web, done only when its E2E flow passes · `[INFRA]` tooling/docs · `[HUMAN]` the loop skips it; Shino does it

**Picking rule:** the first `[ ]` task, top to bottom, whose `Depends on` tasks are all `[x]` or `[~]` and which isn't `[HUMAN]`. **A `[HUMAN] Checkpoint` stops the loop:** no task below an unticked checkpoint may start.

**Starting conditions (2026-11-19):**
- Branch `shino-new`. Yew Sing's `PLAN.md`, `PROGRESS.md`, `scripts/run-tasks.sh` and `scripts/test_guard.py` are never modified; Shino's copies live in `scripts/shino/` and read `PLAN-SHINO.md` / `PROGRESS-SHINO.md`.
- **M5 is built:** interaction sessions, anonymous questions, polls, live questions, reactions, IDU, websocket events, `participation_read.py`, and both apps' screens (`Participation`, `InteractionControl`, `InteractionSessions`). Remaining work is hardening, the end-of-session summary and the real-device E2E pass.
- **M6 is built:** quiz model, LLM drafting, review/approve, publish, attempts with autosave/resume/auto-submit, MCQ grading, short-answer scoring with AI suggestions, results, hard questions, `quiz_read.py`, Moodle quiz sync columns, and both apps' quiz screens. Remaining work is hardening, sync status/retry and the real E2E pass.
- **M7 is partly built:** `analytics.py` is rebuilt on `attendance_read.py` (Late counts, NFR-04 closed), per-student engagement, class trend, assessment by topic/session, student self view, participation and quiz tabs in `Analytics.jsx`. Early warning, the at-risk list, alert lifecycle and the student "needs attention" view are not built.
- **M2 is mostly unbuilt:** the `notifications` table and `notify.emit(event, user_ids, payload, priority)` exist and `attendance.recorded` / `quiz.published` already call it. There is no notification feed endpoint, no push/email worker, no bell/centre UI and no dashboard aggregate endpoint. The dashboards are scheduled last so they aggregate real data.
- Read interfaces are stable: `app/services/attendance_read.py` (FR-313), `participation_read.py` (FR-509), `quiz_read.py` (FR-614) and `app/services/kb/retrieval_api.search(course_id, query, k)` (FR-814). M7 and M2 read through them; never query another module's tables directly.
- LLM rules: normal tests replay recorded responses in `backend/tests/fixtures/llm/`; any new LLM path adds cases to the `live` suite and records fixtures. E2E uses `LLM_FAKE=1`.
- Every schema change needs an Alembic migration chained after the single current head (run `alembic heads` first; never branch a second head).
- Lecturer app runs on phone (Maestro) and browser (Playwright, `npm run e2e:web`); student app is phone-only (Maestro). Existing M5/M6 flows are `[~]` because they were not executed in the last build sessions — S101 runs them before new work starts.
- Deferred, not in this plan: FR-820–FR-824 (M8, Yew Sing) — unlocked by the `quiz_read` interface already delivered.
- **Task IDs restart at S101.** Entries S00–S47 in `PROGRESS-SHINO.md` are the historical log from the first plan and are not reused; new work always logs the S1xx ID from this file.

---

## 0. Baseline

- [x] **S101 [INFRA] Baseline verification and gap list.** Depends on: -.
  Done when: `bash scripts/check.sh` passes on `shino-new`; the targeted `db` suites for analytics, interactions, participation_read, quiz taking/scoring/read and the quiz S35 suite pass; the existing Maestro flows (`student interaction`, `lecturer interaction`, the student and lecturer quiz flows) and `npm run e2e:web` are either run successfully or marked `[~]` with the exact blocker in PROGRESS-SHINO.md; PROGRESS-SHINO.md lists every M2/M5/M6/M7 endpoint and screen with its real status and the gaps this plan will close. No production code changes.
- [ ] **S102 [HUMAN] Checkpoint: baseline accepted.** Depends on: S101. Shino reads the gap list, adjusts priorities if needed, and ticks this to let the loop continue.

## 1. Module 2 — Notifications (dashboards come in section 5)

- [ ] **S110 [API] Notification feed, read state and unread count (FR-205, FR-206, FR-218–FR-220).** Depends on: S102.
  Done when: `GET /me/notifications` returns the caller's rows ordered urgent → important → general then newest first, with `priority`, `event`, `payload`, `read_at`, `created_at` and a deep-link target, supports All/Unread and pagination, and never returns another user's row; `GET /me/notifications/unread-count` returns the badge number; `POST /me/notifications/{id}/read` and `POST /me/notifications/read-all` are idempotent and ownership-checked; tests cover ordering, filters, pagination, read/unread, the badge count and 403/404; the endpoints are described in `docs/interfaces.md`.
- [ ] **S111 [API] Push/email delivery worker and device tokens (FR-207, FR-208, FR-225–FR-227).** Depends on: S110.
  Done when: authenticated clients can register and unregister a push token per device; a background worker claims urgent/important rows, sends Android push through Expo Push and email through SMTP, leaves general rows feed-only, records `delivered_push`/`delivered_email`, retries with backoff, prunes tokens the push service rejects, and is config-gated (disabled cleanly when credentials are absent); tests mock both senders and cover success, failure, retry, general-skip and invalid-token pruning; config keys are documented.
- [ ] **S112 [API] Event catalogue and producer wiring (FR-209–FR-212, FR-228–FR-231).** Depends on: S110.
  Done when: one catalogue module defines event, audience, priority, payload and deep link for `attendance.recorded`, `attendance.flagged`, `face_enrolment.result`, `face_enrolment.pending_review`, `face.unrecognised`, `quiz.published`, `quiz.deadline` and `at_risk.flagged`; each producer calls `notify.emit` after its transaction commits (attendance and face call sites are small edits in Yew Sing's files — note them in PROGRESS-SHINO.md and `docs/requests-for-shino.md`); `attendance.flagged` is urgent; `quiz.deadline` is emitted once per student per deadline; tests fire each event and assert the row's user, priority and payload; R1's Status line is updated if the emit shape changed.
- [ ] **S113 [API] Notification dedupe, coalescing and retention (FR-222, FR-223).** Depends on: S110.
  Done when: repeated same-event/same-target rows inside the configurable window collapse into one item with a count (tested with a burst of attendance records); a background job deletes read rows older than the retention period and leaves unread rows alone; unread counts stay correct after cleanup; tests.
- [ ] **S114 [UI] Notification bell and centre in both apps (FR-218–FR-224).** Depends on: S110, S113, T03.
  Done when: both apps show a bell with an unread badge in the header; the centre has Today/Earlier grouping, All/Unread filters, mark-one/mark-all, relative time, event icon, priority pill, course context and tap-through deep links; empty, loading, error and offline states are present; read state survives a reload; accessibility labels include priority and course; Maestro flow (student) and Playwright flow (lecturer) cover unread → read → deep link.
- [ ] **S115 [HUMAN] Checkpoint: notifications on real devices.** Depends on: S111, S112, S114. Shino receives a real attendance notification, a quiz notification and an at-risk alert on a phone and in the browser; fixes found become follow-up tasks.

## 2. Module 5 — Classroom Interaction (hardening and E2E)

- [ ] **S120 [API] Session/poll lifecycle and end-of-session summary (FR-501, FR-504, FR-513, FR-516).** Depends on: S102.
  Done when: at most one poll per session can be open (opening a new poll closes the previous one; tested); a closed session rejects every write with a clear 409 while remaining readable to enrolled students for the retention period; `GET /lecturer/interactions/{id}/summary` and the student equivalent return questions asked/answered, poll participation, live-question responses, reaction counts and distinct IDU students; the scheduler still auto-closes expired sessions and their polls; tests for each rule.
- [ ] **S121 [API] Anonymity and live-event contract audit (FR-509, FR-515, FR-517).** Depends on: S120.
  Done when: a test walks every lecturer-facing response, log line and export and proves no anonymous student identity or name appears; `docs/interfaces.md` lists every websocket event with its payload; a test proves each event is emitted only after commit and that a failed socket does not roll back the write; duplicate vote/response/IDU attempts return the documented errors.
- [ ] **S122 [UI] Interaction screen polish (FR-510–FR-514, FR-517).** Depends on: S120, T03.
  Done when: both apps show Open/Live/Closed with a countdown to `ends_at`, a reconnect banner with retry, disabled write controls when closed, the section-card layout with "most recent inline + See all sheet", and accessible touch targets; the lecturer sees unanswered counts and the student sees own questions marked "Mine"; Maestro `student interaction` and `lecturer interaction` plus Playwright `interaction.spec.js` pass.
- [ ] **S123 [UI] End-of-session summary screen (FR-513, FR-516).** Depends on: S120, S122.
  Done when: the lecturer can open the summary from the session list and the control screen; the student sees the read-only version after close; both show the same counts as the API; a closed session opened from history renders the summary without live controls; unit tests or an E2E assertion cover the counts.
- [ ] **S124 [HUMAN] Checkpoint: interaction on two devices.** Depends on: S121, S123. Shino runs one seeded session with a second device as a student: ask anonymously, answer a live question, vote, react, toggle IDU, close the poll, end the session and read the summary.

## 3. Module 6 — AI Quiz (hardening and E2E)

- [ ] **S130 [API] Attempt state machine, autosave and timezone (FR-605, FR-607, FR-623).** Depends on: S102.
  Done when: a student has at most one active attempt per quiz; `attempts_allowed` is enforced; answers autosave and an unexpired attempt resumes with its saved answers; the deadline is server-side and expiry auto-submits once; open/close times are stored in UTC, validated (`closes_at > opens_at`, open not in the past by more than the allowed grace) and displayed in Malaysia time; tests cover resume, second attempt, expiry, validation and timezone round-trip.
- [ ] **S131 [API] Grading queue and result completeness (FR-609–FR-613).** Depends on: S130.
  Done when: the lecturer queue lists every unscored short answer with student name, question, answer, suggested answer and maximum points; scoring accepts 0..max only, recomputes the attempt total, and completing the last answer flips the quiz to grading-complete; the result endpoint returns score, percentage, per-question correctness, correct/ideal answer and learning hint subject to `review_visible`; hard questions use the configurable percentage and include topic/source; tests for each.
- [ ] **S132 [API] Moodle quiz sync status and retry (FR-605, FR-620).** Depends on: S130.
  Done when: publishing queues a Moodle `mod_quiz` sync, stores `pending | synced | failed` with the Moodle ids, exposes the status on the lecturer quiz payload, and `POST /lecturer/quizzes/{id}/moodle-sync` retries a failed sync; idempotent; mocked tests plus one `moodle` test against the local Moodle; failures do not block the quiz from opening in SmartClass.
- [ ] **S133 [UI] Student quiz flow polish (FR-606–FR-611, FR-617, FR-618).** Depends on: S130, S131, T03.
  Done when: QuizList groups Open now / Upcoming / Earlier by course and shows attempt state with a Resume action; TakeQuiz has question navigation, answered/unanswered markers, autosave on navigation, 5-minute and 1-minute warnings, submit confirmation and an explicit auto-submit notice; QuizResult shows score/percentage, per-question review when allowed and learning hints; Maestro flow covers start → answer → leave and resume → submit → result.
- [ ] **S134 [UI] Lecturer quiz flow polish (FR-604, FR-612–FR-616, FR-619, FR-621).** Depends on: S130–S132, T03.
  Done when: CreateQuiz has the five section cards, unsaved-changes guard and draft restore; Review has Draft/Approved/Deleted tabs with edit, approve/revert, delete and bulk actions; LiveResults shows live submitted/in-progress/not-submitted counts; ResultsClosed is the scoring queue with AI suggest; Breakdown shows hard questions and topic performance; the Moodle sync status and retry are visible; Maestro and Playwright flows with `LLM_FAKE=1` cover draft → approve → publish → seeded attempt → grade → results.
- [ ] **S135 [HUMAN] Checkpoint: full quiz cycle.** Depends on: S133, S134. Shino drafts from real material, reviews, publishes to two classes, takes it as a student, grades a short answer and reads the results; fixes become follow-up tasks.

## 4. Module 7 — Analytics and Early Warning

- [ ] **S140 [API] Indicator service and topic performance (FR-701–FR-705, FR-715, FR-720).** Depends on: S102, S120, S131.
  Done when: one service computes per student per course the attendance rate and absence frequency (attendance_read), participation frequency, questions and IDU (participation_read), quiz average and trend over the last N graded quizzes (quiz_read), plus class-level session series and topic averages; the formulas match the source screens; results are cached with an "as of" time and invalidated after a session close or quiz grading; the endpoint paginates or aggregates so 100 students stay within the NFR-17 target; tests seed each indicator and compare with the source interface.
- [ ] **S141 [API] Early warning evaluation and alert lifecycle (FR-707–FR-709, FR-711, FR-712).** Depends on: S140, S112.
  Done when: the four conditions are evaluated with configurable thresholds and a minimum-data rule (default 3 sessions/quizzes); each flag carries severity `watch | at-risk` and a human reason; one active alert exists per student + course + condition, re-evaluation does not duplicate it, a cleared condition resolves it, a cooldown prevents re-alerting, and a lecturer can acknowledge/dismiss with a reason (audited); evaluation is hooked after attendance close and after grading complete; `notify.emit(..., priority="important")` is called only for new/changed active alerts; tests per condition, the minimum-data rule, dedupe, resolve and acknowledge.
- [ ] **S142 [API] At-risk list and student self view (FR-706, FR-710, FR-713, FR-714, FR-716).** Depends on: S140, S141.
  Done when: `GET /lecturer/classes/{id}/at-risk` filters by condition/severity/date and returns each student's flag, reason, latest indicators and trend; `GET /student/me/analytics` returns the student's own indicators and "needs attention" items with next steps and no peer data; every endpoint enforces lecturer-owns-class and student-is-self (403 otherwise, tested).
- [ ] **S143 [UI] Lecturer analytics tabs and at-risk drill-down (FR-703–FR-705, FR-713, FR-715, FR-717, FR-719).** Depends on: S140–S142, T03.
  Done when: Analytics has Overview / Attendance / Participation / Quiz / At-risk tabs on real endpoints; the class picker and date range drive every tab; charts show real dates and have table fallbacks; the at-risk tab filters and drills into a student; the "as of" time and CSV export are visible; Playwright covers all tabs and the drill-down, and the lecturer Maestro flow reaches the at-risk list.
- [ ] **S144 [UI] Student My Analytics (FR-706, FR-714).** Depends on: S140, S142, T03.
  Done when: the student screen shows own attendance, participation, quiz trend and "needs attention" items with plain-language explanations and next steps; it never shows another student or a class rank; Maestro flow with seeded data asserts the student's own numbers.
- [ ] **S145 [HUMAN] Checkpoint: analytics review.** Depends on: S143, S144. Shino checks the numbers against the attendance, participation and quiz screens, then triggers an at-risk alert end to end and resolves it.

## 5. Module 2 (rest) — Dashboards

- [ ] **S150 [API] Role-shaped dashboard endpoints (FR-201–FR-204, FR-213–FR-217).** Depends on: S112, S114, S122, S142.
  Done when: `GET /me/dashboard` returns a student shape (live session, needs-attention notifications, today's classes with attendance state, upcoming quizzes and assignment from moodle, latest three Moodle announcements, general feed preview) and a lecturer shape (today's class cards with controls and live counts, pending grading, at-risk alerts, participation snapshot, recent quiz activity, announcements); the response contains only the caller's courses (tested per role); urgent/important are ordered before general; each card carries a deep link; announcements come from the Moodle forum and the endpoint degrades cleanly when Moodle is unavailable; tests.
- [ ] **S151 [UI] Student dashboard rebuild (FR-201, FR-204, FR-213–FR-217).** Depends on: S150, T03.
  Done when: Home is rebuilt on the endpoint in the fixed section order, with live-session card, needs-attention block, classes, quizzes, announcements and feed preview; skeletons, empty and offline states are present; pull-to-refresh and refresh-on-focus work; tapping each card opens the right screen and returning refreshes; Maestro flow seeds all three priorities and a live session.
- [ ] **S152 [UI] Lecturer dashboard rebuild, phone and web (FR-202, FR-213–FR-215).** Depends on: S150, T03.
  Done when: the lecturer Home uses the endpoint for class cards, live counts, pending grading, at-risk alerts and participation snapshot; Start/Open, +15 min and End class still work; the web layout is a two-column grid with side navigation and the phone layout is one column; Maestro and Playwright flows cover the cards and controls.
- [ ] **S153 [HUMAN] Checkpoint: all four modules on real devices.** Depends on: S151, S152. Shino walks M2 → M5 → M6 → M7 on a phone and in the browser; Yew Sing joins to check the seams (his events in the feed, the FR-313/509/614 interfaces, at-risk alerts he receives as a lecturer).

## 6. Wrap-up

- [ ] **S160 [INFRA] Docs and interfaces refresh.** Depends on: all API tasks.
  Done when: `docs/interfaces.md` holds the notification feed/event catalogue, attendance read, participation read, quiz read and KB retrieval contracts; README/CLAUDE.md run instructions cover push/email config, `LLM_FAKE=1` E2E and the seeded dashboard/analytics data; `docs/requests-for-shino.md` has no open R1/R2 lines; FR traceability shows every FR-2xx/5xx/6xx/7xx mapped to a task or an explicit deferral.
- [ ] **S161 [INFRA] Final verification.** Depends on: S160.
  Done when: `bash scripts/check.sh` passes; the full non-live `db` suite passes; the student and lecturer Maestro flows and the lecturer Playwright suite pass; no test is skipped or weakened without a `TEST-CHANGE:` line in PROGRESS-SHINO.md; the final PROGRESS-SHINO.md entry lists the checks and any `[~]` items with their blockers.
- [ ] **S162 [HUMAN] Merge preparation.** Depends on: S161. When Shino says "prepare the merge", run `.claude/commands/prepare-merge.md` against `shino-new`: checks, conflict resolution against `main`, and a note for Shino with anything still open. Claude never merges.

**Deferred (not in this plan, waiting on Yew Sing's M8):** FR-820–FR-824.
