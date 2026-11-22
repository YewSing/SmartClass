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
- REVIEW: S17 - `registry.build` uses a payload `title`/`message` as the whole title/message for every event, so `moodle.deadline_reminder` (template `Deadline soon: {title}`) would lose its prefix if its emitter passes the Moodle event name as `title`. S81 should pass the name under another key (e.g. `deadline_title`) or limit the override.
- S17 follow-up: the `announcement.posted` link `/announcements/{id}` has no student read endpoint/screen yet; the notification carries the full text. Decide in S19/S20 (open the feed item, or add `GET /student/announcements/{id}`).

### Requests for Yew Sing
<!-- Interface gaps in M1/M3/M4/M8 that a task needed. Copy each to docs/requests-for-shino.md style when sending. -->
- S18 (2026-11-22): `attendance_read` covers closed sessions only, so the dashboards read open-session data through two existing M3 functions: `attendance_stats.student_course_history` (student's status in an open session) and `session_service.get_session_counts` (live counts). Please list them in `docs/interfaces.md` as stable, or add an open-session read to `attendance_read`.

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

### S10 — Notification store and event interface — 2026-11-22
- Changed: `m2_notifications` model + migration `e7f8a9b0c1d2` (head); `app/services/notifications/registry.py` (all FR-206 events + `announcement.posted`, each with priority, templates, app-relative link, subject, dedup window) and `store.py::deliver` (own session, advisory lock per event+subject, skips unknown users and duplicates); `notify.emit` now persists through it (lazy import, same signature, never raises).
- Decisions: priority only from the event type; payload `title`/`message`/`link` override the defaults (FR-205); an unsafe link (external, `//`, `..`, `%`, scheme) stores nothing; no subject fields → subject = hash of the text. M3's fixed `message` ("Attendance recorded for X") overrides the template, so the status isn't shown; fine for now.
- Interface/schema changes: new table `m2_notifications`; event table with priorities/fields/windows in `docs/interfaces.md`. `emit` must be called after commit (it opens its own session). No M3 code changed.
- Tests: `tests/test_notifications_store.py` (31: priorities, templates, unsafe links, dedup within/after window and per recipient, unknown events/users, payload never stored or logged, M3 `broadcast_attendance_update` lands a row); check.sh passes. Next: S11 feed; S12–S14 hang delivery off `deliver`'s returned ids.

### S11 — Feed and read state — 2026-11-22
- Changed: `routers/notifications.py` (`GET /notifications`, `GET /notifications/priority`, `POST /notifications/{id}/read`, `POST /notifications/read-all`), `services/notifications/feed.py`, `schemas/notification.py`; registered in `main.py`.
- Decisions: any active role has a feed; keyset cursor on (created_at, id) as opaque base64, bad cursor → 422; priority list = unread urgent then important, max 50; read is idempotent (first `read_at` kept); someone else's id → 404; read endpoints return the new `unread_count` (S12 can reuse it).
- Interface/schema changes: new endpoints (documented in `docs/interfaces.md` "Notification feed API"); no schema change.
- Tests: `tests/test_notifications_feed.py` (19: ordering incl. ties, pagination across ties and new arrivals, counts, priority scope, read/read-all, isolation, auth, emit → feed). Next: S12 websocket.

### S12 — Live notifications over websocket — 2026-11-22
- Changed: `services/notifications/live.py` (per-user hub, `publish` called by `store.deliver` after its commit, `publish_unread_count`); `WS /notifications/ws?token=` in `routers/notifications.py`; read/read-all queue an `unread_count` message via `after_commit`; `feed.out` shared by REST and WS.
- Decisions: bad/expired/refresh token, role mismatch or inactive user → accepted then closed 1008 (so clients see the code); `connected` carries the current unread count; nothing queued or replayed; live failures are logged, never fail the event. Single uvicorn worker assumed (as M3).
- Interface/schema changes: new WS endpoint and message types in `docs/interfaces.md` "Live notifications"; no schema change.
- Tests: `tests/test_notifications_live.py` (12, in-process ASGI websocket client: 1008 cases, right user/all connections only, sent after commit, dedup sends nothing, reconnect not stale, read updates); check.sh passes (784). Next: S13 push; reviewer note: no per-socket send timeout, fine at this scale.

### S13 — Push tokens and Expo push — 2026-11-22
- Changed: `m2_push_tokens` model + migration `f8a9b0c1d2e3` (head); `routers/push_tokens.py` (`POST /me/push-tokens` atomic upsert, `DELETE /me/push-tokens/{token}`); `services/notifications/push.py` (background send after `store.deliver` commits, batches of 100, `DeviceNotRegistered` deletes the token, failures logged without token/secret); `EXPO_*`/`PUSH_*` settings.
- Decisions: only urgent/important, only `PUSH_PLATFORMS` (default `android`, FR-210: iOS in-app + email); a token used by another account moves to the caller; someone else's token → 404; no retry on network failure; tests drain pending pushes before truncation (autouse `_drain_push`).
- Interface/schema changes: new table `m2_push_tokens`, endpoints + push message shape in `docs/interfaces.md` "Push tokens and Expo push"; `FakeExpoPush.requests` added (additive).
- Tests: `tests/test_notifications_push.py` (30, respx only: format/platform 422s, one row per device, concurrent registration, ownership, priorities, iOS, dedup, batching, DeviceNotRegistered, network/500, background, auth header); check.sh passes (814). Next: S14 email.

### S14 — Email for urgent/important — 2026-11-22
- Changed: `services/notifications/mailer.py` (background send after `store.deliver` commits, stdlib `smtplib` in a thread, one connection per try); `SMTP_*`/`EMAIL_*` settings (off while `SMTP_HOST` empty), `.env.example`; tests drain email too and an autouse `_no_real_smtp` keeps email off unless a test turns it on.
- Decisions: urgent/important only, to `users.email` of active users; subject `[SmartClass] (Urgent: )<title>`, CR/LF stripped; temporary errors (disconnect, OSError, 4xx incl. 4xx recipient refusal) retried ≤ `EMAIL_MAX_RETRIES` per send with doubling delay; 5xx recipient rejection drops that message only; login/sender refusal stops; logs hold counts + exception names only.
- Interface/schema changes: no schema change; settings + behaviour in `docs/interfaces.md` "Email for urgent/important".
- Tests: `tests/test_notifications_email.py` (18, fake SMTP sink: priorities, dedup, inactive, off when unset, ssl/starttls/plain, link base, header injection, background, retry/max/connection refused, rejected/greylisted recipient, login failure, no secrets/addresses in logs, push unaffected); check.sh passes (832). Next: S15 preferences/retention.

### S15 — Preferences and retention — 2026-11-22
- Changed: `m2_notification_preferences` model + migration `a9b0c1d2e3f4` (head; also `ix_m2_notifications_created`); `routers/notification_preferences.py` (`GET/PUT /me/notification-preferences`); `services/notifications/preferences.py` (`channel_filter` used by push/mailer queries); `services/notifications/retention.py` (`purge` + daily `retention_loop`, started in `main.py`); `NOTIFICATION_RETENTION_*` settings.
- Decisions: FR-211 says general isn't emailed and S13/S14 never push/email general, so general push/email are opt-in (default off) and FR-214's switch turns them on/off; urgent/important `false` → 422, strict booleans, partial PUT; retention ≤ 0 days deletes nothing (no accidental wipe); read state doesn't matter for retention.
- Interface/schema changes: new table + endpoints + retention settings in `docs/interfaces.md` "Preferences and retention"; push/email sections updated for opted-in general.
- Tests: `tests/test_notifications_prefs.py` (25: defaults, per-user save, partial PUT, 422s, auth, general push/email on/off per user, urgent/important unaffected, purge cutoff/configured days/idempotent/zero days, loop sleeps a day, survives errors, off when interval ≤ 0; clocks monkeypatched); check.sh passes (857). Next: S16 Moodle announcements/deadlines.

### S16 — Moodle announcements and deadlines on login — 2026-11-22
- Changed: `m2_moodle_snapshot` model + migration `b0c1d2e3f4a5` (head); `services/dashboard/moodle_snapshot.py` (`refresh_on_login` reads news-forum discussions + course calendar events with the user's own token, saves all at once; `get_snapshot` for S18); `MOODLE_SNAPSHOT_*` / `MOODLE_PUBLIC_URL` settings; 3 forum/calendar functions in `configure_moodle.php` (already present in the local Moodle).
- Decisions/M1 change: one call in `POST /auth/moodle-login` after its commit, **plus** an additive `MoodleProfile.moodle_token` field (repr-hidden, set in `authenticate`) — needed because the route never sees the token; noted in `docs/requests-for-shino.md`. No token → nothing fetched (never the service token); errors, Moodle warnings, bad shapes, timeout (8 s) keep the old row; logs carry only the exception class.
- Interface/schema changes: new table `m2_moodle_snapshot`; "Moodle announcements and deadlines snapshot" in `docs/interfaces.md`.
- Tests: `tests/test_moodle_snapshot.py` (20 respx + 1 `moodle`); `test_moodle_login.py` unchanged and passing; check.sh passes (878). **[~] manual check:** the local Moodle answers token.php with `invaliddatarootpermissions` (Yew Sing's `test_local_moodle_*` fail the same way), so fix the Moodle dataroot permissions, then run `cd backend && python -m pytest -m moodle tests/test_moodle_snapshot.py tests/test_moodle_login.py`. Next: S17 announcements.

### S17 — Lecturer announcements — 2026-11-22
- Changed: `m2_announcements` model + migration `c1d2e3f4a5b6` (head); `routers/announcements.py` (`POST/GET /lecturer/classes/{occurrence_id}/announcements`); `services/notifications/announcements.py` (create + after-commit `announcement.posted` to active enrolled students, Moodle post queue, `announcement_moodle_loop` in `main.py`); `ANNOUNCEMENT_MOODLE_*` settings; `mod_forum_add_discussion` added to `configure_moodle.php`; `registry.build` now keeps a caller's full title/message for `announcement.posted` too (slots cut text to 120 chars).
- Decisions: posts use the service token (the lecturer's token is never stored), lecturer named in the message; the queue is in the table (pending → posted/failed, backoff 30 s doubling up to 30 min, 5 tries); the marker `(SmartClass announcement #id)` stops a retry double-posting after a lost reply; no `MOODLE_TOKEN`/loop off → first failure final; unknown class → 403; the audit keeps no message text.
- Interface/schema changes: new table, endpoints, settings in `docs/interfaces.md` "Lecturer announcements"; no M1/M3/M4/M8 code changed.
- Tests: `tests/test_announcements.py` (25 respx + 1 `moodle`); check.sh passes (903). **[~] manual check:** re-run `configure_moodle.php` in the Moodle container (adds `mod_forum_add_discussion`), fix the dataroot permissions (`invaliddatarootpermissions`, as in S16), then `cd backend && python -m pytest -m moodle tests/test_announcements.py` (it leaves one "[SmartClass test]" post in WIA0000's Announcements). Next: S18 dashboard reads.

### S18 — Dashboard reads — 2026-11-22
- Changed: `services/dashboard/reads.py`, `routers/dashboard.py` (`GET /student/me/dashboard`, `GET /lecturer/dashboard`), `schemas/dashboard.py`; registered in `main.py`.
- Decisions: today = MYT date of `reads.clock()`; a class is "today" with a weekly slot today or a session dated today (open first, else latest); overview = newest open session, else newest closed; closed counts/rates via `attendance_read`, open-session status/counts via M3's `student_course_history`/`get_session_counts` (request for Yew Sing under Next); `needs_confirmation` → status null.
- Interface/schema changes: new endpoints in `docs/interfaces.md` "Dashboard reads"; `live_activity`/`participation`/`quizzes`/`at_risk_alerts` always `null` until S80; no schema change.
- Tests: `tests/test_dashboard.py` (16: open/closed status, rates incl. excused/null, snapshot + isolation, priority order, weekly slot without session, other day, open vs closed overview, other lecturer/outsider, roles); check.sh passes (919). Next: S19 notification centre UI.
