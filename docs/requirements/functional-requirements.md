# Functional Requirements

**Project:** Smart Classroom Management System (SmartClass) — UM FYP
**Source of scope:** `docs/private/PROJECT PROPOSAL PAPER.pdf` (local only, git-ignored) (revised scope, Nov 2026)
**Module ownership:** M1, M3, M4, M8 → Yong Yew Sing | M2, M5, M6, M7 → Chow Shino
**Last revised:** 2026-11-19

IDs are numbered per module: `FR-1xx` = Module 1, `FR-3xx` = Module 3, and so on.
Priorities use MoSCoW. **Deferred** = in scope of the proposal but blocked on another module; not built until that module exists.

---

## Context: SPeCTRUM (Moodle) integration

UM's LMS, SPeCTRUM, runs on Moodle. Real SPeCTRUM signs users in with Microsoft 365 SSO and gets enrolments from MAYA. SmartClass can't get web-service access to the real SPeCTRUM, so it uses a **local Moodle 4.5 instance that simulates SPeCTRUM** (`backend/moodle/`). Moodle is the source of truth for:

- user accounts (students and lecturers) and their credentials,
- courses, enrolments and lecturer assignments,
- course materials uploaded by lecturers,
- the official attendance record (Moodle Attendance plugin, `mod_attendance`).

Every SmartClass feature runs in SmartClass. Moodle is only the source of data and the place finalised attendance is copied to.

---

## Module 1 — User Management (Owner: Yew Sing)

### 1A. Authentication and accounts

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-101 | The system shall authenticate students and lecturers with their SPeCTRUM (Moodle) username and password through Moodle's token-based web-service login. SmartClass shall never store the Moodle password. | Must Have | Student, Lecturer |
| FR-102 | The system shall create a SmartClass account automatically on a user's first successful Moodle login. The role (student or lecturer) shall be derived from the user's Moodle course roles. | Must Have | System |
| FR-103 | The system shall authenticate administrators with a local email and password, independent of Moodle, in the web app only. The phone apps have no administrator sign-in. | Must Have | Admin |
| FR-104 | The system shall retrieve courses, student enrolments and lecturer assignments from Moodle on login and on a manual or scheduled sync, and shall reflect enrolments added or removed in Moodle. Class lists shall not be maintained separately in SmartClass. | Must Have | System |
| FR-105 | The system shall enforce role-based access control with three roles (Student, Lecturer, Administrator), so each user can only reach the functions and data their role permits. | Must Have | System |
| FR-106 | The system shall issue a short-lived access token and a refresh token after login, and shall support logout. | Must Have | System |
| FR-107 | The system shall let users view their profile: name, matric/staff number, email, faculty and enrolled or taught courses. Moodle-sourced fields are read-only. | Should Have | All |
| FR-108 | The system shall let administrators view all accounts, deactivate or reactivate an account, and create other administrator accounts. | Should Have | Admin |

### 1B. Face data registration (self-enrolment with student-card verification)

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-109 | The system shall require a student to accept a PDPA consent notice in the mobile app before any face data is captured, and shall record the consent version and timestamp. | Must Have | Student |
| FR-110 | The system shall let a student self-enrol their face in the mobile app by taking guided selfies (several angles) and a photo of their UM matric card. | Must Have | Student |
| FR-111 | The system shall automatically verify a submission by (a) comparing the face on the matric card with the selfies against a similarity threshold, and (b) reading the matric number (and name) from the card with OCR and checking it matches the logged-in student's account. | Must Have | System |
| FR-112 | The system shall approve the submission automatically when both checks in FR-111 pass, and shall then register the face embeddings for attendance recognition. | Must Have | System |
| FR-113 | When either check in FR-111 fails, the system shall place the submission in a verification queue for lecturers of the student's courses, showing the selfie and the card side by side with the OCR result and similarity score. The lecturer shall approve or reject it with a reason. | Must Have | Lecturer |
| FR-114 | The system shall notify the student of the verification result and let a rejected student submit again. | Should Have | Student |
| FR-115 | The system shall show the student their face enrolment status: not enrolled, pending review, active or rejected (with reason). | Should Have | Student |
| FR-116 | The system shall let a student withdraw consent, which deletes their face embeddings. | Must Have | Student |
| FR-117 | The system shall let administrators act as a fallback: perform the lecturer review in FR-113, and reset a student's face data. | Should Have | Admin |
| FR-118 | The system shall record an audit entry for every face verification decision, consent change, account deactivation and role change. | Should Have | System |
| FR-119 | The system shall let lecturers open any class they teach and view its details and full list of enrolled students, with each student's matric number and face registration status. | Should Have | Lecturer |

---

## Module 2 — Dashboard and Notifications (Owner: Shino)

Module 2 is the app's front door and its messaging layer. Every screen that answers "what needs my attention now?" is a dashboard; every event another module raises becomes a notification here. Dashboards read through the other modules' read interfaces and never write domain data.

### 2A. Dashboards

**Student dashboard (Home tab).** Top to bottom: greeting and notification bell with unread badge; a "Live now" card when an attendance or interaction session is open for one of the student's courses; "Needs attention" (urgent then important, at most three, with "See all"); today's classes with the student's attendance state; upcoming quizzes with countdown and open/close state and assignment from Moodle; the latest three announcements; and a preview of general notifications.

**Lecturer dashboard (Home tab, phone and browser).** Top: greeting and notification bell. Then today's class cards, each with Start session / Open interaction, live Present/Late counts, End class and +15 min; "Needs attention" (at-risk alerts, short answers waiting to be scored, pending face reviews); a participation snapshot for the current class; recent quiz activity; and announcements. On web the cards use a two-column grid with the side navigation; on phone they stack in one column.

**Flow:** the dashboard loads → the server returns one role-shaped payload → the screen renders section cards in a fixed order → tapping a card deep-links to the source screen → returning refreshes the card. While loading, each section shows a skeleton; when a section has no data it shows a short empty-state message, not a blank area.

**Logic:** the dashboard is a read-only projection. Attendance counts come from M3 (FR-313), participation from M5 (FR-509), quiz activity from M6 (FR-614), at-risk flags from M7 (FR-709) and announcements from the course's Moodle announcements forum. Every query is scoped to the caller's enrolled or taught courses. Counts must agree with the screens they link to; the dashboard never recalculates a rate differently.

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-201 | The system shall provide a student dashboard that displays the student's attendance status, upcoming deadlines, latest announcements, notifications and ongoing classroom activities. It shall open the relevant screen when a card is tapped and refresh on focus. | Must Have | Student |
| FR-202 | The system shall provide a lecturer dashboard that displays an overview of class attendance, student participation, assessment activities and notifications, with start/extend/end controls for the current class. | Must Have | Lecturer |
| FR-203 | The system shall display on each dashboard only the data permitted for the user's role and enrolled or taught courses. | Must Have | System |
| FR-204 | The system shall display urgent and important notifications at the top of the dashboard, above general notifications. | Must Have | System |
| FR-213 | The system shall show loading, empty, error and offline/stale states on every dashboard section, with pull-to-refresh and a visible "as of" time when data is older than the refresh interval. | Should Have | System |
| FR-214 | The system shall deep-link every dashboard card to its source screen and return the user to the dashboard with the card refreshed when they come back. | Should Have | System |
| FR-215 | The system shall render the lecturer dashboard as a responsive layout: one column on phones and a two-column grid with side navigation in a desktop browser. | Should Have | Lecturer |
| FR-216 | The system shall show an ongoing-activity card for an open attendance or interaction session, with one tap to join, and hide it when nothing is open. | Must Have | Student |
| FR-217 | The system shall show the latest announcements from the course's Moodle announcements forum, read-only, and shall not invent announcements when the forum is unavailable. | Should Have | System |

### 2B. Notification feed

**UI:** a bell in the app header opens the Notification centre. Items are grouped Today / Earlier, with filter chips All / Unread and a "Mark all read" action. Each item shows an event icon, title, one-line body, course or class context, relative time and a priority pill. Tapping an item marks it read and opens the related screen. Unread items use a dot and a heavier title; priority is never conveyed by colour alone.

**Flow:** event raised → notification row written → unread badge increments → delivery worker handles urgent/important → user opens the centre → item read (one or all) → badge decrements on every signed-in device.

**Logic:** the feed is the durable record of every notification. Ordering is priority (urgent, important, general) then newest first. General notifications never trigger push or email. A notification is owned by exactly one user; it is never broadcast to a whole class. Read state is stored server-side, not only on the phone.

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-205 | The system shall assign each notification one of three priority levels: **urgent** (act now), **important** (act soon) or **general** (information only). The level is chosen by the producing event, not by the client. | Must Have | System |
| FR-206 | The system shall list all notifications received by a user in an in-app notification feed, ordered by priority and then by time received, with Today/Earlier grouping, All/Unread filters and pagination. | Must Have | Student, Lecturer |
| FR-218 | The system shall show an unread count on the notification bell and update it without a manual refresh when a notification arrives or is read. | Must Have | Student, Lecturer |
| FR-219 | The system shall let a user mark one notification or all notifications as read; the read state shall persist across devices and shall not delete the notification. | Must Have | Student, Lecturer |
| FR-220 | The system shall render each notification with its event icon, title, short body, course/class context, relative time and priority, and shall open the related screen when tapped. | Must Have | Student, Lecturer |
| FR-221 | The system shall map each event to a deep link: attendance events open the attendance screen, quiz events open the quiz, interaction events open the session, at-risk events open the student's analytics, and face events open the face status or review screen. | Should Have | System |
| FR-222 | The system shall collapse repeated occurrences of the same event for the same user and target within a configurable window (default 5 minutes) into one feed item with a count, so a burst of attendance records does not flood the feed. | Should Have | System |
| FR-223 | The system shall keep notifications for a configurable retention period (default 90 days) and delete older read notifications in a background job; unread counts shall always match the rows that remain. | Could Have | System |
| FR-224 | The system shall make the notification centre accessible: at least 44×44 px touch targets, screen-reader labels that include priority and course, and no meaning conveyed by colour alone. | Should Have | System |

### 2C. Delivery channels

**Logic:** urgent and important rows enter a delivery queue when written. The worker claims a row, sends the allowed channels, records `delivered_push` / `delivered_email`, and retries with exponential backoff. A failed channel never deletes the in-app row. General rows are never queued.

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-207 | The system shall send a push notification or email for each urgent and important notification within a configurable time (default 60 seconds) of the triggering event. General notifications shall appear in the notification feed only. | Must Have | System |
| FR-208 | The system shall deliver push notifications on Android devices. On iOS devices, the system shall deliver notifications in-app and by email. The lecturer web app receives in-app notifications and email. | Must Have | System |
| FR-225 | The system shall let an authenticated app register and unregister a push token per device, shall keep at most one active token per user per device, and shall remove tokens the push service reports as invalid. | Must Have | System |
| FR-226 | The system shall render email notifications from a fixed template containing the event title, body, course context, time and a link back to the app; it shall not include sensitive face images, quiz answers or other students' data. | Should Have | System |
| FR-227 | The system shall retry failed push or email deliveries with backoff, expose the delivery flags for support, and never let a delivery failure block the action that raised the event. | Should Have | System |
| FR-228 | The system shall keep a single event catalogue that defines, for each event, its audience, priority, payload and deep link; adding an event without a catalogue entry shall fail a test. | Should Have | System |

### 2D. Events raised by other modules

Producers call `notify.emit(event, user_ids, payload, priority)` after their database transaction commits. The call is best-effort: if notification storage fails, the producer logs it and the original action still succeeds.

| Event | Audience | Priority | Payload | Opens |
|-------|----------|----------|---------|-------|
| `attendance.recorded` | the student | general | course code, status (Present/Late), time | Attendance |
| `attendance.flagged` | the class lecturer | urgent | student name, course code, flag time | Live session / flags |
| `face_enrolment.result` | the student | important | status (active/rejected), reason | Face status |
| `face_enrolment.pending_review` | lecturers of the student's courses | important | student name, matric number, submission time | Face review |
| `face.unrecognised` | the class lecturer | general | course code, session time, count of unmatched faces | Live session |
| `quiz.published` | enrolled students | important | quiz title, course code, opens/closes | Quiz |
| `quiz.deadline` | enrolled students who have not submitted | important | quiz title, closes at | Quiz |
| `at_risk.flagged` | the class lecturer | important | student name, course code, condition, severity | Student analytics |

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-209 | The system shall notify a student when their attendance has been recorded (event `attendance.recorded`, FR-406). | Must Have | System |
| FR-210 | The system shall notify a lecturer when a student is identified as at-risk by Module 7 (FR-709), and shall assign the notification important priority. | Must Have | Lecturer |
| FR-211 | The system shall assign important priority to, and notify students of, newly published quizzes and upcoming quiz deadlines. | Must Have | System |
| FR-212 | The system shall notify a student of the face enrolment result (event `face_enrolment.result`, FR-114), and shall notify lecturers of pending face enrolment reviews and unrecognised faces (events `face_enrolment.pending_review` and `face.unrecognised`, FR-113 and FR-407). | Should Have | System |
| FR-229 | The system shall expose one notification entry point (`notify.emit`) that stores the in-app row first and queues delivery second; callers shall not write notification rows directly. | Must Have | System |
| FR-230 | The system shall send `attendance.flagged` as urgent because the lecturer must resolve it before the session closes (FR-318/FR-319). | Must Have | System |
| FR-231 | The system shall not notify a user about another user's private data: payloads shall carry only the minimum context needed to understand and open the notification. | Must Have | System |

---

## Module 3 — Attendance Management (Owner: Yew Sing)

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-301 | The system shall open each class's attendance session automatically at its scheduled time, starting a configurable time before the class (default 15 minutes), and close it at the scheduled end. | Must Have | System |
| FR-302 | The system shall record a student as **Present**, with a timestamp, when Module 4 submits a verified recognition for that student during an open session. If that recognition comes more than a configurable time (default 15 minutes) after the class's effective start time, the status is **Late** instead. Only the first recognition counts. | Must Have | System |
| FR-303 | The system shall mark every enrolled student without a Present or Late record as **Absent** when the session closes. | Must Have | System |
| FR-304 | The system shall use four attendance statuses: Present, Late, Excused and Absent. Excused is set only by a lecturer's override (for example, for a medical certificate). | Must Have | System |
| FR-305 | The system shall let the lecturer manually override a student's status for a session, with an optional reason. Each override shall be logged with actor, old status, new status, reason (if given) and timestamp. | Must Have | Lecturer |
| FR-306 | The system shall show the lecturer a live view of an open session: who is present or late, who is not yet recognised, and the counts. It shall update without a manual refresh. | Must Have | Lecturer |
| FR-307 | The system shall keep the attendance history of every student for every session of each course. | Must Have | System |
| FR-308 | The system shall calculate each student's attendance rate per course ((Present + Late sessions) ÷ (closed sessions − Excused sessions)), so Late counts as attended and Excused doesn't count against the student. | Must Have | System |
| FR-309 | The system shall let a student view their own attendance history and attendance rate per course. | Must Have | Student |
| FR-310 | The system shall let a lecturer generate attendance reports for a session, or for a course over a date range, and export them as CSV. | Should Have | Lecturer |
| FR-311 | The system shall copy the finalised attendance of a closed session to the matching session of the course's Moodle Attendance activity (`mod_attendance`). Failed syncs shall be retried automatically. | Must Have | System |
| FR-312 | The system shall re-sync a session to Moodle when its attendance is overridden after the first sync, and shall show the lecturer each session's sync status (pending, synced, failed). A closed or overridden session is sent at once and its new status appears on the lecturer's screen without a refresh; the queue and retries remain for when Moodle is down. | Should Have | Lecturer |
| FR-313 | The system shall expose attendance records and rates through an internal read interface for Module 7 (Learning Analytics). | Must Have | System |
| FR-314 | The system shall export attendance reports as PDF. | Could Have | Lecturer |
| FR-315 | The system shall let a lecturer set the weekly schedule (day, time, room) of the classes they teach. Moodle doesn't supply a timetable, so the schedule is kept in SmartClass. | Must Have | Lecturer |
| FR-316 | The system shall let the lecturer start a class now, extend it, or end it early. These actions are audited and don't alter the weekly schedule. A change to the weekly schedule applies from the next class (at most one scheduled session per class per day); Start now covers an extra class. A class that didn't happen is confirmed "Not held" (FR-317). (Changing or cancelling one class was removed by Yew Sing on 2026-11-12.) | Must Have | Lecturer |
| FR-317 | When a session reaches its end with no recognitions and no lecturer action, the system shall not mark anyone Absent or sync to Moodle until the lecturer confirms whether the class was held. | Must Have | System, Lecturer |
| FR-318 | The system shall let an enrolled student with no attendance record flag in the app, during an open session, that they are in class but weren't recognised, and shall alert the lecturer in the app. | Must Have | Student |
| FR-319 | The system shall let the lecturer confirm a flag, recording Present or Late from the flag time, or reject it with a reason. The decision is audited and shown to the student. An unresolved flag leaves the student Absent and stays in the lecturer's list. | Must Have | Lecturer |
| FR-320 | The system shall compare synced sessions with Moodle and never silently overwrite a status changed there. It shall show the lecturer both values and let them choose. Student self-marking in Moodle stays off for these sessions. | Should Have | Lecturer |

---

## Module 4 — Facial Recognition Attendance Verification (Owner: Yew Sing)

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-401 | The system shall use a Raspberry Pi with a camera module at the classroom entrance, which captures frames only while an attendance session is open for its room. | Must Have | System |
| FR-402 | The Raspberry Pi shall detect faces locally and send only the cropped face images to the backend over an authenticated connection (per-device key). | Must Have | System |
| FR-403 | The backend shall extract a face embedding from each crop and match it against the registered embeddings of students enrolled in the session's course, accepting a match only at or above a configurable similarity threshold. | Must Have | System |
| FR-404 | The system shall confirm a student only after they are matched consistently across a configurable number of consecutive frames (default 3). | Must Have | System |
| FR-405 | The system shall submit each confirmed recognition, with timestamp and device ID, to Module 3 to record attendance. | Must Have | System |
| FR-406 | The system shall give feedback on recognition: the student is told on their phone that attendance was recorded, and the lecturer's live session view shows them as present or late. | Must Have | Student, Lecturer |
| FR-407 | The system shall keep faces that are detected but not matched as supporting evidence, not as a task for the lecturer. When a student flags (FR-318), the lecturer sees the closest unmatched face with its similarity. Lecturers are never asked to identify a face from memory. | Must Have | Lecturer |
| FR-408 | The system shall let administrators register camera devices, assign each to a room, and regenerate a device's key. Each device's online or offline status (heartbeat) shall be shown. | Should Have | Admin |
| FR-409 | The system shall support a USB webcam (Logitech) on a laptop as a backup capture device, using the same pipeline. | Should Have | System |
| FR-410 | The system shall delete unrecognised-face crops once they are resolved, or after a retention period. | Should Have | System |
| FR-411 | The Raspberry Pi shall buffer crops while the backend is unreachable and send them, with original timestamps, when the connection returns. | Could Have | System |

---

## Module 5 — Classroom Interaction (Owner: Shino)

All interactions in this module are non-graded. Graded assessments are handled by Module 6.

**UI map.**
- **Student:** Home shows a "Live now" card for any open session in an enrolled course; the Participation tab lists open sessions when opened cold. The in-session screen uses one tinted section card per activity: Live question, Live poll, React, Ask a question and the session question feed. A closed session becomes a read-only summary.
- **Lecturer:** Home owns opening and ending the session for the current class (Start/Open, +15 min, End class). The Interaction tab lists all sessions (Open first, then newest) and opens the live control screen. The control screen shows a live pulse, unanswered-question count, the latest question/poll/live question inline, and a "See all" bottom sheet for the full history.

**Flow.**
1. The lecturer opens the class session (or opens an interaction session directly); the server creates or reuses today's session and broadcasts `interaction_opened`.
2. Enrolled students see the live card and join; the screen loads the whole session state in one request.
3. The lecturer posts a live question or a poll; students answer or vote; the lecturer watches counts update.
4. Students ask named or anonymous questions; the lecturer marks each answered.
5. Students react or press "I Don't Understand"; the lecturer sees distinct-student counts, not click counts.
6. The lecturer closes voting, then ends the session (or the scheduler closes it at `ends_at`); the screen switches to the read-only summary.

**Logic.**
- A session belongs to one class occurrence and one lecturer. Only the lecturer who opened it may close it. Opening a new session closes the lecturer's other live sessions, so one lecturer has at most one live session.
- An interaction session may share its lifecycle with the attendance session of the same class time: ending the class ends both, and +15 min extends both. `ends_at` is the single source of truth for "live"; the scheduler closes expired sessions and their open polls.
- Writes are accepted only while the session is open and only from students enrolled in the course. Closed sessions are read-only.
- Every write stores session, student and timestamp for Module 7. Anonymous identity is stored for counting but stripped from every lecturer and student response.
- A student has at most one vote per poll, one response per live question, one current reaction per session and one IDU signal per session; reacting or pressing IDU again cancels it.
- Live updates use a websocket room per session, broadcast after commit. If the socket drops, the screen reconnects and refetches; it never relies on the socket for correctness.

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-501 | The system shall allow a lecturer to open and close an interaction session for a scheduled class of a course they teach. Students enrolled in the course shall be able to participate only while the session is open. Opening a new session shall close the lecturer's other live sessions. | Must Have | Lecturer |
| FR-502 | The system shall allow a student to submit a question during an open interaction session, with an option to submit it anonymously. The system shall not display the identity of an anonymous student to the lecturer or other students. | Must Have | Student |
| FR-503 | The system shall display submitted questions to the lecturer in real time and shall allow the lecturer to mark each question as answered. | Must Have | Lecturer |
| FR-504 | The system shall allow a lecturer to create a live poll with a question and two or more answer options, and to open and close voting. At most one poll per session shall be open at a time. | Must Have | Lecturer |
| FR-505 | The system shall allow each enrolled student to vote once per poll while it is open, and shall display the poll results to the lecturer in real time. A student shall see the running totals after voting, not before. | Must Have | Student |
| FR-506 | The system shall allow a lecturer to post one active live question to the class and shall display students' responses to the lecturer in real time. Posting a new live question shall close the previous one. | Should Have | Lecturer |
| FR-507 | The system shall allow a student to send a reaction (from a predefined set) during an open session, and shall display the reaction counts to the lecturer in real time. Tapping the same reaction again shall cancel it. | Should Have | Student |
| FR-508 | The system shall provide an "I Don't Understand" button that a student can select during an open session, and shall display the number of distinct students who selected it to the lecturer in real time. Tapping again shall cancel the signal. | Must Have | Student |
| FR-509 | The system shall record every question, poll vote, response, reaction and "I Don't Understand" signal with the session, student and timestamp, for use by Module 7. The system shall retain the student's identity for anonymous questions for counting purposes only. | Must Have | System |
| FR-510 | The system shall show a session's state (Open/Live, Closed, auto-closed) with a countdown to `ends_at`, and shall disable every write control when the session is closed. | Must Have | Student, Lecturer |
| FR-511 | The system shall keep each activity in its own section card, show only the most recent item inline, and put the full history in a "See all" bottom sheet, so the main controls stay visible when a session is busy. | Should Have | Student, Lecturer |
| FR-512 | The system shall reject duplicate writes (second vote, second response, repeated IDU) with a clear message, and shall rate-limit question submission to protect the live session. | Should Have | System |
| FR-513 | The system shall provide an end-of-session summary to the lecturer: questions asked and answered, poll participation, live-question response count, reaction counts and distinct IDU students. Students shall see a read-only version of the same summary after the session closes. | Should Have | Lecturer, Student |
| FR-514 | The system shall show a connection banner when live updates are unavailable, keep the last loaded state readable, and offer retry instead of a blank screen. | Should Have | Student, Lecturer |
| FR-515 | The system shall guarantee anonymity end to end: an anonymous question's student identity shall never appear in a lecturer response, a student feed, a log line or an export; only aggregate counts may use it. | Must Have | System |
| FR-516 | The system shall keep a closed session readable to enrolled students for a configurable period (default 7 days) while rejecting all writes. | Could Have | Student |
| FR-517 | The system shall document and test the live event contract (`interaction_opened`, `interaction_closed`, `question_asked`, `question_answered`, `poll_created`, `poll_vote`, `live_question_posted`, `live_question_response`, `reaction_updated`, `idu_signal`) and broadcast each event only after its transaction commits. | Must Have | System |

---

## Module 6 — AI-Powered Quiz and Assessment (Owner: Shino)

Interface used from M8: retrieval over the course knowledge base (FR-814), so Module 6 does not parse materials itself.
Interfaces M8 needs from M6 (deferred FR-820 to FR-824): quiz results per student per question, tagged with topic or source material, and whether the student has an active graded attempt.

**UI map.**
- **Lecturer:** QuizList shows course cards with category filters (All, Open, Closed, Scheduled, Draft) and a quiz card per set; CreateQuiz is one scrollable builder with five section cards — Draft with AI, Build, Review questions, Quiz details and Finish; LiveResults shows progress and per-question correctness; ResultsClosed is the "Score & review" screen; Breakdown shows hard questions and topic performance.
- **Student:** the Quiz tab lists "Open now" first, then Earlier/closed grouped by course. TakeQuiz is one question at a time with a countdown, progress, save/resume and a submit confirmation. QuizResult shows the score, per-question review (when the lecturer allows it) and learning hints.

**Flow.**
1. Lecturer opens CreateQuiz, picks a class, optionally selects Moodle materials and writes an instruction; "Draft with AI" generates questions, or the lecturer adds them manually.
2. Lecturer reviews each question (edit, approve/revert, delete, points, hint), then sets title, time limit, open/close, attempts and review visibility, and publishes to one or more classes.
3. Publishing creates one quiz per target class, emits `quiz.published`, and queues a Moodle quiz sync.
4. Students see the quiz, start one attempt, answer with autosave, and submit manually or at the deadline.
5. MCQ answers grade immediately; short answers wait in the lecturer's queue; the lecturer accepts or changes AI-suggested scores.
6. When no short answer is unscored, grading is complete: the student sees the result, and the data flows to M7/M8.

**Logic.**
- Quiz status: `draft → published → closed`. Question status: `draft ↔ approved → deleted`; only approved questions can be published. An attempt status: `started → submitted | auto_submitted`.
- One active attempt per student per quiz at a time. The number of attempts is configurable per quiz (default 1). The deadline is server-side (`started_at + time_limit`); the client countdown is display only.
- A quiz is open only between `opens_at` and `closes_at` in Malaysia time. Times are stored in UTC and displayed in the user's local time.
- MCQ grading supports single- and multi-option answers and per-question points; unanswered questions score zero. Short-answer scoring is 0..max points and recomputes the attempt total.
- `review_visible = false` hides the question text and ideal answers from the student after submission; the score still appears once grading is complete.
- Publishing clones approved questions into each target course, so each class has its own quiz and attempt set.

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-601 | The system shall allow a lecturer to select one or more materials of a course they teach and specify the question type (multiple-choice or short-answer), level and the number of questions to generate. A natural-language instruction may replace the explicit type/count fields. | Must Have | Lecturer |
| FR-602 | The system shall generate draft questions from the selected materials using an LLM. Each multiple-choice question shall include answer options and the correct answer, and each short-answer question shall include a suggested answer. Malformed output shall be retried once, then reported as a clear error without saving partial questions. | Must Have | System |
| FR-603 | The system shall tag each generated question with its source material, topic and, where available, page or slide. | Must Have | System |
| FR-604 | The system shall allow a lecturer to review, edit, approve, revert approval or delete each generated question. The system shall allow only approved questions to be published and shall validate each question before approval. | Must Have | Lecturer |
| FR-605 | The system shall allow a lecturer to publish a quiz from approved questions with a title, time limit, open and close date/time, attempts allowed, review visibility and one or more target classes. It shall also allow saving the same set as a draft. | Must Have | Lecturer |
| FR-606 | The system shall allow a student to view the published quizzes of courses they are enrolled in, on mobile devices and computers, grouped by Open now / Upcoming / Earlier, with the attempt state and a resume action for an active attempt. | Must Have | Student |
| FR-607 | The system shall allow a student to make the configured number of attempts per quiz within the time limit, autosave answers, resume an unexpired attempt, and automatically submit the attempt when the time limit expires. | Must Have | Student |
| FR-608 | The system shall automatically grade multiple-choice questions upon submission, including multi-option answers, and shall award zero for unanswered questions. | Must Have | System |
| FR-609 | The system shall allow a lecturer to review and score short-answer responses in a queue, with the student's answer, the suggested answer, the question's maximum points and the score control. | Must Have | Lecturer |
| FR-610 | The system shall provide an AI-suggested score for each short-answer response, which the lecturer can accept or change. | Could Have | System |
| FR-611 | The system shall allow a student to view their quiz score and per-question results after grading is complete, subject to the quiz's review visibility setting. | Must Have | Student |
| FR-612 | The system shall allow a lecturer to view quiz results, including each student's score, the class average, submitted/in-progress/not-submitted counts and per-question correctness. | Must Have | Lecturer |
| FR-613 | The system shall identify and display to the lecturer the questions answered incorrectly by more than a configurable percentage of students (default 50%), with their topic and source material. | Should Have | System |
| FR-614 | The system shall share quiz results per student per question, with the question's topic and source material, with Module 7 and Module 8. | Must Have | System |
| FR-615 | The system shall warn before leaving an unsaved quiz builder, offer Save as draft, and restore a saved draft with its details and questions when reopened. | Should Have | Lecturer |
| FR-616 | The system shall provide review tabs for Draft / Approved / Deleted questions, inline editing of question text, options, correct answer, suggested answer, points and learning hint, and bulk approve/delete for the selected drafts. | Should Have | Lecturer |
| FR-617 | The system shall give the student a clear attempt experience: one question at a time or a navigable question list, previous/next, answered/unanswered markers, save on navigation, a warning at 5 minutes and 1 minute left, a submit confirmation, and an explicit auto-submit notice at zero. | Must Have | Student |
| FR-618 | The system shall show the student, after grading, the score and percentage, each question's correctness, the correct or ideal answer when review is visible, and a learning hint or recommended review topic. | Should Have | Student |
| FR-619 | The system shall show the lecturer live attempt progress (not started / in progress / submitted) and update it without a manual refresh while the quiz is open. | Should Have | Lecturer |
| FR-620 | The system shall sync a published quiz set to the matching Moodle course as a `mod_quiz` activity, show each quiz's sync status (pending, synced, failed) and let the lecturer retry a failed sync. | Should Have | Lecturer, System |
| FR-621 | The system shall reject generated questions that are duplicates, refer to "the passage" instead of the subject, or have an obviously invalid answer key, and shall mark them for lecturer review rather than publishing them. | Should Have | System |
| FR-622 | The system shall present questions and answers as plain readable text on a phone (no raw LaTeX or markdown artefacts) and shall meet the app's touch-target and screen-reader rules. | Should Have | System |
| FR-623 | The system shall store all quiz times in UTC, accept and display them in Malaysia time, and reject a close time that is not after the open time. | Must Have | System |
| FR-624 | The system shall keep draft quizzes and their questions until the lecturer deletes them, and shall delete abandoned drafts older than a configurable period (default 90 days) in a background job. | Could Have | System |

---

## Module 7 — Learning Analytics and Early Warning (Owner: Shino)

**UI map.**
- **Lecturer:** Analytics screen with a class picker, date range and tabs: Overview, Attendance, Participation, Quiz, At-risk. Overview shows headline indicators and a session trend; Attendance shows rates, absence patterns and at-risk students; Participation shows participants per session and question/IDU counts; Quiz shows score trend and topic performance; At-risk lists flagged students with the condition and a drill-down. Every chart has a table fallback and a CSV export.
- **Student:** My Analytics shows only the student's own attendance, participation, quiz trend and "needs attention" items, with a plain-language explanation of each indicator and what to do next.

**Flow.**
1. A session closes or a quiz finishes grading.
2. The evaluation service recomputes the affected student's indicators from the read interfaces.
3. Conditions are evaluated; new or changed flags create or update an at-risk alert.
4. The alert goes to M2 as an important notification for the lecturer.
5. The lecturer opens Analytics → At-risk, drills into the student, and sees the evidence.
6. When the condition clears, the alert resolves; the student sees their own status in My Analytics.

**Logic.**
- Indicators are read-only projections; M7 never edits attendance, participation or quiz rows.
- Attendance rate is `(present + late) ÷ (closed sessions − excused)`; absence frequency is absences per closed session; participation frequency is sessions participated ÷ interaction sessions held; quiz trend is the direction of the last N graded quiz percentages (default 3).
- Early warning uses configurable thresholds and a minimum-data rule (default: at least 3 closed sessions or 3 graded quizzes) so a new course does not flag everyone.
- An alert is unique per student + course + condition while active. Re-evaluating the same condition does not create duplicates; a resolved condition may re-alert after a cooldown.
- Every endpoint enforces NFR-04: a lecturer sees only classes they teach; a student sees only their own indicators.

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-701 | The system shall collect attendance data from Module 3 (FR-313), participation data from Module 5 (FR-509) and quiz results from Module 6 (FR-614) through their read interfaces, without writing to those modules. | Must Have | System |
| FR-702 | The system shall calculate the following indicators for each student per course: attendance rate, absence frequency, classroom participation frequency, number of questions submitted, number of "I Don't Understand" signals, quiz score average and quiz trend across the last N graded quizzes. | Must Have | System |
| FR-703 | The system shall display to the lecturer the indicators of each individual student in the lecturer's courses, with search, sort and a drill-down per student. | Must Have | Lecturer |
| FR-704 | The system shall display to the lecturer the class-level engagement trend across sessions, with real dates and separate attendance, participation and quiz series. | Must Have | Lecturer |
| FR-705 | The system shall display to the lecturer the class assessment performance by topic and by session, including the topics with the lowest average score. | Should Have | Lecturer |
| FR-706 | The system shall display to a student their own attendance status, engagement summary and academic performance indicators. A student shall not be able to view other students' indicators. | Must Have | Student |
| FR-707 | The system shall flag a student as at-risk when any of the following conditions is met: (a) the attendance rate falls below a configurable minimum percentage; (b) the student is absent for a configurable number of consecutive sessions; (c) quiz scores decline across a configurable number of consecutive quizzes; (d) classroom participation decreases by more than a configurable percentage compared with the previous period. | Must Have | System |
| FR-708 | The system shall evaluate the early warning conditions in FR-707 after each attendance session closes and after each quiz is graded, and shall not evaluate before the configured minimum amount of data exists. | Must Have | System |
| FR-709 | When a student is flagged, the system shall generate an alert stating the student, the course, the condition met and the severity, and shall send it to the lecturer through Module 2 (FR-210). | Must Have | Lecturer |
| FR-710 | The system shall display to the lecturer a list of at-risk students in their courses, with the condition that triggered each flag and a link to the evidence. | Should Have | Lecturer |
| FR-711 | The system shall classify each flag as **watch** or **at-risk** from configurable severity thresholds, and shall include a short reason ("Attendance 62% (below 75%)", "Absent 3 sessions in a row") in the alert and the list. | Should Have | System |
| FR-712 | The system shall keep one active alert per student, course and condition, resolve it automatically when the condition clears, avoid re-alerting within a configurable cooldown, and let the lecturer acknowledge or dismiss an alert with a reason. | Must Have | System |
| FR-713 | The system shall let the lecturer filter the at-risk list by class, condition, severity and date, and shall show each student's latest indicator values and trend beside the flag. | Should Have | Lecturer |
| FR-714 | The system shall show a student their own "needs attention" items and recommended next steps (for example, attend the next session or review a weak topic), without exposing a comparative rank or another student's data. | Should Have | Student |
| FR-715 | The system shall show when analytics were last computed ("as of" time), recompute affected indicators after a session close or quiz grading, and never display a stale number without that timestamp. | Should Have | System |
| FR-716 | The system shall enforce access control on every analytics endpoint: lecturers only for classes they teach, students only for themselves, and administrators only through the audit-safe admin view (if provided). | Must Have | System |
| FR-717 | The system shall export the lecturer's analytics (per student, per session, per topic) as CSV with the same numbers shown on screen, and shall audit the export. | Should Have | Lecturer |
| FR-718 | The system shall keep individual quiz answers and question text out of analytics responses; only scores, correctness aggregates, topics and source references may be shared with other modules. | Must Have | System |
| FR-719 | The system shall make charts accessible with labels, values and a table fallback, and shall not rely on colour alone to distinguish series. | Should Have | System |
| FR-720 | The system shall return the lecturer's analytics for a class of 100 students within the NFR-17 page-load target, using pagination or aggregation rather than loading every raw row. | Should Have | System |

---

## Module 8 — Personalized Learning: AI Learning Assistant (Owner: Yew Sing)

Module 8 turns each course's lecturer materials into a course knowledge base. Students learn from it through a cited AI assistant (similar to NotebookLM). Recommendations based on quiz results depend on Module 6 and are **deferred** (FR-820–FR-824).

### 8A. Course knowledge base

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-801 | The system shall read course materials directly from the course's Moodle page (no re-upload to SmartClass), and shall detect new, changed and removed files on each sync. | Must Have | System |
| FR-802 | The system shall extract text from supported materials (PDF, PowerPoint, Word, plain text), split it into passages, create embeddings and store them in a per-course knowledge base. Each passage keeps its source file and page or slide number. | Must Have | System |
| FR-803 | The system shall let a lecturer trigger a sync of their course's materials, and shall sync automatically on a schedule. | Must Have | Lecturer |
| FR-804 | The system shall show the lecturer each material's processing status: indexed, no extractable text (e.g. scanned), unsupported or error. | Should Have | Lecturer |

### 8B. Student learning assistant

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-805 | The system shall let a student ask questions about a course they are enrolled in, and shall answer from that course's materials with citations (file and page or slide) for each claim. | Must Have | Student |
| FR-806 | When the materials do not cover a question, the system shall answer from general knowledge and clearly label the answer as not from the course materials. | Must Have | Student |
| FR-807 | The system shall restrict each student to the knowledge bases of the courses they are enrolled in. | Must Have | System |
| FR-808 | The system shall save chat sessions per student, let the student list, rename and delete them, and use the conversation history for follow-up questions. | Must Have | Student |
| FR-809 | The system shall let a student open a cited source straight from the citation: a cited PDF opens in the app at the cited page; other cited files (PowerPoint, Word) open in another app, with the citation showing the slide or section number. (Changed 2026-11-13: no passage screen in between.) | Should Have | Student |
| FR-810 | The system shall generate a summary or study guide for a selected material or topic, with citations. (The student app offers the summary only; study guide left its menu on 2026-11-14 because it read like a normal answer. The API still accepts it.) | Should Have | Student |
| FR-811 | The system shall generate non-graded flashcards and practice questions, with answers and citations, from a selected material or topic. | Should Have | Student |
| FR-812 | The system shall suggest external learning resources (YouTube videos and search keywords) for a topic the student is studying. | Could Have | Student |

### 8C. Lecturer view and integration

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-813 | The system shall show lecturers anonymised aggregates of what students ask the assistant (most-asked topics, the materials cited most often, and most-asked topics the materials don't cover). A topic is shown only when at least 3 distinct students asked about it. Lecturers shall never be able to read individual students' chats. | Should Have | Lecturer |
| FR-814 | The system shall provide an internal retrieval interface over a course's knowledge base for Module 6 (quiz generation). | Should Have | System |
| FR-815 | The system shall let a lecturer ask questions over the materials of a course they teach, through the same assistant students use and with citations, so they can check what students are told. These chats are private to the lecturer and are not counted in question trends. | Should Have | Lecturer |
| FR-816 | The system shall generate a short "before next class" summary for the lecturer from the question trends (FR-813): what to revisit, with material sections, and what the materials don't cover. It shall use only the aggregates (topics asked by at least 3 students), never individual chats. | Should Have | Lecturer |

### 8D. Deferred — depends on Module 6 quiz results

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-820 | The system shall refuse course-content help in the assistant while the student has an active graded quiz attempt in that course. | Deferred (Must) | System |
| FR-821 | The system shall analyse a student's incorrect quiz answers to identify weak topics or concepts. | Deferred (Must) | System |
| FR-822 | The system shall recommend the relevant sections of the lecturer's materials (and external resources, FR-812) for each weak topic, personalised per student. | Deferred (Must) | Student |
| FR-823 | The system shall explain why a student's quiz answer was wrong, citing the materials. | Deferred (Should) | Student |
| FR-824 | The system shall summarise, for lecturers, the topics and questions the class most often answers incorrectly, with the related material sections to revisit. | Deferred (Should) | Lecturer |

---

## Notes and assumptions

- **Moodle simulation:** FR-101 uses the simulated SPeCTRUM's username and password. Real SPeCTRUM uses Microsoft 365 SSO, so signing in against the live system would need Microsoft OAuth and approval from UM IT. This is recorded as a scope limitation and future work.
- **Face privacy:** selfies and card photos are used only for verification and are then deleted. Only embeddings are kept (NFR-01, NFR-02). Lecturers never approve a face from memory: FR-113 always shows the card next to the selfie, and attendance flags (FR-319) are checked in the room.
- **Attendance statuses:** Present, Late, Excused and Absent (FR-304), which map one-to-one to Moodle's Attendance plugin.
- **No liveness detection** (proposal §4.9). The camera is at the entrance under the lecturer's supervision.
- **Assistant language:** English only. An LLM API is required (provider set in configuration). Answers prefer course materials (FR-805) over general knowledge (FR-806).
- **Thresholds** (face similarity, consecutive frames, card-match similarity, aggregate minimum group size, notification coalescing window, analytics minimum-data and severity thresholds, and retention periods for notifications, interaction history and quiz drafts) are configuration values, not hard-coded.
