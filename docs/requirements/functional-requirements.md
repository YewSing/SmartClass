# Functional Requirements

**Project:** Smart Classroom Management System (SmartClass) — UM FYP
**Source of scope:** `docs/private/PROJECT PROPOSAL PAPER.pdf` (local only, git-ignored) (revised scope, Nov 2026)
**Module ownership:** M1, M3, M4, M8 → Yong Yew Sing | M2, M5, M6, M7 → Chow Shino
**Last revised:** 2026-11-20 (M1, M3, M4, M8 rewritten 2026-11-08; M2, M5, M6, M7 written by Shino)

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

Role-based dashboards plus push, email and in-app notifications with three priority levels (urgent, important, general). Other modules raise notifications through one internal event interface (FR-205). Moodle announcements and deadlines are read from the simulated SPeCTRUM.

### 2A. Dashboards

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-201 | The system shall show each student a dashboard with: today's classes and their attendance status, attendance rate per course (from FR-309), upcoming deadlines and latest announcements from Moodle, urgent and important notifications, and any classroom activity (live poll, live question, open quiz) running now. | Must Have | Student |
| FR-202 | The system shall show each lecturer a dashboard with: today's classes, attendance overview of the current or latest session, participation summary (from Module 5), running and recent quizzes (from Module 6), at-risk alerts (from Module 7) and urgent and important notifications. | Must Have | Lecturer |
| FR-203 | The system shall retrieve announcements (course news forum) and deadlines (assignment and calendar events) for the user's courses from Moodle on login and on each sync, and show them with course, title, date and a link back to Moodle. Announcements and deadlines are not copied into a separate editable store. | Must Have | System |

### 2B. Notification delivery

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-205 | The system shall provide one internal notification event interface that any module can call with: event type, recipients, priority, title, message and a link to the relevant screen. Modules shall not send push or email themselves. | Must Have | System |
| FR-206 | The system shall support at least these events: `attendance.recorded`, `attendance.flagged`, `face_enrolment.result`, `face_enrolment.pending_review`, `quiz.published`, `quiz.deadline_reminder`, `quiz.graded`, `game.started`, `poll.started`, `confusion.spike`, `at_risk.alert`, and Moodle deadline reminders. | Must Have | System |
| FR-207 | The system shall give every notification one priority: **urgent**, **important** or **general**, set by the event type. | Must Have | System |
| FR-208 | The system shall show urgent and important notifications at the top of the dashboard until read, and general notifications in the notification feed only. | Must Have | System |
| FR-209 | The system shall keep an in-app notification feed per user, newest first, with read and unread state, "mark as read" and "mark all as read". | Must Have | All |
| FR-210 | The system shall send urgent and important notifications as push notifications on Android through the Expo Push Notification Service. On iOS they are delivered in-app and by email (proposal §4.9). | Must Have | System |
| FR-211 | The system shall send urgent and important notifications by email (SMTP) to the user's registered email address. General notifications are not emailed. | Should Have | System |
| FR-212 | The system shall register a device's push token when the user signs in on the phone app, and remove it on logout. | Must Have | System |
| FR-213 | The system shall push live notifications to an open app screen without a manual refresh. | Must Have | System |
| FR-214 | The system shall let a user choose to turn off push and email for general notifications. Urgent and important notifications cannot be turned off. | Could Have | All |
| FR-215 | The system shall send a reminder before a Moodle deadline or an open quiz closes, a configurable time before it (default 24 hours and 1 hour). | Should Have | Student |
| FR-216 | The system shall not send the same event to the same user twice (de-duplication by event type, subject and time window). | Should Have | System |
| FR-217 | The system shall let a lecturer send a short announcement to the students of a class they teach. It is delivered as an *important* notification, and the lecturer can choose to also post it to the course's announcement forum in Moodle so it appears there too. Failed posts are retried and the lecturer sees the post status. | Should Have | Lecturer |
| FR-218 | The system shall keep notifications for a configurable retention period (default 90 days), then delete them. | Could Have | System |

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

Non-graded real-time interaction during a class: live questions, polls, live quick answers, reactions and an "I Don't Understand" button. An interaction session is tied to one class session (Module 3) and is open only while that class is running. Graded quizzes are Module 6, not here (FR-513).

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-501 | The system shall let a lecturer open and close the interaction session of a class they are running. It shall close automatically when the class session ends (FR-301, FR-316). | Must Have | Lecturer, System |
| FR-502 | The system shall let only students enrolled in the course (and the lecturers who teach it) join its interaction session. | Must Have | System |
| FR-503 | The system shall let a student submit a live question to the lecturer during an open session, with an option to submit it **anonymously**. | Must Have | Student |
| FR-504 | The system shall never show a lecturer or other students the identity behind an anonymous question. The identity is stored only so the question can be counted in the class totals (FR-713). | Must Have | System |
| FR-505 | The system shall let students upvote questions, once each, and shall list questions by votes and time. | Should Have | Student |
| FR-506 | The system shall let a lecturer mark a question as answered, pin it, or hide it. Each hide is audited. | Must Have | Lecturer |
| FR-507 | The system shall let a lecturer create a live poll (a question with 2–6 options, single or multiple choice), start it, and close it. | Must Have | Lecturer |
| FR-508 | The system shall let each student vote once per poll while it is open, and change their vote until it closes. | Must Have | Student |
| FR-509 | The system shall show the lecturer live poll results as they come in, and let the lecturer choose whether students see the results. | Must Have | Lecturer |
| FR-510 | The system shall let a lecturer ask a live quick question and collect short text answers (up to a configurable length). Answers are shown to the lecturer as a list, anonymous to the class. | Should Have | Lecturer, Student |
| FR-511 | The system shall let students send quick reactions (for example thumbs-up, "clear", "too fast", "too slow") during an open session, limited to one reaction per student every few seconds. The lecturer sees running counts. | Should Have | Student |
| FR-512 | The system shall provide an "I Don't Understand" button. A press may carry an optional topic tag, is limited by a per-student cooldown (configurable, default 2 minutes), and is shown to the lecturer as a live count and timeline. | Must Have | Student |
| FR-513 | The system shall not grade or score any interaction in this module. Formal assessment is Module 6. | Must Have | System |
| FR-514 | The system shall raise a `confusion.spike` notification to the lecturer when "I Don't Understand" presses within a configurable window (default 2 minutes) reach a configurable share of the class (default 25%). | Should Have | System |
| FR-515 | The system shall show lecturers confusion only as an aggregate (count and timeline). Individual presses are not attributed to a named student in the lecturer's live view. | Must Have | System |
| FR-516 | The system shall update the lecturer's and students' screens in real time without a manual refresh. | Must Have | System |
| FR-517 | The system shall store every interaction event (type, student, session, timestamp) so Module 7 can count participation, questions and confusion signals per student (FR-513 and FR-702 interface). | Must Have | System |
| FR-518 | The system shall show the lecturer a session summary after class: questions asked and answered, poll results, reactions, and the confusion timeline. | Should Have | Lecturer |
| FR-519 | The system shall let a lecturer export a session summary as CSV. Anonymous questions are exported without identity. | Could Have | Lecturer |
| FR-520 | The system shall let a student see their own past questions and the lecturer's "answered" status. | Could Have | Student |

---

## Module 6 — AI-Powered Quiz and Assessment (Owner: Shino)

Lecturers generate draft questions from the course materials with a natural-language prompt, review and publish them, and students play or take the quiz in the SmartClass app. Quizzes are either **game quizzes** (live, points, leaderboards, not counted toward marks) or **graded quizzes** (timed, private results). Questions are graded automatically. Source materials come from Moodle through Module 8's knowledge base (FR-814). Quizzes are not synced to Moodle (see notes).

### 6A. Drafting and review

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-601 | The system shall let a lecturer describe the quiz in a natural-language prompt (for example, "game quiz, 10 MCQ and 2 short-answer on week 5 slides, 20 seconds per question"), optionally with selected materials (FR-804). The system shall read the quiz details in the prompt (type, number and types of questions, timer, open and close time, shuffle) and fill them into the quiz settings (FR-606); the lecturer reviews them before publishing. | Must Have | Lecturer |
| FR-602 | The system shall draft multiple-choice questions and short-answer questions (with a suggested answer) from the prompt and the course knowledge base (FR-814). By default it may draft extended questions that relate to the material, because slides can be brief; if the lecturer says to use only the material, it shall use only the material. Each question is labelled "from material" or "extended". | Must Have | System |
| FR-603 | The system shall tag every question with its topic and, where it draws on the materials, the source file and page or slide, and generate a short explanation of the correct answer citing that source. | Must Have | System |
| FR-604 | The system shall let a lecturer edit, delete, reorder, regenerate and add questions, and refine the draft with a further prompt (for example, "make question 3 harder"). Questions stay as saved drafts until the lecturer approves them, and only approved questions can be published. | Must Have | Lecturer |

### 6B. Publishing and taking quizzes

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-605 | The system shall support two quiz types, chosen by the lecturer for each quiz. A **game quiz** is played live in class, awards points, shows leaderboards, and does not count toward marks. A **graded quiz** gives each student a private result and is never ranked publicly. The timer is a separate setting (FR-606). | Must Have | Lecturer |
| FR-606 | The system shall let a lecturer set a quiz's title, type, timer mode (a time limit per question, or one time limit for the whole quiz), open and close time, shuffle, and when results are released (FR-618), then publish it to the course's enrolled students, who receive a `quiz.published` notification (FR-206). A live game always uses per-question timers; a graded quiz can use either mode. The lecturer can unpublish or close a quiz, and its questions cannot be edited once it has attempts. | Must Have | Lecturer |
| FR-607 | The system shall show students a card for each quiz of their enrolled courses and let them start or join it from the card. A graded quiz allows one attempt. Answers are saved as the student works, so an attempt resumes after a lost connection without extending the time. | Must Have | Student |
| FR-608 | The system shall enforce the quiz's timer on the server, whether per question or for the whole quiz. When a timer ends, the answer is locked and the attempt moves on or is submitted automatically. | Must Have | System |
| FR-609 | The system shall expose to Module 8 whether a student currently has an active graded quiz attempt in a course (FR-820). Game quizzes don't count. | Must Have | System |

### 6C. Live game and leaderboards

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-610 | The system shall let a lecturer run a game quiz live in class: the lecturer releases one question at a time, students see it with a countdown on their phones, and the lecturer sees live answer counts and can pause, skip or end. Screens update without a manual refresh, and a late joiner enters at the current question. | Must Have | Lecturer, Student |
| FR-611 | The system shall reveal the correct answer after each live question, with how the class answered and the explanation (FR-603), then show the leaderboard (FR-613). | Must Have | System |
| FR-612 | The system shall score each correct answer in a game quiz with base points plus a speed bonus (the faster the answer, the more points). The lecturer can turn the speed bonus off. | Must Have | System |
| FR-613 | The system shall show a game quiz leaderboard after each question and at the end, with the top five and the student's own rank. Students can use a nickname or opt out of being shown. Graded quizzes have no leaderboard. | Must Have | Student |
| FR-614 | The system shall keep a course leaderboard that adds up each student's points across the course's game quizzes. | Should Have | Student |
| FR-615 | The system shall give game quizzes visual feedback: a countdown, correct and wrong animations, a streak indicator for consecutive correct answers, and a podium at the end. | Should Have | Student |

### 6D. Grading and results

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-616 | The system shall grade multiple-choice answers automatically, and grade short answers automatically with the AI by comparing them with the suggested answer, giving a score and a short reason. The scores are final without lecturer approval. | Must Have | System |
| FR-617 | The system shall flag short-answer scores the AI is not confident about, and let the lecturer change any short-answer score with feedback. Each change is logged with actor, old score, new score and timestamp. | Should Have | Lecturer |
| FR-618 | The system shall show a student their result once the lecturer releases it: their marks, and for each question their answer, the correct answer and the explanation. The lecturer chooses whether to release marks, answers, both or neither, and unreleased parts stay hidden. | Must Have | Student |
| FR-619 | The system shall show the lecturer quiz results: submissions, score distribution, average, and per-question correct rate, including the questions most often answered incorrectly. | Must Have | Lecturer |
| FR-620 | The system shall give Module 8 each student's answers per question, with the question's topic and source tag (FR-603) and the quiz type (graded or game), to support FR-821 to FR-824. Module 8 may weigh game answers lower than graded ones. | Must Have | System |
| FR-621 | The system shall give Module 7 each student's graded-quiz scores with the date, and each student's game-quiz answers by topic and participation (FR-702). | Must Have | System |

---

## Module 7 — Learning Analytics and Early Warning (Owner: Shino)

Combines attendance (Module 3), participation (Module 5) and quiz results (Module 6) into indicators, dashboards and rule-based at-risk alerts. Alerts go out through Module 2.

### 7A. Indicators and dashboards

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-701 | The system shall collect data from Module 3 (through FR-313), Module 5 (FR-517) and Module 6 (FR-621). Module 7 only reads this data and never changes it. | Must Have | System |
| FR-702 | The system shall calculate, per student per course: attendance rate and number of absences, consecutive absences, participation frequency (polls answered, questions, reactions), number of questions submitted, number of confusion signals, graded-quiz scores with their trend, game-quiz participation, and topic mastery per student (from graded and game quiz answers, shown separately). Excused sessions are not counted as absences (FR-308). | Must Have | System |
| FR-703 | The system shall give each lecturer a class-level dashboard for a course: attendance trend by session, participation trend, quiz performance by quiz and by topic (FR-603), and the number of at-risk students. | Must Have | Lecturer |
| FR-704 | The system shall give each lecturer a student-level view: that student's indicators, trends over time and any alerts. | Must Have | Lecturer |
| FR-705 | The system shall let a student view their own attendance status, engagement summary, quiz performance and topic mastery. A student can never see another student's data. | Must Have | Student |
| FR-706 | The system shall show a student's indicator as "not enough data" when there are too few sessions or quizzes to judge (a configurable minimum), and shall not raise an alert from it. | Should Have | System |
| FR-707 | The system shall let a lecturer export a course analytics report as CSV. | Could Have | Lecturer |

### 7B. Early warning

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-708 | The system shall flag a student as at-risk with a rule-based check against these default rules: (a) attendance rate below a minimum (default 80%), (b) absent for a number of consecutive sessions (default 3), (c) graded-quiz scores declining over a number of consecutive quizzes (default 3), (d) participation dropping by more than a set share against the student's earlier average (default 50%). | Must Have | System |
| FR-709 | The system shall let a lecturer change the thresholds for the courses they teach, and turn individual rules on or off. Values are configuration, not hard-coded. | Should Have | Lecturer |
| FR-710 | The system shall evaluate the rules after each attendance session is finalised and after each quiz is graded, and at least once a day. | Must Have | System |
| FR-711 | The system shall raise an `at_risk.alert` through Module 2 to the lecturer when a student first meets a rule, showing which rule fired and the numbers behind it. The same rule for the same student shall not alert again until it clears and recurs. | Must Have | System |
| FR-712 | The system shall show the lecturer a list of at-risk students per course with their rules and evidence, and let the lecturer mark an alert as acknowledged, followed up, or dismissed (with an optional note). | Must Have | Lecturer |
| FR-713 | The system shall keep anonymous questions (FR-504) out of any individual-level figure shown to a lecturer. They are counted only in class totals. | Must Have | System |
| FR-714 | The system shall let a lecturer open the analytics of a class only if they teach it, and shall reject other lecturers (NFR-04). Administrators may view all classes. The API check is `ensure_teaches_occurrence` for lecturers. | Must Have | System |
| FR-715 | The system shall record an audit entry when an alert is acknowledged, dismissed or its thresholds changed. | Should Have | System |
| FR-716 | The system shall show lecturers the most-missed quiz topics and the class's lowest-engagement sessions, to help plan what to revisit. (Per-topic recommendations are Module 8, FR-824.) | Could Have | Lecturer |

> **Open issue for Shino (found 2026-11-09, not fixed because M7 is your module):** `GET /lecturer/analytics` in `backend/app/routers/analytics.py` checks that the caller is a lecturer or admin, but not that a lecturer teaches the class in `occurrence_id`. Any lecturer can read any class's analytics, including the names, matric numbers and attendance rates of its at-risk students. NFR-04 says lecturers may only reach the courses they teach. Requirement FR-714 now covers this.
>
> **Fix:** when the caller is a lecturer, call `await ensure_teaches_occurrence(db, actor, occurrence_id)` (from `app.core.deps`) after the "Occurrence not found" check. It returns 403 if they aren't assigned to the class. `backend/tests/test_lecturer_access.py` shows how to test it. Delete this note once it's fixed.

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
- **Thresholds** (face similarity, consecutive frames, card-match similarity, aggregate minimum group size, retention periods, attendance minimum, consecutive absences, decline window, cooldowns, quiz reminder times, scoring points and speed bonus) are configuration values, not hard-coded.
- **Interfaces to other modules:** M2 receives events from FR-113, FR-114, FR-318, FR-406 (Yew Sing's modules). M5 and M6 feed M7. M6 reads M8's retrieval (FR-814) and exposes FR-609 and FR-620 to M8.
- **Anonymity (M5):** anonymous questions are hidden from lecturers, but their author is stored for class totals only.
- **iOS push:** per proposal §4.9, iOS gets in-app and email notifications only.
- **Quizzes are not synced to Moodle.** Proposal §4.6 says the quiz set syncs back to Moodle. This is dropped by decision (2026-11-20), because students play and are graded in SmartClass. Record it as a scope change.
- **Game vs graded quizzes (M6):** only graded quizzes count toward M7 score trends and trigger M8's FR-820 restriction. Game quiz answers feed M7 topic mastery and participation, and M8 as a lower-weight signal, but never the at-risk score-decline rule.
- **AI grading** of short answers is automatic and final (FR-616); the lecturer can override flagged scores (FR-617).
