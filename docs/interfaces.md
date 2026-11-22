# Interfaces Yew Sing's modules give Shino's modules

This page lists the Python functions Shino's modules may call to read data Yew Sing's modules
own. It is plain English on purpose: the code is the source of truth, this page says what to
expect from it. Fields may be added; names are not changed without a note in
`docs/requests-for-shino.md`.

Three interfaces so far:

- **Attendance read interface for Module 7 (FR-313)** — below.
- **Course knowledge base retrieval for Module 6 (FR-814, T88)** — below.
- **Notification hook for Module 2 (FR-406, T44)** — below.

---

## Attendance read interface for Module 7 (FR-313)

`app/services/attendance_read.py` gives M7 attendance records, attendance rates and
consecutive absences, so M7 does not have to count `AttendanceRecord` rows itself.

### How to call it

```python
from app.services.attendance_read import course_rates, consecutive_absences

@router.get("/lecturer/analytics/...")
async def handler(course_id: int, db: AsyncSession = Depends(get_db),
                  actor: User = Depends(require_role("lecturer"))):
    # check access first (NFR-04): ensure_teaches_occurrence / your own course check
    rates = await course_rates(db, course_id)
```

The functions take an `AsyncSession` and read only; they never commit.

### Rules

These are the same rules the student app and the lecturer reports use (FR-308):

- Only **closed** sessions count. Open, scheduled, cancelled and `needs_confirmation` sessions
  are left out.
- A student enrolled in a class with no record in one of its closed sessions is **absent**.
- **Late** counts as attended. **Excused** is left out of the rate.
- The rate is `(present + late) ÷ (closed − excused)` as a percentage with one decimal.
  When nothing counts (`closed − excused` is 0) the rate is `None`, not 0.
- Enrolment is per class (occurrence), so a tutorial session lists only that group's students.
  A course result joins all its classes (lecture and tutorials) together, the same way the
  student app groups a course.
- Dates are the MYT date of the class. Date ranges are inclusive.

### Functions

| Function | Arguments | Returns | Order |
|---|---|---|---|
| `course_records` | `db, course_id, from_date=None, to_date=None` | `list[AttendanceRow]` — every enrolled student in every closed session of the course | oldest session first, then matric no |
| `student_records` | `db, student_id, course_id=None, from_date=None, to_date=None` | `list[AttendanceRow]` — one student in every closed session of their classes | oldest first |
| `course_rates` | `db, course_id, from_date=None, to_date=None` | `list[AttendanceRate]` — one row per enrolled student | matric no |
| `student_rates` | `db, student_id, from_date=None, to_date=None` | `list[AttendanceRate]` — one row per course | course code |
| `consecutive_absences` | `db, course_id, min_current=0` | `list[AbsenceStreak]` — one row per enrolled student with `current >= min_current` | highest `current` first, then matric no |
| `absence_streak` | `statuses: list[str]` (oldest first) | `tuple[int, int]` — `(current, longest)` | pure helper, no DB |

A date range whose `from_date` is after `to_date` raises `ValueError`. Unknown course or
student ids return an empty list.

### Returned fields

`AttendanceRow` — one student's status in one closed session:

| Field | Meaning |
|---|---|
| `session_id` | attendance session id |
| `occurrence_id` | class (occurrence) id |
| `class_type` | `LECTURE` or `TUTORIAL` |
| `class_label` | the class's label, or `None` |
| `course_id`, `course_code` | the course |
| `student_id`, `matric_no`, `name` | the student (`students.id`, matric no, full name) |
| `date` | MYT date of the class |
| `starts_at` | session start time (`starts_at`, else `opened_at`) |
| `status` | `present`, `late`, `excused` or `absent` |
| `detected_at` | when the record was detected, or `None` |
| `overridden` | `True` when a lecturer changed the status |

`AttendanceRate` — one student's counts and rate for one course:

| Field | Meaning |
|---|---|
| `student_id`, `matric_no`, `name` | the student |
| `course_id`, `course_code`, `course_name` | the course |
| `present`, `late`, `excused`, `absent` | session counts |
| `closed_sessions` | all four counts added together |
| `counted_sessions` | `closed_sessions - excused` |
| `rate` | percentage 0–100 with one decimal, or `None` when nothing counts |

`AbsenceStreak` — consecutive absences of one student in one course:

| Field | Meaning |
|---|---|
| `student_id`, `matric_no`, `name` | the student |
| `course_id`, `course_code` | the course |
| `current` | absences in a row up to the latest closed session (0 if they last attended) |
| `longest` | longest run of absences so far |
| `last_attended` | date of the latest present/late session, or `None` if never |

### Statuses

The four statuses are `present | late | excused | absent` (`ATTENDANCE_STATUSES` in
`app/models/attendance.py`). `ATTENDED_STATUSES` is `("present", "late")`. The old
`unidentified` status no longer exists.

### No permission checks

The interface does not check who is asking. Callers must check the user may see the course
(NFR-04) before calling it, because it returns names and matric numbers.

### Stability

Fields may be added, but never renamed or removed without a note in
`docs/requests-for-shino.md`.

### Why switch

`app/routers/analytics.py` (M7) counts only `present` (around lines 75–76, 151–152 and 206) and
still treats the removed `unidentified` status as absent. Since T30, Late counts as attended
(FR-308), so in M7 Late students look absent and its rate disagrees with the student app's
`/student/me/attendance/courses`. Suggested fix: build the counts from `student_rates`,
`course_rates` or `course_records` instead of counting `AttendanceRecord` rows directly.
Yew Sing did not edit `analytics.py` because M7 belongs to Shino.
(2026-11-21: `analytics.py` was removed in plan-shino.md S02; the rebuilt M7 reads `attendance_read`.)

---

## Module 8 → Module 6 — course knowledge base retrieval (FR-814)

**File:** `backend/app/services/kb/retrieval_api.py`

```python
async def search(course_id: int, query: str, k: int = 8) -> list[Passage]
```

Returns the top-k passages for `query` within one course. Module 6 (AI quiz generation)
uses this to draft questions from a course's materials without parsing them itself.

Each `Passage` (from `app.services.kb.search`) carries its source so citations and quiz
question references can point at the material:

| Field | Meaning |
|---|---|
| `material_id`, `title` | the source file |
| `section_name` | the Moodle section (e.g. "Week 3") |
| `location_type` | `page`, `slide` or `section` |
| `location_start`, `location_end` | the page/slide/section number(s) |
| `heading`, `text` | the passage itself |
| `score`, `vector_similarity` | retrieval confidence (RRF score, cosine similarity) |

The search is hybrid (vector + keyword) and is scoped to `course_id`, so Module 6 gets
only the materials of the course it is generating for. The function owns its own
database session; the caller passes no session.

---

## Notification hook for Module 2 (FR-406, T44)

**File:** `backend/app/services/notify.py`

```python
async def emit(event: str, user_ids: Iterable[int], payload: dict) -> None
```

Yew Sing's modules raise a notification event here and Module 2 delivers it (push, in-app or
email). Since S10 it **stores an in-app notification** per recipient (`m2_notifications`, see
"Module 2 notification events" below); push/email follow in S13/S14. It **never raises**, so a
notification can never fail the request that raised it. `user_ids` are `users.id`, not
`students.id` or `lecturers.id`. The payload is never logged: it holds names and matric numbers
(NFR-02 / PDPA).

### Events currently raised

| Event | To | Payload fields |
|---|---|---|
| `attendance.recorded` | the student | `session_id`, `course_code`, `course_name`, `status` (`present` \| `late`), `detected_at`, `source` (`recognition` \| `student_flag`), `message` |

`attendance.flagged` and `face_enrolment.pending_review` / `face_enrolment.result` (R1 in
`docs/requests-for-shino.md`) are not raised through `emit` yet.

### Module 2 notification events (S10, Shino)

`emit` calls `app/services/notifications/store.py::deliver`, which opens its **own** DB session, so
call `emit` after your commit (an `after_commit` callback). The event registry is
`app/services/notifications/registry.py`:

- The **priority** comes from the event type only (FR-207); a `priority` in the payload is ignored.
- `title`, `message`, `link` in the payload override the defaults (FR-205). Otherwise they are
  filled from the payload fields below; a missing field falls back to fixed text (link: none).
- `link` must be an app-relative path (`/quizzes/7`); external URLs, `//`, `..`, schemes or odd
  characters are rejected and **nothing is stored** (logged as `UnsafeLink`).
- **De-duplication (FR-216):** same event + recipient + subject inside the event's window is
  dropped. Without the subject fields, identical title/message/link count as the same subject.
- Unknown events and unknown recipients are logged and skipped. Only the rendered title,
  message and link are stored, never the payload.

| Event | Priority | Payload fields used | Subject | Window |
|---|---|---|---|---|
| `attendance.recorded` | general | `session_id`, `course_code`, `status` | `session_id` | 24 h |
| `attendance.flagged` | important | `session_id`, `course_code`, `flag_id` | `flag_id` | 24 h |
| `face_enrolment.pending_review` | important | `enrolment_id` | `enrolment_id` | 24 h |
| `face_enrolment.result` | important | `enrolment_id`, `status` | `enrolment_id` + `status` | 24 h |
| `quiz.published` | important | `quiz_id`, `quiz_title`, `course_code` | `quiz_id` | 24 h |
| `quiz.deadline_reminder` | urgent | `quiz_id`, `quiz_title`, `remaining`, `reminder` | `quiz_id` + `reminder` | 3 d |
| `quiz.graded` | important | `quiz_id`, `quiz_title` | `quiz_id` | 24 h |
| `game.started` | urgent | `game_id`, `quiz_title`, `course_code` | `game_id` | 6 h |
| `poll.started` | general | `poll_id`, `attendance_session_id`, `course_code` | `poll_id` | 6 h |
| `confusion.spike` | urgent | `attendance_session_id`, `spike_id`, `course_code` | session + `spike_id` | 6 h |
| `at_risk.alert` | important | `alert_id`, `course_id`, `course_code` | `alert_id` | 30 d |
| `moodle.deadline_reminder` | important | `moodle_event_id`, `title`, `course_code`, `remaining`, `reminder` | event + `reminder` | 3 d |
| `announcement.posted` | important | `announcement_id`, `title`, `message` | `announcement_id` | 24 h |
| `notification.test` | important | — (S19 test button) | fixed `test` | 1 min |

### Notification feed API (S11, Shino)

Any signed-in active user (student, lecturer, admin); only the caller's own notifications. Someone
else's (or a missing) id → 404. Item: `{id, event, priority, title, message, link, read, read_at, created_at}`.

| Endpoint | Returns |
|---|---|
| `GET /notifications?limit=20&cursor=` | `{items, next_cursor, unread_count}`: newest first (`created_at`, then `id`); `limit` 1–100; pass `next_cursor` back for older items, `null` = last page; bad cursor → 422 |
| `GET /notifications/priority` | `{items, unread_count}`: unread urgent first, then important, newest first within each, at most 50 (FR-208) |
| `POST /notifications/{id}/read` | `{notification, unread_count}`; idempotent, keeps the first `read_at` |
| `POST /notifications/read-all` | `{marked, unread_count}` |
| `POST /notifications/test` | `{sent}` (S19): sends the caller a `notification.test` (important, no link) that goes out like a real one (feed, live, push, email); `sent: false` when one was sent in the last minute |

**Apps (S19).** Both apps show a bell with `unread_count` on Home/Dashboard, a feed screen and a
preferences screen. They keep one `WS /notifications/ws` open while signed in and re-read the first
page on every `connected`. Links they open: student `/attendance/sessions/{id}`, `/profile/face`,
`/home`; lecturer `/attendance/sessions/{id}`, `/face-verification`, `/analytics/courses/{id}`,
`/home`. Other links (quizzes, games, interaction, announcements) open nothing yet; the feed item
shows the full text. The phone apps register the Expo push token after sign-in (`POST
/me/push-tokens`) and delete it on sign-out, in development/store builds with an EAS `projectId`
only (Expo Go on Android has no remote push since SDK 53; the browser never registers).

### Live notifications (S12, Shino)

`WS /notifications/ws?token=<access JWT>` — any active user, own notifications only (FR-213). A
missing, bad, expired or refresh token, a role that doesn't match the user, or an inactive user:
the socket is accepted and closed with **1008**. Messages (server → client; client text is ignored):

- `{type:"connected", unread_count}` — once, on connect.
- `{type:"notification", notification:<feed item>, unread_count}` — each new notification, sent to
  every open connection of the recipient only, after `notify.emit` has committed it.
- `{type:"unread_count", unread_count}` — after a read / read-all that changed something.

Nothing is queued or replayed for closed connections: on (re)connect the client re-reads
`GET /notifications`. The hub lives in the API process (single uvicorn worker).

### Push tokens and Expo push (S13, Shino)

- `POST /me/push-tokens {token, platform}` — any signed-in active user (FR-212). `token` must be an
  Expo push token (`ExponentPushToken[...]` / `ExpoPushToken[...]`), `platform` `android` | `ios`,
  else 422. One row per device (`m2_push_tokens.token` is unique): 201 when new, 200 when it
  already exists (refreshes `last_seen_at`; a token last used by another account moves to the caller).
  Returns `{token, platform, created_at, last_seen_at}`.
- `DELETE /me/push-tokens/{token}` (URL-encode the brackets) — on logout. 204; someone else's or an
  unknown token → 404.
- After `notify.emit` commits, **urgent and important** notifications are sent through the Expo Push
  API (`EXPO_PUSH_URL`) in a background task, in batches of ≤100, to the recipients' tokens whose
  platform is in `PUSH_PLATFORMS` (default `android`; FR-210: iOS gets in-app + email). General ones
  are pushed only to users who turned general push on (S15). Message: `title`, `body`, `data:{notification_id, event, priority, link}`.
  `DeviceNotRegistered` deletes the token; network/HTTP failures are logged and dropped (no retry).
  Config: `EXPO_ACCESS_TOKEN` (optional bearer), `EXPO_PUSH_TIMEOUT_SECONDS`, `PUSH_ENABLED`.

### Email for urgent/important (S14, Shino)

- After `notify.emit` commits, **urgent and important** notifications are emailed (FR-211) in a
  background task (`app/services/notifications/mailer.py`, stdlib `smtplib` in a thread) to the
  recipient's `users.email`; inactive users are skipped; general ones only to users who turned
  general email on (S15). Off while
  `SMTP_HOST` is empty. Subject `[SmartClass] <title>` (`[SmartClass] Urgent: <title>` for urgent;
  CR/LF stripped), body = message + the link when `EMAIL_LINK_BASE_URL` is set.
- Temporary failures (disconnect, timeout, 4xx) are retried at most `EMAIL_MAX_RETRIES` times per
  send (delay `EMAIL_RETRY_DELAY_SECONDS`, doubling); a 5xx recipient rejection drops only that
  message; a login/sender failure stops the send. Logs hold counts and exception names only.
- Config: `SMTP_HOST`, `SMTP_PORT` (587), `SMTP_SECURITY` (`starttls` | `ssl` | `none`),
  `SMTP_USERNAME` (empty = no login), `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_TIMEOUT_SECONDS`.

### Preferences and retention (S15, Shino)

- `GET /me/notification-preferences` — any signed-in active user (FR-214). Returns
  `{push:{urgent,important,general}, email:{urgent,important,general}}`; `urgent`/`important` are
  always `true`; `general` defaults to `false` (FR-210/FR-211 send only urgent/important by default).
- `PUT /me/notification-preferences` — same shape, every key optional (omitted = unchanged), strict
  booleans, unknown keys → 422. `urgent`/`important` set to `false` → **422** (nothing saved). Turning
  `general` on makes general notifications go out on that channel too; off stops them.
  Stored in `m2_notification_preferences` (one row per user, no row = defaults).
- Retention (FR-218): a daily job (`services/notifications/retention.py`, started in `main.py`)
  deletes notifications older than `NOTIFICATION_RETENTION_DAYS` (default 90), read or not.
  `NOTIFICATION_RETENTION_INTERVAL_SECONDS` (default 86400; ≤ 0 turns the job off); a retention of
  ≤ 0 days deletes nothing.

### Moodle announcements and deadlines snapshot (S16, Shino)

- **M1 hook (additive):** `moodle_auth.MoodleProfile.moodle_token` (repr-hidden) carries the user's
  own token out of `authenticate`; `POST /auth/moodle-login` calls
  `services/dashboard/moodle_snapshot.refresh_on_login(user_id, profile)` once after its commit, which
  clears the token from the profile. It never raises, so login never fails because of it (FR-203).
- With that token only (never the service token; no token → nothing fetched) it reads the news
  forums' discussions (`mod_forum_get_forums_by_courses`, `mod_forum_get_forum_discussions`) and
  course calendar events from now to `MOODLE_SNAPSHOT_DEADLINE_DAYS` ahead
  (`core_calendar_get_calendar_events`; these three are in the `smartclass` service allowlist in
  `backend/moodle/scripts/configure_moodle.php`; real SPeCTRUM needs the same).
- Saved all at once in `m2_moodle_snapshot` (one row per user: `announcements`, `deadlines` JSON
  lists, `refreshed_at` naive MYT). Any error, Moodle warning, bad shape or timeout
  (`MOODLE_SNAPSHOT_TIMEOUT_SECONDS`, default 8) keeps the previous row. Course syncs never refresh it.
- Item: `{course_id (Moodle id), course_code, course_name, id, title (plain text), date (ISO with
  +08:00), link}`; deadlines also `type` (e.g. `assign`, may be null). Announcements newest first,
  deadlines soonest first, each capped at `MOODLE_SNAPSHOT_MAX_ITEMS` (30). Links use
  `MOODLE_PUBLIC_URL` (empty = `MOODLE_URL`).
- Read: `await moodle_snapshot.get_snapshot(db, user_id)` → `{announcements, deadlines, refreshed_at}`
  or `None` (no successful refresh yet). No endpoint yet (S18 dashboard).

### Lecturer announcements (S17, Shino)

- `POST /lecturer/classes/{occurrence_id}/announcements` `{title, message, post_to_moodle=false}` →
  201 `AnnouncementOut`. Teaching lecturer only (403 otherwise, also for an unknown class). Title one
  line, 1–200 chars; message 1–1000 chars, line breaks kept; extra fields → 422.
- Notifies the class's active enrolled students with `announcement.posted` (important), the
  lecturer's title/message in full, link `/announcements/{id}`; audit `ANNOUNCEMENT_SEND`.
- `post_to_moodle`: queued in `m2_announcements` (`moodle_status` `not_requested | pending | posted |
  failed`). One try in the background after commit, then `announcement_moodle_loop` retries after
  `ANNOUNCEMENT_MOODLE_RETRY_BASE_SECONDS` (30) doubling up to `..._RETRY_MAX_SECONDS` (1800), at most
  `ANNOUNCEMENT_MOODLE_MAX_ATTEMPTS` (5) tries, then `failed`. Without `MOODLE_TOKEN` or with
  `ANNOUNCEMENT_MOODLE_INTERVAL_SECONDS <= 0` the first failure is final.
- Posted with the **service token** (`mod_forum_add_discussion` to the course's news forum, added to
  the `smartclass` allowlist in `configure_moodle.php`; real SPeCTRUM needs it too), so Moodle shows
  the service account as author; the message names the lecturer and ends with the marker
  `(SmartClass announcement #<id>)`, which a retry looks for first so a lost reply isn't posted twice.
- `GET /lecturer/classes/{occurrence_id}/announcements` → newest first: `{id, occurrence_id,
  course_code, title, message, author_name, recipient_count, created_at, moodle: {status, attempts,
  last_attempt_at, next_try_at, error, discussion_id, link, posted_at}}`.

### Dashboard reads (S18, Shino)

- `GET /student/me/dashboard` (student only) → `{date, today_classes[], attendance_rates[], moodle,
  priority_notifications[], unread_count, live_activity}`.
  - `today_classes`: the student's classes with a weekly slot today or a session dated today (MYT),
    earliest first: `{occurrence_id, course_id, course_code, course_name, class_type, class_label, room,
    start_time, end_time ("HH:MM", the session's times, else the slot), session_id, session_status
    (open | closed | needs_confirmation | null), attendance_status}`. `attendance_status` is
    `present | late | excused | absent`, `not_recorded` while the session is open and the student
    wasn't seen yet, or `null` (no session yet, or `needs_confirmation`). Several sessions on one day:
    the open one, else the latest.
  - `attendance_rates`: `attendance_read.student_rates` per course `{course_id, course_code,
    course_name, present, late, excused, absent, closed_sessions, rate}` (rate `null` when nothing counts).
  - `moodle`: the S16 snapshot `{announcements, deadlines, refreshed_at}`; empty lists and
    `refreshed_at: null` before the first successful refresh.
- `GET /lecturer/dashboard` (lecturer only) → `{date, today_classes[], attendance_overview,
  priority_notifications[], unread_count, participation, quizzes, at_risk_alerts}`.
  - `today_classes`: as above for the classes the lecturer is assigned to, without `attendance_status`.
  - `attendance_overview`: the newest **open** session of the lecturer's classes, else the newest
    **closed** one, else `null`: `{session_id, occurrence_id, course_id, course_code, course_name,
    class_type, class_label, session_status, date, starts_at, enrolled, present, late, excused, absent,
    not_recorded, rate}`. Open: counts from M3's `session_service.get_session_counts` (`absent` = marked
    absent, `not_recorded` = not seen yet, `rate` null). Closed: counts from `attendance_read.course_records`
    for that session (`not_recorded` 0, rate as FR-308).
- Both: `priority_notifications` = unread urgent then important (S11 `GET /notifications/priority`),
  `unread_count` = all unread. `live_activity`, `participation`, `quizzes`, `at_risk_alerts` are always
  present and `null` until S80 fills them from M5/M6/M7.

### Live channels (until M2)

The apps can also listen on WebSockets directly:

- Lecturers: `/ws/sessions/{id}?token=<access JWT>` — the session's live feed (`attendance_update`,
  `attendance_flagged`, `attendance_flag_resolved`, `session_closed`, ...). Only the lecturer who
  teaches the class may connect.
- Students: `/ws/me?token=<access JWT>` — the student's own events (`connected`,
  `attendance_recorded`, `attendance_flag_resolved`). Only an active student may connect; anyone
  else is closed with code 1008.

## Module 5 — Classroom interaction session (S30, Shino)

Keyed to M3's class session (`attendance_session_id`); M5 never opens, extends or closes it and no
M3 code calls M5. Table `m5_interaction_sessions` (one row per class session: `status` open|closed,
`closed_reason` lecturer|class_ended, opened/closed times).

- **Effective state:** open only while the class session is `open` and the lecturer hasn't closed
  it early. A running class with no row counts as open (default on). `scheduled` → closed
  `not_started`; `closed`/`needs_confirmation`/`cancelled` → closed `class_ended` at once.
- `GET /interaction/{attendance_session_id}` (lecturer or student) → `{attendance_session_id,
  occurrence_id, course_code, course_name, class_status, status, closed_reason, opened_at,
  closed_at, role}`. Joining a running class creates its row.
- `POST /lecturer/interaction/{id}/close` (early close, class keeps running; idempotent; audited
  `INTERACTION_CLOSED`) and `POST /lecturer/interaction/{id}/open` (reopen; 409 once the class isn't
  open; audited `INTERACTION_OPENED`). Same response.
- **Access:** the lecturer assigned to the class (or, for a session without a class, the lecturer
  who ran it) and active students enrolled in it; anyone else and unknown ids → 403.
- **Writes (S31–S33):** call `app.services.interaction.sessions.require_open(db, id)` first. It
  share-locks the class session row and the interaction row for the transaction (M3's close and the
  lecturer's close wait for the write) and raises 409 `Interaction is closed`.
- **Sweep:** `interaction_sweep_loop` (main.py) every `INTERACTION_SWEEP_SECONDS` (default 10; ≤ 0
  off) marks rows of ended classes `closed/class_ended`; `sessions.on_closed` listeners
  (`async (attendance_session_id)`) run after the commit of a sweep or a lecturer close (S35 sends
  the websocket `closed` event from there).

### Live questions (S31, FR-503–FR-506)

Tables `m5_questions` (session, asker `student_id`, text ≤ 500, anonymous, answered_at, pinned,
hidden, created_at) and `m5_question_votes` (one per question and student). The asker is stored
even when anonymous (class totals, FR-713) but never leaves the service for an anonymous question.

- `GET /interaction/{id}/questions` (lecturer or student) → `{attendance_session_id, status,
  questions: [QuestionOut]}`, pinned first, then most upvotes, then oldest. Students never get
  hidden questions; the lecturer gets them with `hidden: true`. Works after the class too.
- `QuestionOut`: `{id, attendance_session_id, text, anonymous, author_name, mine, upvotes,
  upvoted_by_me, answered, answered_at, pinned, hidden, created_at}`. No student/user id ever;
  `author_name` is null for anonymous questions; `mine` is true only for the asker.
- `POST /interaction/{id}/questions {text, anonymous}` (students only, 201). `POST
  /interaction/{id}/questions/{qid}/upvote` (students; a repeat is a no-op; own question 409;
  hidden or other session 404).
- `PATCH /lecturer/interaction/{id}/questions/{qid} {answered?, pinned?, hidden?}`. Hide/unhide
  audited `INTERACTION_QUESTION_HIDDEN|UNHIDDEN` (target `m5_question`, values `{hidden}` only).
- Every write calls `require_open` (409 when the interaction is closed).

### Live polls (S32, FR-507–FR-509)

Tables `m5_polls` (session, question ≤ 300, multiple, status draft|open|closed, show_results,
created_by, created/started/closed times), `m5_poll_options` (2–6 per poll, text ≤ 120, position)
and `m5_poll_votes` (one row per chosen option; a student's vote is replaced as a whole).

- `GET /interaction/{id}/polls` (lecturer or student) → `{attendance_session_id, status, polls:
  [PollOut]}`, newest first. Students never get drafts. Works after the class too.
- `PollOut`: `{id, attendance_session_id, question, multiple, status, show_results, options: [{id,
  text, votes}], total_voters, my_option_ids, created_at, started_at, closed_at}`. `votes` and
  `total_voters` are always set for the lecturer and are `null` for students unless `show_results`
  is on. `my_option_ids` is the caller's own vote ([] for the lecturer). No response says who voted.
  `status` reads `closed` for an open poll while the interaction is closed.
- Lecturer: `POST /lecturer/interaction/{id}/polls {question, options[2..6], multiple?,
  show_results?}` (201, draft; distinct options); `POST .../polls/{pid}/start` (draft only, else
  409; sends `poll.started` to the active enrolled students after commit); `POST
  .../polls/{pid}/close` (idempotent; a draft → 409); `PATCH .../polls/{pid} {show_results}`.
- Student: `POST /interaction/{id}/polls/{pid}/vote {option_ids}` replaces their vote while the poll
  is open (single choice: exactly one; duplicates or another poll's option → 422; draft → 404;
  closed poll → 409).
- Every write calls `require_open` (409 when the interaction is closed). Votes are logged in
  `m5_events` (S34); the websocket for live results is S35.

### Quick questions, reactions and confusion (S33, FR-510–FR-515)

Tables `m5_quick_questions` (session, prompt ≤ 300, max_chars 1–500, status open|closed,
created_by, created/closed times), `m5_quick_answers` (one per student per quick question, text ≤
max_chars, replaced while open), `m5_reactions` (session, student, kind, time),
`m5_confusion_presses` (session, student, optional topic ≤ 60, time) and `m5_confusion_spikes`
(session, started_at, last_at, peak_students, class_size). Student ids are stored for M7 (S34) but
never returned.

- Quick questions: `GET /interaction/{id}/quick-questions` → `{attendance_session_id, status,
  quick_questions: [{id, attendance_session_id, prompt, max_chars, status, answer_count, answers:
  [{id, text, created_at}], my_answer, created_at, closed_at}]}`, newest first. The lecturer gets
  every answer with no names; students get `answers`/`answer_count` = null and only their own
  `my_answer`. Lecturer: `POST /lecturer/interaction/{id}/quick-questions {prompt, max_chars?}`
  (201, open at once; default `INTERACTION_QUICK_ANSWER_DEFAULT_CHARS` = 140), `POST
  .../quick-questions/{qid}/close` (idempotent). Student: `POST
  /interaction/{id}/quick-questions/{qid}/answer {text}` (over max_chars → 422, closed → 409).
- Reactions: student `POST /interaction/{id}/reactions {kind: thumbs_up|clear|too_fast|too_slow}`
  → 201 `{kind, created_at, next_allowed_at}`; one per `INTERACTION_REACTION_COOLDOWN_SECONDS` (5)
  per student, else 429 with `Retry-After`. Lecturer `GET /lecturer/interaction/{id}/reactions` →
  `{attendance_session_id, status, counts: {kind: n}, total}`.
- Confusion: student `POST /interaction/{id}/confusion {topic?}` → 201 `{created_at,
  next_allowed_at}`; one per `INTERACTION_CONFUSION_COOLDOWN_SECONDS` (120) per student, else 429
  with `Retry-After`. Lecturer `GET /lecturer/interaction/{id}/confusion` → `{attendance_session_id,
  status, total, recent, recent_students, class_size, window_seconds, spike_active, spikes, timeline:
  [{start, count}], topics: [{topic, count}]}` (aggregates only, FR-515; buckets of
  `INTERACTION_CONFUSION_BUCKET_SECONDS` = 60).
- Spike (FR-514): after each press, if the distinct students pressing in the last
  `INTERACTION_CONFUSION_WINDOW_SECONDS` (120) reach `ceil(INTERACTION_CONFUSION_SPIKE_SHARE` (0.25)
  `× active enrolled students)`, a spike starts and `confusion.spike` (urgent, subject
  `spike:{session}:{spike_id}`) goes to the class session's lecturer after commit. Presses at/above
  the threshold within a window of the spike's `last_at` extend it (no new notification); a new spike
  needs a whole window without one. Presses are serialised per class session.
- Every write calls `require_open` (409 when the interaction is closed); the GETs work after class.

### Interaction event log and M7 read interface (S34, FR-513, FR-517, FR-713)

Table `m5_events` (session, `student_id`, `type`, `ref_id`, `anonymous`, `created_at`): one row per
student action, written in the same transaction as the action (`app.services.interaction.events.record`).
Types: `question_asked` (ref = question, `anonymous` copied), `question_upvoted` (ref = question; a
repeat upvote adds nothing), `poll_voted` (ref = poll; every change of vote), `quick_answered` (ref =
quick question; every replacement), `reaction`, `confusion`. Rejected actions (403/409/422/429) leave
no row. The migration backfilled rows from the S31–S33 tables.

M7 reads it only through `app/services/interaction_read.py` (read only, no permission checks: the
caller checks NFR-04 first; frozen dataclasses, fields only ever added). Nothing is graded.

| Function | Arguments | Returns |
|---|---|---|
| `course_student_counts` | `db, course_id, from_date=None, to_date=None` | `list[StudentInteractionCounts]`, one per student enrolled in any class of the course (zeros kept), by matric no |
| `student_counts` | `db, student_id, course_id=None, from_date=None, to_date=None` | one per course the student is enrolled in, by course code |
| `session_student_counts` | `db, attendance_session_id` | one per student enrolled in that session's class |
| `course_session_totals` | `db, course_id, from_date=None, to_date=None` | `list[SessionInteractionTotals]`, every session of the course, oldest first |
| `session_totals` | `db, attendance_session_id` | `SessionInteractionTotals` or `None` |

- `StudentInteractionCounts`: `student_id, matric_no, name, course_id, course_code, sessions_active,
  polls_answered` (distinct polls), `questions` (named only), `upvotes, quick_answers` (distinct quick
  questions), `reactions, confusion`. **Anonymous questions are never in a per-student figure** and
  don't make a student `sessions_active` (FR-713).
- `SessionInteractionTotals`: `session_id, occurrence_id, course_id, course_code, date, polls_run`
  (non-draft polls), `poll_answers` (distinct poll × student), `questions` (anonymous included),
  `anonymous_questions, upvotes, quick_answers` (distinct), `reactions, confusion, participants`
  (distinct students, anonymous askers included). No identity fields.
- Dates are the MYT class date (`class_date`, else opened/starts date), inclusive; `from_date >
  to_date` raises `ValueError`. Sessions of any status count. Unknown ids → `[]` / `None`.
- FR-702 "participation frequency" is for M7 to combine (e.g. polls_answered + questions + reactions).

### Interaction websocket (S35, FR-516)

`WS /interaction/{attendance_session_id}/ws?token=<access JWT>` for the teaching lecturer and
enrolled active students (same access as `GET /interaction/{id}`). The server accepts, then closes
with 1008 for a bad/expired/refresh token, another role (admin), an inactive user, no access or an
unknown id. Client text is ignored. Hub: `app/services/interaction/live.py` (one API worker).

- `{"type":"connected", ...}` once: the `GET /interaction/{id}` body (`status`, `closed_reason`,
  `class_status`, `role`, ...). If the class isn't running (`class_status != "open"`) it is
  followed by `closed` and the socket is closed (1000).
- `{"type":"changed","topic":T}` after the commit of a change; the client re-reads that topic with
  the REST GETs (which shape data per role). Messages carry **no ids, names, text or counts**, so
  students never learn identities, hidden questions, drafts or others' answers. One message per
  topic per transaction. Rejected writes (403/404/409/422/429) and no-op repeats send nothing.

  | Topic and change | Lecturer | Students |
  |---|---|---|
  | `questions`: ask, new upvote, moderate | yes | yes |
  | `polls`: create (draft), show_results on a draft | yes | no |
  | `polls`: start, close, show_results change | yes | yes |
  | `polls`: vote | yes | only while `show_results` is on |
  | `quick_questions`: ask, close | yes | yes |
  | `quick_questions`: answer | yes | no |
  | `reactions`, `confusion` | yes | no |
- `{"type":"opened"}` after the lecturer reopens; `{"type":"closed","reason":"lecturer"|"class_ended"}`
  after an early close (the socket stays open) or the class ending (sent by the sweep within
  `INTERACTION_SWEEP_SECONDS`, then the server closes the socket with 1000).
  A class that ends after the lecturer's early close also gets `closed/class_ended` + 1000 (each
  sweep checks the connected class sessions).
- Nothing is replayed: on (re)connect the client re-reads every list after `connected`. The socket
  is registered just before `connected` is sent, so a `changed` can arrive first; treat it like any
  other (the re-read after `connected` covers it).
- Python: `live.changed(db, attendance_session_id, topic, students=True)` queues a message for after
  the commit (reactions/confusion always lecturer-only); `sessions.open_interaction` now returns
  `True` when it reopened.

### After class: summary, CSV, my questions (S36, FR-518–FR-520)

Read only (`app/services/interaction/summary.py`); no schema change. Both lecturer routes need the
teaching lecturer (403 otherwise, unknown id 403) and work while the class runs too.

- `GET /lecturer/interaction/{id}/summary` → `{attendance_session_id, course_code, course_name,
  class_date, class_status, status, question_counts: {asked, answered, anonymous, hidden, upvotes},
  questions: [QuestionOut] (lecturer view: anonymous → author_name null, hidden flagged), polls:
  [PollOut] (drafts left out, counts always set), quick_questions: [{id, prompt, status,
  answer_count, answers: [{id, text, created_at}], created_at}], reactions: {kind: n},
  reactions_total, confusion: {total, spikes, timeline: [{start, count}], topics: [{topic, count}]}}`.
  No student/user id anywhere; only named questions carry a name.
- `GET /lecturer/interaction/{id}/summary.csv` → `text/csv` attachment
  `interaction_<course>_<yyyymmdd>_<id>.csv`, columns `Section, Time, Text, Author, Status, Count`.
  Sections: `Class`, `Questions asked|answered`, `Anonymous questions`, `Question` (Author is the
  name or `Anonymous`; Status `answered|unanswered[, pinned][, hidden]`; Count = upvotes), `Poll` +
  `Poll option`, `Quick question` + `Quick answer` (no author), `Reaction`, `Confusion presses|spikes`,
  `Confusion` (timeline bucket), `Confusion topic`. Text cells starting with `= + - @`, tab or CR get
  a leading `'`.
- `GET /student/me/questions?attendance_session_id=&limit=50&before=` (students) → `{questions:
  [{id, attendance_session_id, occurrence_id, course_code, course_name, class_date, text, anonymous,
  upvotes, answered, answered_at, created_at}], next_before}`: the caller's own questions across
  every class session, newest first (by id), anonymous ones included (they're the asker's own),
  hidden ones left out. `limit` 1–200; pass `next_before` as `before` for the next page.
