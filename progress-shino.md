# PROGRESS — Shino's modules (M2, M5, M6, M7)

Short log for [plan-shino.md](plan-shino.md), newest entry at the bottom of "Log". Each entry is at most 5 lines:
`### Sxx — <title> — <date>` then: Changed · Decisions · Interface/schema changes · Tests · Next.
Yew Sing's log is [PROGRESS.md](PROGRESS.md); never edit it. Test removals need a line `TEST-CHANGE: <test> - <why>` here.

## Blocked
<!-- Format: - Sxx: <problem>, what was tried, what is needed. Remove the line when it's resolved. -->

## Next
<!-- Follow-up ideas found during tasks that are out of the current task's scope. -->

- LOOP (2026-11-21): S02's post-commit `check.sh` failed only in the live LLM suite, which ran because S02 restored `app/services/kb/integrations.py` (now identical to `origin/main`). All failures were Yew Sing's assistant test answering "general" instead of "course" for an in-syllabus question (5/28, then 2/28 on re-run): model variance, not S02. Rounds after S02 don't touch `kb/`, so it doesn't re-trigger. Mention it to Yew Sing.
- LOOP (2026-11-21): `scripts/check.sh` now caches a pass inside the loop (`.claude/.check-pass`, fingerprint = round base + code tree), so the Stop hook and post-commit runs on unchanged code take seconds. Test: `backend/tests/test_check_cache.py`.
- No runnable task (2026-11-21): S04 `[HUMAN] Checkpoint: review S01–S03` is unticked and every remaining task depends on it (S10+ sit below it). Shino needs to review the S02 removal list and the S03 helpers, then tick S04 `[x]` in plan-shino.md.

- S02 manual checks done (2026-11-22): dev DB downgraded to `b5c6d7e8f9a0` (head); no session needed closing (the "session 16" was left by S02's own interrupted spec run and is gone; session 10 is WIA0000's always-open class); `npm run e2e:web -- live-session.spec.js` 1/1 passed; `pytest -m live` 16 passed, 7 failed, 5 skipped (LLM_QUOTA). All 7 failures are Yew Sing's `test_in_syllabus_is_grounded` (`general` instead of `course`); `app/services/kb/` is identical to `origin/main`, so this is M8 model variance, not S02. S02 ticked `[x]`. S04 ticked by Shino 2026-11-22.
- REVIEW: S03 - the live trigger runs the whole `-m live` suite when `app/services/quiz/` changes, so the flaky M8 test above would fail M6 rounds. Added to S41's Done when: quiz-only changes run only Shino's M6 live tests.

### Requests for Yew Sing
<!-- Interface gaps in M1/M3/M4/M8 that a task needed. Copy each to docs/requests-for-shino.md style when sending. -->

### S02 notes (2026-11-21)
- **Dev DB downgrade (Shino runs this once; the loop does not touch the dev DB).** The dev DB is at the removed revision `f5a6b7c8d9e0` (`alembic current` fails with "Can't locate revision"). From `backend/`, put the three removed files back temporarily, downgrade, then delete them:
  `git show dfefa19:backend/alembic/versions/e3f4a5b6c7d8_notifications.py > alembic/versions/e3f4a5b6c7d8_notifications.py`
  `git show dfefa19:backend/alembic/versions/e4f5a6b7c8d9_dashboard_cache.py > alembic/versions/e4f5a6b7c8d9_dashboard_cache.py`
  `git show dfefa19:backend/alembic/versions/f5a6b7c8d9e0_interaction.py > alembic/versions/f5a6b7c8d9e0_interaction.py`
  `alembic downgrade b5c6d7e8f9a0` then `rm alembic/versions/e3f4a5b6c7d8_notifications.py alembic/versions/e4f5a6b7c8d9_dashboard_cache.py alembic/versions/f5a6b7c8d9e0_interaction.py` and check `alembic current` prints `b5c6d7e8f9a0 (head)`. (`a6b7c8d9e0f1_quizzes` was never applied to the dev DB.)
- **Kept endpoints:** none. No M1/M3/M4/M8 screen or test called the removed notification, dashboard, interaction, quiz or `/lecturer/analytics` endpoints; the lecturer Analytics tab keeps only M3's attendance report export (`GET /lecturer/classes/{id}/attendance/report` + CSV), which is Yew Sing's.
- **M1/M3/M8 code reverted to Yew Sing's version:** login no longer refreshes a Moodle dashboard snapshot (`auth.py`, `moodle_auth.py`, Moodle WS allowlist in `configure_moodle.php`), sessions/scheduler no longer broadcast interaction status, `kb/integrations.get_active_attempt` returns `None` again (M6 quiz lock comes back in S47), `notify.emit` logs only.
- TEST-CHANGE: backend/tests/test_notifications.py (test_policy_and_stable_attendance_subject, test_external_notification_link_is_rejected, test_recurring_events_and_custom_title, test_feed_deduplicates_and_isolates_recipients, test_read_all_only_changes_caller, test_dashboard_role_and_priority_scope, test_dashboard_student_status_and_lecturer_counts) - pre-plan M2 feed/dashboard code removed in S02; rebuilt test-first in S10/S11/S18.
- TEST-CHANGE: backend/tests/test_dashboard_moodle.py (test_fetch_only_news_and_requested_course_events, test_partial_calendar_warning_is_not_a_successful_snapshot, test_refresh_failure_preserves_snapshot, test_snapshot_filters_removed_enrolments, test_refresh_persists_content_without_credentials, test_live_moodle_login_populates_dashboard_snapshot) - pre-plan M2 Moodle snapshot removed in S02; rebuilt in S16.
- TEST-CHANGE: backend/tests/test_interaction.py (all 15 tests: access/lifecycle, questions, polls, quick answers, reactions, confusion, summary/M7 read, websocket) - pre-plan M5 code removed in S02; rebuilt in S30–S36.
- TEST-CHANGE: mobile JS tests lecturer `services/dashboard.test.js`, student `services/dashboard.test.js`, `interactionEvents.test.js`, `interactionRefresh.test.js` and Maestro `student/e2e/interaction.yaml` - they tested removed pre-plan M2/M5 client code; rebuilt with S19/S20/S38.
- TEST-CHANGE: lecturer `e2e-web/desktop.spec.js` (Quiz/Analytics part of "every screen opens") and `e2e-web/tabs.spec.js` ("page deeper inside another tab") - the quiz/analytics mock screens they walked through are now "Coming soon" placeholders; desktop now checks the placeholders, tabs uses the Assistant tab's "Before next class" page as the deeper page (same tab-reset behaviour).

## Log

### S01 — Shino task loop — 2026-11-21
- Changed: added `scripts/shino/run-tasks.sh` (same engine as `scripts/run-tasks.sh`, pointed at plan-shino.md / progress-shino.md), `/shino-run-plan`, `/shino-next-task`, `/shino-plan-task`, the `shino-reviewer` agent and `scripts/shino/opencode/` prompts.
- Decisions: fresh start; earlier M2/M5/M6/M7 code is removed in S02, not reused. Both loops share `.claude/.loop.lock`, so only one runs at a time (they share the test DB).
- Interface changes: `scripts/test_guard.py` also accepts `TEST-CHANGE:` in progress-shino.md (additive).
- Tests: `backend/tests/test_shino_loop_script.py`.

### S02 — Clean slate for M2/M5/M6/M7 — 2026-11-21
- Changed: removed all pre-plan M2/M5/M6/M7 backend code (notification/dashboard/interaction/quiz routers, services, models, schemas, 4 migrations, legacy `routers/analytics.py` + `schemas/analytics.py`) and their tests; M1/M3/M8 files are back to Yew Sing's last commit `45888be` (backend identical); lecturer Quiz tab and student Participation tab show a shared `ComingSoon` placeholder, lecturer Analytics shows it plus M3's attendance report export. Removal list, kept endpoints (none), dev-DB downgrade and TEST-CHANGE lines: "S02 notes" under Next.
- Decisions: restored one assertion the pre-plan work had dropped from lecturer `attendance.test.js`; `tabs.spec.js` uses the Assistant tab's "Before next class" page as its deeper page.
- Interface/schema changes: `GET /lecturer/analytics` and all M2/M5/M6 endpoints gone; Alembic head is `b5c6d7e8f9a0` (one head); `notify.emit` logs only; replies added to R2 and the analytics issue in `docs/requests-for-shino.md`.
- Tests: check.sh normal stages pass; live stage (triggered because `kb/integrations.py` reverted to Yew Sing's b62d2c3 version) failed 5/28, then 2/28 on re-run, always `test_in_syllabus_is_grounded` returning `general` (Yew Sing's M8 model flakiness, not this change); Playwright desktop/tabs/export 11/11 pass. **[~] manual check:** close the open WIA0000 session 16 in the dev DB, then run `npm run e2e:web -- live-session.spec.js`, and re-run `pytest -m live` once so `.claude/.live-pass` gets recorded.

### S03 — Test helpers for Shino's modules — 2026-11-21
- Changed: new `tests/shino_helpers.py` with the fixtures `shino_class` (SH101: lecturer, 4 enrolled students, an outsider student, a second lecturer on SH202, and an open session from M3's `session_schedule.start_now`), `fake_expo_push` (respx; supports DeviceNotRegistered, network failure and HTTP errors, and blocks any other outgoing call), `fake_smtp` (patches `smtplib.SMTP` and `SMTP_SSL`, `fail_next`, never keeps passwords) and `shino_llm` (replays `tests/fixtures/llm/m6/<name>.json`; live tests call the real LLM; `--record-llm` saves passing live tests only). `tests/conftest.py` imports them.
- Decisions: the LLM helper patches `kb.llm.chat`, so `chat_json` goes through it too. Replay warns when the prompt changed since recording and fails when there are more calls than recorded. The SMTP fake assumes S14 uses stdlib `smtplib`.
- Interface changes: `scripts/check.sh` also runs the live suite when `app/services/quiz/` changes, and new untracked files in kb/ or quiz/ now count as changes. The hash is unchanged while quiz/ is empty.
- Tests: `test_shino_helpers.py` (7 tests) and `test_check_live_trigger.py` (3 tests); check.sh passes (722 passed). Next: S04 checkpoint (Shino).
